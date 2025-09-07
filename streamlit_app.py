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
# Appens URL läses nu från Streamlit Clouds secrets
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
        
        credentials = Credentials.from_authorized_user_info(response.json(), SCOPES)
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

# Hantera callback från Google
auth_code = st.query_params.get('code')
if auth_code and st.session_state.drive_service is None:
    with st.spinner("Verifierar inloggning..."):
        st.session_state.drive_service = exchange_code_for_service(auth_code)
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
    # Användaren är inloggad!
    st.success("✅ Du är nu ansluten till Google Drive!")
    st.markdown("---")
    st.markdown("### Välj din Källmapp")
    
    folder_path = st.text_input(
        "Ange sökväg till din mapp (t.ex. `Min Mapp/Undermapp` eller `Namn på Delad Enhet/Min Mapp`):",
        ""
    )

    if st.button("Läs in mapp"):
        if folder_path:
            with st.spinner("Hämtar fillista..."):
                result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, folder_path)
                if 'error' in result:
                    st.error(result['error'])
                elif 'units' in result:
                    st.session_state.story_items = result['units']
        else:
            st.warning("Vänligen ange en sökväg till en mapp.")

    if 'story_items' in st.session_state:
        st.markdown("### Mappens innehåll:")
        for item in st.session_state.story_items:
            st.write(f"- `{item['filename']}` (typ: {item['type']})")
