import os,csv,sys,logging,json
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from app_utils import (BulkReportPDF, FPDF_AVAILABLE, _get_default_export_path, 
                       prompt_to_open_file, gui_esporta_partita_pdf, gui_esporta_partita_json, 
                       gui_esporta_partita_csv, gui_esporta_possessore_pdf, 
                       gui_esporta_possessore_json, gui_esporta_possessore_csv,
                       GenericTextReportPDF, is_file_locked, get_alternative_filename)
import pandas as pd # Importa pandas
from PyQt5.QtCore import (QDate, QDateTime, QPoint, QProcess, QSettings, 
                          QSize, QStandardPaths, Qt, QTimer, QUrl, 
                          pyqtSignal, QModelIndex, QProcessEnvironment, 
                          pyqtSlot, QThread)
from PyQt5.QtGui import (QCloseEvent, QColor, QDesktopServices, QFont, 
                         QIcon, QPalette, QPixmap)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QApplication, 
                             QCheckBox, QComboBox, QDateEdit, QDateTimeEdit,
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QFrame, QGridLayout,
                             QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMenu, QMessageBox, QProgressBar,
                             QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
                             QSpinBox, QStyle, QStyleFactory, QTabWidget,
                             QTableWidget, QTableWidgetItem, QTextEdit,
                             QVBoxLayout, QWidget,QProgressDialog,QTextBrowser,QSlider, QCompleter,QSplitter)
from config import (
    SETTINGS_DB_TYPE, SETTINGS_DB_HOST, SETTINGS_DB_PORT, 
    SETTINGS_DB_NAME, SETTINGS_DB_USER, SETTINGS_DB_SCHEMA,
    COLONNE_POSSESSORI_DETTAGLI_NUM ,COLONNE_POSSESSORI_DETTAGLI_LABELS,COLONNE_VISUALIZZAZIONE_POSSESSORI_NUM,
    COLONNE_VISUALIZZAZIONE_POSSESSORI_LABELS, COLONNE_INSERIMENTO_POSSESSORI_NUM, COLONNE_INSERIMENTO_POSSESSORI_LABELS,
    NUOVE_ETICHETTE_POSSESSORI)
from dialogs import (ModificaPossessoreDialog, PartiteComuneDialog, ModificaImmobileDialog,
                     PossessoriComuneDialog, LocalitaSelectionDialog, ModificaComuneDialog, 
                     PartitaDetailsDialog, CreateUserDialog, ModificaLocalitaDialog, PeriodoStoricoEditDialog, 
                     CreatePossessoreDialog, DBConfigDialog, DocumentViewerDialog, PeriodoStoricoDetailsDialog,
                     ComuneSelectionDialog, PartitaSearchDialog, PossessoreSelectionDialog, ImmobileDialog, 
                     DettagliLegamePossessoreDialog, UserSelectionDialog, qdate_to_datetime, datetime_to_qdate,
                     _hash_password, _verify_password)
from custom_widgets import QPasswordLineEdit, ImmobiliTableWidget, LazyLoadedWidget
logger = logging.getLogger("CatastoGUI.gui_widgets")
if TYPE_CHECKING:
    from gui_main import CatastoMainWindow 
    from catasto_db_manager import CatastoDBManager
try:
    from catasto_db_manager import CatastoDBManager, DBMError, DBUniqueConstraintError, DBNotFoundError, DBDataError
except ImportError:
    # Fallback o gestione errore
    class DBMError(Exception):
        pass  # ... definizioni fallback come nel file originale
    print("ATTENZIONE: catasto_db_manager non trovato, usando eccezioni DB fallback in gui_widgets.py")

class DashboardWidget(QWidget):
    # Segnali per navigare ad altri tab (manteniamo la logica)
    go_to_tab_signal = pyqtSignal(str, str) # Segnale emetterà (nome_tab_principale, nome_sotto_tab)
    # --- INIZIO MODIFICA ---
    # Definiamo il nuovo segnale che trasporterà una stringa (il testo della ricerca)
    ricerca_globale_richiesta = pyqtSignal(str)
    # --- FINE MODIFICA ---

    def __init__(self, db_manager: 'CatastoDBManager', current_user_info: Optional[Dict], parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user_info = current_user_info
        
        self.logger = logging.getLogger(f"CatastoGUI.{self.__class__.__name__}")
        self.is_admin = self.current_user_info.get('ruolo') == 'admin' if self.current_user_info else False
        self._initUI()
        self.load_initial_data() # Lazy loading

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(25)

        # 1. Intestazione
        nome_utente = self.current_user_info.get('nome_completo', 'Utente') if self.current_user_info else 'Utente'
        header_label = QLabel(f"<h2>Benvenuto in Meridiana 1.3.0, {nome_utente}</h2>")
        header_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_label)

        # 2. Ricerca Globale
        search_group = QGroupBox("Ricerca Rapida")
        search_layout = QHBoxLayout(search_group)
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("Cerca qualsiasi cosa nel catasto...")
        self.search_edit.setMinimumHeight(35)
        self.search_button = QPushButton("Cerca"); self.search_button.clicked.connect(self._avvia_ricerca_globale)
        self.search_edit.returnPressed.connect(self._avvia_ricerca_globale)
        search_layout.addWidget(self.search_edit); search_layout.addWidget(self.search_button)
        main_layout.addWidget(search_group)

        # 3. Statistiche Rapide
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        self.stat_comuni_label = self._create_stat_card("Comuni", "0", "background-color: #e6f7ff; border-color: #91d5ff;")
        self.stat_partite_label = self._create_stat_card("Partite", "0", "background-color: #f6ffed; border-color: #b7eb8f;")
        self.stat_possessori_label = self._create_stat_card("Possessori", "0", "background-color: #fffbe6; border-color: #ffe58f;")
        self.stat_immobili_label = self._create_stat_card("Immobili", "0", "background-color: #fff1f0; border-color: #ffccc7;")
        stats_layout.addWidget(self.stat_comuni_label); stats_layout.addWidget(self.stat_partite_label)
        stats_layout.addWidget(self.stat_possessori_label); stats_layout.addWidget(self.stat_immobili_label)
        main_layout.addLayout(stats_layout)

        # 4. Attività Recenti e Azioni Rapide
        bottom_layout = QHBoxLayout()
        
        recent_activity_group = QGroupBox("Attività Utenti Recenti") # Titolo più appropriato
        recent_activity_layout = QVBoxLayout(recent_activity_group)
        self.audit_table = QTableWidget()
        
        # --- INIZIO MODIFICA ---
        # Cambiamo le colonne per mostrare le informazioni della sessione
        self.audit_table.setColumnCount(5)
        self.audit_table.setHorizontalHeaderLabels(["Data/Ora", "Utente", "Azione", "Esito", "Indirizzo IP"])
        # --- FINE MODIFICA ---

        self.audit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        recent_activity_layout.addWidget(self.audit_table)
        bottom_layout.addWidget(recent_activity_group, 2)

        actions_group = QGroupBox("Azioni Rapide")
        actions_layout = QVBoxLayout(actions_group)
        btn_new_prop = QPushButton("Registra Nuova Proprietà"); 
        btn_new_prop.clicked.connect(lambda: self.go_to_tab_signal.emit("Inserimento", "Reg. Proprietà"))
        btn_new_partita = QPushButton("Inserisci Nuova Partita"); 
        btn_new_partita.clicked.connect(lambda: self.go_to_tab_signal.emit("Inserimento", "Partita"))
        btn_new_consult = QPushButton("Registra Consultazione")
        btn_new_consult.clicked.connect(lambda: self.go_to_tab_signal.emit("Inserimento", "Reg. Consultazione"))
        btn_reports = QPushButton("Vai alla Reportistica"); 
        btn_reports.clicked.connect(lambda: self.go_to_tab_signal.emit("Report", ""))
        # --- INIZIO MODIFICA: Pulsante visibile solo per admin ---
        if self.is_admin:
            actions_layout.addSpacing(15)

            # Creiamo un pulsante specifico per il backup
            btn_backup = QPushButton(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton), " Esegui Backup")
            #btn_backup.setStyleSheet("background-color: #ffeeba; border: 1px solid #ffc107;")

            # Collega il segnale per andare al tab "Sistema" e al sotto-tab "Backup/Ripristino DB"
            btn_backup.clicked.connect(lambda: self.go_to_tab_signal.emit("Sistema", "Backup/Ripristino DB"))

            actions_layout.addWidget(btn_backup)
        # --- FINE MODIFICA ---
        
        actions_layout.addWidget(btn_new_prop); actions_layout.addWidget(btn_new_partita); actions_layout.addWidget(btn_new_consult) ; actions_layout.addWidget(btn_reports)
        actions_layout.addStretch()
        bottom_layout.addWidget(actions_group, 1)

        main_layout.addLayout(bottom_layout, 1) # Stretch factor per la parte inferiore
        
    def _create_stat_card(self, title, value, style):
        card = QLabel(f"<h3>{title}</h3><p style='font-size: 24pt; font-weight: bold;'>{value}</p>")
        card.setAlignment(Qt.AlignCenter)
        card.setStyleSheet(f"QLabel {{ border: 1px solid; border-radius: 8px; padding: 10px; {style} }}")
        card.setMinimumHeight(100)
        return card

    # In gui_widgets.py, nel metodo DashboardWidget.load_initial_data

    def load_initial_data(self):
        """Carica tutti i dati necessari per la dashboard."""
        self.logger.info("Caricamento dati per la Dashboard...")
        # La parte delle statistiche rimane invariata
        stats = self.db_manager.get_dashboard_stats()
        self.stat_comuni_label.setText(f"<h3>Comuni</h3><p style='font-size: 24pt; font-weight: bold;'>{stats.get('total_comuni', 0)}</p>")
        self.stat_partite_label.setText(f"<h3>Partite</h3><p style='font-size: 24pt; font-weight: bold;'>{stats.get('total_partite', 0)}</p>")
        self.stat_possessori_label.setText(f"<h3>Possessori</h3><p style='font-size: 24pt; font-weight: bold;'>{stats.get('total_possessori', 0)}</p>")
        self.stat_immobili_label.setText(f"<h3>Immobili</h3><p style='font-size: 24pt; font-weight: bold;'>{stats.get('total_immobili', 0)}</p>")

        # Carica gli ultimi log di sessione
        session_logs = self.db_manager.get_recent_session_logs(limit=5)
        
        self.audit_table.setRowCount(len(session_logs))
        for row, log in enumerate(session_logs):
            # --- INIZIO MODIFICA DEFINITIVA ---
            # Usiamo le chiavi corrette ('data_login' e 'indirizzo_ip') restituite dalla query
            ts = log.get('data_login')
            ts_str = ts.strftime("%d/%m/%y %H:%M") if ts else "N/D"

            user_display = log.get('nome_completo') or log.get('username', 'N/D')
            action_display = log.get('azione', 'N/D').replace('_', ' ').title()
            esito_display = "Successo" if log.get('esito') else "Fallito"

            self.audit_table.setItem(row, 0, QTableWidgetItem(ts_str))
            self.audit_table.setItem(row, 1, QTableWidgetItem(user_display))
            self.audit_table.setItem(row, 2, QTableWidgetItem(action_display))
            self.audit_table.setItem(row, 3, QTableWidgetItem(esito_display))
            self.audit_table.setItem(row, 4, QTableWidgetItem(log.get('indirizzo_ip', 'N/D'))) # <-- Colonna corretta
            # --- FINE MODIFICA DEFINITIVA ---
            
        self.audit_table.resizeColumnsToContents()

    def _avvia_ricerca_globale(self):
        """Emette un segnale per passare al tab di ricerca globale e inserire il testo."""
        testo_ricerca = self.search_edit.text().strip()
        if not testo_ricerca:
            return
            
        # --- INIZIO MODIFICA ---
        # Sostituisci la vecchia logica con una singola riga che emette il segnale
        self.ricerca_globale_richiesta.emit(testo_ricerca)
        # --- FINE MODIFICA ---
class WelcomeScreen(QDialog):
    def __init__(self, parent=None, logo_path: str = None, help_url: str = None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"CatastoGUI.{self.__class__.__name__}")
        self.setWindowTitle("Benvenuto - Meridiana 1.3.0")
        self.setModal(True)
        self.setFixedSize(1024, 768)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.help_url = help_url
        self.logo_path = logo_path

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- NUOVA STRUTTURA DI LAYOUT PER CENTRATURA VERTICALE ---
        # 1. Spaziatore superiore per spingere il contenuto verso il basso
        main_layout.addStretch(1)

        # Logo
        logo_layout = QHBoxLayout()
        logo_layout.addStretch(1)
        logo_label = QLabel()
        if self.logo_path and os.path.exists(self.logo_path):
            pixmap = QPixmap(str(self.logo_path))
            # Riduciamo leggermente le dimensioni massime per garantire più spazio
            scaled_pixmap = pixmap.scaled(750, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch(1)
        main_layout.addLayout(logo_layout)

        # Titolo e Sottotitolo
        title_label = QLabel("Meridiana 1.3.0"); title_label.setFont(QFont("Segoe UI", 28, QFont.Bold)); title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Gestionale Catasto Storico - Archivio di Stato di Savona"); subtitle_label.setFont(QFont("Segoe UI", 14)); subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)

        # Crediti
        credits_label = QLabel("Sviluppato da: Marco Santoro\nCopyright © 2025 - Tutti i diritti riservati\nConcesso in comodato d'uso gratuito all'Archivio di Stato di Savona"); credits_label.setFont(QFont("Segoe UI", 9)); credits_label.setAlignment(Qt.AlignCenter)
        credits_label.setStyleSheet("color: #6c757d;")
        main_layout.addWidget(credits_label)
        main_layout.addSpacing(20)

        # Pulsante Guida
        if self.help_url:
            help_button = QPushButton("Apri Manuale Utente"); help_button.setFont(QFont("Segoe UI", 11)); help_button.setFixedSize(220, 40)
            help_button.clicked.connect(self._open_help_url)
            help_button_layout = QHBoxLayout(); help_button_layout.addStretch(); help_button_layout.addWidget(help_button); help_button_layout.addStretch()
            main_layout.addLayout(help_button_layout)

        # 2. Spaziatore inferiore per spingere il contenuto verso l'alto
        main_layout.addStretch(1)
        # --- FINE NUOVA STRUTTURA ---

        self.setLayout(main_layout)

    def _open_help_url(self):
        if not self.help_url: return
        self.logger.info(f"Apertura del manuale richiesta: {self.help_url}")
        # La logica che gestisce sia URL che file locali
        if self.help_url.lower().startswith(('http://', 'https://')):
            QDesktopServices.openUrl(QUrl(self.help_url))
        elif os.path.exists(self.help_url):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.help_url))
        else:
            QMessageBox.warning(self, "File Non Trovato", f"Il file della guida non è stato trovato:\n{self.help_url}")

    def mousePressEvent(self, event):
        # Chiude la finestra con un click, come richiesto
        self.logger.info("Welcome Screen chiusa tramite click del mouse.")
        self.accept()

    def keyPressEvent(self, event):
        # Chiude la finestra con un tasto, come richiesto
        self.logger.info(f"Welcome Screen chiusa tramite pressione del tasto: {event.key()}")
        self.accept()