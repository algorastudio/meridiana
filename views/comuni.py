import os,csv,sys,logging,json
from models.comune import Comune
from workers import GenericDBThread
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

class ElencoComuniWidget(LazyLoadedWidget):
    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        # Stampa di debug visibile nella console all'avvio
        print("--- DEBUG: Inizializzazione di ElencoComuniWidget ---")
        if db_manager:
            self.db_manager = db_manager
            self.logger.info(f"Widget inizializzato CORRETTAMENTE con DBManager (ID Oggetto: {id(self.db_manager)})")
        else:
            self.db_manager = None
            self.logger.error("ERRORE CRITICO: ElencoComuniWidget inizializzato SENZA un DBManager valido!")
            QMessageBox.critical(self, "Errore Widget", "Il widget dei comuni non ha ricevuto il gestore del database.")
            return

        layout = QVBoxLayout(self)

        comuni_group = QGroupBox("Elenco Comuni Registrati")
        comuni_layout = QVBoxLayout(comuni_group)

        self.filter_comuni_edit = QLineEdit()
        self.filter_comuni_edit.setPlaceholderText("Filtra per nome, provincia...")
        self.filter_comuni_edit.textChanged.connect(self.apply_filter)
        comuni_layout.addWidget(self.filter_comuni_edit)

        self.comuni_table = QTableWidget()
        self.comuni_table.setColumnCount(7) # ID, Nome, Cod. Cat., Prov., Data Ist., Data Sopp., Note
        self.comuni_table.setHorizontalHeaderLabels([
            "ID", "Nome Comune", "Cod. Catastale", "Provincia",
            "Data Istituzione", "Data Soppressione", "Note"
        ])
        self.comuni_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.comuni_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.comuni_table.setSelectionMode(QTableWidget.SingleSelection) # Importante per menu contestuale su una riga
        self.comuni_table.setAlternatingRowColors(True)
        header = self.comuni_table.horizontalHeader()
        header.setStretchLastSection(True)
        # Tutte le colonne possono essere ridimensionate manualmente
        for i in range(self.comuni_table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        self.comuni_table.setSortingEnabled(True)
        # self.comuni_table.itemDoubleClicked.connect(self.mostra_partite_del_comune) # Il doppio click può rimanere

        # Imposta la policy per il menu contestuale sulla tabella
        self.comuni_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.comuni_table.customContextMenuRequested.connect(self.apri_menu_contestuale_comune)
        # --- INIZIO MODIFICA ---
        # Collega il segnale di cambio selezione a una funzione che abilita/disabilita i pulsanti
        self.comuni_table.itemSelectionChanged.connect(self._update_action_buttons_state)
        # --- FINE MODIFICA ---

        comuni_layout.addWidget(self.comuni_table)

        action_buttons_layout = QHBoxLayout()
        
        # --- INIZIO MODIFICA: Creazione del nuovo pulsante ---
        self.btn_modifica_comune = QPushButton("Modifica Comune Selezionato")
        self.btn_modifica_comune.clicked.connect(self.azione_modifica_comune)
        self.btn_modifica_comune.setEnabled(False) # Inizia disabilitato
        action_buttons_layout.addWidget(self.btn_modifica_comune)
        # --- FINE MODIFICA ---
        self.btn_mostra_partite = QPushButton("Mostra Partite del Comune Selezionato")
        self.btn_mostra_partite.clicked.connect(self.azione_mostra_partite)
        action_buttons_layout.addWidget(self.btn_mostra_partite)

        self.btn_mostra_possessori = QPushButton("Mostra Possessori del Comune Selezionato")
        self.btn_mostra_possessori.clicked.connect(self.azione_mostra_possessori)
        action_buttons_layout.addWidget(self.btn_mostra_possessori)

        self.btn_mostra_localita = QPushButton("Mostra Località del Comune Selezionato")
        self.btn_mostra_localita.clicked.connect(self.azione_mostra_localita)
        action_buttons_layout.addWidget(self.btn_mostra_localita)
        
        action_buttons_layout.addStretch()
        comuni_layout.addLayout(action_buttons_layout)
        layout.addWidget(comuni_group)
        self.setLayout(layout)

         # Chiamata esplicita per caricare i dati
        self.logger.info("Chiamata a load_comuni_data() da __init__.")
        
    def load_data(self):
        """
        Metodo pubblico per caricare o ricaricare i dati dei comuni nella tabella.
        Questo metodo contiene la logica principale di popolamento.
        """
    def load_data(self):
        """
        Popola la tabella comuni richiamando i dati dal DB Manager in modo asincrono.
        """
        self.logger.info(">>> ESECUZIONE DI load_data in ElencoComuniWidget (Async)...")
        self.comuni_table.setSortingEnabled(False)
        self.comuni_table.setRowCount(0)

        # Disabilita temporaneamente la tabella e mostra il caricamento
        self.comuni_table.setEnabled(False)
        self.comuni_table.setRowCount(1)
        item = QTableWidgetItem("Caricamento in corso...")
        item.setTextAlignment(Qt.AlignCenter)
        self.comuni_table.setItem(0, 0, item)
        self.comuni_table.setSpan(0, 0, 1, self.comuni_table.columnCount())

        if not self.db_manager:
            self.logger.error("load_data chiamato ma self.db_manager è None!")
            return

        self.logger.info(">>> Avvio thread per db_manager.get_all_comuni_details()...")
        self.worker = GenericDBThread(self.db_manager.get_all_comuni_details)
        self.worker.finished_signal.connect(self._on_load_data_finished)
        self.worker.error_signal.connect(self._on_load_data_error)
        self.worker.start()

    def _on_load_data_finished(self, comuni_list):
        # Ripristina lo stato della tabella
        self.comuni_table.setEnabled(True)
        self.comuni_table.clearSpans()
        self.comuni_table.setRowCount(0)

        try:
            self.logger.info(f"--- RISULTATO RICEVUTO da db_manager: Tipo={type(comuni_list)}, Lunghezza={len(comuni_list) if comuni_list is not None else 'None'} ---")

            if not comuni_list:
                self.logger.warning("Nessun comune restituito dal DB manager per la visualizzazione.")
                self.comuni_table.setRowCount(1)
                item = QTableWidgetItem("Nessun comune trovato nel database.")
                item.setTextAlignment(Qt.AlignCenter)
                self.comuni_table.setItem(0, 0, item)
                self.comuni_table.setSpan(0, 0, 1, self.comuni_table.columnCount())
                return
                
            self.logger.info(f">>> Inizio ciclo FOR per popolare la tabella con {len(comuni_list)} elementi.")
            self.comuni_table.setRowCount(len(comuni_list))
            for row_idx, comune in enumerate(comuni_list):
                self.comuni_table.setItem(row_idx, 0, QTableWidgetItem(str(comune.id)))
                self.comuni_table.setItem(row_idx, 1, QTableWidgetItem(comune.nome_comune or ''))
                self.comuni_table.setItem(row_idx, 2, QTableWidgetItem(comune.codice_catastale or ''))
                self.comuni_table.setItem(row_idx, 3, QTableWidgetItem(comune.provincia or ''))
                data_ist = comune.data_istituzione
                self.comuni_table.setItem(row_idx, 4, QTableWidgetItem(str(data_ist) if data_ist else ''))
                data_soppr = comune.data_soppressione
                self.comuni_table.setItem(row_idx, 5, QTableWidgetItem(str(data_soppr) if data_soppr else ''))
                self.comuni_table.setItem(row_idx, 6, QTableWidgetItem(comune.note or ''))
            
            self.comuni_table.resizeColumnsToContents()
            self.logger.info(">>> Fine ciclo FOR.")

        except Exception as e:
            self._on_load_data_error(str(e))
        finally:
            self.comuni_table.setSortingEnabled(True)
            self.logger.info(">>> load_data terminato.")

    def _on_load_data_error(self, error_msg):
        self.comuni_table.setEnabled(True)
        self.comuni_table.clearSpans()
        self.logger.error(f"Errore imprevisto durante il popolamento della tabella comuni: {error_msg}")
        QMessageBox.critical(self, "Errore Caricamento Dati", f"Si è verificato un errore imprevisto: {error_msg}")
        self.comuni_table.setRowCount(0)

    def _load_data_on_first_show(self):
        """
        Metodo per il lazy loading. Soddisfa il contratto della classe base
        e chiama il nostro nuovo metodo di caricamento pubblico.
        """
        self.load_data()
    def _slot_modifica_dati_comune(self, comune_id: int):
        """
        Slot per il menu di modifica. Ora chiama il metodo corretto 'load_data'.
        """
        self.logger.info(f"Menu contestuale: richiesta modifica per comune ID {comune_id}")
        dialog = ModificaComuneDialog(self.db_manager, comune_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.logger.info(f"Dati del comune ID {comune_id} modificati. Aggiornamento lista comuni.")
            self.load_data()  # <-- CORRETTO
        else:
            self.logger.info(f"Modifica del comune ID {comune_id} annullata dall'utente.")

    def azione_modifica_comune(self):
        """Azione eseguita dal pulsante 'Modifica Comune Selezionato'."""
        selected_info = self._get_selected_comune_info_from_table()
        if selected_info:
            comune_id, _ = selected_info
            self._slot_modifica_dati_comune(comune_id)
        else:
            QMessageBox.information(self, "Nessuna Selezione", "Seleziona un comune dalla tabella per modificarlo.")

    def apply_filter(self):
        """Filtra le righe della tabella in base al testo inserito."""
        filter_text = self.filter_comuni_edit.text().strip().lower()
        for row in range(self.comuni_table.rowCount()):
            row_visible = False
            if not filter_text:  # Se il filtro è vuoto, mostra tutte le righe
                row_visible = True
            else:
                for col in range(self.comuni_table.columnCount()):
                    item = self.comuni_table.item(row, col)
                    if item and filter_text in item.text().lower():
                        row_visible = True
                        break
            self.comuni_table.setRowHidden(row, not row_visible)
        
        filter_text = self.filter_comuni_edit.text().strip().lower()
        for row in range(self.comuni_table.rowCount()):
            row_visible = False
            if not filter_text:
                row_visible = True
            else:
                for col in range(self.comuni_table.columnCount()):
                    item = self.comuni_table.item(row, col)
                    if item and filter_text in item.text().lower():
                        row_visible = True
                        break
            self.comuni_table.setRowHidden(row, not row_visible)
    
    def _get_comune_info_from_row(self, row: int) -> Optional[Tuple[int, str]]:
        """Helper per ottenere ID e nome del comune da una specifica riga."""
        try:
            comune_id_item = self.comuni_table.item(row, 0) # Colonna ID
            nome_comune_item = self.comuni_table.item(row, 1) # Colonna Nome Comune
            if comune_id_item and nome_comune_item and comune_id_item.text().isdigit():
                return int(comune_id_item.text()), nome_comune_item.text()
        except Exception as e:
            self.logger.error(f"Errore nel recuperare info comune dalla riga {row}: {e}")
        return None

    def _get_selected_comune_info_from_table(self) -> Optional[Tuple[int, str]]:
        """Helper per ottenere ID e nome del comune attualmente selezionato nella tabella."""
        current_row = self.comuni_table.currentRow()
        if current_row < 0:
            # Nessuna riga selezionata, ma il menu contestuale potrebbe essere stato attivato su una riga specifica
            # Questo metodo è più per i pulsanti che dipendono da una selezione esplicita.
            return None 
        return self._get_comune_info_from_row(current_row)
    
    

    def _get_selected_comune_info(self) -> Optional[Tuple[int, str]]:
        """Helper per ottenere ID e nome del comune correntemente selezionato nella tabella."""
        selected_items = self.comuni_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Nessuna Selezione",
                                "Seleziona un comune dalla tabella.")
            return None

        # selectedItems può dare più item se la selezione non è per riga
        row = self.comuni_table.currentRow()
        # currentRow è più sicuro per single row selection
        if row < 0:  # Nessuna riga effettivamente selezionata
            QMessageBox.warning(self, "Nessuna Selezione",
                                "Seleziona un comune dalla tabella.")
            return None

        try:
            comune_id_item = self.comuni_table.item(row, 0)  # Colonna ID
            nome_comune_item = self.comuni_table.item(
                row, 1)  # Colonna Nome Comune

            if comune_id_item and nome_comune_item:
                comune_id = int(comune_id_item.text())
                nome_comune = nome_comune_item.text()
                return comune_id, nome_comune
            else:
                QMessageBox.warning(
                    self, "Errore Selezione", "Impossibile recuperare ID o nome del comune dalla riga.")
                return None
        except ValueError:
            QMessageBox.warning(self, "Errore Dati",
                                "L'ID del comune non è un numero valido.")
            return None
        except Exception as e:
            logging.getLogger("CatastoGUI").error(
                f"Errore in _get_selected_comune_info: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Errore", f"Si è verificato un errore imprevisto: {e}")
            return None

    # Questo è per il doppio click
    def mostra_partite_del_comune(self, item: QTableWidgetItem):
        """Apre un dialogo con le partite del comune selezionato tramite doppio click."""
        # Questa funzione ora può usare l'helper se item è valido,
        # o mantenere la sua logica se item è il modo primario per ottenere la riga.
        if not item:
            return
        row = item.row()
        # ... (resto della logica di mostra_partite_del_comune come prima, usando 'row' per prendere ID e nome)
        try:
            comune_id_item = self.comuni_table.item(row, 0)
            nome_comune_item = self.comuni_table.item(row, 1)
            if comune_id_item and nome_comune_item:
                comune_id = int(comune_id_item.text())
                nome_comune = nome_comune_item.text()
                dialog = PartiteComuneDialog(
                    self.db_manager, comune_id, nome_comune, self)
                dialog.exec_()
        except ValueError:
            QMessageBox.warning(self, "Errore Dati",
                                "L'ID del comune non è un numero valido.")
        except Exception as e:
            logging.getLogger("CatastoGUI").error(
                f"Errore in mostra_partite_del_comune: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore", f"Errore: {e}")
    def apri_menu_contestuale_comune(self, position: QPoint):
        index = self.comuni_table.indexAt(position)
        if not index.isValid(): return
        row = index.row()
        comune_info = self._get_comune_info_from_row(row)
        if not comune_info: return
        comune_id_selezionato, nome_comune_selezionato = comune_info
        
        menu = QMenu(self.comuni_table)
        
       # ... (azioni esistenti per Visualizza Partite, Possessori, Località) ...
        action_vedi_partite = menu.addAction(QApplication.style().standardIcon(QStyle.SP_FileDialogContentsView), "Visualizza Partite")
        action_vedi_partite.triggered.connect(lambda: self._slot_vedi_partite_comune(comune_id_selezionato, nome_comune_selezionato))
        
        action_vedi_possessori = menu.addAction(QApplication.style().standardIcon(QStyle.SP_DirLinkIcon), "Visualizza Possessori")
        action_vedi_possessori.triggered.connect(lambda: self._slot_vedi_possessori_comune(comune_id_selezionato, nome_comune_selezionato))

        action_vedi_localita = menu.addAction(QApplication.style().standardIcon(QStyle.SP_DirHomeIcon), "Visualizza Località")
        action_vedi_localita.triggered.connect(lambda: self._slot_vedi_localita_comune(comune_id_selezionato, nome_comune_selezionato))
        
        menu.addSeparator()

        # --- NUOVA AZIONE PER MODIFICA COMUNE ---
         # Azione 4: Modifica Dati Comune (senza icona)
        action_modifica_comune = menu.addAction("Modifica Dati Comune")
        action_modifica_comune.triggered.connect(
            lambda: self._slot_modifica_dati_comune(comune_id_selezionato)
        )
        
        menu.exec_(self.comuni_table.viewport().mapToGlobal(position))

   
    def _slot_vedi_partite_comune(self, comune_id: int, nome_comune: str):
        self.logger.info(f"Azione: Visualizza partite per comune ID {comune_id} ('{nome_comune}')")
        dialog = PartiteComuneDialog(self.db_manager, comune_id, nome_comune, self)
        dialog.exec_()

    def _slot_vedi_possessori_comune(self, comune_id: int, nome_comune: str):
        self.logger.info(f"Azione: Visualizza possessori per comune ID {comune_id} ('{nome_comune}')")
        dialog = PossessoriComuneDialog(self.db_manager, comune_id, nome_comune, self)
        dialog.exec_()

    def _slot_vedi_localita_comune(self, comune_id: int, nome_comune: str):
        self.logger.info(f"Azione: Visualizza località per comune ID {comune_id} ('{nome_comune}')")
        dialog = LocalitaSelectionDialog(self.db_manager, comune_id, self, selection_mode=False)
        dialog.setWindowTitle(f"Località del Comune di {nome_comune}")
        dialog.exec_()

     # Metodi per i pulsanti esterni (possono riutilizzare gli slot)
    def azione_mostra_partite(self):
        selected_info = self._get_selected_comune_info_from_table()
        if selected_info:
            self._slot_vedi_partite_comune(selected_info[0], selected_info[1])
        else:
            QMessageBox.information(self, "Nessuna Selezione", "Seleziona un comune dalla tabella.")

    def azione_mostra_possessori(self):
        selected_info = self._get_selected_comune_info_from_table()
        if selected_info:
            self._slot_vedi_possessori_comune(selected_info[0], selected_info[1])
        else:
            QMessageBox.information(self, "Nessuna Selezione", "Seleziona un comune dalla tabella.")
            
    def azione_mostra_localita(self):
        selected_info = self._get_selected_comune_info_from_table()
        if selected_info:
            self._slot_vedi_localita_comune(selected_info[0], selected_info[1])
        else:
            QMessageBox.information(self, "Nessuna Selezione", "Seleziona un comune dalla tabella.")
            
    def _update_action_buttons_state(self):
        """Abilita o disabilita i pulsanti di azione in base alla selezione nella tabella."""
        has_selection = bool(self.comuni_table.selectedItems())
        self.btn_modifica_comune.setEnabled(has_selection)
        self.btn_mostra_partite.setEnabled(has_selection)
        self.btn_mostra_possessori.setEnabled(has_selection)
        self.btn_mostra_localita.setEnabled(has_selection)



class InserimentoComuneWidget(LazyLoadedWidget): # Eredita da LazyLoadedWidget
    comune_appena_inserito = pyqtSignal(int)

    def __init__(self, db_manager: 'CatastoDBManager', utente_attuale_info: Optional[Dict[str, Any]], parent=None):
        super().__init__(parent) # Chiama il costruttore della classe base
        self.db_manager = db_manager
        self.utente_attuale_info = utente_attuale_info
        # self.logger e self._data_loaded sono gestiti dalla classe base

        self._initUI()

    def _initUI(self):
        # ... (tutta la definizione della UI rimane la stessa)
        main_layout = QVBoxLayout(self)
        form_group = QGroupBox("Dati del Nuovo Comune")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        self.nome_comune_edit = QLineEdit()
        form_layout.addRow("Nome Comune (*):", self.nome_comune_edit)
        self.provincia_edit = QLineEdit("SV")
        self.provincia_edit.setMaxLength(100)
        form_layout.addRow("Provincia (*):", self.provincia_edit)
        self.regione_edit = QLineEdit()
        self.regione_edit.setMaxLength(100)
        form_layout.addRow("Regione (*):", self.regione_edit)
        self.codice_catastale_edit = QLineEdit()
        self.codice_catastale_edit.setPlaceholderText("Es. A123 (opzionale)")
        form_layout.addRow("Codice Catastale:", self.codice_catastale_edit)
        self.data_istituzione_check = QCheckBox("Imposta data istituzione")
        self.data_istituzione_edit = QDateEdit(calendarPopup=True)
        self.data_istituzione_edit.setDisplayFormat("yyyy-MM-dd")
        self.data_istituzione_edit.setEnabled(False)
        self.data_istituzione_check.toggled.connect(self.data_istituzione_edit.setEnabled)
        data_istituzione_layout = QHBoxLayout(); data_istituzione_layout.addWidget(self.data_istituzione_check); data_istituzione_layout.addWidget(self.data_istituzione_edit)
        form_layout.addRow("Data Istituzione:", data_istituzione_layout)
        self.data_soppressione_check = QCheckBox("Imposta data soppressione")
        self.data_soppressione_edit = QDateEdit(calendarPopup=True)
        self.data_soppressione_edit.setDisplayFormat("yyyy-MM-dd")
        self.data_soppressione_edit.setEnabled(False)
        self.data_soppressione_check.toggled.connect(self.data_soppressione_edit.setEnabled)
        data_soppressione_layout = QHBoxLayout(); data_soppressione_layout.addWidget(self.data_soppressione_check); data_soppressione_layout.addWidget(self.data_soppressione_edit)
        form_layout.addRow("Data Soppressione:", data_soppressione_layout)
        self.note_edit = QTextEdit()
        self.note_edit.setFixedHeight(60)
        form_layout.addRow("Note:", self.note_edit)
        self.periodo_combo = QComboBox()
        form_layout.addRow("Periodo Storico:", self.periodo_combo)
        main_layout.addWidget(form_group)
        button_layout = QHBoxLayout()
        self.submit_button = QPushButton("Inserisci Comune"); self.submit_button.clicked.connect(self.inserisci_comune)
        self.clear_button = QPushButton("Pulisci Campi"); self.clear_button.clicked.connect(self.pulisci_campi)
        button_layout.addStretch(); button_layout.addWidget(self.submit_button); button_layout.addWidget(self.clear_button)
        main_layout.addLayout(button_layout)
        main_layout.addStretch(1)

    def _load_data_on_first_show(self):
        """Metodo per il lazy loading, chiamato la prima volta."""
        self.logger.info("InserimentoComuneWidget: Esecuzione lazy loading dei periodi storici...")
        self._carica_elenco_periodi()

    def _carica_elenco_periodi(self):
        self.periodo_combo.clear()
        self.periodo_combo.addItem("--- Nessuno ---", None)
        try:
            periodi = self.db_manager.get_historical_periods()
            if periodi:
                for periodo in periodi:
                    display_text = f"{periodo.get('nome')} ({periodo.get('anno_inizio')} - {periodo.get('anno_fine', 'oggi')})"
                    self.periodo_combo.addItem(display_text, periodo.get('id'))
        except DBMError as e:
            QMessageBox.critical(self, "Errore Caricamento", f"Impossibile caricare l'elenco dei periodi storici:\n{e}")


    def pulisci_campi(self):
        self.nome_comune_edit.clear(); self.provincia_edit.setText("SV"); self.regione_edit.clear()
        self.codice_catastale_edit.clear(); self.note_edit.clear()
        
        # --- MODIFICA QUI: Resetta anche le checkbox ---
        self.data_istituzione_check.setChecked(False)
        self.data_soppressione_check.setChecked(False)
        # Il segnale 'toggled' disabiliterà automaticamente i QDateEdit
        
        self.periodo_combo.setCurrentIndex(0)
        self.nome_comune_edit.setFocus()

    def inserisci_comune(self):
        # Raccoglie i dati da tutti i campi
        nome_comune = self.nome_comune_edit.text().strip()
        provincia = self.provincia_edit.text().strip()
        regione = self.regione_edit.text().strip()
        codice_catastale = self.codice_catastale_edit.text().strip() or None
        note = self.note_edit.toPlainText().strip() or None
        periodo_id_val = self.periodo_combo.currentData()
        
        # --- MODIFICA QUI: Legge le date solo se le checkbox sono spuntate ---
        data_ist = self.data_istituzione_edit.date().toPyDate() if self.data_istituzione_check.isChecked() else None
        data_sopp = self.data_soppressione_edit.date().toPyDate() if self.data_soppressione_check.isChecked() else None

        if not nome_comune:
            QMessageBox.warning(self, "Dati Mancanti", "Il nome del comune è obbligatorio.")
            self.nome_comune_edit.setFocus()
            return
        if not provincia:
            QMessageBox.warning(self, "Dati Mancanti", "La provincia è obbligatoria.")
            self.provincia_edit.setFocus()
            return
        if not regione:
            QMessageBox.warning(self, "Dati Mancanti", "La regione è obbligatoria.")
            self.regione_edit.setFocus()
            return

        if data_ist and data_sopp and data_sopp < data_ist:
            QMessageBox.warning(self, "Date Non Valide", "La data di soppressione non può essere precedente alla data di istituzione.")
            self.data_soppressione_edit.setFocus()
            return

        username_per_log = self.utente_attuale_info.get('username', 'utente_sconosciuto') if self.utente_attuale_info else 'utente_sconosciuto'
        
        try:
            comune_id = self.db_manager.create_comune(
                nome_comune=nome_comune, provincia=provincia, regione=regione,
                periodo_id=periodo_id_val, codice_catastale=codice_catastale,
                data_istituzione=data_ist, data_soppressione=data_sopp, # Passa i valori corretti (o None)
                note=note, utente=username_per_log
            )
            QMessageBox.information(self, "Successo", f"Comune '{nome_comune}' inserito con ID: {comune_id}.")
            self.pulisci_campi()
            self.comune_appena_inserito.emit(comune_id)
        except (DBUniqueConstraintError, DBDataError, DBMError) as e:
            QMessageBox.critical(self, "Errore Inserimento", str(e))

# In gui_widgets.py, aggiungi questa nuova classe

