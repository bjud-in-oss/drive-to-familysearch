import os
from pathlib import Path
from googleapiclient.errors import HttpError
import io
import json

# Konfiguration
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
SUPPORTED_TEXT_EXTENSIONS = ('.txt',)
SUPPORTED_PDF_EXTENSIONS = ('.pdf',)
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_TEXT_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS
PROJECT_FILE_NAME = '.storyproject.json'

def get_available_drives(service):
    drives = [{'id': 'root', 'name': 'Min enhet'}]
    try:
        response = service.drives().list().execute()
        drives.extend(response.get('drives', []))
        return drives
    except HttpError as e: return {'error': f"Kunde inte hämta enheter: {e}"}

def list_folders(service, folder_id='root'):
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, supportsAllDrives=True, includeItemsFromAllDrives=True, spaces='drive', fields='files(id, name)').execute()
        return results.get('files', [])
    except HttpError as e: return {'error': f"Kunde inte hämta mappar: {e}"}

def load_story_order(service, folder_id):
    """Letar efter en projektfil och returnerar den sparade ordningen."""
    try:
        query = f"'{folder_id}' in parents and name = '{PROJECT_FILE_NAME}' and trashed = false"
        response = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
        files = response.get('files', [])
        if files:
            request = service.files().get_media(fileId=files[0]['id'])
            fh = io.BytesIO()
            downloader = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            project_data = json.loads(fh.getvalue())
            return project_data.get('order', [])
    except HttpError as e: print(f"Kunde inte ladda projektfil: {e}")
    return None

def save_story_order(service, folder_id, story_items):
    """Sparar den nuvarande ordningen till projektfilen."""
    # Spara endast en lista av filnamn, för att hålla filen liten
    order_to_save = [item['filename'] for item in story_items]
    content = json.dumps({'order': order_to_save}).encode('utf-8')
    fh = io.BytesIO(content)
    
    #... (Logik för att ladda upp/uppdatera filen kommer i en senare fas)
    print("Simulerar sparande av projektfil...")
    return True

def get_content_units_from_folder(service, folder_id):
    all_units = []
    try:
        # Hämta alla filer i mappen
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, pageSize=1000, fields="files(id, name, mimeType, thumbnailLink)").execute()
        items = results.get('files', [])
        
        # Filtrera bort de som inte stöds
        for item in items:
            filename = item.get('name')
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                unit = {'filename': filename, 'id': item.get('id'), 'type': 'unknown', 'thumbnail': item.get('thumbnailLink')}
                if ext in SUPPORTED_IMAGE_EXTENSIONS: unit['type'] = 'image'
                elif ext in SUPPORTED_TEXT_EXTENSIONS: unit['type'] = 'text'
                elif ext in SUPPORTED_PDF_EXTENSIONS: unit['type'] = 'pdf'
                all_units.append(unit)
        
        # Ladda den sparade ordningen
        saved_order = load_story_order(service, folder_id)
        if saved_order:
            # Skapa en mappning från filnamn till enhet för snabb sortering
            unit_map = {unit['filename']: unit for unit in all_units}
            # Bygg den sorterade listan
            sorted_units = [unit_map[filename] for filename in saved_order if filename in unit_map]
            # Lägg till eventuella nya filer (som inte fanns i projektfilen) i slutet
            new_files = [unit for filename, unit in unit_map.items() if filename not in saved_order]
            sorted_units.extend(sorted(new_files, key=lambda x: x['filename'].lower()))
            return {'units': sorted_units}
        else:
            # Om ingen sparad ordning finns, sortera alfabetiskt
            all_units.sort(key=lambda x: x['filename'].lower())
            return {'units': all_units}
            
    except HttpError as e: return {'error': f"Kunde inte hämta filer från Google Drive: {e}"}
