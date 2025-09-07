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

# --- Applikationens Flöde ---

st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

# Använd Streamlits "session state" för att minnas tillstånd
if 'drive_service' not in st.session_state:
    st.session_state.drive_service = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'story_items' not in st.session_state:
    st.session_state.story_items = None
if 'path_history' not in st.session_state:
    st.session_state.path_history = []
if 'current_folder_id' not in st.session_state:
    st.session_state.current_folder_id = 'root'
if 'current_folder_name' not in st.session_state:
    st.session_state.current_folder_name = 'Min enhet / Delade enheter'


# Hantera callback från Google
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
        st.query_params.clear()

# Visa antingen inloggningssidan eller huvudsidan
if st.session_state.drive_service is None:
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    
    auth_url = get_auth_url()
    if auth_url:
        st.link_button("Logga in med Google", auth_url)
    else:
        st.error("Fel: Appen saknar konfiguration. Administratören måste ställa in secrets (CLIENT_ID, CLIENT_SECRET, APP_URL) på Streamlit Cloud.")

else:
    # Användaren är inloggad! Visa filbläddraren och fillistan.
    if st.session_state.user_email:
        st.success(f"✅ Ansluten till Google Drive som: **{st.session_state.user_email}**")
    else:
        st.warning("✅ Ansluten till Google Drive.")
    
    st.markdown("---")
    st.markdown("### Välj din Källmapp")

    # --- FILBLÄDDRAREN ---
    current_path_display = " / ".join([name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name])
    st.write(f"**Nuvarande plats:** `{current_path_display}`")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("⬅️ Gå upp") and st.session_state.path_history:
            st.session_state.current_folder_id, st.session_state.current_folder_name = st.session_state.path_history.pop()
            st.session_state.story_items = None # Rensa fillistan när vi byter mapp
            st.rerun()

        if st.button("✅ Välj denna mapp"):
            with st.spinner("Hämtar fillista..."):
                result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
                if 'error' in result: st.error(result['error'])
                elif 'units' in result:
                    st.session_state.story_items = result['units']

    with col2:
        folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in folders:
            st.error(folders['error'])
        elif folders:
            for folder in sorted(folders, key=lambda x: x['name'].lower()):
                if st.button(f"📁 {folder['name']}", use_container_width=True):
                    st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    st.session_state.story_items = None # Rensa fillistan
                    st.rerun()
        else:
            st.write("Inga undermappar hittades.")

    # Visa fillistan om den har laddats
    if st.session_state.story_items is not None:
        st.markdown("---")
        st.markdown("### Filer i den valda mappen:")
        if not st.session_state.story_items:
            st.info("Inga relevanta filer (bilder, txt, pdf) hittades i denna mapp.")
        else:
            for item in st.session_state.story_items:
                st.write(f"- `{item['filename']}` (typ: {item['type']})")
