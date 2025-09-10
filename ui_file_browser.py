import streamlit as st
import pdf_motor
from ui_story_panel import reload_story_items # Importerar från filen vi snart ska skapa

def render_file_browser():
    """
    Ritar upp gränssnittet för att navigera i Google Drive,
    välja enhet och bläddra i mappar.
    """
    st.markdown("### Välj Källmapp")
    
    # Om ingen enhet är vald, visa listan på tillgängliga enheter
    if st.session_state.current_folder_id is None:
        drives = pdf_motor.get_available_drives(st.session_state.drive_service)
        if 'error' in drives:
            st.error(drives['error'])
        else:
            for drive in sorted(drives, key=lambda x: x.get('name', '').lower()):
                icon = "📁" if drive.get('id') == 'root' else "🏢"
                if st.button(f"{icon} {drive.get('name', 'Okänd enhet')}", use_container_width=True, key=drive.get('id')):
                    st.session_state.current_folder_id = drive.get('id')
                    st.session_state.current_folder_name = drive.get('name')
                    st.session_state.path_history = []
                    st.rerun()
    # Om en enhet är vald, visa mappnavigationen
    else:
        path_parts = [name for id, name in st.session_state.path_history] + [st.session_state.current_folder_name]
        st.write(f"**Plats:** `{' / '.join(path_parts)}`")
        
        c1, c2 = st.columns(2)
        if c1.button("⬅️ Byt enhet", use_container_width=True):
            st.session_state.current_folder_id, st.session_state.path_history, st.session_state.story_items = None, [], None
            st.rerun()
        if c2.button("⬆️ Gå upp", use_container_width=True, disabled=not st.session_state.path_history):
            prev_id, prev_name = st.session_state.path_history.pop()
            st.session_state.current_folder_id, st.session_state.current_folder_name = prev_id, prev_name
            st.session_state.story_items = None
            st.rerun()
            
        if st.button("✅ Läs in denna mapp", type="primary", use_container_width=True):
            reload_story_items()

        # Visa undermappar
        folders = pdf_motor.list_folders(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in folders:
            st.error(folders['error'])
        elif folders:
            st.markdown("*Undermappar:*")
            for folder in sorted(folders, key=lambda x: x.get('name', '').lower()):
                if st.button(f"📁 {folder.get('name', 'Okänd mapp')}", key=folder.get('id'), use_container_width=True):
                    st.session_state.path_history.append((st.session_state.current_folder_id, st.session_state.current_folder_name))
                    st.session_state.current_folder_id = folder.get('id')
                    st.session_state.current_folder_name = folder.get('name')
                    st.session_state.story_items = None
                    st.rerun()
