import streamlit as st
import os
import requests
from urllib.parse import urlencode
import re

# Importera Googles bibliotek
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Importera vår motor
import pdf_motor

# --- Konfiguration ---
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = st.secrets.get("APP_URL") 
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_URI = 'https://oauth2.googleapis.com/token'
AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'

# --- Applikationens Flöde (Början) ---
st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

# Session state – robust initialisering
def initialize_state():
    defaults = {
        'drive_service': None, 'user_email': None, 'story_items': None,
        'path_history': [], 'current_folder_id': None, 'current_folder_name': None,
        'organize_mode': False, 'selected_indices': set(), 'clipboard': [],
        'quick_sort_mode': False, 'unsorted_items': []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_state()

# --- Inloggningslogik ---
def get_auth_url():
    """Bygger inloggnings-URL:en."""
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

# --- Applikationens Flöde, Del 2: Gränssnittet ---

# Hantera callback från Google (när användaren skickas tillbaka efter inloggning)
auth_code = st.query_params.get('code')
if auth_code and st.session_state.drive_service is None:
    with st.spinner("Verifierar inloggning..."):
        st.session_state.drive_service = exchange_code_for_service(auth_code)
        if st.session_state.drive_service:
            try:
                user_info = st.session_state.drive_service.about().get(fields='user').execute()
                st.session_state.user_email = user_info['user']['emailAddress']
            except Exception:
                st.session_state.user_email = "Okänd"
        # Rensa bort koden från URL:en för att undvika att den körs igen
        st.query_params.clear()
        st.rerun()

# Huvudlogik: Visa antingen inloggningssidan eller huvudsidan
if st.session_state.drive_service is None:
    # Användaren är INTE inloggad
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    
    auth_url = get_auth_url()
    if auth_url:
        st.link_button("Logga in med Google", auth_url)
    else:
        st.error("Fel: Appen saknar konfiguration. GOOGLE_CLIENT_ID och GOOGLE_CLIENT_SECRET måste ställas in i 'Secrets'.")

else:
    # Användaren ÄR inloggad!
    if st.session_state.user_email:
        st.success(f"✅ Du är nu ansluten till Google Drive som: **{st.session_state.user_email}**")
    else:
        st.warning("✅ Ansluten till Google Drive (kunde inte verifiera användarnamn).")
    
    st.markdown("---")
    st.info("I nästa steg bygger vi filbläddraren här.")

# HÄR SLUTAR DEL 3
