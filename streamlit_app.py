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

    with st.spinner("Uppdaterar fillista..."):

        result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)

        if 'error' in result: st.error(result['error'])

        elif 'units' in result: st.session_state.story_items = result['units']

    st.rerun()



# --- Applikationens Flöde ---

st.set_page_config(layout="wide")

st.title("Berättelsebyggaren")



def initialize_state():

    defaults = {

        'drive_service': None, 'user_email': None, 'story_items': None, 'path_history': [], 

        'current_folder_id': None, 'current_folder_name': None, 'organize_mode': False, 

        'selected_indices': set(), 'clipboard': [], 'quick_sort_mode': False, 'unsorted_items': []

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

        

        # FILBLÄDDRARE

        if not st.session_state.quick_sort_mode:

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

                    reload_story_items()



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



            with st.expander("➕ Infoga ny text..."):

                with st.form("new_text_form", clear_on_submit=True):

                    new_text_name = st.text_input("Filnamn (utan .txt)")

                    new_text_style = st.selectbox("Textstil", ['p', 'h1', 'h2'])

                    new_text_content = st.text_area("Innehåll")

                    submitted = st.form_submit_button("Spara ny textfil")

                    if submitted:

                        if new_text_name and new_text_content:

                            prefix = f"{len(st.session_state.story_items):03d}"

                            final_filename = f"{prefix}_{new_text_name}.{new_text_style}.txt"

                            with st.spinner("Sparar textfil..."):

                               result = pdf_motor.upload_new_text_file(st.session_state.drive_service, st.session_state.current_folder_id, final_filename, new_text_content)

                               if 'error' in result: st.error(result['error'])

                               else:

                                   st.success("Textfil sparad!")

                                   reload_story_items()

                        else:

                            st.warning("Filnamn och innehåll får inte vara tomt.")



            st.divider()

            

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

            with tool_cols[0]:

                if st.button("Klipp ut 📤", disabled=not st.session_state.selected_indices, use_container_width=True):

                    st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(list(st.session_state.selected_indices))]

                    for i in sorted(list(st.session_state.selected_indices), reverse=True): del st.session_state.story_items[i]

                    st.session_state.selected_indices = set()

                    pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)

                    st.rerun()

            

            with tool_cols[1]:

                if st.button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):

                    st.session_state.story_items = st.session_state.clipboard + st.session_state.story_items

                    st.session_state.clipboard = []

                    pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)

                    st.rerun()

            

            if st.session_state.clipboard: st.success(f"{len(st.session_state.clipboard)} i urklipp.")

            

            if st.button("Ta bort 🗑️", type="primary", disabled=not st.session_state.selected_indices, use_container_width=True):

                indices_to_remove = sorted(list(st.session_state.selected_indices), reverse=True)

                for i in indices_to_remove:

                    st.session_state[f"select_{st.session_state.story_items[i]['id']}"] = False

                    del st.session_state.story_items[i]

                st.session_state.selected_indices = set()

                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)

                st.rerun()

                

        # Inställningar & Publicering

        if st.session_state.story_items is not None:

            st.divider()

            st.markdown("### Inställningar & Publicering")



            settings_quality = st.slider("Bildkvalitet (lägre = mindre filstorlek)", 10, 95, 85, key="quality_slider")

            settings_max_size = st.number_input("Max filstorlek per PDF (MB)", min_value=1, max_value=100, value=15, key="max_size_input")

            

            if st.button("Skapa PDF-album 🚀", type="primary", use_container_width=True):

                st.session_state.generated_pdfs = None 

                progress_bar_area = st.empty()

                

                def update_progress(fraction, text):

                    progress_bar_area.progress(fraction, text)

                

                settings = {'quality': settings_quality, 'max_size_mb': settings_max_size}

                

                result = pdf_motor.generate_pdfs_from_story(

                    st.session_state.drive_service,

                    st.session_state.story_items,

                    settings,

                    update_progress

                )

                

                if 'error' in result:

                    st.error(result['error'])

                elif 'pdfs' in result:

                    st.session_state.generated_pdfs = result['pdfs']

                

                progress_bar_area.empty() # Ta bort förloppsindikatorn när klar



            if 'generated_pdfs' in st.session_state and st.session_state.generated_pdfs:

                st.success("Dina PDF-album är klara!")

                folder_name = st.session_state.current_folder_name.replace(" ", "_")

                for i, pdf_buffer in enumerate(st.session_state.generated_pdfs):

                    st.download_button(

                        label=f"Ladda ner Del {i+1}",

                        data=pdf_buffer,

                        file_name=f"{folder_name}_Del_{i+1}.pdf",

                        mime="application/pdf",

                        use_container_width=True,

                        key=f"download_{i}"

                    )



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

                    # Visa den visuella listan även här

                    for item in st.session_state.story_items:

                        with st.container():

                            i_col1, i_col2 = st.columns([1,5])

                            with i_col1:

                                if item.get('type') == 'image' and item.get('thumbnail'): st.image(item['thumbnail'], width=75)

                                elif item.get('type') == 'pdf': st.markdown("<p style='font-size: 32px; text-align: center;'>📑</p>", unsafe_allow_html=True)

                                elif item.get('type') == 'text': st.markdown("<p style='font-size: 32px; text-align: center;'>📄</p>", unsafe_allow_html=True)

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

            st.info("⬅️ Använd filbläddraren i sidopanelen för att välja en mapp och klicka på 'Läs in denna mapp'.")
