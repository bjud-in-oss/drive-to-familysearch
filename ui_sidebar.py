import streamlit as st
import pdf_motor # Vår motor för all backend-logik
from ui_renderer import reload_story_items # Vi kommer behöva denna här

def render_sidebar():
    """
    Ritar upp hela sidopanelen, inklusive användarinfo,
    filbläddrare och verktyg för organisering.
    """
    st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
    st.divider()

    # --- FILBLÄDDRARE (visas inte i snabbsortering) ---
    if not st.session_state.quick_sort_mode:
        st.markdown("### Välj Källmapp")
        if st.session_state.current_folder_id is None:
            # Användaren har inte valt enhet än, visa listan på enheter
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
        else:
            # Användaren navigerar i en mappstruktur
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
                reload_story_items() # Använder omladdningsfunktionen

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

    # --- VERKTYG FÖR ORGANISERING ---
    if st.session_state.story_items is not None and st.session_state.organize_mode:
        st.divider()
        st.markdown("### Verktyg")
        st.info("Dina originalfiler raderas eller ändras aldrig.", icon="ℹ️")

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

        selected_indices = {i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{item['id']}")}
        st.info(f"{len(selected_indices)} objekt valda.")

        tool_cols = st.columns(2)
        if tool_cols[0].button("Klipp ut 📤", disabled=not selected_indices, use_container_width=True):
            st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(list(selected_indices))]
            for i in sorted(list(selected_indices), reverse=True):
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()
        if tool_cols[1].button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):
            st.session_state.story_items = st.session_state.clipboard + st.session_state.story_items
            st.session_state.clipboard = []
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()

        if st.session_state.clipboard:
            st.success(f"{len(st.session_state.clipboard)} i urklipp.")

        if st.button("Ta bort 🗑️", type="primary", disabled=not selected_indices, use_container_width=True):
            for i in sorted(list(selected_indices), reverse=True):
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()
