## Fas-plan 1: Grundläggande Applikation & Google-anslutning ##
Syfte: Att etablera en stabil, molnbaserad miljö för applikationen och implementera den centrala, säkra anslutningen till en användares Google Drive. Denna fas handlar om att bygga den fundamentala bron mellan programmet och användarens data, samt att lösa alla initiala plattformsproblem.

Funktionella Krav:

Applikationen ska köras på en pålitlig, gratis molnplattform (Streamlit Community Cloud).

Den ska presentera en tydlig inloggningssida för användaren.

Användaren ska kunna autentisera sig via en standardiserad och säker Google OAuth 2.0-process.

Efter en lyckad inloggning ska appen få en auktoriseringstoken för att kunna läsa användarens filer på Google Drive.

Gränssnittet ska uppdateras för att visa en "inloggad"-status.

Teknisk Design:

Plattform: Streamlit Community Cloud, publicerad via ett GitHub-repository.

Grund-bibliotek: Streamlit.

Autentisering: En specialbyggd OAuth 2.0-process som använder requests-biblioteket för att kommunicera direkt med Googles API-slutpunkter. Konfiguration (nycklar och app-adress) hanteras säkert via st.secrets.

Gränssnitt: En st.link_button för inloggning. Logiken hanterar ?code=-parametern i URL:en när användaren skickas tillbaka från Google. Programmets tillstånd (om man är inloggad eller ej) hanteras med st.session_state.

## Fas-plan 2: Filbläddrare och Visuell Lista ##
Syfte: Att bygga det primära gränssnittet för att interagera med Google Drive. Detta innefattar en grafisk filbläddrare för att enkelt kunna navigera i mappstrukturen, samt att omvandla fillistan från text till en rik, visuell representation med miniatyrbilder.

Funktionella Krav:

Användaren ska först kunna välja en startpunkt: "Min enhet" eller en specifik "Delad enhet".

Användaren ska kunna klicka på mappar för att navigera djupare i mappstrukturen.

Det ska finnas knappar för att navigera uppåt i hierarkin och för att återvända till startpunkts-vyn.

När en mapp är vald, ska en "Läs in"-knapp visa mappens innehåll i huvudfönstret.

Listan över innehållet ska vara visuell, med miniatyrbilder för bilder och ikoner för andra filtyper.

Teknisk Design:

Gränssnitt: Filbläddraren byggs i Streamlits sidopanel (st.sidebar) med dynamiskt skapade st.button-element för varje mapp. Huvudfönstret visar den visuella listan.

Motor: pdf_motor.py utökas med funktioner för att hämta listor på tillgängliga enheter (get_available_drives) och undermappar (list_folders).

Visualisering: st.image används för att visa miniatyrbilder direkt från den thumbnailLink som Google Drive API:et tillhandahåller. st.markdown används för ikoner.

## Fas-plan 3: Sortering & Organisering ##
Syfte: Att ge användaren fullständig kreativ kontroll över berättelsens narrativa flöde genom att implementera en komplett uppsättning verktyg för att arrangera, kuratera och omorganisera objekten i den visuella listan.

Funktionella Krav:

Ett "Organisera-läge" ska kunna aktiveras med en toggle-knapp.

I detta läge ska varje objekt ha en kryssruta för att kunna väljas.

En "Verktyg"-panel ska dyka upp med följande funktioner:

Ta bort: Avlägsna valda objekt från berättelselistan (utan att radera originalfilen).

Klipp ut & Klistra in: Flytta valda objekt till en ny position i listan.

Snabbsortering: Ett två-panels-gränssnitt för att snabbt bygga upp berättelsen från en osorterad hög med filer.

Användarens anpassade sorteringsordning ska sparas automatiskt i en .storyproject.json-fil i källmappen och laddas nästa gång mappen öppnas.

Teknisk Design:

Gränssnitt: En st.toggle styr organize_mode. st.checkbox läggs till i den visuella listan. Verktygspanelen byggs i st.sidebar med knappar som är aktiva/inaktiva beroende på sammanhanget. Snabbsorteringen använder st.columns för att skapa sin två-panelsvy.

Motor: pdf_motor.py utökas med funktioner för att spara (save_story_order) och ladda (load_story_order) JSON-projektfilen, vilket kräver fulla drive-rättigheter.

Interaktivitet: Alla åtgärder manipulerar st.session_state.story_items-listan och anropar st.rerun() för att omedelbart uppdatera gränssnittet.

## Fas-plan 4: Skapandet av Innehåll och Förbättrad Visuell Lista ##
Syfte: Att omvandla applikationen från en passiv organisatör till ett aktivt skapande-verktyg. Användaren ska kunna lägga till nytt textinnehåll och dekonstruera PDF-dokument. Samtidigt ska den visuella listan förbättras för att ge en mer exakt förhandsvisning av allt innehåll, inklusive PDF-sidor och text.

Funktionella Krav:

Visuella Miniatyrer: Den generiska ikonen för PDF-filer (📑) ska ersättas med en riktig miniatyrbild av dokumentets första sida. Alla miniatyrer (bilder och PDF:er) ska ha samma bredd men bibehålla sina ursprungliga proportioner.

Textförhandsvisning: Den generiska ikonen för textfiler (📄) ska ersättas med en direkt visning av textfilens innehåll i listan.

Infoga Text: I Organiserings-läget ska det finnas en funktion för att skapa en ny textfil med namn, stil och innehåll. Filen ska sparas på Google Drive och automatiskt dyka upp i berättelselistan.

Dela upp PDF: Varje PDF-objekt i listan ska (i Organiserings-läget) ha en "Dela upp"-knapp som ersätter den ursprungliga filen med en serie nya, en-sidiga PDF-filer.

Teknisk Design:

Gränssnitt: Huvudlistan i streamlit_app.py modifieras för att anropa pdf_motor.render_pdf_page_as_image för varje PDF och visa resultatet med st.image. Textinnehåll visas med st.info. Nya knappar och formulär för "Infoga text" och "Dela upp PDF" läggs till i Organiserings-läget.

Motor: pdf_motor.py utökas med funktionerna render_pdf_page_as_image (med PyMuPDF), upload_new_text_file, och split_pdf_and_upload (med pypdf).

## Fas-plan 5: PDF-generering ##
Syfte: Att implementera applikationens kärnfunktion: att omvandla den kuraterade och sorterade berättelselistan till ett eller flera färdiga, nedladdningsbara PDF-dokument.

Funktionella Krav:

Inställningar: Användaren ska kunna justera inställningar för bildkvalitet, maximal filstorlek (i MB) och sidmarginaler (i mm), där 0 marginal är standard.

Generering: En "Skapa PDF-album"-knapp ska starta processen. Programmet ska då hämta alla originalfiler från Google Drive i rätt ordning.

Automatisk Uppdelning: Processen måste respektera den inställda maxstorleken och automatiskt dela upp berättelsen i flera numrerade PDF-filer om gränsen överskrids.

Feedback & Nedladdning: Användaren ska se en förloppsindikator under processen. När den är klar ska en eller flera nedladdningsknappar presenteras.

Teknisk Design:

Gränssnitt: En ny sektion, "Inställningar & Publicering", läggs till i sidopanelen i streamlit_app.py. Den innehåller st.slider och st.number_input för inställningar, en st.button för att starta processen, en st.progress för feedback, och slutligen st.download_button för varje genererad fil.

Motor: pdf_motor.py utökas med den stora huvudfunktionen generate_pdfs_from_story, som innehåller den anpassade logiken från ditt ursprungliga skript för att bygga PDF-sidor med fpdf2 och Pillow, inklusive den iterativa storlekskontrollen.

## Fas 6: Stil-editor & Inställningar ##
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

## Fas 7: Städ-guiden & Slutförande ##
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
