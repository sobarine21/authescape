import streamlit as st
import google.generativeai as genai
import google.auth
import base64
import json
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configure Streamlit Page ---
st.set_page_config(page_title="ScapeAPI - Gmail AI Responder", page_icon="📧", layout="wide")
st.title("📧 ScapeAPI - AI Email Responder")
st.write("Automatically generate and save suggested email responses as drafts.")

# --- Load Google API Credentials from Streamlit Secrets ---
GMAIL_CLIENT_ID = st.secrets["GMAIL_CLIENT_ID"]
GMAIL_CLIENT_SECRET = st.secrets["GMAIL_CLIENT_SECRET"]
GMAIL_REFRESH_TOKEN = st.secrets["GMAIL_REFRESH_TOKEN"]

# --- Configure Google AI API ---
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- Function to Authenticate Gmail API ---
def authenticate_gmail():
    creds_data = {
        "client_id": GMAIL_CLIENT_ID,
        "client_secret": GMAIL_CLIENT_SECRET,
        "refresh_token": GMAIL_REFRESH_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    creds = Credentials.from_authorized_user_info(creds_data)
    service = build("gmail", "v1", credentials=creds)
    return service

# --- Function to Fetch the Latest Email ---
def fetch_latest_email(service):
    try:
        results = service.users().messages().list(userId="me", maxResults=1).execute()
        messages = results.get("messages", [])

        if not messages:
            return None, None

        msg = service.users().messages().get(userId="me", id=messages[0]["id"]).execute()
        payload = msg["payload"]
        headers = payload["headers"]

        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

        body = ""
        if "data" in payload.get("body", {}):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        elif "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    break

        return sender, body
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return None, None

# --- Function to Generate AI Response ---
@st.cache_data(ttl=3600)
def generate_response(email_content):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Generate a polite and professional email response:\n" + email_content)
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"

# --- Function to Save Response as Draft in Gmail ---
def save_draft(service, recipient, subject, response_text):
    try:
        email_message = f"To: {recipient}\r\nSubject: Re: {subject}\r\n\r\n{response_text}"
        encoded_message = base64.urlsafe_b64encode(email_message.encode("utf-8")).decode("utf-8")

        draft = {
            "message": {
                "raw": encoded_message
            }
        }

        service.users().drafts().create(userId="me", body=draft).execute()
        st.success("✅ Suggested response saved as a draft!")
    except HttpError as error:
        st.error(f"Error saving draft: {error}")

# --- Gmail Authentication ---
service = authenticate_gmail()

# --- Fetch Email & Generate Response ---
if st.button("Fetch & Respond"):
    sender, email_content = fetch_latest_email(service)
    
    if not email_content:
        st.warning("No new emails found!")
    else:
        st.subheader("📩 Latest Email Received")
        st.write(f"**From:** {sender}")
        st.write(f"**Content:** {email_content}")

        st.subheader("💡 Suggested Response")
        response_text = generate_response(email_content)
        st.write(response_text)

        if st.button("Save as Draft"):
            save_draft(service, sender, "Automated Response", response_text)
