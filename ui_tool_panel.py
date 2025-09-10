import streamlit as st
import pdf_motor

def render_tool_panel():
    """
    Ritar upp hela verktygspanelen som visas när en mapp är inläst.
    Inkluderar organiseringsverktyg och PDF-inställningar.
    """
    # --- VERKTYG FÖR ORGANISERING ---
    if st.session_state.organize_mode:
        st.divider()
        st.markdown("### Verktyg")

        # --- Knappar för text-infogning ---
        selected_indices = [i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{item['id']}")]
        
        if len(selected_indices) == 1:
            idx = selected_indices[0]
            st.button("➕ Infoga text FÖRE markerad", on_click=lambda: st.session_state.update(show_text_modal=True, text_insert_index=idx), use_container_width=True)
            st.button("➕ Infoga text EFTER markerad", on_click=lambda: st.session_state.update(show_text_modal=True, text_insert_index=idx + 1), use_container_width=True)
        else:
            st.button("➕ Lägg till text sist", on_click=lambda: st.session_state.update(show_text_modal=True, text_insert_index=None), use_container_width=True)
        
        st.divider()
        
        # --- Övriga verktyg ---
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

        st.info(f"{len(selected_indices)} objekt valda.")

        tool_cols = st.columns(2)
        if tool_cols[0].button("Klipp ut 📤", disabled=not selected_indices, use_container_width=True):
            st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(selected_indices, reverse=False)]
            for i in sorted(selected_indices, reverse=True):
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()
        if tool_cols[1].button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):
            insert_pos = selected_indices[0] + 1 if len(selected_indices) == 1 else 0
            st.session_state.story_items = st.session_state.story_items[:insert_pos] + st.session_state.clipboard + st.session_state.story_items[insert_pos:]
            st.session_state.clipboard = []
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()

        if st.session_state.clipboard:
            st.success(f"{len(st.session_state.clipboard)} i urklipp.")

        if st.button("Ta bort 🗑️", type="primary", disabled=not selected_indices, use_container_width=True):
            for i in sorted(selected_indices, reverse=True):
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()

    # --- PDF-GENERERING (visas alltid när en mapp är inläst) ---
    st.divider()
    st.markdown("### Inställningar & Publicering")

    if 'pdf_settings' not in st.session_state:
        st.session_state.pdf_settings = {'quality': 85, 'max_size_mb': 15.0, 'margin_mm': 0.0}
    
    st.session_state.pdf_settings['quality'] = st.slider("Bildkvalitet (JPEG)", 1, 100, st.session_state.pdf_settings['quality'])
    st.session_state.pdf_settings['max_size_mb'] = st.number_input("Max filstorlek per PDF (MB)", 1.0, value=st.session_state.pdf_settings['max_size_mb'])
    st.session_state.pdf_settings['margin_mm'] = st.number_input("Marginal runt innehåll (mm)", 0.0, 50.0, st.session_state.pdf_settings['margin_mm'], 0.5)

    if st.button("Skapa PDF-album 📚", type="primary", use_container_width=True, disabled=not st.session_state.story_items):
        st.session_state.run_pdf_generation = True
        st.rerun()
