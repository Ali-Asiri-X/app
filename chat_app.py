import os
import argparse
import threading
from posixpath import split
from time import sleep
from os import error, path as os_path
from datetime import datetime  # Import datetime module

# Set file path for the XML configuration
file_path = os_path.dirname(os_path.realpath(__file__))

# Argument parsing for user input
parser = argparse.ArgumentParser(description='DDS Chat Application')
parser.add_argument('user', help='User Name', type=str)
parser.add_argument('group', help='Group Name', type=str)
parser.add_argument('-f', '--firstname', help='First Name', type=str, default='')
parser.add_argument('-l', '--lastname', help='Last Name', type=str, default='')
args = parser.parse_args()

# Set environment variables for the user and group
os.environ['user'] = str(args.user)
os.environ['group'] = str(args.group)

# Import RTI Connext DDS Connector
import rticonnextdds_connector as rti

# Lock for thread safety
lock = threading.RLock()
finish_thread = False

# Open RTI Connector and start the chat application




# Function to handle user subscription tasks
def user_subscriber_task(user_input):
    global finish_thread
    while not finish_thread:
        try:
            user_input.wait(500)
        except rti.TimeoutError:
            continue

        with lock:
            user_input.read()
            for sample in user_input.samples:
                if (sample.info['sample_state'] == "NOT_READ") and \
                   (sample.valid_data == False) and \
                   (sample.info['instance_state'] == "NOT_ALIVE_NO_WRITERS"):
                    data = sample.get_dictionary()
                    print("#Dropped user: " + data['username'])

# Function to handle message subscription tasks
def message_subscriber_task(message_input):
    global finish_thread
    while not finish_thread:
        try:
            message_input.wait(500)
        except rti.TimeoutError:
            continue

        with lock:
            message_input.take()
            for sample in message_input.samples.valid_data_iter:
                data = sample.get_dictionary()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{timestamp}] #New chat message from user: {data['fromUser']}. Message: '{data['message']}'")

# Function to handle user commands
def command_task(user, message_output, user_input):
  
    global finish_thread
    while not finish_thread:
        command = input("Please enter command:\n")

        if command == "exit":
            finish_thread = True
        elif command == "list":
            with lock:
                user_input.read()
                for sample in user_input.samples.valid_data_iter:
                    if sample.info['instance_state'] == 'ALIVE':
                        data = sample.get_dictionary()
                        print("#username/group: " + data['username'] + "/" + data['group'])
        elif command.startswith("send "):
            destination = command.split(maxsplit=2)
            if len(destination) == 3:
                with lock:
                    message_output.instance.set_string("fromUser", user)
                    message_output.instance.set_string("toUser", destination[1])
                    message_output.instance.set_string("toGroup", destination[1])
                    message_output.instance.set_string("message", destination[2])
                    message_output.write()
            else:
                print("Wrong usage. Use \"send user|group message\" \n")
        else:
            print("Unknown command\n")
with rti.open_connector(
    config_name="Chat_ParticipantLibrary::ChatParticipant",
    url=file_path + "/chat_app.xml"
    ) as connector:

    
        user_ouput = connector.get_output("ChatUserPublisher::ChatUser_Writer")
        message_output = connector.get_output("ChatMessagePublisher::ChatMessage_Writer")

        user_input = connector.get_input("ChatUserSubscriber::ChatUser_Reader")
        message_input = connector.get_input("ChatMessageSubscriber::ChatMessage_Reader")

        # Register user
        user_ouput.instance.set_string("username", args.user)
        user_ouput.instance.set_string("group", args.group)
        if args.firstname != "":
            user_ouput.instance.set_string("firstname", args.firstname)
        if args.lastname != "":
            user_ouput.instance.set_string("lastname", args.lastname)
        user_ouput.write()

        t1 = threading.Thread(target=command_task, args=(args.user, message_output, user_input,))
        t1.start()

        t2 = threading.Thread(target=message_subscriber_task, args=(message_input,))
        t2.start()

        t3 = threading.Thread(target=user_subscriber_task, args=(user_input,))
        t3.start()

        t1.join()
        t2.join()
        t3.join()

        # Unregister user
        user_ouput.instance.set_string("username", args.user)
        user_ouput.write(action="unregister")