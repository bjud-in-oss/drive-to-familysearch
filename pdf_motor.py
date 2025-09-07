import os
from pathlib import Path
from googleapiclient.errors import HttpError
import io

# Konfiguration (oförändrad)
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
SUPPORTED_TEXT_EXTENSIONS = ('.txt',)
SUPPORTED_PDF_EXTENSIONS = ('.pdf',)
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_TEXT_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS

def get_folder_id_from_path(service, path_string):
    """
    NY, UPPGRADERAD FUNKTION:
    Hittar ID för en mapp genom att söka i både 'Min enhet' och alla 'Delade enheter'.
    """
    parent_id = 'root'
    parts = [part for part in path_string.strip().split('/') if part]
    if not parts:
        return {'error': 'Sökvägen är tom.'}

    for i, part in enumerate(parts):
        try:
            query = f"'{parent_id}' in parents and name = '{part}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            
            # Avgörande ändring: Dessa parametrar instruerar API:et att söka överallt.
            results = service.files().list(
                q=query,
                corpora="allDrives",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            if not items:
                # Ge ett mer specifikt felmeddelande
                if i == 0:
                    return {'error': f"Hittade inte startmappen eller den Delade Enheten med namnet: '{part}'. Kontrollera stavningen."}
                else:
                    return {'error': f"Hittade inte undermappen '{part}'."}
            parent_id = items[0]['id']
            
    except HttpError as error:
        return {'error': f"Ett API-fel inträffade: {error}"}

    return {'id': parent_id}

def get_content_units_from_folder(service, folder_path):
    # Denna funktion är nu korrekt eftersom den anropar den nya, smartare get_folder_id_from_path
    id_result = get_folder_id_from_path(service, folder_path)
    if 'error' in id_result: return id_result
    folder_id = id_result['id']

    all_units = []
    try:
        # Samma viktiga parametrar behövs här
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            corpora="allDrives",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
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
