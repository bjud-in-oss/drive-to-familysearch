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

def get_available_drives(service):
    drives = [{'id': 'root', 'name': 'Min enhet'}]
    try:
        response = service.drives().list().execute()
        drives.extend(response.get('drives', []))
        return drives
    except HttpError as e:
        return {'error': f"Kunde inte hämta lista på enheter: {e}"}

def list_folders(service, folder_id='root'):
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(
            q=query, supportsAllDrives=True, includeItemsFromAllDrives=True,
            spaces='drive', fields='files(id, name)'
        ).execute()
        return results.get('files', [])
    except HttpError as e:
        return {'error': f"Kunde inte hämta mappar: {e}"}

def get_content_units_from_folder(service, folder_id):
    all_units = []
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True,
            pageSize=1000, fields="files(id, name, mimeType, thumbnailLink)"
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
