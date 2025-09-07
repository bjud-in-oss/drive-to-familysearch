import streamlit as st
import os
import requests
from urllib.parse import urlencode

# Importera Googles bibliotek
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Importera vår motor
import pdf_motor

# --- Konfiguration ---
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = st.secrets.get("APP_URL") 
# VIKTIG ÄNDRING: Vi behöver nu fulla rättigheter för att kunna spara projektfilen
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_URI = 'https://oauth2.googleapis.com/token'
AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'

# --- Inloggningslogik (Oförändrad) ---
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

# Session state – robust initialisering
def initialize_state():
    defaults = {
        'drive_service': None, 'user_email': None, 'story_items': None,
        'path_history': [], 'current_folder_id': None, 'current_folder_name': None,
        'organize_mode': False, 'selected_indices': set(), 'clipboard': []
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

initialize_state()

# Hantera callback från Google
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
    # Inloggningssida
    st.markdown("### Välkommen!")
    auth_url = get_auth_url()
    if auth_url: st.link_button("Logga in med Google", auth_url)
    else: st.error("Fel: Appen saknar konfiguration i 'Secrets'.")
else:
    # Huvudapplikation
    col_main, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
        st.divider()
        
        # --- FILBLÄDDRARE I SIDOPANELEN ---
        # ... (Denna del är oförändrad)
        st.markdown("### Välj Källmapp")
        if st.session_state.current_folder_id is None:
            drives = pdf_motor.get_available_drives(st.session_state.drive_service)
            if 'error' in drives: st.error(drives['error'])
            else:
                for drive in sorted(drives, key=lambda x: x['name'].lower()):
                    icon = "📁" if drive['id'] == 'root' else "🏢"
                    if st.button(f"{icon} {drive['name']}", use_container_width=True, key=drive['id']):
                        st.session_state.current_folder_id, st.session_state.current_folder_name = drive['id'], drive['name']
                        st.session_state.path_history = []
                        st.rerun()
        else:
            path_parts = [name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name]
            st.write(f"**Plats:** `{' / '.join(path_parts)}`")
            if st.button("⬅️ Byt enhet"):
                st.session_state.current_folder_id, st.session_state.path_history, st.session_state.story_items = None, [], None
                st.rerun()
            if st.button("⬆️ Gå upp") and st.session_state.path_history:
                prev_id, prev_name = st.session_state.path_history.pop()
                st.session_state.current_folder_id, st.session_state.current_folder_name = prev_id, prev_name
                st.session_state.story_items = None
                st.rerun()
            if st.button("✅ Läs in denna mapp", type="primary"):
                with st.spinner("Hämtar fillista..."):
                    result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
                    if 'error' in result: st.error(result['error'])
                    elif 'units' in result: st.session_state.story_items = result['units']
            folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
            if 'error' in folders: st.error(folders['error'])
            elif folders:
                for folder in sorted(folders, key=lambda x: x['name'].lower()):
                    if st.button(f"📁 {folder['name']}", key=folder['id'], use_container_width=True):
                        st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                        st.session_state.current_folder_id, st.session_state.current_folder_name = folder['id'], folder['name']
                        st.session_state.story_items = None
                        st.rerun()
        
        # --- VERKTYG FÖR ORGANISERING I SIDOPANELEN ---
        if st.session_state.story_items is not None and st.session_state.organize_mode:
            st.divider()
            st.markdown("### Verktyg")
            st.session_state.selected_indices = {i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{i}")}
            st.write(f"{len(st.session_state.selected_indices)} objekt valda.")
            
            # KNAPPAR FÖR KLIPP UT & KLISTRA IN
            if st.button("Klipp ut valda 📤", disabled=not st.session_state.selected_indices):
                st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(list(st.session_state.selected_indices))]
                for i in sorted(list(st.session_state.selected_indices), reverse=True):
                    del st.session_state.story_items[i]
                for i in range(len(st.session_state.story_items) + 10): st.session_state[f"select_{i}"]=False
                st.session_state.selected_indices = set()
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()

            if st.button("Klistra in överst 📥", disabled=not st.session_state.clipboard):
                st.session_state.story_items = st.session_state.clipboard + st.session_state.story_items
                st.session_state.clipboard = []
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()
                
            if st.session_state.clipboard:
                st.info(f"{len(st.session_state.clipboard)} objekt finns i urklipp.")

            if st.button("Ta bort valda från berättelsen 🗑️", disabled=not st.session_state.selected_indices):
                for i in sorted(list(st.session_state.selected_indices), reverse=True):
                    del st.session_state.story_items[i]
                for i in range(len(st.session_state.story_items) + 10): st.session_state[f"select_{i}"]=False
                st.session_state.selected_indices = set()
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()

    with col_main:
        # --- VISUELL LISTA I HUVUDFÖNSTRET ---
        if st.session_state.story_items is None:
            st.info("Välj en mapp i panelen till höger och klicka på 'Läs in denna mapp' för att börja.")
        else:
            st.toggle("Ändra ordning & innehåll", key="organize_mode")
            st.markdown("---")
            st.markdown("### Berättelsens flöde")
            if not st.session_state.story_items:
                st.info("Inga filer att visa.")
            else:
                for i, item in enumerate(st.session_state.story_items):
                    is_in_clipboard = item in st.session_state.clipboard
                    item_opacity = 0.5 if is_in_clipboard else 1.0 # Visuell feedback
                    
                    with st.container():
                        cols = [1, 5] if not st.session_state.organize_mode else [0.5, 1, 5]
                        col_list = st.columns(cols)
                        if st.session_state.organize_mode:
                            col_list[0].checkbox("", key=f"select_{i}")
                        with col_list[-2]:
                            if item['type'] == 'image' and item.get('thumbnail'): st.image(item['thumbnail'], width=100, output_format="PNG")
                            elif item['type'] == 'pdf': st.markdown(f"<div style='font-size: 48px; text-align: center; opacity: {item_opacity};'>📑</div>", unsafe_allow_html=True)
                            elif item['type'] == 'text': st.markdown(f"<div style='font-size: 48px; text-align: center; opacity: {item_opacity};'>📄</div>", unsafe_allow_html=True)
                        with col_list[-1]:
                            st.write(f"<div style='opacity: {item_opacity};'>{item['filename']}</div>", unsafe_allow_html=True)
                    st.divider()
