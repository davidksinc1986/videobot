import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http

scopes = ["https://www.googleapis.com/auth/youtube.upload"]

flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", scopes)

credentials = flow.run_local_server(port=0)

youtube = googleapiclient.discovery.build(
    "youtube", "v3", credentials=credentials)

request = youtube.videos().insert(

    part="snippet,status",

    body={
        "snippet": {
            "title": "Video automatizado",
            "description": "Video creado por IA",
            "tags": ["bot", "ia"],
            "categoryId": "22"
        },

        "status": {
            "privacyStatus": "public"
        }
    },

    media_body=googleapiclient.http.MediaFileUpload("video.mp4")

)

response = request.execute()

print("VIDEO SUBIDO")
