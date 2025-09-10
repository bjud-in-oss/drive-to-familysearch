Fas-plan 4: Skapandet av Innehåll och Förbättrad Visuell Lista
Syfte: Att omvandla applikationen från en passiv organisatör till ett aktivt skapande-verktyg. Användaren ska kunna lägga till nytt textinnehåll och dekonstruera PDF-dokument. Samtidigt ska den visuella listan förbättras för att ge en mer exakt förhandsvisning av allt innehåll, inklusive PDF-sidor och text.

Funktionella Krav:

Visuella Miniatyrer: Den generiska ikonen för PDF-filer (📑) ska ersättas med en riktig miniatyrbild av dokumentets första sida. Alla miniatyrer (bilder och PDF:er) ska ha samma bredd men bibehålla sina ursprungliga proportioner.

Textförhandsvisning: Den generiska ikonen för textfiler (📄) ska ersättas med en direkt visning av textfilens innehåll i listan.

Infoga Text: I Organiserings-läget ska det finnas en funktion för att skapa en ny textfil med namn, stil och innehåll. Filen ska sparas på Google Drive och automatiskt dyka upp i berättelselistan.

Dela upp PDF: Varje PDF-objekt i listan ska (i Organiserings-läget) ha en "Dela upp"-knapp som ersätter den ursprungliga filen med en serie nya, en-sidiga PDF-filer.

Teknisk Design:

Gränssnitt: Huvudlistan i streamlit_app.py modifieras för att anropa pdf_motor.render_pdf_page_as_image för varje PDF och visa resultatet med st.image. Textinnehåll visas med st.info. Nya knappar och formulär för "Infoga text" och "Dela upp PDF" läggs till i Organiserings-läget.

Motor: pdf_motor.py utökas med funktionerna render_pdf_page_as_image (med PyMuPDF), upload_new_text_file, och split_pdf_and_upload (med pypdf).

Fas-plan 5: PDF-generering
Syfte: Att implementera applikationens kärnfunktion: att omvandla den kuraterade och sorterade berättelselistan till ett eller flera färdiga, nedladdningsbara PDF-dokument.

Funktionella Krav:

Inställningar: Användaren ska kunna justera inställningar för bildkvalitet, maximal filstorlek (i MB) och sidmarginaler (i mm), där 0 marginal är standard.

Generering: En "Skapa PDF-album"-knapp ska starta processen. Programmet ska då hämta alla originalfiler från Google Drive i rätt ordning.

Automatisk Uppdelning: Processen måste respektera den inställda maxstorleken och automatiskt dela upp berättelsen i flera numrerade PDF-filer om gränsen överskrids.

Feedback & Nedladdning: Användaren ska se en förloppsindikator under processen. När den är klar ska en eller flera nedladdningsknappar presenteras.

Teknisk Design:

Gränssnitt: En ny sektion, "Inställningar & Publicering", läggs till i sidopanelen i streamlit_app.py. Den innehåller st.slider och st.number_input för inställningar, en st.button för att starta processen, en st.progress för feedback, och slutligen st.download_button för varje genererad fil.

Motor: pdf_motor.py utökas med den stora huvudfunktionen generate_pdfs_from_story, som innehåller den anpassade logiken från ditt ursprungliga skript för att bygga PDF-sidor med fpdf2 och Pillow, inklusive den iterativa storlekskontrollen.

Fas 6: Stil-editor & Inställningar
Syfte: Att ge dig full kreativ kontroll över textens utseende i de slutgiltiga PDF-filerna. Istället för att ha fasta stilar för rubriker och text, ska du kunna definiera dem själv.

Funktionella Krav:

En ny knapp i sidopanelen, t.ex. "Redigera textstilar...".

Knappen öppnar en ny vy eller dialogruta.

I denna vy kan du se och redigera egenskaperna för varje stil (h1, h2, p, etc.).

Du ska kunna ändra typsnitt, storlek, stil (fet/kursiv) och justering (vänster/centrerad/marginaljusterad).

Dina anpassade stilar ska sparas permanent (i en styles.json-fil på din Drive) så att de laddas automatiskt nästa gång du använder appen.

Teknisk Design:

Vi skapar en st.dialog som innehåller st.selectbox för att välja stil att redigera, samt st.selectbox för typsnitt, st.number_input for storlek, etc.

Vi skapar nya funktioner i pdf_motor.py för att läsa och skriva styles.json-filen till och från din Google Drive.

PDF-genereringsmotorn kommer att anpassas för att läsa och använda dessa anpassade stilar.

Fas 7: Städ-guiden & Slutförande
Syfte: Att erbjuda ett enkelt och säkert sätt att städa upp efter ett avslutat projekt, för att undvika digital oreda.

Funktionella Krav:

Efter att en PDF har genererats, ska en ny knapp "Hantera källfiler..." visas.

Denna knapp öppnar en guidad process ("Städ-guiden").

Guiden ska ge dig tre tydliga val för vad du vill göra med din Källmapp och dess innehåll:

Behåll allt: Lämna både Källmappen och den nya Resultatmappen orörda.

Arkivera: Packa ihop hela Källmappen till en enda .zip-fil och radera sedan den ursprungliga mappen.

Radera Källmappen: Ett permanent val för att endast behålla de färdiga PDF-filerna.

Varje val ska ha en tydlig förklaring av konsekvenserna.

Teknisk Design:

Guiden implementeras som en st.dialog.

Vi använder Pythons inbyggda bibliotek (shutil, zipfile) för att hantera arkiveringen.

Google Drive API-anrop kommer att användas för att hantera raderingen av mappen på ett säkert sätt.
