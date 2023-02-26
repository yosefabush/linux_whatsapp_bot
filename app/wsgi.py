import os
import json
import pandas
import socket
import requests
import unicodedata
from datetime import datetime
# from Database import Database
from flask import Flask, request
from requests.structures import CaseInsensitiveDict
from Models.ConversationSession import ConversationSession

requests.packages.urllib3.disable_warnings()
app = Flask(__name__)

PORT = os.getenv("PORT", default=5000)
TOKEN = os.getenv('TOKEN', default=None)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", default=None)
PHONE_NUMBER_ID_PROVIDER = os.getenv("NUMBER_ID_PROVIDER", default="104091002619024")
FACEBOOK_API_URL = 'https://graph.facebook.com/v16.0'
TIMEOUT_FOR_OPEN_SESSION_MINUTES = 1
if None in [TOKEN, VERIFY_TOKEN]:
    raise Exception(f"Error on env var '{TOKEN, VERIFY_TOKEN}' ")
# db = Database()
to = None
language_support = {"he": "he_IL", "en": "en_US"}

headers = CaseInsensitiveDict()
headers["Accept"] = "application/json"
headers["Authorization"] = f"Bearer {TOKEN}"
session_open = False

conversation = {
    "Greeting": "ברוך הבא לבוט של מוזס!"
}

# Define a list of predefined conversation steps
conversation_steps = ConversationSession.conversation_steps_in_class

conversation_history = list()
for i in range(5):
    old_session = ConversationSession(f"1234{i}")
    conversation_history.append(old_session)
    if i == 3:
        old_session.convers_step_resp[str(i)] = "test"

print([item.get_user_id() for item in conversation_history])


@app.route("/")
def whatsapp_echo():
    return f"WhatsApp bot server is ready! container:'{socket.gethostname()}' "


@app.route("/bot", methods=["POST", "GET"])
def receive_message():
    """Receive a message using the WhatsApp Business API."""
    global to
    print(f"receive_message /bot trigger '{request}'")
    try:
        if request.method == "GET":
            print("Inside GET verify token!")
            mode = request.args.get("hub.mode")
            challenge = request.args.get("hub.challenge")
            received_token = request.args.get("hub.verify_token")
            if mode and received_token:
                if mode == "subscribe" and received_token == VERIFY_TOKEN:
                    print("Token Verified successfully")
                    return challenge, 200
                else:
                    return "", 403
        else:
            try:
                # print(f"webhook")
                user_msg = webhook_parsing_message_and_destination()
                if user_msg is None:
                    raise Exception("Read data from Whatsapp message failed")
            except Exception as ERR:
                # receive data from postman
                print(f"webhook parse error '{ERR}'")
                raise Exception(f"webhook parse error '{ERR}'")

            # Do something with the received message
            print(f"Received message: {user_msg}")

            _language = "en" if 'HEBREW' not in unicodedata.name(user_msg.strip()[0]) else "he"
            # print(_language)
            if _language == "en":
                if 'hello' in user_msg:
                    send_response_using_whatsapp_api('Hi There!')
                elif 'where' in user_msg:
                    send_response_using_whatsapp_api("Go to: http://google.com")
                else:
                    send_response_using_whatsapp_api("Unknown msg")
            else:
                chat_whatsapp(user_msg)
            return 'OK', 200
    except Exception as ex:
        print(f"receive_message Exception {ex}")
        return f"Something went wrong : '{ex}'"


def chat_input():
    # Print a greeting message and the predefined conversation steps
    print(conversation["Greeting"])
    for key, value in conversation_steps.items():
        print(f"{value} - {key}")

    # Get the user's name
    user_id = input(f"{conversation_steps['1']}\n")
    session = None
    conversation_history_ids = [item.get_user_id() for item in conversation_history]
    if user_id in conversation_history_ids:
        session = conversation_history[conversation_history_ids.index(user_id)]
        diff_time = datetime.now() - session.start_data
        seconds_in_day = 24 * 60 * 60
        minutes, second = divmod(diff_time.days * seconds_in_day + diff_time.seconds, 60)
        if minutes > TIMEOUT_FOR_OPEN_SESSION_MINUTES:
            print("To much time pass, CREATE NEW SESSION")
            session = None
        else:
            print("SESSION is still open!")

    if not session:
        print("Hi " + user_id + " You are new!:")
        # Initialize a ConversationSession object to track the call flow for this user
        session = ConversationSession(user_id)
        session.increment_call_flow()
    else:
        print("Hi " + user_id + " You are known!:")

    # Loop through the conversation flow
    while True:
        # call step
        current_conversation_step = str(session.get_call_flow_location())
        if current_conversation_step == "3":
            choices = ["ב", "א"]
            # Get user input
            user_input = input(f"{conversation_steps[current_conversation_step]}\n{choices}\n").lower()
        else:
            # Get user input
            user_input = input(f"{conversation_steps[current_conversation_step]}\n").lower()
        if not session.validate_user_input(user_input):
            continue
        # Add the user input to the ConversationSession object
        session.increment_call_flow()
        after_action_conversation_step = str(session.get_call_flow_location())
        # Check if conversation reach to last step
        if after_action_conversation_step == str(len(conversation_steps)):  # 7
            session.issue_to_be_created = user_input
            print(f"recevied message: '{session.issue_to_be_created}'")
            print(f"{conversation_steps[after_action_conversation_step]}\n")
            break


def chat_whatsapp(user_msg):
    # Get the user's name
    log = ""
    if user_msg in ["אדמין"]:
        for s in conversation_history:
            if not s.session_active:
                log += f"ID: {s.user_id} Sent message: {s.issue_to_be_created}\n"
        send_response_using_whatsapp_api(log)
        return
    session = check_if_session_exist(to)
    if session is None:
        print("Hi " + to + " You are new!:")
        steps_message = ""
        for key, value in conversation_steps.items():
            steps_message += f"{value} - {key}\n"

        send_response_using_whatsapp_api(conversation["Greeting"])
        print(f"{steps_message}")
        session = ConversationSession(to)
        send_response_using_whatsapp_api(conversation_steps[str(session.get_call_flow_location())])
        session.increment_call_flow()
        conversation_history.append(session)
    else:
        current_conversation_step = str(session.get_call_flow_location())
        print(f"Current step is: {current_conversation_step}")
        is_answer_valid, message_in_error = session.validate_and_set_answer(current_conversation_step, user_msg)
        if is_answer_valid:
            if current_conversation_step == "2":
                send_response_using_whatsapp_api("שלום " + session.convers_step_resp["1"] + "!")
            if current_conversation_step == "3":
                choices = ["ב", "א"]
                send_response_using_whatsapp_api(f"{conversation_steps[current_conversation_step]}\n{choices}\n")
            else:
                send_response_using_whatsapp_api(conversation_steps[current_conversation_step])
            session.increment_call_flow()
            next_step_conversation_after_increment = str(session.get_call_flow_location())
            # Check if conversation reach to last step
            if next_step_conversation_after_increment == str(len(conversation_steps) + 1):  # 7
                # session.validate_and_set_answer(current_conversation_step, user_msg)
                # session.issue_to_be_created = user_msg
                # send_response_using_whatsapp_api(f"{conversation_steps[current_conversation_step]}\n")
                print("Conversation ends!")
                session.set_status(False)
                print(session.get_all_responses())
                return
        else:
            print("Try again")
            send_response_using_whatsapp_api(message_in_error)
            fixed_step = str(int(current_conversation_step) - 1)
            if fixed_step == "3":
                choices = ["ב", "א"]
                send_response_using_whatsapp_api(f"{conversation_steps[fixed_step]}\n{choices}\n")
            else:
                send_response_using_whatsapp_api(conversation_steps[fixed_step])
            return


def check_if_session_exist(user_id):
    print(f"Check check_if_session_exist '{user_id}'")
    session_index = None
    # search for active session with user_id
    for index, session in enumerate(conversation_history):
        if session.user_id == user_id and session.session_active:
            session_index = index
            break

    if session_index is not None:
        print("SESSION exist!")
        return conversation_history[session_index]
    return None


def send_response_using_whatsapp_api(message, phone_number=PHONE_NUMBER_ID_PROVIDER, debug=True):
    """Send a message using the WhatsApp Business API."""
    try:
        print(f"Sending message: '{message}' ")
        url = f"{FACEBOOK_API_URL}/{PHONE_NUMBER_ID_PROVIDER}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": f"{to}",
            "type": "text",
            "text": {
                "preview_url": False,
                "body": f"{message}"
            }
        }

        pay = {
            "messaging_product": "whatsapp",
            "to": f"{to}",
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {
                    "code": "en_US"
                }
            }
        }
        if debug:
            print(f"Payload '{payload}' ")
            print(f"Headers '{headers}' ")
            print(f"URL '{url}' ")
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if not response.ok:
            return f"Failed send message, response: '{response}'"
        print(f"Message sent successfully to :'{to}'!")
        # return f"Message sent successfully to :'{to}'!"
    except Exception as EX:
        print(f"Error send whatsapp : '{EX}'")
        raise EX


def webhook_parsing_message_and_destination():
    global to
    # print(request)
    res = request.get_json()
    print(res)
    try:
        if res['entry'][0]['changes'][0]['value']['messages'][0]['id']:
            to = res['entry'][0]['changes'][0]['value']['messages'][0]['from']
            # print("phone_number", res['entry'][0]['changes'][0]['value']['metadata']['phone_number_id'])
            return res['entry'][0]['changes'][0]['value']['messages'][0]['text']["body"]
    except Exception as ex:
        print(f"webhook_parsing_message err {ex}]")
        pass
    return None


def verify_token(req):
    # /bot?hub.mode=subscribe&hub.challenge=331028360&hub.verify_token=WHATSAPP_VERIFY_TOKEN
    if req.args.get("hub.mode") == "subscribe" and req.args.get("hub.challenge"):
        if not req.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token missmatch", 403
        return req.args['hub.challenge'], 200
    return "Hello world", 200


@app.route("/botTest", methods=["POST", "GET"])
def receive_message_chat_whatsapp():
    """Receive a message using the WhatsApp Business API."""
    global to
    print(f"receive_message /botTest trigger '{request}'")
    try:
        if request.method == "GET":
            print("Inside receive message with verify token")
            mode = request.args.get("hub.mode")
            challenge = request.args.get("hub.challenge")
            received_token = request.args.get("hub.verify_token")
            if mode and received_token:
                if mode == "subscribe" and received_token == VERIFY_TOKEN:
                    return challenge, 200
                else:
                    return "", 403
        else:
            try:
                # receive data from twilio webhooks
                print(f"Inside Post method")
                user_msg = request.values.get('Body', '').lower()
                print(f"user_msg {user_msg}")
                to = request.values.get('From', '').lower()
                print(f"to1 {to}")
                to = to.split("+")[1]
                print(f"to2 {to}")
                if '' in [user_msg, to]:
                    print(request.get_json())
                    raise Exception("error")
                print("receive data from whatsapp webhooks", user_msg, to)
            except Exception:
                # receive data from postman
                print(f"postman")
                data = request.get_json()
                to = data['to']
                user_msg = data['template']['name']
                print("receive data from postman", user_msg, to)

            # Do something with the received message
            print("Received message:", user_msg)

            _language = "en" if 'HEBREW' not in unicodedata.name(user_msg.strip()[0]) else "he"
            print(_language)
            if _language == "en":
                if 'hello' in user_msg:
                    send_response_using_whatsapp_api('Hi There!')
                elif 'where' in user_msg:
                    send_response_using_whatsapp_api("Go to: http://google.com")
                else:
                    send_response_using_whatsapp_api("Unknown msg")
            else:
                chat_whatsapp(user_msg)
                # if 'היי' in user_msg:
                #     print(send_response_using_whatsapp_api("שלום רב!"))
                # else:
                #     print(send_response_using_whatsapp_api("אני לומד להציק ללידור הגיי"))
            return 'OK', 200
    except Exception as ex:
        print(f"receive_message botTest Exception {ex}")
        return f"Something went wrong : '{ex}'"


if __name__ == "__main__":
    app.run(debug=True, port=PORT)
