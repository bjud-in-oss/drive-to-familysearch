import streamlit as st
import pdf_motor # Vår motor för all backend-logik

def render_login_page(auth_url):
    """Visar inloggningssidan."""
    st.markdown("### Välkommen!")
    st.markdown("För att börja, anslut ditt Google Drive-konto.")
    
    if auth_url:
        st.link_button("Logga in med Google", auth_url, use_container_width=True)
    else:
        st.error("Fel: Appen saknar konfiguration. GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET och APP_URL måste ställas in i 'Secrets'.")

def reload_story_items():
    """Hjälpfunktion för att ladda om fillistan efter en ändring."""
    with st.spinner("Uppdaterar fillista..."):
        # Rensa all gammal cache för miniatyrbilder
        for key in list(st.session_state.keys()):
            if key.startswith("thumb_cache_"):
                del st.session_state[key]
        
        # Hämta innehållet på nytt
        result = pdf_motor.get_content_units_from_folder(st.session_state.drive_service, st.session_state.current_folder_id)
        if 'error' in result: 
            st.error(result['error'])
        elif 'units' in result: 
            st.session_state.story_items = result['units']
    st.rerun()

def render_sidebar():
    """Ritar upp hela sidopanelen med filbläddrare och verktyg."""
    st.markdown(f"**Ansluten som:**\n{st.session_state.user_email}")
    st.divider()
    
    # --- FILBLÄDDRARE (om inte i snabbsortering) ---
    if not st.session_state.quick_sort_mode:
        st.markdown("### Välj Källmapp")
        # Startvyn, välj enhet
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
        # Navigera i mappar
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
        
        selected_items_indices = [i for i, item in enumerate(st.session_state.story_items) if st.session_state.get(f"select_{item['id']}", False)]
        st.info(f"{len(selected_items_indices)} objekt valda.")

        # --- Knappar för text-infogning ---
        if len(selected_items_indices) == 1:
            idx = selected_items_indices[0]
            if st.button(f"➕ Infoga text FÖRE markerad", key="add_text_before", use_container_width=True):
                st.session_state.show_text_modal = True
                st.session_state.text_insert_index = idx
                st.rerun()
            if st.button(f"➕ Infoga text EFTER markerad", key="add_text_after", use_container_width=True):
                st.session_state.show_text_modal = True
                st.session_state.text_insert_index = idx + 1
                st.rerun()
        else:
            if st.button("➕ Lägg till text sist", key="add_text_end", use_container_width=True):
                st.session_state.show_text_modal = True
                st.session_state.text_insert_index = None # Betyder "sist"
                st.rerun()

        # --- Knappar för klipp & klistra etc ---
        tool_cols = st.columns(2)
        if tool_cols[0].button("Klipp ut 📤", disabled=not selected_items_indices, use_container_width=True):
            st.session_state.clipboard = [st.session_state.story_items[i] for i in sorted(selected_items_indices)]
            for i in sorted(selected_items_indices, reverse=True): 
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()
        if tool_cols[1].button("Klistra in 📥", disabled=not st.session_state.clipboard, use_container_width=True):
            # Klistra in överst om inget är markerat, annars efter det första markerade
            insert_pos = selected_items_indices[0] + 1 if len(selected_items_indices) == 1 else 0
            st.session_state.story_items = st.session_state.story_items[:insert_pos] + st.session_state.clipboard + st.session_state.story_items[insert_pos:]
            st.session_state.clipboard = []
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()
        
        if st.session_state.clipboard: st.success(f"{len(st.session_state.clipboard)} i urklipp.")
        
        if st.button("Ta bort 🗑️", type="primary", disabled=not selected_items_indices, use_container_width=True):
            for i in sorted(selected_items_indices, reverse=True): 
                del st.session_state.story_items[i]
            pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
            st.rerun()

def render_main_content():
    """Ritar upp huvudinnehållet, antingen snabbsortering eller berättelselistan."""
    
    # --- SNABBSORTERINGS-LÄGE ---
    if st.session_state.get('quick_sort_mode', False):
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
                if not st.session_state.story_items: st.info("Börja genom att klicka.")
                for item in st.session_state.story_items:
                    st.text(item.get('filename'))

    # --- NORMALT BERÄTTELSE-LÄGE ---
    elif st.session_state.story_items is not None:
        st.toggle("Ändra ordning & innehåll (Organisera-läge)", key="organize_mode")
        st.markdown("### Berättelsens flöde")
        
        # --- Dialogruta för att skapa textfil ---
        if st.session_state.get('show_text_modal', False):
            with st.form("new_text_form"):
                st.markdown("### Skapa ny textfil")
                new_filename = st.text_input("Filnamn (använd t.ex. 'min_fil.h1.txt' för rubrik)", "ny_text.p.txt")
                new_content = st.text_area("Innehåll", height=200)
                submitted = st.form_submit_button("Spara textfil på Google Drive")
                
                if submitted:
                    if not any(new_filename.lower().endswith(ext) for ext in pdf_motor.SUPPORTED_TEXT_EXTENSIONS):
                        st.error(f"Filnamnet måste sluta med något av: {pdf_motor.SUPPORTED_TEXT_EXTENSIONS}")
                    else:
                        with st.spinner(f"Sparar {new_filename}..."):
                            result = pdf_motor.upload_new_text_file(st.session_state.drive_service, st.session_state.current_folder_id, new_filename, new_content)
                            if 'error' in result:
                                st.error(result['error'])
                            else:
                                insert_index = st.session_state.get('text_insert_index')
                                if insert_index is not None:
                                    st.session_state.story_items.insert(insert_index, result['unit'])
                                else:
                                    st.session_state.story_items.append(result['unit'])
                                
                                pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                                st.success(f"'{new_filename}' har skapats!")
                                st.session_state.show_text_modal = False
                                st.rerun()
        
        # --- Visa själva listan med objekt ---
        for i, item in enumerate(st.session_state.story_items):
            with st.container(border=True):
                cols = [1, 5] if not st.session_state.organize_mode else [0.5, 1, 5]
                col_list = st.columns(cols)
                
                checkbox_col, thumb_col, content_col = (None, col_list[0], col_list[1]) if not st.session_state.organize_mode else (col_list[0], col_list[1], col_list[2])

                if st.session_state.organize_mode:
                    checkbox_col.checkbox("Välj", key=f"select_{item['id']}", label_visibility="collapsed")

                with thumb_col:
                    if item.get('type') == 'image' and item.get('thumbnail'):
                        st.image(item['thumbnail'], use_column_width=True)
                    elif item.get('type') == 'pdf':
                        cache_key = f"thumb_cache_{item['id']}"
                        if cache_key not in st.session_state:
                            with st.spinner("Genererar PDF-vy..."):
                                render_result = pdf_motor.render_pdf_page_as_image(st.session_state.drive_service, item['id'])
                                st.session_state[cache_key] = render_result.get('image', "ERROR")
                        
                        if st.session_state[cache_key] != "ERROR":
                            st.image(st.session_state[cache_key], use_column_width=True, caption=f"Sida 1")
                        else:
                            st.markdown("<p style='font-size: 48px; text-align: center;'>📑</p>", unsafe_allow_html=True)
                    elif item.get('type') == 'text':
                        st.markdown("<p style='font-size: 48px; text-align: center;'>📄</p>", unsafe_allow_html=True)
                
                with content_col:
                    st.write(item.get('filename'))
                    if item.get('type') == 'text' and 'content' in item:
                        st.info(item.get('content'))

                    if st.session_state.organize_mode and item['type'] == 'pdf':
                       if st.button("Dela upp ✂️", key=f"split_{item['id']}"):
                            with st.spinner(f"Delar upp {item['filename']}..."):
                                result = pdf_motor.split_pdf_and_upload(st.session_state.drive_service, item['id'], item['filename'], st.session_state.current_folder_id)
                                if 'error' in result: 
                                    st.error(result['error'])
                                elif 'new_files' in result:
                                    st.session_state.story_items = st.session_state.story_items[:i] + result['new_files'] + st.session_state.story_items[i+1:]
                                    pdf_motor.save_story_order(st.session_state.drive_service, st.session_state.current_folder_id, st.session_state.story_items)
                                    st.success("PDF uppdelad!")
                                    reload_story_items()
    else:
        st.info("⬅️ Använd filbläddraren i sidopanelen för att välja en mapp och börja bygga din berättelse.")
