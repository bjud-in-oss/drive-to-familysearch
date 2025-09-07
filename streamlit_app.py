import streamlit as st
import os
import requests
from urllib.parse import urlencode

# Importera Googles bibliotek
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Importera vår motor
import pdf_motor

# --- Konfiguration ---
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = st.secrets.get("APP_URL") 
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TOKEN_URI = 'https://oauth2.googleapis.com/token'
AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'

# --- Inloggningslogik ---

def get_auth_url():
    """Bygger inloggnings-URL:en."""
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        return None
    params = {
        'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI,
        'response_type': 'code', 'scope': ' '.join(SCOPES),
        'access_type': 'offline', 'prompt': 'consent'
    }
    return AUTH_URI + '?' + urlencode(params)

def exchange_code_for_service(auth_code):
    """Byter auktoriseringskod mot en giltig anslutning."""
    try:
        token_data = {
            'code': auth_code, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI, 'grant_type': 'authorization_code'
        }
        response = requests.post(TOKEN_URI, data=token_data)
        response.raise_for_status()
        
        credentials_data = response.json()
        credentials_data['client_id'] = CLIENT_ID
        credentials_data['client_secret'] = CLIENT_SECRET

        credentials = Credentials.from_authorized_user_info(credentials_data, SCOPES)
        drive_service = build('drive', 'v3', credentials=credentials)
        return drive_service
    except Exception as e:
        st.error(f"Ett fel inträffade vid inloggning: {e}")
        return None

# --- Applikationens Flöde (fortfarande bara test-texten) ---

st.title("Steg 1: Logik tillagd")
st.success("Om du ser detta, fungerar appen fortfarande efter att all bakgrundslogik har lagts till!")
