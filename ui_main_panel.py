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

def render_main_content():
    """
    Ritar upp huvudinnehållet, antingen snabbsortering eller den detaljerade berättelselistan.
    """
    if st.session_state.story_items is not None and st.session_state.quick_sort_mode:
        # --- SNABBSORTERINGS-LÄGE ---
        st.warning("SNABBSORTERINGS-LÄGE AKTIVT")
        if st.button("✅ Avsluta Snabbsortering och spara"):
            if st.session_state.unsorted_items:
                st.session_state.story_items.extend(st.session_state.unsorted_items)
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.session_state.quick_sort_mode = False
            st.rerun()

        qs_col1, qs_col2 = st.columns(2)
        with qs_col1:
            st.markdown("#### Kvar att sortera")
            with st.container(height=600):
                for i, item in enumerate(st.session_state.unsorted_items):
                    if st.button(f"➕ {item['filename']}", key=f"add_{item['id']}", use_container_width=True):
                        st.session_state.story_items.append(item)
                        st.session_state.unsorted_items.pop(i)
                        st.rerun()
        with qs_col2:
            st.markdown("#### Din Berättelse (i ordning)")
            with st.container(height=600):
                if not st.session_state.story_items:
                    st.info("Börja genom att klicka på objekt från vänster.")
                for item in st.session_state.story_items:
                    i_col1, i_col2 = st.columns([1, 5])
                    if item.get('type') == 'image' and item.get('thumbnail'):
                        i_col1.image(item['thumbnail'], width=75)
                    elif item.get('type') == 'pdf':
                        i_col1.markdown("📑")
                    elif item.get('type') == 'text':
                        i_col1.markdown("📄")
                    i_col2.write(item.get('filename'))

    elif st.session_state.story_items is not None:
        # --- NORMALT BERÄTTELSE-LÄGE ---
        st.toggle("Ändra ordning & innehåll (Organisera-läge)", key="organize_mode")
        st.markdown("### Berättelsens flöde")
        for i, item in enumerate(st.session_state.story_items):
            with st.container():
                cols = [1, 10] if not st.session_state.organize_mode else [0.5, 1, 10]
                col_list = st.columns(cols)
                
                # Bestäm vilka kolumner som finns baserat på organiseringsläget
                checkbox_col = col_list[0] if st.session_state.organize_mode else None
                thumb_col = col_list[1] if st.session_state.organize_mode else col_list[0]
                content_col = col_list[2] if st.session_state.organize_mode else col_list[1]

                if checkbox_col:
                    checkbox_col.checkbox("", key=f"select_{item['id']}")

                with thumb_col:
                    if item.get('type') == 'image' and item.get('thumbnail'):
                        st.image(item['thumbnail'], width=100)
                    elif item.get('type') == 'pdf':
                        # Använd vår nya render-funktion från den avancerade motorn
                        cache_key = f"thumb_cache_{item['id']}"
                        if cache_key not in st.session_state:
                            with st.spinner("Genererar PDF-vy..."):
                                render_result = pdf_motor.render_pdf_page_as_image(st.session_state.drive_service, item['id'])
                                if 'image' in render_result:
                                    st.session_state[cache_key] = render_result['image']
                                else:
                                    st.session_state[cache_key] = "ERROR" # Markera att rendering misslyckades
                        
                        if st.session_state.get(cache_key) != "ERROR":
                            st.image(st.session_state[cache_key], use_column_width=True, caption="Sida 1")
                        else:
                            # Fallback till ikon om renderingen misslyckades eller om Google gav en thumbnail
                            if item.get('thumbnail'):
                                st.image(item['thumbnail'], width=100)
                            else:
                                st.markdown("<p style='font-size: 48px;'>📑</p>", unsafe_allow_html=True)
                    elif item.get('type') == 'text' and 'content' in item:
                        st.info(item.get('content'))
                    elif item.get('type') == 'text':
                        st.markdown("<p style='font-size: 48px;'>📄</p>", unsafe_allow_html=True)

                with content_col:
                    st.write(item.get('filename'))
                    if st.session_state.organize_mode and item['type'] == 'pdf':
                        if st.button("Dela upp ✂️", key=f"split_{item['id']}"):
                            with st.spinner(f"Delar upp {item['filename']}..."):
                                result = pdf_motor.split_pdf_and_upload(st.session_state.drive_service, item['id'], item['filename'], st.session_state.current_folder_id)
                                if 'error' in result:
                                    st.error(result['error'])
                                elif 'new_files' in result:
                                    # Ersätt den gamla filen med de nya i listan
                                    st.session_state.story_items = st.session_state.story_items[:i] + result['new_files'] + st.session_state.story_items[i+1:]
                                    pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                                    st.success("PDF uppdelad!")
                                    reload_story_items() # Ladda om hela listan för att visa de nya filerna korrekt
            st.divider()
    else:
        st.info("⬅️ Använd filbläddraren för att börja.")
