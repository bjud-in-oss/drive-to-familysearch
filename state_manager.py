import streamlit as st

def initialize_state():
    """
    Initialiserar alla variabler vi behöver i session state på ett säkert sätt.
    Detta säkerställer att appen inte kraschar på grund av saknade nycklar.
    """
    defaults = {
        'drive_service': None, 
        'user_email': None, 
        'story_items': None, 
        'path_history': [], 
        'current_folder_id': None, 
        'current_folder_name': None, 
        'organize_mode': False, 
        'selected_indices': set(),  # Notera: 'selected_indices' fanns i din originalkod, behåller den
        'clipboard': [], 
        'quick_sort_mode': False, 
        'unsorted_items': []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
