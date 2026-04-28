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

class UnifiedFuzzySearchThread(QThread):
    """Thread unificato per eseguire ricerche fuzzy in background."""
    results_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, gin_search_manager, query_text, options):
        super().__init__()
        self.gin_search_manager = gin_search_manager
        self.query_text = query_text
        self.options = options

    def run(self):
        """Esegue la ricerca fuzzy."""
        try:
            self.progress_updated.emit(10)
            
            threshold = self.options.get('threshold', 0.3)
            max_results = self.options.get('max_results', 100)

            # --- MODIFICA: Logica di ricerca semplificata ---
            # Questo thread ora chiama un metodo unificato che a sua volta
            # orchestra le ricerche individuali.
            # Assumiamo che `gin_search_manager` abbia un metodo come `search_all_entities_fuzzy`.
            if not hasattr(self.gin_search_manager, 'search_all_entities_fuzzy'):
                self.error_occurred.emit("Il DB Manager non supporta 'search_all_entities_fuzzy'.")
                return

            self.progress_updated.emit(30)

            results_data = self.gin_search_manager.search_all_entities_fuzzy(
                query_text=self.query_text,
                search_possessori=self.options.get('search_possessori', True),
                search_localita=self.options.get('search_localita', True),
                search_immobili=self.options.get('search_immobili', True),
                search_variazioni=self.options.get('search_variazioni', True),
                search_contratti=self.options.get('search_contratti', True),
                search_partite=self.options.get('search_partite', True),
                max_results_per_type=self.options.get('max_results_per_type', 50),
                similarity_threshold=threshold
            )

            # Prepara il dizionario finale per l'emissione del segnale
            final_results = {
                'query_text': self.query_text,
                'threshold': threshold,
                'timestamp': datetime.now(),
                'total_results': sum(len(entities) for entities in results_data.values()),
                'results_by_type': results_data # Mantiene la struttura per tipo
            }

            self.progress_updated.emit(100)
            self.results_ready.emit(final_results)

        except Exception as e:
            logging.getLogger(__name__).error(f"Errore nel thread di ricerca: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


# ========================================================================
# WIDGET PRINCIPALE UNIFICATO
# ========================================================================

class UnifiedFuzzySearchWidget(QWidget):
    """Widget unificato per ricerca fuzzy con una singola interfaccia robusta."""

    # --- MODIFICA: Il costruttore non ha più il parametro 'mode' ---
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.parent_window = parent
        self.logger = logging.getLogger(__name__)

        # Inizializza componenti GIN. Assumiamo che db_manager sia già esteso.
        self.gin_search = self.db_manager

        # Variabili di stato
        self.current_results = {}
        self.search_thread = None
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        # Setup UI
        self._init_ui() # --- MODIFICA: Chiamata a un singolo metodo di setup UI
        self._setup_signals()
        self._check_gin_status()

  

    def _init_ui(self):
        """Configura l'interfaccia utente unificata con un layout robusto."""
        # Layout principale dell'intero widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- INIZIO NUOVA STRUTTURA ---
        # 1. Creiamo un widget contenitore per tutti i contenuti tranne la status bar
        content_container_widget = QWidget()
        content_layout = QVBoxLayout(content_container_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        # --- FINE NUOVA STRUTTURA ---

        # === AREA RICERCA (da aggiungere al content_layout) ===
        search_frame = QFrame()
        search_frame.setFrameStyle(QFrame.StyledPanel)
        search_frame.setMaximumHeight(120)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 8, 10, 8)
        # ... (il codice interno di search_frame, search_row, controls_row rimane identico)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca in possessori, località, immobili, variazioni, contratti, partite...")
        search_row.addWidget(self.search_edit, 1)
        self.search_btn = QPushButton("Cerca")
        search_row.addWidget(self.search_btn)
        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.setMaximumWidth(30)
        search_row.addWidget(self.clear_btn)
        search_layout.addLayout(search_row)
        # --- BLOCCO "CONTROLLI AVANZATI" DA SOSTITUIRE ---
        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Soglia:"))
        self.precision_slider = QSlider(Qt.Horizontal)
        self.precision_slider.setRange(10, 90)
        self.precision_slider.setValue(30)
        self.precision_slider.setMaximumWidth(100)
        controls_row.addWidget(self.precision_slider)

        self.precision_label = QLabel("0.30")
        self.precision_label.setMinimumWidth(30)
        controls_row.addWidget(self.precision_label)

        controls_row.addWidget(QLabel("Max Risultati:"))
        self.max_results_combo = QComboBox()
        self.max_results_combo.addItems(["50", "100", "200", "500"])
        self.max_results_combo.setCurrentText("100")
        self.max_results_combo.setMaximumWidth(70)
        controls_row.addWidget(self.max_results_combo)

        controls_row.addStretch()

        # Creiamo i nuovi pulsanti specifici
        self.btn_export_csv = QPushButton("Esporta CSV")
        self.btn_export_csv.setEnabled(False)
        controls_row.addWidget(self.btn_export_csv)

        self.btn_export_pdf = QPushButton("Esporta PDF")
        self.btn_export_pdf.setEnabled(False)
        if not FPDF_AVAILABLE:
            self.btn_export_pdf.setToolTip("Libreria FPDF2 non trovata. Funzione non disponibile.")
        controls_row.addWidget(self.btn_export_pdf)
        
        # La riga errata "controls_row.addWidget(self.export_btn)" è stata rimossa.
        
        search_layout.addLayout(controls_row)
        # --- FINE BLOCCO DA SOSTITUIRE ---
        
        content_layout.addWidget(search_frame) # AGGIUNTO AL CONTENT_LAYOUT

        # === CHECKBOXES (da aggiungere al content_layout) ===
        types_layout = QHBoxLayout()
        types_group = QGroupBox("Cerca in:")
        types_group_layout = QHBoxLayout(types_group)
        # ... (tutte le checkbox vengono create e aggiunte a types_group_layout come prima) ...
        self.search_possessori_cb = QCheckBox("👥 Possessori"); self.search_possessori_cb.setChecked(True); types_group_layout.addWidget(self.search_possessori_cb)
        self.search_localita_cb = QCheckBox("🏘️ Località"); self.search_localita_cb.setChecked(True); types_group_layout.addWidget(self.search_localita_cb)
        self.search_immobili_cb = QCheckBox("🏢 Immobili"); self.search_immobili_cb.setChecked(True); types_group_layout.addWidget(self.search_immobili_cb)
        self.search_variazioni_cb = QCheckBox("📋 Variazioni"); self.search_variazioni_cb.setChecked(True); types_group_layout.addWidget(self.search_variazioni_cb)
        self.search_contratti_cb = QCheckBox("📄 Contratti"); self.search_contratti_cb.setChecked(True); types_group_layout.addWidget(self.search_contratti_cb)
        self.search_partite_cb = QCheckBox("📊 Partite"); self.search_partite_cb.setChecked(True); types_group_layout.addWidget(self.search_partite_cb)
        types_layout.addWidget(types_group)

        content_layout.addLayout(types_layout) # AGGIUNTO AL CONTENT_LAYOUT

        # === AREA RISULTATI (da aggiungere al content_layout) ===
        self.results_tabs = QTabWidget()
        self.results_tabs.setMinimumHeight(400)
        # ... (tutta la creazione delle tabelle e l'aggiunta a results_tabs rimane identica) ...
        self.unified_table = self._create_table_widget(["Tipo", "Nome/Descrizione", "Dettagli", "Similarità", "Campo"], [1, 2], 3); self.results_tabs.addTab(self.unified_table, "🔍 Tutti")
        self.possessori_table = self._create_table_widget(["Nome Completo", "Comune", "Partite", "Similitud."], [0], 3); self.results_tabs.addTab(self.possessori_table, "👥 Possessori")
        self.localita_table = self._create_table_widget(["Nome", "Tipo", "Civico", "Comune", "Immobili", "Similitud."], [0, 3], 5); self.results_tabs.addTab(self.localita_table, "📍 Località")
        self.immobili_table = self._create_table_widget(["Natura", "Classificazione", "Partita", "Suffisso", "Comune", "Similitud."], [1, 4], 5); self.results_tabs.addTab(self.immobili_table, "🏢 Immobili")
        self.variazioni_table = self._create_table_widget(["Tipo", "Data", "Rif. e Partita Origine", "Similitud."], [2], 3)
        self.results_tabs.addTab(self.variazioni_table, "📋 Variazioni")
        self.contratti_table = self._create_table_widget(["Tipo", "Data", "Partita", "Similitud."], [0], 3); self.results_tabs.addTab(self.contratti_table, "📄 Contratti")
        # --- MODIFICA QUESTA RIGA ---
        self.partite_table = self._create_table_widget(
            ["Numero", "Suffisso", "Possessori", "Tipo", "Stato", "Data Impianto", "Comune", "Similitud."],
            [2, 6],  # Indici delle colonne da espandere (Possessori e Comune)
            7        # L'indice della colonna 'Similitud.' ora è 7
        )
        # --- FINE MODIFICA --- 
        self.results_tabs.addTab(self.partite_table, "📊 Partite")

        content_layout.addWidget(self.results_tabs) # AGGIUNTO AL CONTENT_LAYOUT

        # --- AGGIUNTA DEL CONTENITORE AL LAYOUT PRINCIPALE ---
        # Diamo a tutto il blocco dei contenuti un fattore di stretch > 0
        main_layout.addWidget(content_container_widget, 1)

        # === STATUS BAR (ora separata e sicura) ===
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setFrameShadow(QFrame.Sunken)
        status_frame.setMaximumHeight(30)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)
        self.stats_label = QLabel("Inserire almeno 3 caratteri per iniziare")
        status_layout.addWidget(self.stats_label)
        status_layout.addStretch()
        self.indices_status_label = QLabel("Verifica indici...")
        status_layout.addWidget(self.indices_status_label)
        
        # Aggiungiamo la status bar al layout principale senza stretch
        main_layout.addWidget(status_frame)

        self.search_edit.setFocus()

    def _create_table_widget(self, headers, stretch_columns, similarity_col_index):
        """Helper per creare una QTableWidget standardizzata."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = table.horizontalHeader()
        for i in range(len(headers)):
            if i in stretch_columns:
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        # Salva l'indice della colonna di similarità per usi futuri (es. colorazione)
        table.setProperty("similarity_col", similarity_col_index)
        return table

    def _setup_signals(self):
        """Configura i segnali."""
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_btn.clicked.connect(self._perform_search)
        self.clear_btn.clicked.connect(self._clear_search)
        
        self.precision_slider.valueChanged.connect(lambda v: self.precision_label.setText(f"{v/100:.2f}"))
        self.precision_slider.sliderReleased.connect(self._trigger_search_if_text)

        self.max_results_combo.currentTextChanged.connect(self._trigger_search_if_text)
        # --- MODIFICA QUI: Colleghiamo i nuovi pulsanti ---
        # Rimuoviamo la vecchia riga: self.export_btn.clicked.connect(self._export_results)
        self.btn_export_csv.clicked.connect(self._handle_export_csv)
        self.btn_export_pdf.clicked.connect(self._handle_export_pdf)
        # --- FINE MODIFICA ---

        # Checkbox
        for cb in [self.search_possessori_cb, self.search_localita_cb, self.search_immobili_cb,
                   self.search_variazioni_cb, self.search_contratti_cb, self.search_partite_cb]: # AGGIUNTE NUOVE CHECKBOX
            cb.toggled.connect(self._trigger_search_if_text)

        # Double-click
        
        # --- MODIFICA QUI: Colleghiamo il doppio click per tutte le tabelle ---
        self.unified_table.doubleClicked.connect(self._on_unified_double_click)
        self.possessori_table.doubleClicked.connect(self._on_possessori_double_click)
        self.localita_table.doubleClicked.connect(self._on_localita_double_click)
        self.immobili_table.doubleClicked.connect(self._on_immobili_double_click)
        self.variazioni_table.doubleClicked.connect(self._on_variazioni_double_click)
        self.contratti_table.doubleClicked.connect(self._on_contratti_double_click)
        self.partite_table.doubleClicked.connect(self._on_partite_double_click)
        # --- FINE MODIFICA ---

    def _check_gin_status(self):
        """Verifica lo stato degli indici GIN."""
        if not self.gin_search or not hasattr(self.gin_search, 'verify_gin_indices'):
            self.indices_status_label.setText("❌ Ricerca non disponibile")
            return
        try:
            result = self.gin_search.verify_gin_indices()
            if result.get('status') == 'OK' and result.get('gin_indices', 0) > 0:
                self.indices_status_label.setText(f"✅ Indici GIN attivi ({result['gin_indices']})")
            else:
                self.indices_status_label.setText("⚠️ Indici GIN mancanti o non validi")
        except Exception as e:
            self.indices_status_label.setText("❌ Errore verifica indici")
            self.logger.error(f"Errore verifica indici GIN: {e}")

    def _on_search_text_changed(self, text):
        """Gestisce il cambiamento del testo di ricerca."""
        if len(text) >= 3:
            self.search_timer.start(800) # Delay per evitare ricerche a ogni tasto
            self.stats_label.setText("Pronto per la ricerca...")
        else:
            self.search_timer.stop()
            self._clear_results()
            self.stats_label.setText(f"Inserire almeno {3 - len(text)} caratteri in più")

    def _trigger_search_if_text(self):
        """Rilancia la ricerca se c'è abbastanza testo."""
        if len(self.search_edit.text().strip()) >= 3:
            self._perform_search()

    def _perform_search(self):
        """Esegue la ricerca vera e propria, gestendo il thread precedente."""
        query_text = self.search_edit.text().strip()
        if len(query_text) < 3:
            return

        if not self.gin_search:
            QMessageBox.warning(self, "Errore", "Sistema di ricerca fuzzy non disponibile.")
            return

        # --- MODIFICA CRUCIALE: Gestione del thread esistente ---
        if self.search_thread and self.search_thread.isRunning():
            self.logger.debug("Ricerca precedente ancora in corso. Tentativo di fermarla.")
            self.search_thread.quit()  # Chiede al thread di terminare in modo pulito
            self.search_thread.wait(500) # Attende al massimo 500ms
            if self.search_thread.isRunning():
                self.logger.warning("Il thread precedente non si è fermato in tempo, terminazione forzata.")
                self.search_thread.terminate() # Estrema ratio
                self.search_thread.wait()

        search_options = {
            'threshold': self.precision_slider.value() / 100.0,
            'max_results': int(self.max_results_combo.currentText()),
            'search_possessori': self.search_possessori_cb.isChecked(),
            'search_localita': self.search_localita_cb.isChecked(),
            'search_immobili': self.search_immobili_cb.isChecked(),
            # --- AGGIUNGERE QUESTE OPZIONI ---
            'search_variazioni': self.search_variazioni_cb.isChecked(),
            'search_contratti': self.search_contratti_cb.isChecked(),
            'search_partite': self.search_partite_cb.isChecked(),
        }

        

        self.search_btn.setEnabled(False)
        self.stats_label.setText("Ricerca in corso...")
        
        self.search_thread = UnifiedFuzzySearchThread(self.gin_search, query_text, search_options)
        self.search_thread.results_ready.connect(self._display_results)
        self.search_thread.error_occurred.connect(self._handle_search_error)
        self.search_thread.finished.connect(lambda: self.search_btn.setEnabled(True))
        self.search_thread.start()

    def _display_results(self, results):
        """Visualizza i risultati della ricerca."""
        self.current_results = results
        results_by_type = results.get('results_by_type', {})
        
        self._populate_unified_table(results_by_type)
        self._populate_individual_tables(results_by_type)
        self._update_tab_counters(results_by_type)
        
        total = results.get('total_results', 0)
        self.stats_label.setText(f"Trovati {total} risultati per '{results.get('query_text')}'")
        # --- MODIFICA QUI ---
        self.btn_export_csv.setEnabled(total > 0)
        if FPDF_AVAILABLE:
            self.btn_export_pdf.setEnabled(total > 0)
        # --- FINE MODIFICA ---
    
    def _populate_table(self, table: QTableWidget, data: List[Dict], row_mapper_func):
        """Funzione helper per popolare una QTableWidget."""
        table.setRowCount(0)
        table.setRowCount(len(data))
        similarity_col = table.property("similarity_col")

        for row_idx, item_data in enumerate(data):
            row_content = row_mapper_func(item_data)
            for col_idx, cell_text in enumerate(row_content):
                item = QTableWidgetItem(str(cell_text))
                if col_idx == 0: # Salva i dati completi nel primo item della riga
                    item.setData(Qt.UserRole, item_data)
                
                # Applica colorazione alla colonna di similarità
                if similarity_col is not None and col_idx == similarity_col:
                    try:
                        similarity = float(cell_text)
                        if similarity > 0.7: item.setBackground(QColor("#d4edda")) # Verde
                        elif similarity > 0.5: item.setBackground(QColor("#fff3cd")) # Giallo
                        else: item.setBackground(QColor("#f8d7da")) # Rosso
                    except (ValueError, TypeError):
                        pass
                
                table.setItem(row_idx, col_idx, item)

    def _populate_unified_table(self, results_by_type: Dict[str, List]):
        self.unified_table.setRowCount(0)
        row = 0
        type_icons = {
            'possessore': '👥', 'localita': '🏘️', 'immobile': '🏢', 
            'variazione': '📋', 'contratto': '📄', 'partita': '📊'
        }
        for entity_type, entities in results_by_type.items():
            for entity in entities:
                self.unified_table.insertRow(row)
                icon = type_icons.get(entity_type, '📁')
                
                # ["Tipo", "Nome/Descrizione", "Dettagli", "Similarità", "Campo"]
                self.unified_table.setItem(row, 0, QTableWidgetItem(f"{icon} {entity_type.title()}"))
                self.unified_table.item(row,0).setData(Qt.UserRole, {'type': entity_type, 'data': entity}) # Salva dati per doppio click
                
                self.unified_table.setItem(row, 1, QTableWidgetItem(entity.get('display_text', '')))
                self.unified_table.setItem(row, 2, QTableWidgetItem(entity.get('detail_text', '')))
                self.unified_table.setItem(row, 3, QTableWidgetItem(f"{entity.get('similarity_score', 0):.3f}"))
                self.unified_table.setItem(row, 4, QTableWidgetItem(entity.get('search_field', '')))
                row += 1

    def _populate_individual_tables(self, results_by_type: Dict[str, List]):
        self._populate_table(self.possessori_table, results_by_type.get('possessore', []), 
            lambda p: [p.get('nome_completo', ''), p.get('comune_nome', ''), p.get('num_partite', 0), f"{p.get('similarity_score', 0):.3f}"])
        
        # --- MODIFICA QUESTA CHIAMATA ---
        self._populate_table(self.localita_table, results_by_type.get('localita', []),
            lambda l: [
                l.get('nome', ''),
                l.get('tipo', '') or '',
                l.get('comune_nome', ''),
                l.get('num_immobili', 0),
                f"{l.get('similarity_score', 0):.3f}"
            ]
        )
        # --- FINE MODIFICA ---
        # --- MODIFICA QUESTA CHIAMATA ---
        self._populate_table(self.immobili_table, results_by_type.get('immobile', []), 
            lambda i: [
                i.get('natura', ''),
                i.get('classificazione', ''),
                i.get('numero_partita', ''),
                i.get('suffisso_partita', '') or '', # Aggiunto il valore per la nuova colonna
                i.get('comune_nome', ''),
                f"{i.get('similarity_score', 0):.3f}"
            ]
        )
        # --- FINE MODIFICA ---

        self._populate_table(self.variazioni_table, results_by_type.get('variazione', []),
            lambda v: [
                v.get('tipo', ''),
                v.get('data_variazione', ''),
                v.get('detail_text', ''), # Usa detail_text per la nuova colonna
                f"{v.get('similarity_score', 0):.3f}"])

        self._populate_table(self.contratti_table, results_by_type.get('contratto', []), 
            lambda c: [c.get('tipo', ''), c.get('data_contratto', ''), c.get('numero_partita', ''), f"{c.get('similarity_score', 0):.3f}"])

        self._populate_table(self.partite_table, results_by_type.get('partita', []), 
            lambda pt: [
                pt.get('numero_partita', ''),
                pt.get('suffisso_partita', '') or '',
                pt.get('possessori_concatenati', '') or '', # NUOVA COLONNA
                pt.get('tipo_partita', ''),
                pt.get('stato', ''),
                str(pt.get('data_impianto', '')) if pt.get('data_impianto') else '',
                pt.get('comune_nome', ''),
                f"{pt.get('similarity_score', 0):.3f}"
            ]
        )
    def _update_tab_counters(self, results_by_type: Dict[str, List]):
        """Aggiorna i contatori nei titoli dei tab."""
        # --- MODIFICA: La logica di base_index non è più necessaria ---
        self.results_tabs.setTabText(0, f"🔍 Tutti ({sum(len(v) for v in results_by_type.values())})")
        self.results_tabs.setTabText(1, f"👥 Possessori ({len(results_by_type.get('possessore', []))})")
        self.results_tabs.setTabText(2, f"🏘️ Località ({len(results_by_type.get('localita', []))})")
        self.results_tabs.setTabText(3, f"🏢 Immobili ({len(results_by_type.get('immobile', []))})")
        # --- AGGIUNGERE QUESTE RIGHE ---
        self.results_tabs.setTabText(4, f"📋 Variazioni ({len(results_by_type.get('variazione', []))})")
        self.results_tabs.setTabText(5, f"📄 Contratti ({len(results_by_type.get('contratto', []))})")
        self.results_tabs.setTabText(6, f"📊 Partite ({len(results_by_type.get('partita', []))})")

    def _clear_results(self):
        """Pulisce tutti i risultati e i contatori."""
        tables = [
            self.unified_table, self.possessori_table, self.localita_table, 
            self.immobili_table, self.variazioni_table, self.contratti_table, 
            self.partite_table
        ]
        for table in tables:
            table.setRowCount(0)
        
        self._update_tab_counters({})
        
        # --- MODIFICA QUI: Disabilita i nuovi pulsanti invece del vecchio ---
        self.btn_export_csv.setEnabled(False)
        self.btn_export_pdf.setEnabled(False)
        # --- FINE MODIFICA ---
        
        self.current_results = {}

    def _handle_search_error(self, error_message):
        """Gestisce gli errori di ricerca."""
        self.search_btn.setEnabled(True)
        self.stats_label.setText("❌ Errore ricerca")
        self.logger.error(f"Errore ricerca fuzzy: {error_message}")
        QMessageBox.critical(self, "Errore Ricerca", f"Si è verificato un errore:\n{error_message}")

    def _clear_search(self):
        """Pulisce il campo di ricerca e i risultati."""
        self.search_edit.clear()
        self._clear_results()
        self.stats_label.setText("Pronto")



    def _on_unified_double_click(self, index):
        """
        Gestisce il doppio click nella tabella unificata, chiamando il gestore appropriato.
        """
        if not index.isValid(): return
            
        item_con_dati = self.unified_table.item(index.row(), 0)
        if not item_con_dati: return

        full_item_data = item_con_dati.data(Qt.UserRole)
        if not isinstance(full_item_data, dict): return

        entity_type = full_item_data.get('type')

        # Simula un evento di doppio click sul tab appropriato
        if entity_type == 'partita':
            self._on_partite_double_click(index)
        elif entity_type == 'possessore':
            self._on_possessori_double_click(index)
        elif entity_type == 'localita':
            self._on_localita_double_click(index)
        elif entity_type == 'immobile':
            self._on_immobili_double_click(index)
        elif entity_type == 'variazione':
            self._on_variazioni_double_click(index)
        elif entity_type == 'contratto':
            self._on_contratti_double_click(index)
        else:
            QMessageBox.warning(self, "Tipo Sconosciuto", f"Nessuna azione di dettaglio definita per il tipo '{entity_type}'.")
    def _handle_export_csv(self):
        """Esporta i risultati correnti della ricerca unificata in un file CSV."""
        if not self.current_results or not self.current_results.get('total_results', 0) > 0:
            QMessageBox.warning(self, "Nessun Risultato", "Non ci sono risultati da esportare.")
            return

        query_text = self.current_results.get('query_text', 'ricerca')
        default_filename = f"ricerca_fuzzy_{query_text}_{date.today().isoformat()}.csv"
        filename, _ = QFileDialog.getSaveFileName(self, "Esporta Risultati in CSV", default_filename, "File CSV (*.csv)")

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                # Usiamo le intestazioni della tabella "Tutti"
                headers = ['Tipo Entità', 'Nome/Descrizione', 'Dettagli', 'Similarità', 'Campo Trovato']
                writer = csv.writer(csvfile, delimiter=';')
                writer.writerow(headers)
                
                for entity_type, entities in self.current_results.get('results_by_type', {}).items():
                    for entity in entities:
                        writer.writerow([
                            entity_type,
                            entity.get('display_text', ''),
                            entity.get('detail_text', ''),
                            f"{entity.get('similarity_score', 0):.3f}",
                            entity.get('search_field', '')
                        ])
            prompt_to_open_file(self, filename)
        except Exception as e:
            self.logger.error(f"Errore esportazione CSV fuzzy: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Esportazione", f"Impossibile salvare il file CSV:\n{e}")

    def _handle_export_pdf(self):
        """Esporta i risultati correnti della ricerca unificata in un file PDF."""
        if not self.current_results or not self.current_results.get('total_results', 0) > 0:
            QMessageBox.warning(self, "Nessun Risultato", "Non ci sono risultati da esportare.")
            return
            
        query_text = self.current_results.get('query_text', 'ricerca')
        default_filename = f"ricerca_fuzzy_{query_text}_{date.today().isoformat()}.pdf"
        filename, _ = QFileDialog.getSaveFileName(self, "Esporta Risultati in PDF", default_filename, "File PDF (*.pdf)")

        if not filename:
            return

        try:
            pdf = BulkReportPDF(report_title=f"Risultati Ricerca Fuzzy per '{query_text}'")
            pdf.alias_nb_pages()
            pdf.set_font('Times', '', 12)
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            for entity_type, entities in self.current_results.get('results_by_type', {}).items():
                if not entities: continue
                
                pdf.set_font('Helvetica', 'B', 12)
                pdf.cell(0, 10, f"Risultati per: {entity_type.title()} ({len(entities)})", ln=1)
                
                headers = ['Nome/Descrizione', 'Dettagli', 'Similarità']
                # Adattiamo i dati per la tabella
                data_rows = [
                    (entity.get('display_text', ''), entity.get('detail_text', ''), f"{entity.get('similarity_score', 0):.3f}")
                    for entity in entities
                ]
                # La classe BulkReportPDF gestirà la creazione della tabella
                pdf.print_table(headers, data_rows)
                pdf.ln(5)

            pdf.output(filename)
            prompt_to_open_file(self, filename)
        except Exception as e:
            self.logger.error(f"Errore esportazione PDF fuzzy: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Esportazione", f"Impossibile generare il file PDF:\n{e}")
   

    def _get_entity_id_from_table(self, table: QTableWidget, index) -> Optional[int]:
        """Helper generico per estrarre l'ID dell'entità da una riga della tabella."""
        if not index.isValid():
            return None

        # I dati completi sono sempre salvati nella UserRole della prima colonna (indice 0)
        item_con_dati = table.item(index.row(), 0)
        if not item_con_dati:
            return None
            
        entity_data_wrapper = item_con_dati.data(Qt.UserRole)
        if not isinstance(entity_data_wrapper, dict):
            return None

        # Gestisce sia il tab "Tutti" (dove i dati sono annidati in 'data') 
        # sia i tab specifici (dove i dati sono al primo livello).
        if 'data' in entity_data_wrapper and isinstance(entity_data_wrapper['data'], dict):
            return entity_data_wrapper['data'].get('entity_id')
        elif 'entity_id' in entity_data_wrapper:
            return entity_data_wrapper.get('entity_id')

        return None

    def _on_possessori_double_click(self, index):
        entity_id = self._get_entity_id_from_table(self.possessori_table, index)
        if entity_id:
            dialog = ModificaPossessoreDialog(self.db_manager, entity_id, self)
            if dialog.exec_() == QDialog.Accepted:
                self._perform_search() # Aggiorna i risultati se ci sono state modifiche

    def _on_localita_double_click(self, index):
        entity_id = self._get_entity_id_from_table(self.localita_table, index)
        if entity_id:
            localita_details = self.db_manager.get_localita_details(entity_id)
            if localita_details and localita_details.get('comune_id'):
                dialog = ModificaLocalitaDialog(self.db_manager, entity_id, localita_details.get('comune_id'), self)
                if dialog.exec_() == QDialog.Accepted:
                    self._perform_search()
            else:
                QMessageBox.warning(self, "Errore Dati", f"Impossibile caricare i dettagli per la località ID {entity_id}.")

    def _on_immobili_double_click(self, index):
        entity_id = self._get_entity_id_from_table(self.immobili_table, index)
        if entity_id:
            immobile_details = self.db_manager.get_immobile_details(entity_id)
            if immobile_details and immobile_details.get('partita_id'):
                partita_details = self.db_manager.get_partita_details(immobile_details.get('partita_id'))
                if partita_details and partita_details.get('comune_id'):
                    dialog = ModificaImmobileDialog(self.db_manager, entity_id, partita_details.get('comune_id'), self)
                    if dialog.exec_() == QDialog.Accepted:
                        self._perform_search()
                else:
                    QMessageBox.warning(self, "Errore Dati", f"Impossibile determinare il comune per l'immobile ID {entity_id}.")
            else:
                 QMessageBox.warning(self, "Errore Dati", f"Impossibile caricare i dettagli per l'immobile ID {entity_id}.")

    def _on_partite_double_click(self, index):
        entity_id = self._get_entity_id_from_table(self.partite_table, index)
        if entity_id:
            full_details = self.db_manager.get_partita_details(entity_id)
            if full_details:
                dialog = PartitaDetailsDialog(full_details, self)
                dialog.exec_()
            else:
                QMessageBox.warning(self, "Errore Dati", f"Impossibile caricare i dettagli per la partita ID {entity_id}.")

    def _show_generic_details_popup(self, table: QTableWidget, index: 'QModelIndex', entity_type_name: str):
        """Mostra un popup leggibile per entità senza un dialogo di dettaglio dedicato."""
        item_con_dati = table.item(index.row(), 0)
        if not item_con_dati: return
        entity_data = item_con_dati.data(Qt.UserRole)
        entity_id = entity_data.get('entity_id', 'N/A')

        testo_formattato = f"<h3>Dettagli - {entity_type_name.title()} ID: {entity_id}</h3>"
        testo_formattato += "<table border='0' cellspacing='5'>"
        for key, value in entity_data.items():
            chiave_formattata = key.replace('_', ' ').title()
            testo_formattato += f"<tr><td><b>{chiave_formattata}:</b></td><td>{value}</td></tr>"
        testo_formattato += "</table>"
        QMessageBox.information(self, f"Dettagli - {entity_type_name.title()}", testo_formattato)

    def _on_variazioni_double_click(self, index):
        self._show_generic_details_popup(self.variazioni_table, index, 'variazione')

    def _on_contratti_double_click(self, index):
        self._show_generic_details_popup(self.contratti_table, index, 'contratto')
