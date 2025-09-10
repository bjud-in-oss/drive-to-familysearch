import streamlit as st
import requests
from urllib.parse import urlencode

# Importera Googles bibliotek
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- Konfiguration ---
# Hämtar secrets från Streamlit för säker hantering
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = st.secrets.get("APP_URL") 
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_URI = 'https://oauth2.googleapis.com/token'
AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'

def get_auth_url():
    """
    Skapar den unika URL som användaren ska skickas till för att logga in med Google.
    """
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        return None
        
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return f"{AUTH_URI}?{urlencode(params)}"

def exchange_code_for_service(auth_code):
    """
    När Google skickar tillbaka användaren med en temporär kod,
    byter denna funktion ut koden mot en riktig åtkomst-token
    och skapar ett Drive service-objekt.
    """
    try:
        token_data = {
            'code': auth_code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        response = requests.post(TOKEN_URI, data=token_data)
        response.raise_for_status()  # Kastar ett fel om statuskoden är t.ex. 400
        
        credentials_data = response.json()
        
        # Google-biblioteket kräver att dessa finns i dictionaryn för att skapa Credentials
        credentials_data['client_id'] = CLIENT_ID
        credentials_data['client_secret'] = CLIENT_SECRET
        
        credentials = Credentials.from_authorized_user_info(credentials_data, SCOPES)
        drive_service = build('drive', 'v3', credentials=credentials)
        return drive_service
        
    except requests.exceptions.RequestException as e:
        st.error(f"Ett nätverksfel inträffade vid inloggning: {e}")
        return None
    except Exception as e:
        st.error(f"Ett generellt fel inträffade vid inloggning: {e}")
        st.error(f"Felsökningsinfo: {response.text if 'response' in locals() else 'Ingen respons från servern.'}")
        return None
