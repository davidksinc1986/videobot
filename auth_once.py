import os
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_PATH = os.environ.get("GOOGLE_CLIENT_SECRET_PATH", "client_secret.json")
TOKEN_OUTPUT_PATH = os.environ.get("YOUTUBE_TOKEN_OUTPUT_PATH", "token.pickle")

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_SECRET_PATH,
    SCOPES
)

credentials = flow.run_local_server(port=8080)

token_dir = os.path.dirname(TOKEN_OUTPUT_PATH)
if token_dir:
    os.makedirs(token_dir, exist_ok=True)

with open(TOKEN_OUTPUT_PATH, "wb") as f:
    pickle.dump(credentials, f)

print("TOKEN CREADO")


