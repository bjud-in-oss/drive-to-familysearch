import streamlit as st

# Importera våra egna, välorganiserade moduler
import google_auth
import state_manager
import ui_sidebar
import ui_main_panel

def render_login_page():
    """Visar den enkla inloggningssidan."""
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    
    auth_url = google_auth.get_auth_url()
    if auth_url:
        st.link_button("Logga in med Google", auth_url)
    else:
        st.error("Fel: Appen saknar konfiguration. GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET och APP_URL måste ställas in i 'Secrets'.")

# --- Applikationens Huvudflöde ---
st.set_page_config(layout="wide")
st.title("Berättelsebyggaren")

# 1. Säkerställ att session state är initialiserat
state_manager.initialize_state()

# 2. Hantera eventuell callback från Google efter inloggning
auth_code = st.query_params.get('code')
if auth_code and st.session_state.drive_service is None:
    with st.spinner("Verifierar inloggning..."):
        st.session_state.drive_service = google_auth.exchange_code_for_service(auth_code)
        if st.session_state.drive_service:
            try:
                user_info = st.session_state.drive_service.about().get(fields='user').execute()
                st.session_state.user_email = user_info['user']['emailAddress']
            except Exception:
                st.session_state.user_email = "Okänd"
        
        st.query_params.clear()
        st.rerun()

# 3. Bestäm vilken vy som ska visas
if st.session_state.drive_service is None:
    # Användaren är INTE inloggad -> Visa inloggningssidan
    render_login_page()
else:
    # Användaren ÄR inloggad -> Rita upp huvudgränssnittet
    col_sidebar, col_main = st.columns([1, 2])

    with col_sidebar:
        ui_sidebar.render_sidebar()

    with col_main:
        ui_main_panel.render_main_content()
