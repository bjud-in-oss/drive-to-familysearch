import streamlit as st
import pdf_motor # Behövs för att spara ordningen

def render_quicksort_panel():
    """
    Ritar upp hela gränssnittet för Snabbsorterings-läget,
    med en kolumn för osorterade objekt och en för den nya berättelsen.
    """
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
            # Iterera baklänges för att kunna ta bort objekt säkert
            for i in range(len(st.session_state.unsorted_items) - 1, -1, -1):
                item = st.session_state.unsorted_items[i]
                if st.button(f"➕ {item['filename']}", key=f"add_{item['id']}", use_container_width=True):
                    st.session_state.story_items.append(item)
                    st.session_state.unsorted_items.pop(i)
                    st.rerun()
    with qs_col2:
        st.markdown("#### Din Berättelse (i ordning)")
        with st.container(height=600):
            if not st.session_state.story_items:
                st.info("Börja genom att klicka på objekt från vänster.")
            # Denna vy från originalet var enklare, vi behåller den för snabbhetens skull
            for item in st.session_state.story_items:
                i_col1, i_col2 = st.columns([1, 5])
                if item.get('type') == 'image' and item.get('thumbnail'):
                    i_col1.image(item['thumbnail'], width=75)
                elif item.get('type') == 'pdf':
                    i_col1.markdown("📑")
                elif item.get('type') == 'text':
                    i_col1.markdown("📄")
                i_col2.write(item.get('filename'))
