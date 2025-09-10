import streamlit as st
import os
import requests
from urllib.parse import urlencode
import re
from PIL import Image

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

# --- Inloggningslogik och hjälpfunktioner ---
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

def reload_story_items(show_spinner=True):
    message = "Uppdaterar fillista..."
    if st.session_state.get('story_items') is not None:
        pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
    if show_spinner:
        with st.spinner(message):
            result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
            if 'error' in result: st.error(result['error'])
            elif 'units' in result: st.session_state.story_items = result['units']
    else:
        result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in result: st.error(result['error'])
        elif 'units' in result: st.session_state.story_items = result['units']
    st.session_state.selected_indices = set()
    st.session_state.show_text_inserter = False
    st.rerun()

# --- Applikationens Flöde ---
st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

def initialize_state():
    defaults = {
        'drive_service': None, 'user_email': None, 'story_items': None, 'path_history': [], 
        'current_folder_id': None, 'current_folder_name': None, 'organize_mode': False, 
        'selected_indices': set(), 'clipboard': [], 'quick_sort_mode': False, 
        'unsorted_items': [], 'show_text_inserter': False, 'insertion_index': 0
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value
initialize_state()

auth_code = st.query_params.get('code')
if auth_code and st.session_state.drive_service is None:
    with st.spinner("Verifierar inloggning..."):
        st.session_state.drive_service = exchange_code_for_service(auth_code)
        if st.session_state.drive_service:
            try:
                user_info = st.session_state.drive_service.about().get(fields='user').execute()
                st.session_state.user_email = user_info['user']['emailAddress']
            except Exception: st.session_state.user_email = "Okänd"
        st.query_params.clear()
        st.rerun()

# --- Huvudlayout ---
if st.session_state.drive_service is None:
    st.markdown("### Välkommen!")
    auth_url = get_auth_url()
    if auth_url: st.link_button("Logga in med Google", auth_url)
    else: st.error("Fel: Appen saknar konfiguration i 'Secrets'.")
else:
    # KORREKT STRUKTUR: Definiera kolumner EFTER att vi vet att användaren är inloggad
    col_main, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
        st.divider()
        
        if not st.session_state.quick_sort_mode:
            st.markdown("### Välj Källmapp")
            if st.session_state.current_folder_id is None:
                drives = pdf_motor.get_available_drives(st.session_state.drive_service)
                if 'error' in drives: st.error(drives['error'])
                else:
                    for drive in sorted(drives, key=lambda x: x.get('name', '').lower()):
                        icon = "📁" if drive.get('id') == 'root' else "🏢"
                        if st.button(f"{icon} {drive.get('name', 'Okänd enhet')}", use_container_width=True, key=drive.get('id')):
                            initialize_state()
                            st.session_state.current_folder_id, st.session_state.current_folder_name = drive.get('id'), drive.get('name')
                            st.rerun()
            else:
                path_parts = [name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name]
                st.write(f"**Plats:** `{' / '.join(path_parts)}`")
                c1, c2 = st.columns(2)
                if c1.button("⬅️ Byt enhet", use_container_width=True):
                    initialize_state(); st.rerun()
                if c2.button("⬆️ Gå upp", use_container_width=True, disabled=not st.session_state.path_history):
                    prev_id, prev_name = st.session_state.path_history.pop()
                    st.session_state.current_folder_id, st.session_state.current_folder_name = prev_id, prev_name
                    st.session_state.story_items = None; st.rerun()
                if st.button("✅ Läs in denna mapp", type="primary", use_container_width=True):
                    reload_story_items()
                folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
                if 'error' in folders: st.error(folders['error'])
                elif folders:
                    st.markdown("*Undermappar:*")
                    for folder in sorted(folders, key=lambda x: x.get('name', '').lower()):
                        if st.button(f"📁 {folder.get('name', 'Okänd mapp')}", key=folder.get('id'), use_container_width=True):
                            st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                            st.session_state.current_folder_id, st.session_state.current_folder_name = folder.get('id'), folder.get('name')
                            st.session_state.story_items = None; st.rerun()
        
        if st.session_state.story_items is not None and st.session_state.organize_mode:
            st.divider(); st.markdown("### Verktyg")
            st.info("Originalfiler ändras aldrig.", icon="ℹ️")
            # ... Andra verktyg ...

        if st.session_state.story_items is not None:
            st.divider()
            st.markdown("### Inställningar & Publicering")
            # ... PDF-inställningar ...

    with col_main:
        if st.session_state.story_items is None:
            st.info("⬅️ Använd filbläddraren för att börja.")
        else:
            st.toggle("Ändra ordning & innehåll", key="organize_mode")
            st.divider()
            st.markdown("### Berättelsens flöde")
            if not st.session_state.story_items:
                st.info("Inga filer att visa.")
            else:
                for item in st.session_state.story_items:
                    st.write(item.get('filename'))
