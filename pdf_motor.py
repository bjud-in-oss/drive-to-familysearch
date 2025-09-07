import os
from pathlib import Path
from googleapiclient.errors import HttpError
import io

# Konfiguration
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
SUPPORTED_TEXT_EXTENSIONS = ('.txt',)
SUPPORTED_PDF_EXTENSIONS = ('.pdf',)
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_TEXT_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS

def get_folder_id_from_path(service, path_string):
    """Hittar ID för en mapp oavsett om den ligger i 'Min enhet' eller en 'Delad enhet'."""
    parent_id = 'root'
    parts = [part for part in path_string.strip().split('/') if part]
    if not parts:
        return {'error': 'Sökvägen är tom.'}

    # Steg 1: Hitta startpunkten. Är det en Delad enhet eller Min enhet?
    start_folder_name = parts[0]
    
    try:
        # Leta först bland Delade enheter
        drives_result = service.drives().list().execute()
        shared_drives = drives_result.get('drives', [])
        found_shared_drive = False
        for drive in shared_drives:
            if drive.get('name') == start_folder_name:
                parent_id = drive.get('id')
                found_shared_drive = True
                break
        
        parts_to_traverse = parts[1:] if found_shared_drive else parts

        # Steg 2: Gå igenom resten av mappstrukturen
        for part in parts_to_traverse:
            query = f"'{parent_id}' in parents and name = '{part}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            
            results = service.files().list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            if not items:
                return {'error': f"Mappen '{part}' hittades inte."}
            parent_id = items[0]['id']
            
    except HttpError as error:
        return {'error': f"Ett API-fel inträffade: {error}"}

    return {'id': parent_id}

def get_content_units_from_folder(service, folder_path):
    id_result = get_folder_id_from_path(service, folder_path)
    if 'error' in id_result: return id_result
    folder_id = id_result['id']
    all_units = []
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
            fields="files(id, name, mimeType, thumbnailLink)"
        ).execute()
        items = results.get('files', [])
        if not items: return {'units': []}
        for item in items:
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
                all_units.append(unit)
        all_units.sort(key=lambda x: x['filename'].lower())
        return {'units': all_units}
    except HttpError as error: return {'error': f"Kunde inte hämta filer från Google Drive: {error}"}
