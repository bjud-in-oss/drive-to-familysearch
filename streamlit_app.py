import streamlit as st

# Importera våra egna, slutgiltiga moduler
import google_auth
import state_manager
import ui_file_browser  # Ny, specifik modul för filbläddraren
import ui_tool_panel    # Ny, specifik modul för verktygspanelen
import ui_quicksort_panel
import ui_story_panel

def render_login_page():
    """Visar den enkla inloggningssidan."""
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    auth_url = google_auth.get_auth_url()
    if auth_url:
        st.link_button("Logga in med Google", auth_url)
    else:
        st.error("Fel: Appen saknar konfiguration. GOOGLE_CLIENT_ID, etc. måste ställas in.")

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
    render_login_page()
else:
    # Användaren ÄR inloggad -> Rita upp gränssnittet med st.sidebar
    with st.sidebar:
        st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
        st.divider()
        
        # Rendera filbläddraren om vi inte är i snabbsorteringsläge
        if not st.session_state.get('quick_sort_mode', False):
            ui_file_browser.render_file_browser()

        # Om en mapp är inläst, visa verktyg och PDF-inställningar
        if st.session_state.story_items is not None:
            ui_tool_panel.render_tool_panel()

    # Huvudinnehållet
    if st.session_state.get('run_pdf_generation', False):
        # Om vi ska generera PDF, visa den vyn
        ui_story_panel.render_pdf_generation_view()
    elif st.session_state.get('generated_pdfs'):
        # Om det finns färdiga PDFer, visa nedladdningsknappar
        st.markdown("### Dina PDF-album är klara!")
        for i, pdf_buffer in enumerate(st.session_state.generated_pdfs):
            st.download_button(
                label=f"Ladda ner Album del {i+1}",
                data=pdf_buffer,
                file_name=f"Berattelse_del_{i+1}.pdf",
                mime="application/pdf"
            )
        if st.button("Skapa ett nytt album"):
            st.session_state.generated_pdfs = []
            st.rerun()
    elif st.session_state.get('quick_sort_mode', False):
        ui_quicksort_panel.render_quicksort_panel()
    elif st.session_state.story_items is not None:
        ui_story_panel.render_story_panel()
    else:
        st.info("⬅️ Använd filbläddraren för att börja.")
