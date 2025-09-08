import os
from pathlib import Path
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
import json
from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF
from PIL import Image

# Konfiguration
PROJECT_FILE_NAME = '.storyproject.json'
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
SUPPORTED_TEXT_EXTENSIONS = ('.txt',)
SUPPORTED_PDF_EXTENSIONS = ('.pdf',)
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_TEXT_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS

# --- Google Drive API-funktioner ---

def get_available_drives(service):
    """Hämtar en lista på användarens 'Min enhet' och alla Delade enheter."""
    drives = [{'id': 'root', 'name': 'Min enhet'}]
    try:
        response = service.drives().list().execute()
        drives.extend(response.get('drives', []))
        return drives
    except HttpError as e:
        return {'error': f"Kunde inte hämta lista på enheter: {e}"}

def list_folders(service, folder_id='root'):
    """Hämtar en lista på alla mappar inuti en specifik mapp."""
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, supportsAllDrives=True, includeItemsFromAllDrives=True, spaces='drive', fields='files(id, name)').execute()
        return results.get('files', [])
    except HttpError as e:
        return {'error': f"Kunde inte hämta mappar: {e}"}

def load_story_order(service, folder_id):
    """Letar efter en projektfil och returnerar den sparade ordningen."""
    try:
        query = f"'{folder_id}' in parents and name = '{PROJECT_FILE_NAME}' and trashed = false"
        response = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, fields="files(id)").execute()
        files = response.get('files', [])
        if files:
            request = service.files().get_media(fileId=files[0]['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            project_data = json.loads(fh.getvalue().decode('utf-8'))
            return project_data.get('order', [])
    except HttpError as e:
        print(f"Kunde inte ladda projektfil: {e}")
    return None

def save_story_order(service, folder_id, story_items):
    """Sparar den nuvarande ordningen till projektfilen på Google Drive."""
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

def download_file_content(service, file_id):
    """Hämtar det fullständiga innehållet av en fil som bytes."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    except HttpError as e:
        print(f"Kunde inte ladda ner fil {file_id}: {e}")
        return None

def get_content_units_from_folder(service, folder_id):
    """Hämtar alla relevanta filer från en mapp och deras metadata."""
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        # Hämta alla filers metadata i ett anrop
        results = service.files().list(
            q=query,
            corpora="allDrives",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            pageSize=1000,
            fields="files(id, name, mimeType, thumbnailLink)"
        ).execute()
        items = results.get('files', [])
        
        # Skapa en mappning från filnamn till google-fil-objekt, exkludera projektfilen
        unit_map = {item.get('name'): item for item in items if item.get('name') != PROJECT_FILE_NAME}
        
        # Ladda den sparade sorteringsordningen
        saved_order = load_story_order(service, folder_id)
        final_google_items = []
        
        # Om det finns en sparad ordning, bygg listan baserat på den
        if saved_order:
            # Plocka ut objekten från mappningen i den sparade ordningen
            ordered_map = {filename: unit_map.pop(filename) for filename in saved_order if filename in unit_map}
            final_google_items.extend(list(ordered_map.values()))
        
        # Lägg till resterande (nya) filer i slutet, sorterade alfabetiskt
        remaining_items = sorted(list(unit_map.values()), key=lambda x: x.get('name', '').lower())
        final_google_items.extend(remaining_items)

        # Konvertera från Google API-format till vårt interna app-format
        story_units = []
        for item in final_google_items:
            filename = item.get('name')
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                unit = {
                    'filename': filename,
                    'id': item.get('id'),
                    'type': 'unknown',
                    'thumbnail': item.get('thumbnailLink') # Kan vara None
                }
                if ext in SUPPORTED_IMAGE_EXTENSIONS:
                    unit['type'] = 'image'
                elif ext in SUPPORTED_TEXT_EXTENSIONS:
                    unit['type'] = 'text'
                elif ext in SUPPORTED_PDF_EXTENSIONS:
                    unit['type'] = 'pdf'
                story_units.append(unit)
        return {'units': story_units}
            
    except HttpError as e:
        return {'error': f"Kunde inte hämta filer från Google Drive: {e}"}

def upload_new_text_file(service, folder_id, filename, content):
    """Laddar upp en ny textfil till Google Drive."""
    try:
        content_bytes = content.encode('utf-8')
        fh = io.BytesIO(content_bytes)
        media_body = MediaIoBaseUpload(fh, mimetype='text/plain', resumable=True)
        file_metadata = {'name': filename, 'parents': [folder_id]}
        service.files().create(body=file_metadata, media_body=media_body, supportsAllDrives=True, fields='id').execute()
        return {'success': True}
    except HttpError as e:
        return {'error': f"Kunde inte ladda upp textfil: {e}"}

def split_pdf_and_upload(service, file_id, original_filename, folder_id):
    """Hämtar, delar upp och laddar upp sidorna i en PDF."""
    try:
        content_buffer = download_file_content(service, file_id)
        if not content_buffer:
            raise Exception("Kunde inte ladda ner PDF-filen för uppdelning.")

        reader = PdfReader(content_buffer)
        newly_created_files = []
        base_name = os.path.splitext(original_filename)[0]
        
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            
            page_buffer = io.BytesIO()
            writer.write(page_buffer)
            page_buffer.seek(0)
            
            new_filename = f"{base_name}_sida_{i+1:03}.pdf"
            media_body = MediaIoBaseUpload(page_buffer, mimetype='application/pdf', resumable=True)
            file_metadata = {'name': new_filename, 'parents': [folder_id]}
            file = service.files().create(
                body=file_metadata,
                media_body=media_body,
                supportsAllDrives=True,
                fields='id, name, mimeType, thumbnailLink'
            ).execute()
            
            new_unit = {
                'filename': file.get('name'), 'id': file.get('id'), 'type': 'pdf',
                'thumbnail': file.get('thumbnailLink')
            }
            newly_created_files.append(new_unit)
            
        return {'new_files': newly_created_files}
    except Exception as e:
        return {'error': f"Kunde inte dela upp PDF: {e}"}
        
def render_pdf_page_as_image(service, file_id, page_num=0):
    """Hämtar en PDF och renderar en specifik sida som en bild."""
    try:
        pdf_buffer = download_file_content(service, file_id)
        if not pdf_buffer:
            raise FileNotFoundError("Kunde inte ladda ner PDF-filen.")

        doc = fitz.open(stream=pdf_buffer, filetype="pdf")
        
        page_count = len(doc)
        if page_num < 0 or page_num >= page_count:
            page_num = 0

        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        doc.close()
        return {'image': img, 'page_count': page_count}
        
    except Exception as e:
        return {'error': f"Kunde inte rendera PDF-sida: {e}"}
