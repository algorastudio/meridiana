"""
Genera il manuale utente PDF di Meridiana 1.3.0.
Richiede: fpdf2 >= 2.8 (pip install fpdf2)
          Font DejaVu disponibili in /usr/share/fonts/truetype/dejavu/
"""

# ── patch cryptography broken in questo ambiente ─────────────────────────────
import sys, types
_FAKE = [
    "cryptography", "cryptography.exceptions",
    "cryptography.hazmat", "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.serialization.pkcs12",
    "cryptography.hazmat.bindings",
    "cryptography.hazmat.bindings._rust",
]
for _n in _FAKE:
    sys.modules.setdefault(_n, types.ModuleType(_n))
# ─────────────────────────────────────────────────────────────────────────────

from fpdf import FPDF
import os

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "resources", "manuale_utente.pdf")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REG  = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")

# palette colori
BLUE   = (1,  82, 155)
LBLUE  = (227, 242, 253)
DGRAY  = (44,  44,  44)
MGRAY  = (90,  90,  90)
LGRAY  = (242, 242, 242)
WHITE  = (255, 255, 255)
YELLOW = (255, 243, 205)
GREEN  = (232, 245, 233)


class PDF(FPDF):
    # ── font helpers ──────────────────────────────────────────────────────────
    def _R(self, size=10):
        self.set_font("DV", "", size); self.set_text_color(*DGRAY)
    def _B(self, size=10):
        self.set_font("DV", "B", size); self.set_text_color(*DGRAY)
    def _BW(self, size=10):
        self.set_font("DV", "B", size); self.set_text_color(*WHITE)
    def _mono(self, size=9):
        self.set_font("MONO", "", size); self.set_text_color(*DGRAY)

    # ── page chrome ───────────────────────────────────────────────────────────
    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 12, "F")
        self._BW(8)
        self.set_xy(10, 2)
        self.cell(95, 8, "MERIDIANA 1.3.0  -  Manuale Utente")
        self.set_xy(10, 2)
        self.cell(190, 8, "Archivio di Stato di Savona", align="R")
        self.ln(14)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_fill_color(*BLUE)
        self.rect(0, self.get_y(), 210, 13, "F")
        self._BW(8)
        self.set_x(0)
        self.cell(210, 6, f"Pagina {self.page_no() - 1}", align="C")

    # ── copertina ─────────────────────────────────────────────────────────────
    def copertina(self):
        self.add_page()
        # banda top blu
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 72, "F")
        self._BW(38)
        self.set_xy(0, 14)
        self.cell(210, 18, "MERIDIANA", align="C")
        self._BW(14)
        self.set_xy(0, 36)
        self.cell(210, 10, "Sistema di Gestione dell'Archivio Catastale Storico", align="C")
        self._BW(10)
        self.set_xy(0, 52)
        self.cell(210, 8, "Manuale Utente  -  Versione 1.3.0", align="C")
        # blocco centrale
        self.set_fill_color(*LBLUE)
        self.rect(20, 82, 170, 52, "F")
        self.set_text_color(*BLUE)
        self._B(13); self.set_xy(20, 90)
        self.cell(170, 8, "Archivio di Stato di Savona", align="C")
        self._R(10); self.set_xy(20, 100)
        self.cell(170, 6, "Piazza Torriglia 1 - 17100 Savona (SV)", align="C")
        self.set_xy(20, 108)
        self.cell(170, 6, "Software sviluppato da Marco Santoro", align="C")
        self.set_xy(20, 116)
        self.cell(170, 6, "Concesso in comodato d'uso gratuito - Maggio 2026", align="C")
        # credits
        self.set_text_color(*MGRAY)
        self._R(8); self.set_xy(0, 268)
        self.cell(210, 6, "Copyright (C) Marco Santoro. Tutti i diritti riservati.", align="C")
        self.set_xy(0, 275)
        self.cell(210, 6, "Stack: Python 3.13 + PyQt5 + PostgreSQL 14+", align="C")

    # ── indice ────────────────────────────────────────────────────────────────
    def _toc_row(self, num, title, page, indent=0):
        self._R(10)
        w_avail = 170 - indent * 7
        dots_w = w_avail - self.get_string_width(f"{num}  {title}  {page}")
        dot_char = "."
        n_dots = max(3, int(dots_w / self.get_string_width(dot_char)))
        self.set_x(15 + indent * 7)
        self.cell(0, 6, f"{num}  {title}  {'.' * n_dots}  {page}", ln=1)

    def pagina_indice(self, voci):
        self.add_page()
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 16, "F")
        self._BW(14)
        self.set_xy(0, 3)
        self.cell(210, 10, "Indice dei Contenuti", align="C")
        self.ln(20)
        for v in voci:
            self._toc_row(v[0], v[1], v[2], v[3] if len(v) > 3 else 0)

    # ── struttura titoli ─────────────────────────────────────────────────────
    def cap(self, num, title):
        self._BW(13)
        self.set_fill_color(*BLUE)
        self.cell(0, 10, f"  {num}  {title}", fill=True, ln=1)
        self.ln(3)

    def sec(self, title):
        self.set_fill_color(*LBLUE)
        self.set_text_color(*BLUE)
        self._B(11)
        self.cell(0, 8, f"  {title}", fill=True, ln=1)
        self.ln(2)

    # ── testo ─────────────────────────────────────────────────────────────────
    def body(self, text, indent=0):
        self._R(10)
        self.set_x(15 + indent * 4)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text, sym="-", indent=1):
        self._R(10)
        x = 15 + indent * 5
        self.set_x(x)
        self.cell(5, 5.5, sym)
        self.multi_cell(0, 5.5, text)

    def nota(self, text):
        self.set_fill_color(*YELLOW)
        self.set_draw_color(255, 193, 7)
        self.set_text_color(102, 77, 0)
        self._R(9)
        self.set_x(15)
        self.multi_cell(0, 5, f"  [!]  {text}", border="L", fill=True)
        self.set_draw_color(0)
        self.ln(1)

    def tip(self, text):
        self.set_fill_color(*GREEN)
        self.set_draw_color(76, 175, 80)
        self.set_text_color(27, 94, 32)
        self._R(9)
        self.set_x(15)
        self.multi_cell(0, 5, f"  [OK] {text}", border="L", fill=True)
        self.set_draw_color(0)
        self.ln(1)

    # ── tabelle ───────────────────────────────────────────────────────────────
    def thead(self, cols, widths):
        self.set_fill_color(*BLUE)
        self._BW(9)
        for c, w in zip(cols, widths):
            self.cell(w, 7, c, border=1, fill=True, align="C")
        self.ln()

    def trow(self, vals, widths, alt=False):
        self.set_fill_color(*LGRAY if alt else WHITE)
        self._R(9)
        self.set_text_color(*DGRAY)
        for v, w in zip(vals, widths):
            self.cell(w, 6, str(v), border=1, fill=True)
        self.ln()

    def subsec(self, title):
        self._B(10); self.set_text_color(*BLUE)
        self.cell(0, 6, f"  {title}", ln=1)
        self.set_text_color(*DGRAY)


# ════════════════════════════════════════════════════════════════════════════ #
def build():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 18, 15)

    pdf.add_font("DV",   "",  FONT_REG)
    pdf.add_font("DV",   "B", FONT_BOLD)
    pdf.add_font("MONO", "",  FONT_MONO)

    # ── COPERTINA ─────────────────────────────────────────────────────────────
    pdf.copertina()

    # ── INDICE ────────────────────────────────────────────────────────────────
    toc = [
        ("1",    "Introduzione a Meridiana",                                    3),
        ("2",    "Installazione e Requisiti di Sistema",                        4),
        ("3",    "Primo Avvio e Configurazione Database",                       5),
        ("4",    "Accesso al Sistema e Gestione Utenti",                        6),
        ("5",    "Dashboard - Pannello Principale (Home)",                      7),
        ("6",    "Consultazione",                                               8),
        ("6.1",  "Elenco Comuni (tab Principale)",                              8, 1),
        ("6.2",  "Ricerca Partite",                                             9, 1),
        ("6.3",  "Ricerca Avanzata Immobili",                                  10, 1),
        ("7",    "Ricerca Globale (Fuzzy Search)",                             11),
        ("8",    "Inserimento Dati",                                           12),
        ("8.1",  "Inserimento Comune",                                         12, 1),
        ("8.2",  "Inserimento Possessore",                                     13, 1),
        ("8.3",  "Inserimento Partita Catastale",                              14, 1),
        ("8.4",  "Inserimento Localita'",                                      15, 1),
        ("8.5",  "Registrazione Proprieta' (Wizard)",                          15, 1),
        ("8.6",  "Operazioni su Partita",                                      17, 1),
        ("8.7",  "Registrazione Consultazione Archivistica",                   18, 1),
        ("8.8",  "Gestione Tipi Localita', Titoli di Possesso, Periodi (Admin)",19, 1),
        ("9",    "Esportazioni",                                               20),
        ("10",   "Reportistica",                                               22),
        ("11",   "Statistiche e Manutenzione Database",                        24),
        ("12",   "Gestione Utenti (solo Admin)",                               25),
        ("13",   "Sistema: Log Audit e Backup (solo Admin)",                   26),
        ("14",   "Menu Barra dei Menu",                                        28),
        ("15",   "Archiviazione Logica (Soft Delete)",                         29),
        ("16",   "Importazione Massiva da CSV",                                30),
        ("17",   "Temi Grafici",                                               31),
        ("18",   "Risoluzione Problemi Comuni",                                32),
    ]
    pdf.pagina_indice(toc)

    # ═════════════════════════ CAP 1 - INTRODUZIONE ═══════════════════════════
    pdf.add_page()
    pdf.cap("1", "Introduzione a Meridiana")
    pdf.body(
        "Meridiana e' un'applicazione desktop professionale per la gestione e la consultazione degli "
        "archivi catastali storici italiani. Il software e' stato sviluppato da Marco Santoro e "
        "concesso in comodato d'uso gratuito all'Archivio di Stato di Savona."
    )
    pdf.body(
        "Il sistema permette di gestire in modo organico tutte le entita' dell'archivio catastale: "
        "comuni, possessori, partite catastali, immobili (fabbricati e terreni), localita', "
        "variazioni di proprieta' e consultazioni archivistiche."
    )
    pdf.sec("Principi Fondamentali dell'Archivio Storico")
    pdf.bullet("I dati storici non vengono mai cancellati fisicamente: le entita' vengono archiviate "
               "logicamente (soft delete) e rimangono consultabili.")
    pdf.bullet("Ogni modifica e' tracciata nel log di audit per garantire la piena accountability.")
    pdf.bullet("Il sistema supporta piu' utenti con profili distinti (operatore / amministratore).")
    pdf.bullet("Tutti i dati sono conservati in un database PostgreSQL centralizzato accessibile in rete.")
    pdf.ln(3)
    pdf.sec("Stack Tecnologico")
    pdf.thead(["Componente", "Tecnologia / Versione"], [80, 100])
    rows = [
        ("Interfaccia Grafica", "Python 3.13 + PyQt5 5.15+"),
        ("Database", "PostgreSQL 14+"),
        ("Driver DB", "psycopg2 (connection pool)"),
        ("Esportazione PDF", "fpdf2 2.8+"),
        ("Esportazione Excel", "openpyxl 3.1+"),
        ("Esportazione CSV", "Modulo standard csv (Python)"),
        ("Build Windows", "PyInstaller + Inno Setup"),
    ]
    for i, r in enumerate(rows):
        pdf.trow(r, [80, 100], alt=bool(i % 2))
    pdf.ln(4)
    pdf.sec("Cronologia Versioni")
    pdf.thead(["Versione", "Data", "Note Principali"], [25, 30, 125])
    for i, r in enumerate([
        ("1.0",   "2025-01", "Prima versione funzionante"),
        ("1.2.0", "2025-05", "CI/CD, build Windows, 16 temi, backup, fuzzy search, gestione utenti"),
        ("1.3.0", "2026-04", "Soft delete, validazione date, suite test 100+, rimozione campo civico"),
        ("1.3.0", "2026-04", "Data layer Dataclass, Titoli possesso, fix display partite, fix QSS"),
    ]):
        pdf.trow(r, [25, 30, 125], alt=bool(i % 2))

    # ═════════════════════════ CAP 2 - INSTALLAZIONE ══════════════════════════
    pdf.add_page()
    pdf.cap("2", "Installazione e Requisiti di Sistema")
    pdf.sec("Requisiti Hardware e Software")
    pdf.thead(["Requisito", "Minimo", "Consigliato"], [60, 60, 60])
    for i, r in enumerate([
        ("Sistema Operativo", "Windows 10 64-bit", "Windows 11 64-bit"),
        ("RAM", "4 GB", "8 GB"),
        ("Disco", "500 MB liberi", "2 GB liberi"),
        ("Risoluzione Schermo", "1280 x 720", "1920 x 1080"),
        ("Rete", "LAN 100 Mbps", "LAN Gigabit"),
        ("PostgreSQL", "14.x", "16.x"),
    ]):
        pdf.trow(r, [60, 60, 60], alt=bool(i % 2))
    pdf.ln(4)
    pdf.sec("Installazione su Windows (Installer .exe)")
    for t in [
        "Scaricare il file Meridiana_Setup_1.3.0.exe dal fornitore.",
        "Eseguire il file con doppio clic. Se richiesto, concedere i permessi di amministratore.",
        "Seguire le istruzioni guidate dell'installer (Inno Setup). La cartella predefinita e' C:\\Program Files\\Meridiana.",
        "Al termine, il collegamento 'Meridiana' verra' creato sul Desktop.",
    ]:
        pdf.bullet(t)
    pdf.tip("Il server PostgreSQL deve essere gia' installato e in esecuzione prima di avviare Meridiana "
            "per la prima volta.")
    pdf.ln(3)
    pdf.sec("Bootstrap del Database (primo avvio su DB nuovo)")
    pdf.body("Se il database non esiste ancora, e' necessario eseguire il bootstrap una sola volta:")
    for t in [
        "Installare PostgreSQL 14+ sul server designato.",
        "Dal menu Impostazioni -> Configurazione Database, inserire i parametri di connessione.",
        "Alla prima connessione riuscita, Meridiana proporra' di eseguire il bootstrap automatico.",
        "Confermare: il sistema creera' schema, tabelle, stored procedure e dati iniziali.",
    ]:
        pdf.bullet(t)
    pdf.nota("Per ambienti gia' esistenti con versione precedente a 1.3.0, eseguire manualmente "
             "gli script SQL mancanti in ordine numerico dalla cartella sql_scripts/.")
    pdf.ln(3)
    pdf.sec("Variabili d'Ambiente per la Connessione")
    pdf.thead(["Variabile", "Descrizione", "Default"], [50, 90, 40])
    for i, r in enumerate([
        ("DB_HOST", "Indirizzo del server PostgreSQL", "localhost"),
        ("DB_NAME", "Nome del database", "catasto_storico"),
        ("DB_USER", "Nome utente PostgreSQL", "postgres"),
        ("DB_PASS", "Password PostgreSQL", "(vuota)"),
        ("DB_PORT", "Porta TCP PostgreSQL", "5432"),
    ]):
        pdf.trow(r, [50, 90, 40], alt=bool(i % 2))

    # ═════════════════════════ CAP 3 - PRIMO AVVIO ════════════════════════════
    pdf.add_page()
    pdf.cap("3", "Primo Avvio e Configurazione Database")
    pdf.sec("Schermata di Benvenuto")
    pdf.body(
        "All'avvio, Meridiana mostra la schermata di benvenuto con il logo e i crediti. "
        "Fare clic su 'Avvia' o premere Invio per procedere alla finestra di configurazione database."
    )
    pdf.sec("Finestra di Configurazione Database")
    pdf.body(
        "La finestra di configurazione (accessibile anche da Menu Impostazioni -> Configurazione Database) "
        "permette di impostare i parametri di connessione a PostgreSQL:"
    )
    pdf.thead(["Campo", "Descrizione"], [50, 130])
    for i, r in enumerate([
        ("Host",       "Indirizzo IP o nome host del server PostgreSQL"),
        ("Porta",      "Porta TCP (default: 5432)"),
        ("Database",   "Nome del database (default: catasto_storico)"),
        ("Utente DB",  "Username PostgreSQL"),
        ("Password DB","Password PostgreSQL"),
    ]):
        pdf.trow(r, [50, 130], alt=bool(i % 2))
    pdf.ln(3)
    pdf.tip("Usare il pulsante 'Verifica Connessione' per testare i parametri prima di confermare.")
    pdf.nota("Le credenziali DB vengono salvate in modo sicuro nelle impostazioni di sistema (QSettings). "
             "Non vengono mai scritte in chiaro in file di configurazione.")
    pdf.ln(3)
    pdf.sec("Watchdog di Connessione")
    pdf.body(
        "Meridiana verifica periodicamente lo stato della connessione al database. "
        "La barra di stato in basso mostra in tempo reale: 'Database: Connesso (nome_db)' oppure "
        "'Database: DISCONNESSO!'. In caso di disconnessione, l'applicazione tenta il ripristino automatico."
    )

    # ═════════════════════════ CAP 4 - ACCESSO ════════════════════════════════
    pdf.add_page()
    pdf.cap("4", "Accesso al Sistema e Gestione Utenti")
    pdf.sec("Login")
    pdf.body(
        "Al primo avvio dopo la configurazione, viene presentata la finestra di login. "
        "Inserire username e password dell'account Meridiana (distinti dalle credenziali PostgreSQL). "
        "L'utente amministratore predefinito viene creato durante il bootstrap del database."
    )
    pdf.sec("Ruoli Utente")
    pdf.thead(["Ruolo", "Descrizione", "Accesso"], [30, 95, 55])
    for i, r in enumerate([
        ("operatore", "Utente standard per consultazione e inserimento dati",
         "Tutti i tab tranne Utenti e Sistema"),
        ("admin", "Amministratore con accesso completo",
         "Accesso completo + Utenti + Sistema"),
    ]):
        pdf.trow(r, [30, 95, 55], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Barra di Stato")
    pdf.body("La barra di stato in fondo alla finestra principale mostra sempre:")
    pdf.bullet("Stato connessione al database (verde = connesso, rosso = disconnesso)")
    pdf.bullet("Utente attualmente loggato e suo ruolo")
    pdf.bullet("Pulsante 'Logout' per cambiare utente senza chiudere l'applicazione")
    pdf.ln(3)
    pdf.sec("Sicurezza delle Password")
    pdf.body(
        "Tutte le password degli utenti Meridiana sono conservate nel database come hash bcrypt. "
        "Non e' possibile recuperare una password dimenticata: un amministratore dovra' reimpostarla "
        "dal tab Gestione Utenti."
    )

    # ═════════════════════════ CAP 5 - DASHBOARD ══════════════════════════════
    pdf.add_page()
    pdf.cap("5", "Dashboard - Pannello Principale (Home)")
    pdf.body(
        "Il tab [Home] e' il pannello principale di Meridiana, visualizzato automaticamente all'accesso. "
        "Fornisce una vista riassuntiva dello stato dell'archivio e accesso rapido alle funzioni piu' usate."
    )
    pdf.sec("Statistiche Principali")
    pdf.body("Nella parte superiore della dashboard sono presenti quattro 'card' con i totali aggiornati:")
    pdf.thead(["Card", "Contenuto"], [50, 130])
    for i, r in enumerate([
        ("Comuni",      "Numero totale di comuni registrati nell'archivio"),
        ("Partite",     "Numero totale di partite catastali (attive + archiviate)"),
        ("Possessori",  "Numero totale di possessori registrati"),
        ("Immobili",    "Numero totale di immobili (fabbricati + terreni)"),
    ]):
        pdf.trow(r, [50, 130], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Ricerca Rapida")
    pdf.body(
        "Il campo 'Ricerca Rapida' nella parte superiore permette di avviare direttamente una "
        "ricerca globale fuzzy su tutto il database (possessori, partite, comuni, immobili) "
        "digitando un testo e premendo Invio o il pulsante 'Cerca'. "
        "Il sistema reindirizza automaticamente al tab [Ricerca]."
    )
    pdf.sec("Attivita' Utenti Recenti")
    pdf.body(
        "La sezione mostra le ultime operazioni registrate nel log di audit, "
        "consentendo di monitorare chi ha fatto cosa e quando nell'archivio."
    )
    pdf.sec("Azioni Rapide")
    pdf.body("I pulsanti di azione rapida permettono di navigare con un clic alle sezioni piu' frequenti:")
    pdf.bullet("Nuova Partita    -> apre direttamente il tab Inserimento > Partita")
    pdf.bullet("Nuovo Possessore -> apre direttamente il tab Inserimento > Possessore")
    pdf.bullet("Cerca Partite   -> apre direttamente il tab Consultazione > Ricerca Partite")
    pdf.bullet("Esporta Dati    -> apre direttamente il tab [Esportazioni]")

    # ═════════════════════════ CAP 6 - CONSULTAZIONE ══════════════════════════
    pdf.add_page()
    pdf.cap("6", "Consultazione")
    pdf.body(
        "Il tab 'Consultazione' raccoglie le funzioni di visualizzazione e modifica dei dati esistenti. "
        "E' composto da tre sotto-tab: Principale, Ricerca Partite e Ricerca Immobili."
    )
    pdf.sec("6.1  Elenco Comuni (tab Principale)")
    pdf.body("Il sotto-tab 'Principale' mostra la tabella di tutti i comuni attivi con le colonne:")
    pdf.thead(["Colonna", "Descrizione"], [55, 125])
    for i, r in enumerate([
        ("ID",                "Identificativo interno del comune"),
        ("Nome Comune",       "Denominazione ufficiale"),
        ("Note",              "Annotazioni amministrative"),
        ("Data Istituzione",  "Data di istituzione del comune"),
        ("Data Soppressione", "Data di eventuale soppressione (se applicabile)"),
    ]):
        pdf.trow(r, [55, 125], alt=bool(i % 2))
    pdf.ln(3)
    pdf.body(
        "Selezionando una riga nella tabella comuni, nella parte destra della schermata "
        "vengono visualizzati i dettagli con le schede:"
    )
    pdf.bullet("Possessori: elenco di tutti i possessori del comune")
    pdf.bullet("Partite: elenco delle partite catastali del comune")
    pdf.bullet("Immobili: elenco degli immobili del comune")
    pdf.bullet("Localita': elenco delle localita' (vie, piazze, borgate, ecc.)")
    pdf.ln(2)
    pdf.body("Da questa schermata e' possibile:")
    pdf.bullet("Doppio clic su un possessore -> apre il dialogo dettagli/modifica del possessore")
    pdf.bullet("Doppio clic su una partita -> apre i dettagli completi con possessori, immobili, variazioni")
    pdf.bullet("Pulsante 'Modifica Comune' -> apre il modulo di modifica del comune selezionato")
    pdf.bullet("Aprire l'elenco completo di possessori o partite del comune con i pulsanti dedicati")
    pdf.tip("Le colonne Nome Comune e Note si adattano automaticamente allo spazio disponibile.")

    pdf.sec("6.2  Ricerca Partite")
    pdf.add_page()
    pdf.body(
        "Il sotto-tab 'Ricerca Partite' permette di cercare partite catastali con filtri multipli "
        "e navigazione paginata dei risultati."
    )
    pdf.body("Filtri disponibili:")
    pdf.thead(["Filtro", "Tipo", "Descrizione"], [50, 30, 100])
    for i, r in enumerate([
        ("Comune",          "Selezione", "Apre il dialogo di selezione comune"),
        ("Numero Partita",  "Numero",    "Cerca per numero catastale esatto o parziale"),
        ("Nome Possessore", "Testo",     "Ricerca per cognome/nome del possessore associato"),
        ("Natura Immobile", "Testo",     "Filtra per tipologia immobile (fabbricato, terreno, ecc.)"),
    ]):
        pdf.trow(r, [50, 30, 100], alt=bool(i % 2))
    pdf.ln(3)
    pdf.body(
        "I risultati vengono visualizzati in una tabella paginata con: ID, Comune, N. Partita, Tipo, Stato. "
        "La barra di navigazione mostra la pagina corrente e il totale dei record trovati."
    )
    pdf.body("Azioni disponibili sui risultati:")
    pdf.bullet("Pulsante 'Mostra Dettagli Partita': apre il dialogo dettagli della partita selezionata")
    pdf.bullet("Doppio clic sulla riga: equivale a 'Mostra Dettagli'")
    pdf.bullet("Pulsante [< Precedente] / [Successiva >]: navigazione tra le pagine")
    pdf.ln(2)
    pdf.body("Il dialogo Dettagli Partita mostra:")
    pdf.bullet("Dati anagrafici della partita (numero, tipo, stato, date di impianto e chiusura)")
    pdf.bullet("Tab Possessori: elenco dei possessori con titolo di possesso e quota percentuale")
    pdf.bullet("Tab Immobili: elenco degli immobili con natura, classificazione e localita'")
    pdf.bullet("Tab Variazioni: storico delle variazioni (volture) con partite di origine e destinazione")
    pdf.bullet("Tab Report: report testuale completo esportabile in PDF o TXT")
    pdf.tip("Dal dialogo dei dettagli e' possibile aprire direttamente il modulo di modifica della partita.")

    pdf.sec("6.3  Ricerca Avanzata Immobili")
    pdf.body(
        "Il sotto-tab 'Ricerca Immobili' offre una ricerca multi-criterio sugli immobili dell'archivio."
    )
    pdf.thead(["Filtro", "Tipo", "Descrizione"], [50, 30, 100])
    for i, r in enumerate([
        ("Comune",           "Selezione", "Filtra immobili di un comune specifico"),
        ("Localita'",        "Selezione", "Filtra per via/piazza/borgata specifica"),
        ("Tipo Immobile",    "Combo",     "Fabbricato / Terreno"),
        ("Natura",           "Testo",     "Casa, cascina, prato, ecc."),
        ("Classificazione",  "Testo",     "Categoria catastale storica"),
        ("Numero Mappa",     "Numero",    "Numero di mappa catastale"),
        ("Solo Attivi",      "Checkbox",  "Esclude immobili collegati a partite chiuse"),
    ]):
        pdf.trow(r, [50, 30, 100], alt=bool(i % 2))
    pdf.ln(3)
    pdf.body(
        "I risultati mostrano: ID, Tipo, Natura, Classificazione, Numero Mappa, Confini, "
        "Partita collegata, Comune, Localita'. Doppio clic apre il dialogo di modifica dell'immobile."
    )

    # ═════════════════════════ CAP 7 - RICERCA GLOBALE ════════════════════════
    pdf.add_page()
    pdf.cap("7", "Ricerca Globale (Fuzzy Search)")
    pdf.body(
        "Il tab [Ricerca] implementa una ricerca full-text fuzzy su tutte le entita' principali "
        "dell'archivio in parallelo. La ricerca sfrutta gli indici GIN di PostgreSQL per restituire "
        "risultati rilevanti anche in presenza di errori di battitura o nomi parziali."
    )
    pdf.sec("Come Funziona la Ricerca Globale")
    pdf.body(
        "Digitare il testo da cercare nel campo principale e premere Invio o il pulsante 'Cerca'. "
        "La ricerca viene eseguita in un thread separato per non bloccare l'interfaccia. "
        "I risultati sono organizzati in schede per categoria:"
    )
    pdf.thead(["Scheda", "Entita' Ricercate"], [45, 135])
    for i, r in enumerate([
        ("Possessori", "Cognome, nome, paternita', nome completo"),
        ("Partite",    "Numero partita, comune, note"),
        ("Comuni",     "Nome comune, note"),
        ("Immobili",   "Natura, classificazione, numero mappa"),
        ("Localita'",  "Nome via/piazza/borgata"),
    ]):
        pdf.trow(r, [45, 135], alt=bool(i % 2))
    pdf.ln(3)
    pdf.tip("La ricerca globale e' la modalita' piu' rapida per trovare un possessore o una partita "
            "senza conoscere esattamente il comune di riferimento.")
    pdf.body(
        "Fare doppio clic su qualsiasi risultato per aprire il dialogo dettagli dell'entita' trovata. "
        "Dal dialogo e' possibile procedere alla modifica o alla stampa del report."
    )

    # ═════════════════════════ CAP 8 - INSERIMENTO ════════════════════════════
    pdf.add_page()
    pdf.cap("8", "Inserimento Dati")
    pdf.body(
        "Il tab 'Inserimento' raccoglie tutti i moduli per l'aggiunta di nuovi dati all'archivio. "
        "E' composto da sette sotto-tab principali e tre aggiuntivi riservati agli amministratori."
    )

    pdf.sec("8.1  Inserimento Comune")
    pdf.thead(["Campo", "Obbl.", "Descrizione"], [55, 20, 105])
    for i, r in enumerate([
        ("Nome Comune",       "Si'", "Denominazione ufficiale del comune"),
        ("Provincia / Note",  "No",  "Annotazioni amministrative, sigle, riferimenti"),
        ("Data Istituzione",  "Si'", "Data di istituzione del comune (gg/mm/aaaa)"),
        ("Data Soppressione", "No",  "Compilare solo se il comune e' stato soppresso"),
    ]):
        pdf.trow(r, [55, 20, 105], alt=bool(i % 2))
    pdf.ln(2)
    pdf.nota("La data di soppressione, se inserita, deve essere successiva alla data di istituzione. "
             "Il sistema verifica automaticamente la coerenza delle date.")

    pdf.sec("8.2  Inserimento Possessore")
    pdf.add_page()
    pdf.thead(["Campo", "Obbl.", "Descrizione"], [55, 20, 105])
    for i, r in enumerate([
        ("Comune di Riferimento", "Si'", "Comune a cui e' associato il possessore"),
        ("Cognome e Nome",        "Si'", "Cognome e nome del possessore"),
        ("Paternita'",            "No",  "'fu Padre' o 'di Madre' secondo uso catastale storico"),
        ("Nome Completo",         "No",  "Campo calcolato; usare 'Genera Nome Completo' per compilarlo"),
        ("Attivo",                "Si'", "Spuntare se il possessore e' ancora attivo"),
    ]):
        pdf.trow(r, [55, 20, 105], alt=bool(i % 2))
    pdf.ln(2)
    pdf.tip("Il pulsante 'Genera Nome Completo' compone automaticamente il campo concatenando "
            "Cognome, Nome e Paternita' nel formato catastale standard.")
    pdf.body(
        "La sezione 'Azioni Aggiuntive' permette di importare in massa una lista di possessori "
        "da un file CSV. Fare clic su 'Info Formato CSV' per la struttura richiesta."
    )

    pdf.sec("8.3  Inserimento Partita Catastale")
    pdf.thead(["Campo", "Obbl.", "Descrizione"], [55, 20, 105])
    for i, r in enumerate([
        ("Comune",        "Si'", "Comune catastale (selezione da elenco)"),
        ("Numero Partita","Si'", "Numero progressivo catastale"),
        ("Suffisso",      "No",  "Lettera aggiuntiva (es. A, B) per partite derivate"),
        ("Tipo",          "Si'", "Principale / Derivata / Aggregata"),
        ("Stato",         "Si'", "Attiva / Chiusa"),
        ("Data Impianto", "Si'", "Data di apertura della partita"),
        ("Data Chiusura", "No",  "Compilare se la partita e' chiusa; deve essere >= data impianto"),
    ]):
        pdf.trow(r, [55, 20, 105], alt=bool(i % 2))
    pdf.ln(2)
    pdf.body("Il modulo include anche una sezione di importazione massiva da CSV.")

    pdf.sec("8.4  Inserimento Localita'")
    pdf.add_page()
    pdf.thead(["Campo", "Obbl.", "Descrizione"], [55, 20, 105])
    for i, r in enumerate([
        ("Comune",        "Si'", "Comune a cui appartiene la localita'"),
        ("Nome Localita'","Si'", "Denominazione completa (es. 'Via Roma 12', 'Borgata Piana')"),
        ("Tipo Localita'","Si'", "Categoria: Via, Piazza, Borgata, Contrada, ecc."),
    ]):
        pdf.trow(r, [55, 20, 105], alt=bool(i % 2))
    pdf.ln(2)
    pdf.nota("Il numero civico non e' piu' un campo separato: va inserito nel nome della via/piazza "
             "(es. 'Via Roma 11A').")

    pdf.sec("8.5  Registrazione Proprieta' (Wizard)")
    pdf.body(
        "Il sotto-tab 'Reg. Proprieta'' e' il modulo piu' completo di Meridiana: permette di registrare "
        "in un'unica operazione atomica una nuova proprieta' con partita, possessori e immobili."
    )
    pdf.body("Il wizard e' composto da quattro passaggi (pagine):")
    pdf.bullet("Pagina 1 - Dati Partita: comune, numero, tipo, data impianto")
    pdf.bullet("Pagina 2 - Possessori: aggiunta di possessori esistenti o creazione di nuovi; "
               "per ogni possessore si specifica il titolo di possesso (proprieta', usufrutto, "
               "comproprietà, enfiteusi, ecc.) e la quota percentuale")
    pdf.bullet("Pagina 3 - Immobili: aggiunta di immobili esistenti oppure creazione di nuovi "
               "inline (natura, classificazione, numero mappa, confini, localita')")
    pdf.bullet("Pagina 4 - Riepilogo: verifica di tutti i dati prima della conferma finale")
    pdf.tip("La registrazione e' atomica: se qualsiasi passaggio fallisce, nessuna modifica viene "
            "salvata nel database (rollback automatico).")

    pdf.sec("8.6  Operazioni su Partita")
    pdf.add_page()
    pdf.body(
        "Il sotto-tab 'Operazioni' mette a disposizione tre operazioni specializzate sulle partite "
        "esistenti. Prima di tutto e' necessario selezionare la 'Partita Sorgente' tramite il pulsante "
        "'Cerca' o inserendo direttamente l'ID."
    )
    pdf.subsec("Duplica Partita")
    pdf.body(
        "Crea una copia della partita sorgente in un'altra partita (o nella stessa). "
        "Opzioni configurabili: copiare i possessori, copiare gli immobili, specificare "
        "la partita di destinazione, scegliere se creare variazioni automatiche."
    )
    pdf.subsec("Trasferisci Immobile")
    pdf.body(
        "Sposta un singolo immobile dalla partita sorgente a un'altra partita di destinazione. "
        "L'operazione registra automaticamente la variazione nel log catastale. "
        "La partita di destinazione si seleziona per ID o tramite ricerca."
    )
    pdf.subsec("Passaggio di Proprieta' (Voltura)")
    pdf.body(
        "Effettua il passaggio di proprieta' (voltura catastale): gli immobili selezionati "
        "vengono trasferiti dalla partita sorgente a una nuova partita, con nuovi possessori. "
        "Si compilano i dati dell'atto (tipo, riferimento notarile, data), si selezionano "
        "gli immobili da trasferire e si aggiungono i nuovi proprietari."
    )
    pdf.nota("Il passaggio di proprieta' chiude automaticamente la partita sorgente se tutti "
             "gli immobili vengono trasferiti.")

    pdf.sec("8.7  Registrazione Consultazione Archivistica")
    pdf.body(
        "Permette di tracciare ogni accesso all'archivio fisico da parte di ricercatori, "
        "studiosi o cittadini, in conformita' con le normative sugli archivi di Stato."
    )
    pdf.thead(["Campo", "Obbl.", "Descrizione"], [55, 20, 105])
    for i, r in enumerate([
        ("Data Consultazione",    "Si'", "Data dell'accesso (precompilata con la data odierna)"),
        ("Nome Richiedente",      "Si'", "Cognome e nome del consultatore"),
        ("Documento d'Identita'", "Si'", "Tipo e numero del documento esibito"),
        ("Motivazione",           "No",  "Scopo della ricerca archivistica"),
        ("Materiale Consultato",  "No",  "Descrizione del materiale catastale consultato"),
        ("Funzionario Autorizzante","Si'","Nome del funzionario che ha autorizzato l'accesso"),
    ]):
        pdf.trow(r, [55, 20, 105], alt=bool(i % 2))

    pdf.sec("8.8  Gestione Tipi Localita', Titoli di Possesso, Periodi Storici (solo Admin)")
    pdf.add_page()
    pdf.subsec("Tipi Localita'")
    pdf.body(
        "Permette agli amministratori di gestire le categorie di localita' (Via, Piazza, Borgata, "
        "Contrada, Strada, Regione, ecc.). Le operazioni disponibili sono: Aggiungi, Modifica, Elimina."
    )
    pdf.nota("Eliminare un tipo di localita' e' possibile solo se nessuna localita' e' attualmente "
             "associata a quel tipo.")
    pdf.subsec("Titoli di Possesso")
    pdf.body(
        "Permette di gestire i titoli giuridici di possesso (Proprieta' esclusiva, Comproprietà, "
        "Usufrutto, Enfiteusi, Superficie, Uso, Abitazione, Servitu', Nuda proprieta'). "
        "I titoli vengono proposti come opzioni nel dialogo di associazione possessore-partita."
    )
    pdf.subsec("Periodi Storici")
    pdf.body(
        "Permette di definire i periodi storici di riferimento per l'archivio catastale "
        "(es. Regno di Sardegna 1720-1860, Regno d'Italia 1861-1946, Repubblica Italiana 1947-oggi). "
        "I periodi vengono usati nella reportistica per contestualizzare i dati storici."
    )

    # ═════════════════════════ CAP 9 - ESPORTAZIONI ═══════════════════════════
    pdf.add_page()
    pdf.cap("9", "Esportazioni")
    pdf.body(
        "Il tab [Esportazioni] permette di estrarre i dati dall'archivio in formato CSV, "
        "Excel (.xlsx) o PDF per consultazione offline, stampa o rielaborazione esterna."
    )
    pdf.sec("Tipi di Dati Esportabili")
    pdf.thead(["Tipo Esportazione", "Contenuto", "Filtro Comune"], [55, 90, 35])
    for i, r in enumerate([
        ("Elenco Possessori",  "ID, Cognome/Nome, Paternita', Nome Completo, N. Partite", "Si'"),
        ("Elenco Partite",     "ID, Numero, Tipo, Stato, Date, N. Possessori, N. Immobili", "Si'"),
        ("Elenco Immobili",    "ID, Tipo, Natura, Classificazione, Mappa, Confini, Partita", "Si'"),
        ("Elenco Localita'",   "ID, Nome, Tipo, Comune", "Si'"),
        ("Elenco Variazioni",  "ID, Tipo, Data, Partita Origine, Partita Destinazione", "Si'"),
        ("Consistenza Patrimoniale", "Report raggruppato per possessore con tutti gli immobili", "Obbl."),
    ]):
        pdf.trow(r, [55, 90, 35], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Come Effettuare un'Esportazione")
    for t in [
        "Selezionare il tipo di dati dal menu 'Tipo di Esportazione'.",
        "Selezionare il comune dal menu 'Filtra per Comune' (o 'Tutti i Comuni' se disponibile).",
        "Scegliere il formato: CSV, XLS (Excel) o PDF.",
        "Nella finestra di salvataggio, scegliere la cartella di destinazione "
        "(predefinita: Documenti/Esportazioni Meridiana).",
        "Fare clic sul link nel pannello di log per aprire il file appena creato.",
    ]:
        pdf.bullet(t)
    pdf.ln(3)
    pdf.sec("Formati Supportati")
    pdf.thead(["Formato", "Estensione", "Caratteristiche Principali"], [30, 30, 120])
    for i, r in enumerate([
        ("CSV",   ".csv",  "Testo separato da punto e virgola (;), compatibile con qualsiasi software"),
        ("Excel", ".xlsx", "Formato nativo Microsoft Excel con intestazioni e colonne ottimizzate"),
        ("PDF",   ".pdf",  "Documento impaginato con intestazione istituzionale e numero pagina"),
    ]):
        pdf.trow(r, [30, 30, 120], alt=bool(i % 2))
    pdf.ln(3)
    pdf.nota("Se si tenta di sovrascrivere un file Excel gia' aperto in Microsoft Excel, "
             "il sistema segnalera' un errore di permessi. Chiudere il file prima di ripetere.")
    pdf.tip("Il pannello di log mostra un link cliccabile sul percorso del file generato: "
            "fare clic per aprirlo automaticamente con il programma predefinito del sistema.")

    # ═════════════════════════ CAP 10 - REPORTISTICA ══════════════════════════
    pdf.add_page()
    pdf.cap("10", "Reportistica")
    pdf.body(
        "Il tab 'Report' permette di generare quattro tipi di report dettagliati. "
        "I report possono essere visualizzati nell'anteprima integrata ed esportati in TXT o PDF."
    )
    pdf.sec("Report Disponibili")
    pdf.subsec("Report Proprieta'")
    pdf.body(
        "Genera il certificato completo di una partita catastale specifica: "
        "dati anagrafici della partita, elenco possessori con titoli di possesso, "
        "elenco immobili con tutti i dettagli, storico delle variazioni. "
        "Procedura: fare clic su 'Cerca...' per selezionare la partita, poi 'Genera Report Proprieta''."
    )
    pdf.subsec("Report Genealogico")
    pdf.body(
        "Traccia la storia di una partita nel tempo, mostrando tutte le variazioni (volture) "
        "con le partite di origine e destinazione, consentendo di ricostruire la catena proprietaria."
    )
    pdf.subsec("Report Possessore")
    pdf.body(
        "Genera il profilo completo di un possessore: tutti i beni posseduti, le partite a lui "
        "associate (attive e storiche), gli immobili per cui e' registrato e la consistenza "
        "patrimoniale. Procedura: fare clic su 'Cerca...' per selezionare il possessore."
    )
    pdf.subsec("Report Consultazioni")
    pdf.body(
        "Genera il registro delle consultazioni archivistiche per un periodo specificato. "
        "Utile per la rendicontazione istituzionale degli accessi all'archivio. "
        "Procedura: selezionare il periodo (da data - a data) e fare clic su 'Genera Report Consultazioni'."
    )
    pdf.sec("Esportazione dei Report")
    pdf.body(
        "Una volta generato, il report viene visualizzato nell'area di anteprima. "
        "Sono disponibili due pulsanti di esportazione:"
    )
    pdf.bullet("'Esporta come TXT': salva il report come file di testo semplice (.txt)")
    pdf.bullet("'Esporta come PDF': genera un PDF formattato con intestazione istituzionale")

    # ═════════════════════════ CAP 11 - STATISTICHE ═══════════════════════════
    pdf.add_page()
    pdf.cap("11", "Statistiche e Manutenzione Database")
    pdf.body("Il tab 'Statistiche' e' composto da tre sezioni accessibili tramite le schede interne.")
    pdf.sec("Statistiche per Comune")
    pdf.body(
        "Mostra una tabella riepilogativa per ogni comune con: numero di partite attive, "
        "numero di possessori, numero di immobili totali, data dell'ultima variazione registrata. "
        "Il pulsante 'Aggiorna Statistiche Comuni' ricarica i dati dal database."
    )
    pdf.sec("Immobili per Tipologia")
    pdf.body(
        "Mostra la distribuzione degli immobili per tipo (Fabbricato / Terreno) e per natura "
        "(Casa, Cascina, Prato, Campo, Bosco, ecc.) con conteggi e percentuali."
    )
    pdf.sec("Manutenzione Database")
    pdf.body("Operazioni di manutenzione avanzata:")
    pdf.bullet("Aggiorna Viste Materializzate: rigenera le viste pre-calcolate del database "
               "per ottimizzare le prestazioni delle query di statistiche")
    pdf.bullet("Verifica Integrita': esegue controlli di coerenza dei dati "
               "(es. partite senza possessori, immobili orfani, variazioni incomplete)")
    pdf.nota("Le operazioni di manutenzione possono richiedere alcuni secondi su database di grandi "
             "dimensioni. L'interfaccia rimane responsiva grazie all'esecuzione in thread separato.")

    # ═════════════════════════ CAP 12 - UTENTI ════════════════════════════════
    pdf.add_page()
    pdf.cap("12", "Gestione Utenti (solo Admin)")
    pdf.body(
        "Il tab 'Utenti' e' visibile solo agli utenti con ruolo 'admin'. "
        "Permette la gestione completa degli account Meridiana."
    )
    pdf.sec("Funzioni Disponibili")
    pdf.thead(["Funzione", "Descrizione"], [50, 130])
    for i, r in enumerate([
        ("Crea Utente",        "Aggiunge un nuovo account con username, password e ruolo"),
        ("Modifica Utente",    "Cambia username, password o ruolo di un utente esistente"),
        ("Disabilita Utente",  "Disabilita l'accesso senza eliminare l'account o la sua storia"),
        ("Elimina Utente",     "Eliminazione definitiva (solo se l'utente non ha mai operato)"),
        ("Reimposta Password", "Imposta una nuova password per l'utente selezionato"),
    ]):
        pdf.trow(r, [50, 130], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Sicurezza degli Account")
    pdf.bullet("Le password sono conservate come hash bcrypt (nessuna password in chiaro nel database).")
    pdf.bullet("Non e' possibile eliminare l'utente admin principale che ha inizializzato il sistema.")
    pdf.bullet("Ogni operazione degli utenti viene tracciata nel Log di Audit con username, "
               "timestamp e dettaglio dell'azione.")

    # ═════════════════════════ CAP 13 - SISTEMA ═══════════════════════════════
    pdf.add_page()
    pdf.cap("13", "Sistema: Log Audit e Backup (solo Admin)")
    pdf.body(
        "Il tab 'Sistema' e' visibile solo agli amministratori e contiene due sotto-tab: "
        "Log Audit e Backup/Ripristino."
    )
    pdf.sec("Log Audit")
    pdf.body(
        "Il Log di Audit registra automaticamente tutte le operazioni eseguite nel sistema: "
        "inserimenti, modifiche, archiviazioni, login, logout, importazioni CSV."
    )
    pdf.thead(["Colonna", "Descrizione"], [45, 135])
    for i, r in enumerate([
        ("Timestamp",  "Data e ora precisa dell'operazione"),
        ("Utente",     "Username dell'utente che ha eseguito l'operazione"),
        ("Azione",     "Tipo di operazione (INSERT, UPDATE, DELETE, ARCHIVE, LOGIN, ecc.)"),
        ("Tabella",    "Entita' coinvolta (comune, partita, possessore, immobile, ecc.)"),
        ("ID Record",  "Identificativo del record modificato"),
        ("Dettagli",   "Descrizione testuale dell'operazione e dei valori coinvolti"),
    ]):
        pdf.trow(r, [45, 135], alt=bool(i % 2))
    pdf.ln(3)
    pdf.body("Filtri disponibili nel Log Audit:")
    pdf.bullet("Filtro per utente (tutti / utente specifico)")
    pdf.bullet("Filtro per tipo di azione")
    pdf.bullet("Filtro per periodo (da data - a data)")
    pdf.bullet("Campo di ricerca testuale libero")

    pdf.sec("Backup/Ripristino Database")
    pdf.add_page()
    pdf.body(
        "Il sotto-tab 'Backup/Ripristino' permette di gestire i backup del database PostgreSQL "
        "direttamente dall'interfaccia di Meridiana, senza necessita' di accedere al server."
    )
    pdf.body("Operazioni disponibili:")
    pdf.bullet("Esegui Backup Ora: crea un dump completo del database in formato SQL compresso. "
               "Il file viene salvato nella cartella di backup configurata "
               "(predefinita: Documenti/Backup Meridiana).")
    pdf.bullet("Seleziona Backup da Ripristinare: apre il dialogo di selezione file per scegliere "
               "un backup .sql o .dump precedentemente creato.")
    pdf.bullet("Ripristina Database: sovrascrive il database corrente con il backup selezionato. "
               "Richiede conferma esplicita prima di procedere.")
    pdf.bullet("Cronologia Backup: visualizza l'elenco dei backup disponibili con data, dimensione "
               "e stato (verificato / non verificato).")
    pdf.ln(2)
    pdf.nota("L'operazione di ripristino e' irreversibile: tutti i dati inseriti dopo il backup "
             "selezionato andranno persi. Eseguire sempre un backup della situazione corrente "
             "prima di ripristinare.")
    pdf.tip("Configurare il promemoria backup dal menu Impostazioni -> Promemoria Backup per ricevere "
            "una notifica periodica quando e' il momento di eseguire un backup.")

    # ═════════════════════════ CAP 14 - MENU ══════════════════════════════════
    pdf.add_page()
    pdf.cap("14", "Menu Barra dei Menu")
    pdf.sec("Menu File")
    pdf.thead(["Voce di Menu", "Funzione"], [70, 110])
    for i, r in enumerate([
        ("Importa Possessori da CSV...", "Apre il dialogo per importare in massa possessori da CSV"),
        ("Importa Partite da CSV...",    "Apre il dialogo per importare in massa partite da CSV"),
        ("Esci",                         "Chiude l'applicazione con conferma"),
    ]):
        pdf.trow(r, [70, 110], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Menu Impostazioni")
    pdf.thead(["Voce di Menu", "Funzione"], [70, 110])
    for i, r in enumerate([
        ("Configurazione Database...",          "Apre il dialogo di configurazione connessione PostgreSQL"),
        ("Impostazioni Aggiornamento Dati...",  "Configura la frequenza di refresh automatico delle tabelle"),
        ("Cambia Tema Grafico [>]",             "Sottomenu con i 16 temi grafici disponibili (vedi cap. 17)"),
        ("Promemoria Backup...",                "Configura la frequenza del promemoria per i backup"),
    ]):
        pdf.trow(r, [70, 110], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Menu Help")
    pdf.thead(["Voce di Menu", "Funzione"], [70, 110])
    for i, r in enumerate([
        ("Visualizza Manuale Utente...",        "Apre il presente manuale in PDF con il visualizzatore predefinito"),
        ("Informazioni su Meridiana / EULA...", "Mostra versione, crediti e testo della licenza d'uso"),
        ("Esporta Log di Sistema...",           "Esporta il file di log per il supporto tecnico"),
    ]):
        pdf.trow(r, [70, 110], alt=bool(i % 2))

    # ═════════════════════════ CAP 15 - SOFT DELETE ═══════════════════════════
    pdf.add_page()
    pdf.cap("15", "Archiviazione Logica (Soft Delete)")
    pdf.body(
        "In un archivio storico catastale i dati non vengono mai cancellati fisicamente. "
        "Meridiana implementa il concetto di 'archiviazione logica' per le quattro entita' principali:"
    )
    pdf.thead(["Entita'", "Come Archiviare", "Effetto"], [38, 80, 62])
    for i, r in enumerate([
        ("Comune",      "Dialogo Modifica -> pulsante 'Archivia...'", "Escluso da ricerche e nuovi inserimenti"),
        ("Partita",     "Dialogo Modifica -> pulsante 'Archivia...'", "Non appare nelle ricerche standard"),
        ("Possessore",  "Dialogo Modifica -> pulsante 'Archivia...'", "Campo 'attivo' impostato a falso"),
        ("Localita'",   "Dialogo Modifica -> pulsante 'Archivia...'", "Non appare nei menu di selezione"),
    ]):
        pdf.trow(r, [38, 80, 62], alt=bool(i % 2))
    pdf.ln(3)
    pdf.body(
        "Ogni operazione di archiviazione richiede una conferma esplicita con dialogo. "
        "L'archiviazione e' reversibile solo tramite query SQL diretta al database "
        "(stored procedure ripristina_xxx) eseguita da un DBA."
    )
    pdf.nota("I record archiviati non appaiono nelle ricerche standard dell'interfaccia grafica, "
             "ma i loro dati rimangono intatti nel database e consultabili tramite report storici.")

    # ═════════════════════════ CAP 16 - CSV ═══════════════════════════════════
    pdf.add_page()
    pdf.cap("16", "Importazione Massiva da CSV")
    pdf.body(
        "Meridiana permette di importare in massa possessori e partite da file CSV, "
        "disponibile sia dal menu File che dai rispettivi tab di inserimento."
    )
    pdf.sec("Formato CSV Possessori")
    pdf.body("Il file CSV deve avere la prima riga come intestazione con i seguenti campi:")
    pdf.thead(["Colonna CSV", "Tipo", "Obbl.", "Descrizione"], [50, 25, 20, 85])
    for i, r in enumerate([
        ("comune_nome",   "testo",    "Si'", "Nome esatto del comune come registrato nel database"),
        ("cognome_nome",  "testo",    "Si'", "Cognome e nome del possessore"),
        ("paternita",     "testo",    "No",  "Es. 'fu Giovanni' o 'di Maria'"),
        ("nome_completo", "testo",    "No",  "Se vuoto, viene generato automaticamente"),
        ("attivo",        "booleano", "No",  "true/false (default: true)"),
    ]):
        pdf.trow(r, [50, 25, 20, 85], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Formato CSV Partite")
    pdf.thead(["Colonna CSV", "Tipo", "Obbl.", "Descrizione"], [50, 25, 20, 85])
    for i, r in enumerate([
        ("comune_nome",      "testo",  "Si'", "Nome esatto del comune"),
        ("numero_partita",   "intero", "Si'", "Numero catastale progressivo"),
        ("suffisso_partita", "testo",  "No",  "Es. 'A', 'B' (default: nessuno)"),
        ("tipo",             "testo",  "Si'", "principale / derivata / aggregata"),
        ("stato",            "testo",  "Si'", "attiva / chiusa"),
        ("data_impianto",    "data",   "Si'", "Formato YYYY-MM-DD"),
        ("data_chiusura",    "data",   "No",  "Formato YYYY-MM-DD"),
    ]):
        pdf.trow(r, [50, 25, 20, 85], alt=bool(i % 2))
    pdf.ln(3)
    pdf.sec("Comportamento in Caso di Errori")
    pdf.bullet("I duplicati vengono ignorati con un messaggio nel log dei risultati.")
    pdf.bullet("Le righe con errori di formato vengono saltate senza interrompere l'importazione.")
    pdf.bullet("Al termine, viene mostrato un riepilogo con record importati, ignorati e in errore.")
    pdf.tip("Usare 'Info Formato CSV' nei rispettivi tab di inserimento per visualizzare un esempio "
            "di file CSV correttamente formattato.")

    # ═════════════════════════ CAP 17 - TEMI ══════════════════════════════════
    pdf.add_page()
    pdf.cap("17", "Temi Grafici")
    pdf.body(
        "Meridiana include 16 temi grafici predefiniti, selezionabili dal menu "
        "Impostazioni -> Cambia Tema Grafico. Il tema viene salvato automaticamente e ripristinato "
        "al prossimo avvio dell'applicazione."
    )
    pdf.thead(["Nome Tema", "Palette Colori", "Stile"], [65, 70, 45])
    for i, r in enumerate([
        ("Azzurro Ligure",      "Azzurro tenue + bianco",         "Ligure/istituzionale"),
        ("Blu Savoia",          "Blu reale + oro",                "Storico/elegante"),
        ("Moderno",             "Grigio neutro + accenti blu",    "Pulito/moderno"),
        ("Pergamena",           "Beige caldo + marrone",          "Cartaceo/archivistico"),
        ("Terra Siena",         "Terracotta + arancio",           "Caldo/classico"),
        ("Verde Bosco",         "Verde scuro + naturale",         "Sobrio/naturale"),
        ("Grigio Ardesia",      "Grigio ardesia + bianco",        "Minimalista"),
        ("Dark Mode",           "Nero + grigio + bianchi",        "Scuro/moderno"),
        ("Moderno Dark",        "Blu notte + grigio scuro",       "Scuro/elegante"),
        ("Ocean Blue",          "Blu oceano + azzurro",           "Fresco/marino"),
        ("Nature Green",        "Verde natura + chiaro",          "Naturale/rilassante"),
        ("Classic Business",    "Grigio neutro + blu business",   "Professionale"),
        ("Purple Royal",        "Viola + lavanda",                "Elegante/distintivo"),
        ("Sunset Orange",       "Arancio + ambra",                "Caldo/vivace"),
        ("High Contrast",       "Nero + bianco + giallo",         "Alta leggibilita'"),
        ("Meridiana Styles",    "Tema personalizzato Meridiana",  "Default"),
    ]):
        pdf.trow(r, [65, 70, 45], alt=bool(i % 2))

    # ═════════════════════════ CAP 18 - RISOLUZIONE PROBLEMI ══════════════════
    pdf.add_page()
    pdf.cap("18", "Risoluzione Problemi Comuni")
    problemi = [
        ("L'applicazione non si connette al database",
         "Verificare che PostgreSQL sia in esecuzione e raggiungibile. "
         "Controllare i parametri in Impostazioni -> Configurazione Database. "
         "Verificare che firewall o VPN non blocchino la porta 5432."),
        ("La ricerca mostra 'Trovate X partite' ma la tabella e' vuota",
         "Problema risolto in versione 1.3.0. "
         "Verificare di avere installato Meridiana 1.3.0 o superiore."),
        ("Avviso 'Unknown property box-shadow' nel log di avvio",
         "Nota informativa non bloccante: la proprieta' CSS box-shadow non e' supportata da Qt. "
         "E' stata rimossa in Meridiana 1.3.0. Se il messaggio appare, "
         "verificare che il tema selezionato sia aggiornato all'ultima versione."),
        ("Impossibile esportare in Excel (file gia' aperto)",
         "Chiudere il file Excel prima di effettuare una nuova esportazione. "
         "Windows blocca la scrittura su file aperti da un altro programma."),
        ("L'importazione CSV non carica nessun record",
         "Verificare che il file CSV usi il punto e virgola come separatore e che "
         "la prima riga contenga le intestazioni esatte. "
         "Controllare il riepilogo errori mostrato al termine dell'importazione."),
        ("Il wizard 'Registrazione Proprieta'' non abilita il pulsante finale",
         "Il pulsante richiede almeno: comune selezionato, numero partita, "
         "almeno un possessore e almeno un immobile nell'elenco."),
        ("Le statistiche della dashboard non si aggiornano",
         "Le statistiche si caricano all'apertura del tab Home. "
         "Navigare verso un altro tab e tornare su Home per forzare il refresh."),
        ("Errore al bootstrap: 'cerca_possessori non esiste'",
         "Problema risolto in versione 1.3.0. Aggiornare Meridiana o eseguire manualmente "
         "lo script sql_scripts/15_integration_audit_users.sql."),
        ("Come recuperare una partita archiviata?",
         "Le entita' archiviate non sono visibili nell'interfaccia grafica. "
         "Un DBA puo' ripristinarle tramite stored procedure SQL: "
         "CALL catasto.ripristina_partita(id_partita);"),
        ("Il campo data mostra formato errato",
         "L'interfaccia accetta il formato gg/mm/aaaa. "
         "I file CSV usano il formato aaaa-mm-gg (ISO 8601). "
         "Assicurarsi di usare il formato corretto per il contesto."),
    ]
    for num, (prob, sol) in enumerate(problemi, 1):
        pdf.subsec(f"{num}. {prob}")
        pdf.body(sol, indent=1)
        pdf.ln(1)
    pdf.ln(4)
    pdf.sec("Supporto Tecnico")
    pdf.body(
        "Per problemi non risolti, contattare il responsabile tecnico allegando il file di log "
        "del sistema, esportabile dal menu Help -> Esporta Log di Sistema. "
        "Il log e' in formato testuale rotante (max 5 MB) e contiene tutte le operazioni e gli "
        "errori registrati dall'applicazione."
    )

    # ─── output ───────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    pdf.output(OUTPUT)
    print(f"Manuale generato: {OUTPUT}")


if __name__ == "__main__":
    build()
