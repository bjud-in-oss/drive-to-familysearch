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
        'organize_mode': False, 'selected_indices': set(), 'clipboard': [],
        'quick_sort_mode': False, 'unsorted_items': []
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
    st.markdown("### Välkommen!")
    auth_url = get_auth_url()
    if auth_url: st.link_button("Logga in med Google", auth_url)
    else: st.error("Fel: Appen saknar konfiguration i 'Secrets'.")
else:
    col_main, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
        st.divider()
        
        if not st.session_state.quick_sort_mode:
            st.markdown("### Välj Källmapp")
            # ... (Filbläddrare, oförändrad) ...
        
        if st.session_state.story_items is not None and st.session_state.organize_mode:
            st.divider()
            st.markdown("### Verktyg")
            st.info("Verktygen ändrar bara 'spellistan'. Dina originalfiler raderas aldrig.", icon="ℹ️")

            # KNAPP FÖR SNABBSORTERING
            if st.button("Starta Snabbsortering 🔢", disabled=st.session_state.quick_sort_mode, use_container_width=True):
                st.session_state.quick_sort_mode = True
                with st.spinner("Förbereder snabbsortering..."):
                    all_files_result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
                    if 'units' in all_files_result:
                        all_items_map = {item['filename']: item for item in all_files_result['units']}
                        sorted_filenames = {item['filename'] for item in st.session_state.story_items}
                        unsorted = [item for filename, item in all_items_map.items() if filename not in sorted_filenames]
                        st.session_state.unsorted_items = sorted(unsorted, key=lambda x: x['filename'].lower())
                st.rerun()

            st.session_state.selected_indices = {i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{item['id']}")}
            st.info(f"{len(st.session_state.selected_indices)} objekt valda.")
            
            tool_cols = st.columns(2)
            if tool_cols[0].button("Klipp ut 📤", disabled=not st.session_state.selected_indices, use_container_width=True):
                st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(list(st.session_state.selected_indices))]
                for i in sorted(list(st.session_state.selected_indices), reverse=True): del st.session_state.story_items[i]
                st.session_state.selected_indices = set()
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()
            if tool_cols[1].button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):
                st.session_state.story_items = st.session_state.clipboard + st.session_state.story_items
                st.session_state.clipboard = []
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()
            if st.session_state.clipboard: st.success(f"{len(st.session_state.clipboard)} i urklipp.")
            if st.button("Ta bort 🗑️", type="primary", disabled=not st.session_state.selected_indices, use_container_width=True):
                for i in sorted(list(st.session_state.selected_indices), reverse=True): del st.session_state.story_items[i]
                st.session_state.selected_indices = set()
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()

    with col_main:
        # --- SNABBSORTERINGS-LÄGE ---
        if st.session_state.story_items is not None and st.session_state.quick_sort_mode:
            st.warning("SNABBSORTERINGS-LÄGE AKTIVT")
            if st.button("✅ Avsluta Snabbsortering och spara"):
                # Lägg tillbaka eventuellt osorterade objekt i slutet av listan
                if st.session_state.unsorted_items:
                    st.session_state.story_items.extend(st.session_state.unsorted_items)
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.session_state.quick_sort_mode = False
                st.rerun()
            
            qs_col1, qs_col2 = st.columns(2)
            with qs_col1:
                st.markdown("#### Kvar att sortera")
                # Använd en container med höjd för att göra den scrollbar
                with st.container(height=600):
                    for i, item in enumerate(st.session_state.unsorted_items):
                        if st.button(f"➕ {item['filename']}", key=f"add_{item['id']}", use_container_width=True):
                            st.session_state.story_items.append(item)
                            st.session_state.unsorted_items.pop(i)
                            st.rerun()
            with qs_col2:
                st.markdown("#### Din Berättelse (i ordning)")
                with st.container(height=600):
                    if not st.session_state.story_items: st.info("Börja genom att klicka på filer i vänstra listan.")
                    for item in st.session_state.story_items: st.write(f"_{item['filename']}_")

        # --- NORMAL VISUELL LISTA / ORGANISERINGS-LÄGE ---
        elif st.session_state.story_items is not None:
            st.toggle("Ändra ordning & innehåll", key="organize_mode")
            st.markdown("---")
            st.markdown("### Berättelsens flöde")
            if not st.session_state.story_items:
                st.info("Inga filer att visa.")
            else:
                for i, item in enumerate(st.session_state.story_items):
                    with st.container():
                        cols = [1, 10] if not st.session_state.organize_mode else [0.5, 1, 10]
                        col_list = st.columns(cols)
                        if st.session_state.organize_mode: col_list[0].checkbox("", key=f"select_{item['id']}")
                        with col_list[-2]:
                            if item.get('type') == 'image' and item.get('thumbnail'): st.image(item['thumbnail'], width=100)
                            elif item.get('type') == 'pdf': st.markdown("<p style='font-size: 48px; text-align: center;'>📑</p>", unsafe_allow_html=True)
                            elif item.get('type') == 'text': st.markdown("<p style='font-size: 48px; text-align: center;'>📄</p>", unsafe_allow_html=True)
                        with col_list[-1]: st.write(item.get('filename', 'Okänt filnamn'))
                    st.divider()
        else:
            st.info("⬅️ Använd filbläddraren i sidopanelen för att börja.")
