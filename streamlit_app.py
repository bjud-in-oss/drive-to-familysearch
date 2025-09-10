import streamlit as st

# Importera våra egna moduler
import google_auth
import ui_renderer
import pdf_motor

def initialize_state():
    """Initialiserar alla variabler vi behöver i session state på ett säkert sätt."""
    defaults = {
        'drive_service': None,
        'user_email': None,
        'story_items': None,
        'path_history': [],
        'current_folder_id': None,
        'current_folder_name': None,
        'organize_mode': False,
        'clipboard': [],
        'quick_sort_mode': False,
        'unsorted_items': [],
        'show_text_modal': False,
        'text_insert_index': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- Applikationens Huvudflöde ---
st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

# Körs alltid först för att säkerställa att session state är redo
initialize_state()

# STEG 1: Hantera eventuell callback från Google
auth_code = st.query_params.get('code')
if auth_code and st.session_state.drive_service is None:
    with st.spinner("Verifierar inloggning..."):
        st.session_state.drive_service = google_auth.exchange_code_for_service(auth_code)
        if st.session_state.drive_service:
            try:
                # Försök hämta användarens e-post för att visa vem som är inloggad
                user_info = st.session_state.drive_service.about().get(fields='user').execute()
                st.session_state.user_email = user_info['user']['emailAddress']
            except Exception:
                st.session_state.user_email = "Okänd"
        # Rensa bort koden från URL:en och ladda om sidan
        st.query_params.clear()
        st.rerun()

# STEG 2: Bestäm vilken vy som ska visas baserat på inloggningsstatus
if st.session_state.drive_service is None:
    # ANVÄNDAREN ÄR INTE INLOGGAD
    auth_url = google_auth.get_auth_url()
    ui_renderer.render_login_page(auth_url)
else:
    # ANVÄNDAREN ÄR INLOGGAD
    col_sidebar, col_main = st.columns([1, 2]) # Justerat förhållandet för bättre layout

    with col_sidebar:
        ui_renderer.render_sidebar()

    with col_main:
        ui_renderer.render_main_content()
