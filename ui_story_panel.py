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

    # --- Dialogruta för att skapa textfil ---
    if st.session_state.get('show_text_modal', False):
        with st.form("new_text_form"):
            st.markdown("### Skapa ny textfil")
            new_filename = st.text_input("Filnamn (använd t.ex. 'min_fil.h1.txt' för rubrik)", "ny_text.p.txt")
            new_content = st.text_area("Innehåll", height=200)
            
            # Knappar i två kolumner
            col1, col2 = st.columns(2)
            
            if col1.form_submit_button("Spara textfil på Google Drive", type="primary", use_container_width=True):
                if not any(new_filename.lower().endswith(ext) for ext in pdf_motor.SUPPORTED_TEXT_EXTENSIONS):
                    st.error(f"Filnamnet måste sluta med något av: {pdf_motor.SUPPORTED_TEXT_EXTENSIONS}")
                else:
                    with st.spinner(f"Sparar {new_filename}..."):
                        result = pdf_motor.upload_new_text_file(
                            st.session_state.drive_service,
                            st.session_state.current_folder_id,
                            new_filename,
                            new_content
                        )
                        if 'error' in result:
                            st.error(result['error'])
                        else:
                            insert_index = st.session_state.get('text_insert_index')
                            if insert_index is not None:
                                st.session_state.story_items.insert(insert_index, result['unit'])
                            else: # Om index är None, lägg till sist
                                st.session_state.story_items.append(result['unit'])
                            
                            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                            st.success(f"'{new_filename}' har skapats och lagts till i din berättelse!")
                            st.session_state.show_text_modal = False
                            st.rerun()

            if col2.form_submit_button("Avbryt", use_container_width=True):
                st.session_state.show_text_modal = False
                st.rerun()
        st.divider()

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
def render_pdf_generation_view():
    """
    Visar en förloppsindikator under PDF-generering och sedan
    nedladdningsknappar för de färdiga filerna.
    """
    st.markdown("### Skapar PDF-album...")
    st.info("Detta kan ta en stund beroende på antalet bilder och deras storlek. Vänligen vänta.")
    
    progress_bar = st.progress(0, "Startar...")
    status_text = st.empty()

    def progress_callback(fraction, message):
        """Uppdaterar progress bar och text från motorn."""
        progress_bar.progress(fraction, message)
        status_text.text(message)

    try:
        result = pdf_motor.generate_pdfs_from_story(
            service=st.session_state.drive_service,
            story_items=st.session_state.story_items,
            settings=st.session_state.pdf_settings,
            progress_callback=progress_callback
        )
        
        if 'pdfs' in result and result['pdfs']:
            st.session_state.generated_pdfs = result['pdfs']
        else:
            st.error("Något gick fel, inga PDF-filer skapades.")
            st.session_state.generated_pdfs = []

    except Exception as e:
        st.error(f"Ett allvarligt fel inträffade under PDF-genereringen: {e}")
        st.session_state.generated_pdfs = []

    # Återställ flaggan och ladda om för att visa nedladdningsknapparna
    st.session_state.run_pdf_generation = False
    st.rerun()
