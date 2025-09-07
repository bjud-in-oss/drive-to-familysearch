import os
from pathlib import Path
from googleapiclient.errors import HttpError
import io
import json
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF
from PIL import Image

# Konfiguration
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
SUPPORTED_TEXT_EXTENSIONS = ('.txt',)
SUPPORTED_PDF_EXTENSIONS = ('.pdf',)
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_TEXT_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS
PROJECT_FILE_NAME = '.storyproject.json'
MM_TO_PT = 2.83465


def get_available_drives(service):
    drives = [{'id': 'root', 'name': 'Min enhet'}]
    try:
        response = service.drives().list().execute()
        drives.extend(response.get('drives', []))
        return drives
    except HttpError as e:
        return {'error': f"Kunde inte hämta lista på enheter: {e}"}




# Standardstilar (kan göras redigerbara i en framtida fas)
STYLES = {
    'p': {'font': 'Helvetica', 'style': '', 'size': 11, 'spacing': 6, 'align': 'J'},
    'h1': {'font': 'Helvetica', 'style': 'B', 'size': 18, 'spacing': 8, 'align': 'L'},
    'h2': {'font': 'Helvetica', 'style': 'B', 'size': 14, 'spacing': 7, 'align': 'L'},
}



# --- Klasser och hjälpfunktioner porterade från originalskript ---



class PreciseFPDF(FPDF):

    """En anpassad FPDF-klass för bättre textkontroll."""

    def add_styled_text(self, text, style, content_width_mm):

        self.set_font(style.get('font', 'Helvetica'), style.get('style', ''), style.get('size', 11))

        self.multi_cell(content_width_mm, style.get('spacing', 6), text, align=style.get('align', 'J'))



def parse_style_from_filename(filename):

    """Hämtar stil-taggen från ett filnamn."""

    stem = Path(filename).stem.lower()

    parts = stem.split('.')

    if len(parts) > 1 and Path(filename).suffix.lower() == '.txt':

        return parts[-1]

    return 'p'



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



# Funktioner för att hantera enheter, mappar och projektfil (oförändrade)

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

            file_id = existing_files[0]['id']

            service.files().update(fileId=file_id, media_body=media_body, supportsAllDrives=True).execute()

        else:

            file_metadata = {'name': PROJECT_FILE_NAME, 'parents': [folder_id]}

            service.files().create(body=file_metadata, media_body=media_body, supportsAllDrives=True, fields='id').execute()

        return {'success': True}

    except HttpError as e:

        return {'error': f"Kunde inte spara projektfilen: {e}"}



# Huvudfunktion för att hämta innehåll från en mapp

def get_content_units_from_folder(service, folder_id):

    try:

        # Hämta fil-metadata

        query = f"'{folder_id}' in parents and trashed = false"

        results = service.files().list(q=query, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True, pageSize=1000, fields="files(id, name, mimeType, thumbnailLink)").execute()

        items = results.get('files', [])

        unit_map = {item.get('name'): item for item in items if item.get('name') != PROJECT_FILE_NAME}

        

        saved_order = load_story_order(service, folder_id)

        final_google_items = []

        if saved_order:

            ordered_map = {filename: unit_map.pop(filename) for filename in saved_order if filename in unit_map}

            final_google_items.extend(list(ordered_map.values()))

        remaining_items = sorted(list(unit_map.values()), key=lambda x: x.get('name', '').lower())

        final_google_items.extend(remaining_items)



        story_units = []

        for item in final_google_items:

            filename = item.get('name')

            ext = os.path.splitext(filename)[1].lower()

            if ext in SUPPORTED_EXTENSIONS:

                unit = {'filename': filename, 'id': item.get('id'), 'type': 'unknown', 'thumbnail': item.get('thumbnailLink')}

                if ext in SUPPORTED_IMAGE_EXTENSIONS: unit['type'] = 'image'

                elif ext in SUPPORTED_PDF_EXTENSIONS: unit['type'] = 'pdf'

                elif ext in SUPPORTED_TEXT_EXTENSIONS:

                    unit['type'] = 'text'

                    # NYTT: Ladda ner innehållet i textfilen

                    try:

                        request = service.files().get_media(fileId=item.get('id'))

                        fh = io.BytesIO()

                        downloader = MediaIoBaseDownload(fh, request)

                        done = False

                        while not done: status, done = downloader.next_chunk()

                        unit['content'] = fh.getvalue().decode('utf-8')

                    except Exception as e:

                        unit['content'] = f"Fel vid läsning av fil: {e}"

                

                story_units.append(unit)

        return {'units': story_units}

    except HttpError as e: return {'error': f"Kunde inte hämta filer: {e}"}



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

        # Hämta original-PDF

        request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()

        downloader = MediaIoBaseDownload(fh, request)

        done = False

        while not done:

            status, done = downloader.next_chunk()

        fh.seek(0)

        

        reader = PdfReader(fh)

        newly_created_files = []

        base_name = os.path.splitext(original_filename)[0]

        

        # Loopa, skapa och ladda upp varje sida

        for i, page in enumerate(reader.pages):

            writer = PdfWriter()

            writer.add_page(page)

            

            page_buffer = io.BytesIO()

            writer.write(page_buffer)

            page_buffer.seek(0)

            

            new_filename = f"{base_name}_sida_{i+1:03}.pdf"

            media_body = MediaIoBaseUpload(page_buffer, mimetype='application/pdf', resumable=True)

            file_metadata = {'name': new_filename, 'parents': [folder_id]}

            file = service.files().create(body=file_metadata, media_body=media_body, supportsAllDrives=True, fields='id, name, mimeType, thumbnailLink').execute()

            

            new_unit = {

                'filename': file.get('name'), 'id': file.get('id'), 'type': 'pdf',

                'thumbnail': file.get('thumbnailLink')

            }

            newly_created_files.append(new_unit)

            

        return {'new_files': newly_created_files}

    except Exception as e:

        return {'error': f"Kunde inte dela upp PDF: {e}"}





# --- NY HUVUDFUNKTION FÖR PDF-GENERERING ---



def generate_pdfs_from_story(service, story_items, settings, progress_callback):

    """Huvudfunktionen som bygger PDF-albumen."""

    doc_width_mm = 210

    margin_mm = 10

    content_width_mm = doc_width_mm - (2 * margin_mm)

    max_size_bytes = settings.get('max_size_mb', 15) * 1024 * 1024

    quality = settings.get('quality', 85)



    generated_pdfs = []

    current_pdf_writer = PdfWriter()

    items_in_current_pdf = 0

    total_items = len(story_items)



    for i, item in enumerate(story_items):

        progress_callback(i / total_items, f"Bearbetar {item['filename']}...")

        content_buffer = download_file_content(service, item['id'])

        if not content_buffer: continue



        page_writer = PdfWriter()

        

        try:

            if item['type'] == 'image':

                with Image.open(content_buffer) as img:

                    img_w, img_h = img.size

                    aspect_ratio = img_h / img_w

                    img_height_mm = content_width_mm * aspect_ratio

                    page_height_mm = img_height_mm + (2 * margin_mm)

                    

                    temp_page_pdf = FPDF(orientation='P', unit='mm', format=(doc_width_mm, page_height_mm))

                    temp_page_pdf.add_page()

                    img_byte_arr = io.BytesIO()

                    img.convert('RGB').save(img_byte_arr, format='JPEG', quality=quality)

                    temp_page_pdf.image(img_byte_arr, x=margin_mm, y=margin_mm, w=content_width_mm)

                    

                    with io.BytesIO(temp_page_pdf.output()) as f:

                        page_writer.add_page(PdfReader(f).pages[0])



            elif item['type'] == 'text':

                text_content = content_buffer.read().decode('utf-8')

                style = STYLES.get(parse_style_from_filename(item['filename']), STYLES['p'])

                

                temp_calc_pdf = FPDF('P', 'mm', 'A4'); temp_calc_pdf.add_page()

                temp_calc_pdf.set_font(style.get('font'), style.get('style'), style.get('size'))

                lines = temp_calc_pdf.multi_cell(w=content_width_mm, h=style.get('spacing'), text=text_content, dry_run=True, output='LINES')

                text_height_mm = len(lines) * style.get('spacing')

                page_height_mm = text_height_mm + (2 * margin_mm)



                temp_page_pdf = PreciseFPDF(orientation='P', unit='mm', format=(doc_width_mm, page_height_mm))

                temp_page_pdf.add_page()

                temp_page_pdf.set_xy(margin_mm, margin_mm)

                temp_page_pdf.add_styled_text(text_content, style, content_width_mm)

                

                with io.BytesIO(temp_page_pdf.output()) as f:

                    page_writer.add_page(PdfReader(f).pages[0])

            

            if len(page_writer.pages) > 0:

                test_writer = PdfWriter()

                for page in current_pdf_writer.pages: test_writer.add_page(page)

                test_writer.add_page(page_writer.pages[0])

                

                with io.BytesIO() as temp_buffer:

                    test_writer.write(temp_buffer)

                    current_size = temp_buffer.tell()



                if current_size > max_size_bytes and items_in_current_pdf > 0:

                    final_pdf_buffer = io.BytesIO()

                    current_pdf_writer.write(final_pdf_buffer)

                    final_pdf_buffer.seek(0)

                    generated_pdfs.append(final_pdf_buffer)

                    

                    current_pdf_writer = page_writer

                    items_in_current_pdf = 1

                else:

                    current_pdf_writer.add_page(page_writer.pages[0])

                    items_in_current_pdf += 1

        except Exception as e:

            print(f"Kunde inte bearbeta {item['filename']}: {e}")



    if items_in_current_pdf > 0:

        final_pdf_buffer = io.BytesIO()

        current_pdf_writer.write(final_pdf_buffer)

        final_pdf_buffer.seek(0)

        generated_pdfs.append(final_pdf_buffer)

        

    progress_callback(1.0, f"Klar! {len(generated_pdfs)} PDF-filer skapade.")

    return {'pdfs': generated_pdfs}

