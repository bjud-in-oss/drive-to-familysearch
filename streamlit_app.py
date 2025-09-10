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

def reload_story_items():
    """Hjälpfunktion för att ladda om fillistan efter en ändring."""
    # Spara den nuvarande ordningen innan omladdning
    pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
    with st.spinner("Uppdaterar fillista..."):
        result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in result: st.error(result['error'])
        elif 'units' in result: st.session_state.story_items = result['units']
    st.rerun()

# --- Applikationens Flöde ---
st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

# Session state – robust initialisering
def initialize_state():
    defaults = {
        'drive_service': None, 'user_email': None, 'story_items': None, 'path_history': [], 
        'current_folder_id': None, 'current_folder_name': None, 'organize_mode': False, 
        'selected_indices': set(), 'clipboard': [], 'quick_sort_mode': False, 
        'unsorted_items': [],
        # Nya variabler för att hantera text-infogning
        'show_text_inserter': False, 
        'insertion_index': 0,
        'insertion_mode': 'efter' # Kan vara 'före' eller 'efter'
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
    # Användaren är INTE inloggad
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    
    auth_url = get_auth_url()
    if auth_url:
        st.link_button("Logga in med Google", auth_url)
    else:
        st.error("Fel: Appen saknar konfiguration. GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET och APP_URL måste ställas in i 'Secrets'.")

else:
    # Användaren ÄR inloggad!
    col_main, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
        st.divider()
        
        # FILBLÄDDRARE (om inte i snabbsortering eller text-infogning)
        if not st.session_state.quick_sort_mode and not st.session_state.show_text_inserter:
            st.markdown("### Välj Källmapp")
            if st.session_state.current_folder_id is None:
                drives = pdf_motor.get_available_drives(st.session_state.drive_service)
                if 'error' in drives: st.error(drives['error'])
                else:
                    for drive in sorted(drives, key=lambda x: x.get('name', '').lower()):
                        icon = "📁" if drive.get('id') == 'root' else "🏢"
                        if st.button(f"{icon} {drive.get('name', 'Okänd enhet')}", use_container_width=True, key=drive.get('id')):
                            st.session_state.current_folder_id, st.session_state.current_folder_name = drive.get('id'), drive.get('name')
                            st.session_state.path_history = []
                            st.rerun()
            else:
                path_parts = [name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name]
                st.write(f"**Plats:** `{' / '.join(path_parts)}`")
                c1, c2 = st.columns(2)
                if c1.button("⬅️ Byt enhet", use_container_width=True):
                    initialize_state()
                    st.rerun()
                if c2.button("⬆️ Gå upp", use_container_width=True, disabled=not st.session_state.path_history):
                    prev_id, prev_name = st.session_state.path_history.pop()
                    st.session_state.current_folder_id, st.session_state.current_folder_name = prev_id, prev_name
                    st.session_state.story_items = None
                    st.rerun()
                if st.button("✅ Läs in denna mapp", type="primary", use_container_width=True):
                    reload_story_items(show_spinner=True)

                folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
                if 'error' in folders: st.error(folders['error'])
                elif folders:
                    st.markdown("*Undermappar:*")
                    for folder in sorted(folders, key=lambda x: x.get('name', '').lower()):
                        if st.button(f"📁 {folder.get('name', 'Okänd mapp')}", key=folder.get('id'), use_container_width=True):
                            st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                            st.session_state.current_folder_id, st.session_state.current_folder_name = folder.get('id'), folder.get('name')
                            st.session_state.story_items = None
                            st.rerun()
        
        # VERKTYG FÖR ORGANISERING
        if st.session_state.story_items is not None and st.session_state.organize_mode:
            st.divider()
            st.markdown("### Verktyg")
            st.info("Dina originalfiler raderas eller ändras aldrig.", icon="ℹ️")

            st.session_state.selected_indices = {i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{item['id']}")}
            
            # --- Infoga text (kontextkänslig) ---
            if len(st.session_state.selected_indices) == 1:
                st.markdown("**Infoga text:**")
                idx = list(st.session_state.selected_indices)[0]
                t_cols = st.columns(2)
                if t_cols[0].button("Före markerad", use_container_width=True):
                    st.session_state.show_text_inserter = True
                    st.session_state.insertion_index = idx
                    st.session_state.insertion_mode = 'före'
                    st.rerun()
                if t_cols[1].button("Efter markerad", use_container_width=True):
                    st.session_state.show_text_inserter = True
                    st.session_state.insertion_index = idx
                    st.session_state.insertion_mode = 'efter'
                    st.rerun()

            # --- Text-infogningsformulär ---
            if st.session_state.show_text_inserter:
                with st.form("new_text_form"):
                    st.markdown("#### Skapa ny text")
                    st.caption(f"Infogas {'efter' if st.session_state.insertion_mode == 'efter' else 'före'} filen: **{st.session_state.story_items[st.session_state.insertion_index]['filename']}**")
                    new_text_name = st.text_input("Filnamn (utan .txt)")
                    new_text_style = st.selectbox("Textstil", ['p', 'h1', 'h2'])
                    new_text_content = st.text_area("Innehåll")
                    
                    submitted = st.form_submit_button("✅ Spara och infoga text")
                    if submitted:
                        if new_text_name and new_text_content:
                            # Skapa ett unikt, sorteringsvänligt filnamn
                            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '', new_text_name.replace(' ', '_'))
                            # Namnet baseras på position för att hamna rätt vid alfabetisk sortering
                            final_filename = f"{st.session_state.insertion_index:03d}a_{clean_name}.{new_text_style}.txt"
                            
                            with st.spinner("Sparar textfil..."):
                               result = pdf_motor.upload_new_text_file(st.session_state.drive_service, st.session_state.current_folder_id, final_filename, new_text_content)
                               if 'error' in result:
                                   st.error(result['error'])
                               else:
                                   st.session_state.show_text_inserter = False
                                   st.success("Textfil sparad! Laddar om listan...")
                                   reload_story_items(show_spinner=False) # Spinner körs redan
                        else:
                            st.warning("Filnamn och innehåll får inte vara tomt.")
                if st.button("Avbryt"):
                    st.session_state.show_text_inserter = False
                    st.rerun()
            
            st.divider()

            if st.button("Starta Snabbsortering 🔢", disabled=st.session_state.quick_sort_mode, use_container_width=True):
                st.session_state.quick_sort_mode = True
                with st.spinner("Förbereder..."):
                    all_files_result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
                    if 'units' in all_files_result:
                        all_items_map = {item['filename']: item for item in all_files_result['units']}
                        sorted_filenames = {item['filename'] for item in st.session_state.story_items}
                        unsorted = [item for filename, item in all_items_map.items() if filename not in sorted_filenames]
                        st.session_state.unsorted_items = sorted(unsorted, key=lambda x: x['filename'].lower())
                st.rerun()

            st.info(f"{len(st.session_state.selected_indices)} objekt valda.")
            
            tool_cols = st.columns(2)
            if tool_cols[0].button("Klipp ut 📤", disabled=not st.session_state.selected_indices, use_container_width=True):
                st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(list(st.session_state.selected_indices))]
                for i in sorted(list(st.session_state.selected_indices), reverse=True): del st.session_state.story_items[i]
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()
            if tool_cols[1].button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):
                # Klistra in efter markerat objekt om ett är valt, annars överst
                insert_pos = list(st.session_state.selected_indices)[0] + 1 if len(st.session_state.selected_indices) == 1 else 0
                st.session_state.story_items[insert_pos:insert_pos] = st.session_state.clipboard
                st.session_state.clipboard = []
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()
            
            if st.session_state.clipboard: st.success(f"{len(st.session_state.clipboard)} i urklipp.")
            
            if st.button("Ta bort 🗑️", type="primary", disabled=not st.session_state.selected_indices, use_container_width=True):
                for i in sorted(list(st.session_state.selected_indices), reverse=True): del st.session_state.story_items[i]
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.rerun()

with col_main:
        # --- SNABBSORTERINGS-LÄGE ---
        if st.session_state.story_items is not None and st.session_state.quick_sort_mode:
            st.warning("SNABBSORTERINGS-LÄGE AKTIVT")
            if st.button("✅ Avsluta Snabbsortering och spara"):
                if st.session_state.unsorted_items:
                    st.session_state.story_items.extend(st.session_state.unsorted_items)
                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                st.session_state.quick_sort_mode = False
                st.rerun()
            
            qs_col1, qs_col2 = st.columns(2)
            with qs_col1:
                st.markdown("#### Kvar att sortera")
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
                    for item in st.session_state.story_items:
                        with st.container():
                            i_col1, i_col2 = st.columns([1,5])
                            if item.get('type') == 'image' and item.get('thumbnail'): i_col1.image(item['thumbnail'], width=75)
                            elif item.get('type') == 'pdf': i_col1.markdown("<p style='font-size: 32px; text-align: center;'>📑</p>", unsafe_allow_html=True)
                            elif item.get('type') == 'text' and 'content' in item: i_col1.info(item.get('content'))
                            elif item.get('type') == 'text': i_col1.markdown("<p style='font-size: 32px; text-align: center;'>📄</p>", unsafe_allow_html=True)
                            with i_col2:
                                st.write(item.get('filename', 'Okänt filnamn'))
        
        # --- NORMAL VISUELL LISTA / ORGANISERINGS-LÄGE ---
        elif st.session_state.story_items is not None:
            st.toggle("Ändra ordning & innehåll (Organisera-läge)", key="organize_mode")
            st.markdown("---")
            st.markdown("### Berättelsens flöde")
            if not st.session_state.story_items:
                st.info("Inga filer att visa.")
            else:
                for i, item in enumerate(st.session_state.story_items):
                    with st.container():
                        cols = [1, 10] if not st.session_state.organize_mode else [0.5, 1, 5, 2]
                        col_list = st.columns(cols)
                        if st.session_state.organize_mode: col_list[0].checkbox("", key=f"select_{item['id']}")
                        with col_list[-3]: # Thumbnail column
                            if item.get('type') == 'image' and item.get('thumbnail'): st.image(item['thumbnail'], width=100)
                            elif item.get('type') == 'pdf':
                                # Använd cache för att inte rendera om i onödan
                                @st.cache_data
                                def get_pdf_thumb(file_id):
                                    res = pdf_motor.render_pdf_page_as_image(st.session_state.drive_service, file_id, 0)
                                    if 'image' in res: return res['image']
                                    return None
                                pdf_thumb = get_pdf_thumb(item['id'])
                                if pdf_thumb: st.image(pdf_thumb, use_column_width='auto')
                                else: st.markdown("<p style='font-size: 48px;'>📑</p>", unsafe_allow_html=True)
                            elif item.get('type') == 'text' and 'content' in item: st.info(item.get('content'))
                            elif item.get('type') == 'text': st.markdown("<p style='font-size: 48px;'>📄</p>", unsafe_allow_html=True)
                        with col_list[-2]: # Filename column
                            st.write(item.get('filename', 'Okänt filnamn'))
                        with col_list[-1]: # Action column
                             if st.session_state.organize_mode and item['type'] == 'pdf':
                                if st.button("Dela upp ✂️", key=f"split_{item['id']}"):
                                    with st.spinner(f"Delar upp {item['filename']}..."):
                                        result = pdf_motor.split_pdf_and_upload(st.session_state.drive_service, item['id'], item['filename'], st.session_state.current_folder_id)
                                        if 'error' in result: st.error(result['error'])
                                        elif 'new_files' in result:
                                            # Ersätt den gamla filen med de nya sidorna
                                            st.session_state.story_items = st.session_state.story_items[:i] + result['new_files'] + st.session_state.story_items[i+1:]
                                            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                                            st.success("PDF uppdelad!")
                                            reload_story_items(show_spinner=False)
                    st.divider()
        else:
            st.info("⬅️ Använd filbläddraren för att börja.")
