import telethon_secret_chat
import os
import inspect

print(f"Library file: {telethon_secret_chat.__file__}")
lib_dir = os.path.dirname(telethon_secret_chat.__file__)

# List files
print("Files:", os.listdir(lib_dir))

# Try to find where send_secret_video is
from telethon_secret_chat import SecretChatManager
print(f"Manager file: {inspect.getfile(SecretChatManager)}")

# Read SecretChatManager source to find send_secret_video
with open(inspect.getfile(SecretChatManager), 'r') as f:
    content = f.read()
    # Find the method
    start = content.find("def send_secret_video")
    if start != -1:
        end = content.find("def ", start + 1)
        print(content[start:end])
    else:
        print("Method not found in Manager")

