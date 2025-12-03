from pathlib import Path
import os
from dotenv import load_dotenv
from twilio.rest import Client
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path)

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

account_sid = TWILIO_SID
auth_token  = TWILIO_AUTH_TOKEN
from_number = TWILIO_NUMBER

client = Client(account_sid, auth_token)

message = client.messages.create(
    to="+19364623793",
    from_=from_number,
    body="Hello from Python!")

print(message.sid)