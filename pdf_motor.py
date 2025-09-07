import os
from pathlib import Path
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
import json
from pypdf import PdfReader, PdfWriter

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
    try:
        query = f"'{folder_id}' in parents and name = '{PROJECT_FILE_NAME}' and trashed = false"
        response = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, fields="files(id)").execute()
        files = response.get('files', [])
        if files:
            request = service.files().get_media(fileId=files[0]['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False: status, done = downloader.next_chunk()
            project_data = json.loads(fh.getvalue())
            return project_data.get('order', [])
    except HttpError as e: print(f"Kunde inte ladda projektfil: {e}")
    return None

def save_story_order(service, folder_id, story_items):
    order_to_save = [item['filename'] for item in story_items]
    content = json.dumps({'order': order_to_save}, indent=2).encode('utf-8')
    fh = io.BytesIO(content)
    media_body = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
    try:
        query = f"'{folder_id}' in parents and name = '{PROJECT_FILE_NAME}' and trashed = false"
        response = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, fields="files(id)").execute()
        existing_files = response.get('files', [])
        if existing_files:
            service.files().update(fileId=existing_files[0]['id'], media_body=media_body, supportsAllDrives=True).execute()
        else:
            file_metadata = {'name': PROJECT_FILE_NAME, 'parents': [folder_id]}
            service.files().create(body=file_metadata, media_body=media_body, supportsAllDrives=True, fields='id').execute()
        return {'success': True}
    except HttpError as e:
        return {'error': f"Kunde inte spara projektfilen: {e}"}

def get_content_units_from_folder(service, folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, pageSize=1000, fields="files(id, name, mimeType, thumbnailLink)").execute()
        items = results.get('files', [])
        
        # Skapa en mappning från filnamn till google-fil-objekt
        unit_map = {item.get('name'): item for item in items if item.get('name') != PROJECT_FILE_NAME}
        
        saved_order = load_story_order(service, folder_id)
        final_google_items = []
        
        # Om det finns en sparad ordning, bygg listan baserat på den
        if saved_order:
            # Plocka ut objekten i rätt ordning
            ordered_map = {filename: unit_map.pop(filename) for filename in saved_order if filename in unit_map}
            final_google_items.extend(list(ordered_map.values()))
        
        # Lägg till resterande (nya) filer i slutet, sorterade alfabetiskt
        # FIX: Sortera baserat på 'name', inte 'filename'
        remaining_items = sorted(list(unit_map.values()), key=lambda x: x.get('name', '').lower())
        final_google_items.extend(remaining_items)

        # Konvertera från Google API-format till vårt interna format
        story_units = []
        for item in final_google_items:
            filename = item.get('name')
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                unit = {
                    'filename': filename, 'id': item.get('id'), 'type': 'unknown',
                    'thumbnail': item.get('thumbnailLink')
                }
                if ext in SUPPORTED_IMAGE_EXTENSIONS: unit['type'] = 'image'
                elif ext in SUPPORTED_TEXT_EXTENSIONS: unit['type'] = 'text'
                elif ext in SUPPORTED_PDF_EXTENSIONS: unit['type'] = 'pdf'
                story_units.append(unit)
        return {'units': story_units}
            
    except HttpError as e: return {'error': f"Kunde inte hämta filer: {e}"}
