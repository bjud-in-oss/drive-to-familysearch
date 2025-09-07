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
    params = {'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI, 'response_type': 'code', 'scope': ' '.join(SCOPES), 'access_type': 'offline', 'prompt': 'consent'}
    return AUTH_URI + '?' + urlencode(params)

def exchange_code_for_service(auth_code):
    try:
        token_data = {'code': auth_code, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI, 'grant_type': 'authorization_code'}
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

# Session state för att minnas tillstånd
if 'drive_service' not in st.session_state: st.session_state.drive_service = None
if 'user_email' not in st.session_state: st.session_state.user_email = None
if 'story_items' not in st.session_state: st.session_state.story_items = None
if 'path_history' not in st.session_state: st.session_state.path_history = []
if 'current_folder_id' not in st.session_state: st.session_state.current_folder_id = None
if 'current_folder_name' not in st.session_state: st.session_state.current_folder_name = None

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
    auth_url = get_auth_url()
    if auth_url: st.link_button("Logga in med Google", auth_url)
    else: st.error("Fel: Appen saknar konfiguration i 'Secrets'.")

else:
    # Användaren är inloggad!
    st.success(f"✅ Ansluten som: **{st.session_state.user_email}**")
    st.markdown("---")

    # Om vi inte har valt en startpunkt, visa "lobbyn"
    if st.session_state.current_folder_id is None:
        st.markdown("### Välj en startpunkt")
        drives = pdf_motor.get_available_drives(st.session_state.drive_service)
        if 'error' in drives:
            st.error(drives['error'])
        else:
            for drive in sorted(drives, key=lambda x: x['name'].lower()):
                icon = "📁" if drive['id'] == 'root' else "🏢"
                if st.button(f"{icon} {drive['name']}", use_container_width=True):
                    st.session_state.current_folder_id = drive['id']
                    st.session_state.current_folder_name = drive['name']
                    st.session_state.path_history = []
                    st.rerun()
    else:
        # Visa filbläddraren
        st.markdown("### Välj din Källmapp")
        
        path_parts = [name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name]
        current_path_display = " / ".join(path_parts)
        st.write(f"**Nuvarande plats:** `{current_path_display}`")

        col1, col2, col3 = st.columns([1.5, 1.5, 4])
        if col1.button("⬅️ Byt enhet (tillbaka till lobbyn)"):
            st.session_state.current_folder_id = None
            st.session_state.path_history = []
            st.session_state.story_items = None
            st.rerun()
        if col2.button("⬆️ Gå upp en nivå") and st.session_state.path_history:
            prev_id, prev_name = st.session_state.path_history.pop()
            st.session_state.current_folder_id = prev_id
            st.session_state.current_folder_name = prev_name
            st.session_state.story_items = None
            st.rerun()

        if st.button("✅ Välj denna mapp för att skapa berättelse", type="primary"):
            with st.spinner("Hämtar fillista..."):
                result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
                if 'error' in result: st.error(result['error'])
                elif 'units' in result:
                    st.session_state.story_items = result['units']
        
        folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in folders: st.error(folders['error'])
        elif folders:
            for folder in sorted(folders, key=lambda x: x['name'].lower()):
                if st.button(f"📁 {folder['name']}", key=folder['id'], use_container_width=True):
                    st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    st.session_state.story_items = None
                    st.rerun()
        else:
            st.write("Inga undermappar hittades.")

    # ----------------------------------------------------------------------
    # NYTT BLOCK: Visar den visuella listan med miniatyrbilder
    # ----------------------------------------------------------------------
    if st.session_state.story_items is not None:
        st.markdown("---")
        st.markdown("### Berättelsens flöde")
        
        if not st.session_state.story_items:
            st.info("Inga relevanta filer (bilder, txt, pdf) hittades i denna mapp.")
        else:
            # Gå igenom varje objekt i listan och rita upp det
            for item in st.session_state.story_items:
                col1, col2 = st.columns([1, 5])
                with col1:
                    # Visa thumbnail för bilder, annars en ikon
                    if item['type'] == 'image' and item.get('thumbnail'):
                        st.image(item['thumbnail'], width=100)
                    elif item['type'] == 'pdf':
                        st.markdown("<div style='font-size: 60px; text-align: center;'>📑</div>", unsafe_allow_html=True)
                    elif item['type'] == 'text':
                        st.markdown("<div style='font-size: 60px; text-align: center;'>📄</div>", unsafe_allow_html=True)
                
                with col2:
                    st.write(item['filename'])
                
                st.divider()
    # ----------------------------------------------------------------------
    # SLUT PÅ NYTT BLOCK
    # ----------------------------------------------------------------------
