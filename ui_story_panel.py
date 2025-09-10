import streamlit as st
import pdf_motor # Vår motor för all backend-logik

def reload_story_items():
    """
    Hjälpfunktion för att ladda om fillistan efter en ändring.
    Denna är kritisk efter operationer som "Dela upp PDF".
    """
    with st.spinner("Uppdaterar fillista..."):
        # Rensa all gammal cache för miniatyrbilder för att tvinga fram en ny rendering
        for key in list(st.session_state.keys()):
            if key.startswith("thumb_cache_"):
                del st.session_state[key]

        result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in result:
            st.error(result['error'])
        elif 'units' in result:
            st.session_state.story_items = result['units']
    st.rerun()

def render_story_panel():
    """
    Ritar upp den vanliga vyn för "Berättelsens flöde",
    med detaljerade miniatyrbilder och interaktiva element.
    """
    st.toggle("Ändra ordning & innehåll (Organisera-läge)", key="organize_mode")
    st.markdown("### Berättelsens flöde")

    # Visa själva listan med objekt, iterera säkert
    for i in range(len(st.session_state.story_items) - 1, -1, -1):
        # Kontrollera om objektet fortfarande finns (kan ha tagits bort av "Dela upp")
        if i >= len(st.session_state.story_items):
            continue
        item = st.session_state.story_items[i]
        
        with st.container():
            cols = [1, 10] if not st.session_state.organize_mode else [0.5, 1, 10]
            col_list = st.columns(cols)
            
            checkbox_col = col_list[0] if st.session_state.organize_mode else None
            thumb_col = col_list[1] if st.session_state.organize_mode else col_list[0]
            content_col = col_list[2] if st.session_state.organize_mode else col_list[1]

            if checkbox_col:
                checkbox_col.checkbox("", key=f"select_{item['id']}")

            with thumb_col:
                # Logik för att visa korrekt miniatyrbild
                if item.get('type') == 'image' and item.get('thumbnail'):
                    st.image(item['thumbnail'], width=100)
                elif item.get('type') == 'pdf':
                    # Använder vår nya, avancerade render-funktion
                    cache_key = f"thumb_cache_{item['id']}"
                    if cache_key not in st.session_state:
                        with st.spinner("Genererar PDF-vy..."):
                            render_result = pdf_motor.render_pdf_page_as_image(st.session_state.drive_service, item['id'])
                            st.session_state[cache_key] = render_result.get('image', "ERROR")
                    
                    if st.session_state.get(cache_key) != "ERROR":
                        st.image(st.session_state[cache_key], use_container_width=True, caption="Sida 1")
                    else:
                        st.markdown("<p style='font-size: 48px;'>📑</p>", unsafe_allow_html=True)
                elif item.get('type') == 'text' and 'content' in item:
                    # Visa textinnehåll direkt om det finns
                    st.info(item.get('content'))
                elif item.get('type') == 'text':
                    st.markdown("<p style='font-size: 48px;'>📄</p>", unsafe_allow_html=True)

            with content_col:
                st.write(item.get('filename'))
                if st.session_state.organize_mode and item['type'] == 'pdf':
                    if st.button("Dela upp ✂️", key=f"split_{item['id']}"):
                        with st.spinner(f"Delar upp {item['filename']}..."):
                            result = pdf_motor.split_pdf_and_upload(
                                service=st.session_state.drive_service,
                                file_id=item['id'],
                                original_filename=item['filename'],
                                folder_id=st.session_state.current_folder_id
                            )
                            if 'error' in result:
                                st.error(result['error'])
                            elif 'new_files' in result:
                                # Ersätt det gamla objektet med de nya
                                st.session_state.story_items = st.session_state.story_items[:i] + result['new_files'] + st.session_state.story_items[i+1:]
                                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                                st.success("PDF uppdelad!")
                                reload_story_items()
            st.divider()
