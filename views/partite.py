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
from workers import GenericDBThread
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

class RicercaPartiteWidget(QWidget):
    def __init__(self, db_manager, parent=None):
        super(RicercaPartiteWidget, self).__init__(parent)
        self.db_manager = db_manager
        
        # Variabili di stato per la paginazione (aggiungi nell'__init__)
        self.current_page = 1
        self.page_size = 50
        self.total_records = 0

        layout = QVBoxLayout()

        # Criteri di ricerca
        criteria_group = QGroupBox("Criteri di Ricerca")
        criteria_layout = QGridLayout()
        self.current_page = 1
        self.page_size = 50  # Numero di record per pagina
        self.total_records = 0
        # --- PANNELLO DI PAGINAZIONE (Definito qui, ma aggiunto dopo) ---
        self.pagination_layout = QHBoxLayout()
        
        self.btn_prev_page = QPushButton("◄ Precedente")
        self.btn_prev_page.clicked.connect(self._prev_page)
        self.btn_prev_page.setEnabled(False)
        
        self.lbl_page_info = QLabel("Pagina 1 di 1 (Totale: 0)")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        
        # Tendina per la scelta dinamica del limite
        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["25", "50", "100", "500"])
        self.combo_page_size.setCurrentText("50")
        self.combo_page_size.currentTextChanged.connect(self._change_page_size)
        
        self.btn_next_page = QPushButton("Successiva ►")
        self.btn_next_page.clicked.connect(self._next_page)
        self.btn_next_page.setEnabled(False)
        
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(self.btn_prev_page)
        self.pagination_layout.addWidget(self.lbl_page_info)
        self.pagination_layout.addSpacing(20)
        self.pagination_layout.addWidget(QLabel("Record per pagina:"))
        self.pagination_layout.addWidget(self.combo_page_size)
        self.pagination_layout.addWidget(self.btn_next_page)
        self.pagination_layout.addStretch()

        # Comune
        comune_label = QLabel("Comune:")
        self.comune_button = QPushButton("Seleziona Comune...")
        self.comune_button.clicked.connect(self.select_comune)
        self.comune_id = None
        self.comune_display = QLabel("Nessun comune selezionato")
        self.clear_comune_button = QPushButton("Cancella")
        self.clear_comune_button.clicked.connect(self.clear_comune)

        criteria_layout.addWidget(comune_label, 0, 0)
        criteria_layout.addWidget(self.comune_button, 0, 1)
        criteria_layout.addWidget(self.comune_display, 0, 2)
        criteria_layout.addWidget(self.clear_comune_button, 0, 3)

        # Numero partita
        numero_label = QLabel("Numero Partita:")
        self.numero_edit = QSpinBox()
        self.numero_edit.setMinimum(0)
        self.numero_edit.setMaximum(9999)
        self.numero_edit.setSpecialValueText("Qualsiasi")

        criteria_layout.addWidget(numero_label, 1, 0)
        criteria_layout.addWidget(self.numero_edit, 1, 1)

        # Possessore
        possessore_label = QLabel("Nome Possessore:")
        self.possessore_edit = QLineEdit()
        self.possessore_edit.setPlaceholderText("Qualsiasi possessore")

        criteria_layout.addWidget(possessore_label, 2, 0)
        criteria_layout.addWidget(self.possessore_edit, 2, 1, 1, 3)

        # Natura immobile
        natura_label = QLabel("Natura Immobile:")
        self.natura_edit = QLineEdit()
        self.natura_edit.setPlaceholderText("Qualsiasi natura immobile")

        criteria_layout.addWidget(natura_label, 3, 0)
        criteria_layout.addWidget(self.natura_edit, 3, 1, 1, 3)

        criteria_group.setLayout(criteria_layout)
        layout.addWidget(criteria_group)

        # Pulsante Ricerca
        search_button = QPushButton("Cerca Partite")
        search_button.clicked.connect(self.do_search)
        layout.addWidget(search_button)

        # Risultati
        results_group = QGroupBox("Risultati")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Comune", "Numero", "Tipo", "Stato"])
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        # Dettagli partita selezionata
        self.detail_button = QPushButton("Mostra Dettagli Partita")
        self.detail_button.clicked.connect(self.show_details)
        
        # Inserisci i controlli sotto la tabella
        results_layout.addWidget(self.results_table)
        results_layout.addLayout(self.pagination_layout)
        results_layout.addWidget(self.detail_button)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        self.setLayout(layout)
    def load_data(self):
        """Carica i dati della tabella applicando la paginazione e i filtri testuali in modo asincrono."""
        offset = (self.current_page - 1) * self.page_size
        
        comune_id = getattr(self, 'comune_id', None)
        numero_partita_val = self.numero_edit.value()
        numero_partita = numero_partita_val if numero_partita_val > 0 and self.numero_edit.text() != self.numero_edit.specialValueText() else None
        possessore = self.possessore_edit.text().strip() or None
        natura = self.natura_edit.text().strip() or None

        # Disabilita temporaneamente la tabella
        self.results_table.setEnabled(False)
        self.results_table.setRowCount(1)
        item = QTableWidgetItem("Caricamento in corso...")
        item.setTextAlignment(Qt.AlignCenter)
        self.results_table.setItem(0, 0, item)
        self.results_table.setSpan(0, 0, 1, self.results_table.columnCount())

        # Avvia il thread
        self.worker = GenericDBThread(
            self.db_manager.search_partite_paginate,
            limit=self.page_size,
            offset=offset,
            comune_id=comune_id,
            numero_partita=numero_partita,
            possessore=possessore,
            immobile_natura=natura
        )
        self.worker.finished_signal.connect(self._on_load_data_finished)
        self.worker.error_signal.connect(self._on_load_data_error)
        self.worker.start()

    def _on_load_data_finished(self, results):
        # Ripristina la tabella
        self.results_table.setEnabled(True)
        self.results_table.clearSpans()
        self.results_table.setRowCount(0)

        try:
            partite, totale = results
            self.total_records = totale
            
            if partite:
                self.results_table.setRowCount(len(partite))
                for row_idx, partita_data in enumerate(partite):
                    # Essendo i dati migrati a Dataclass (o ibridi), gestiamo safe access
                    id_partita = getattr(partita_data, 'id', partita_data.get('id', '')) if isinstance(partita_data, dict) else partita_data.id
                    comune_nome = getattr(partita_data, 'comune_nome', partita_data.get('comune_nome', '')) if isinstance(partita_data, dict) else partita_data.comune_nome
                    numero_partita = getattr(partita_data, 'numero_partita', partita_data.get('numero_partita', '')) if isinstance(partita_data, dict) else partita_data.numero_partita
                    suffisso = getattr(partita_data, 'suffisso_partita', partita_data.get('suffisso_partita')) if isinstance(partita_data, dict) else partita_data.suffisso_partita
                    tipo = getattr(partita_data, 'tipo', partita_data.get('tipo', '')) if isinstance(partita_data, dict) else partita_data.tipo
                    stato = getattr(partita_data, 'stato', partita_data.get('stato', '')) if isinstance(partita_data, dict) else getattr(partita_data, 'stato', '')

                    self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(id_partita)))
                    self.results_table.setItem(row_idx, 1, QTableWidgetItem(comune_nome or ''))
                    
                    num_partita_str = str(numero_partita)
                    if suffisso:
                        num_partita_str = f"{num_partita_str} {suffisso}"
                    self.results_table.setItem(row_idx, 2, QTableWidgetItem(num_partita_str))
                    self.results_table.setItem(row_idx, 3, QTableWidgetItem(tipo or ''))
                    self.results_table.setItem(row_idx, 4, QTableWidgetItem(stato or ''))
                self.results_table.resizeColumnsToContents()
            else:
                self.results_table.setRowCount(1)
                item = QTableWidgetItem("Nessuna partita trovata.")
                item.setTextAlignment(Qt.AlignCenter)
                self.results_table.setItem(0, 0, item)
                self.results_table.setSpan(0, 0, 1, self.results_table.columnCount())

            self._update_pagination_ui()

        except Exception as e:
            self._on_load_data_error(str(e))

    def _on_load_data_error(self, error_msg):
        self.results_table.setEnabled(True)
        self.results_table.clearSpans()
        self.results_table.setRowCount(0)
        logging.getLogger("CatastoGUI").error(f"Errore durante il caricamento paginato delle partite: {error_msg}")
        QMessageBox.critical(self, "Errore", f"Impossibile caricare i dati:\n{error_msg}")

    def _update_pagination_ui(self):
        """Aggiorna l'etichetta e disabilita/abilita i pulsanti in base ai limiti."""
        import math
        total_pages = max(1, math.ceil(self.total_records / self.page_size))
        
        self.lbl_page_info.setText(f"Pagina {self.current_page} di {total_pages} (Totale: {self.total_records})")
        
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < total_pages)

    def _prev_page(self):
        """Passa alla pagina precedente e ricarica."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def _next_page(self):
        """Passa alla pagina successiva e ricarica."""
        import math
        total_pages = math.ceil(self.total_records / self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_data()

    def _change_page_size(self, new_size_str):
        """Cambiando i record per pagina, si resetta alla pagina 1."""
        self.page_size = int(new_size_str)
        self.current_page = 1
        self.load_data()

    def select_comune(self):
        """Apre il selettore di comuni."""
        dialog = ComuneSelectionDialog(self.db_manager, self)
        result = dialog.exec_()

        if result == QDialog.Accepted and dialog.selected_comune_id:
            self.comune_id = dialog.selected_comune_id
            self.comune_display.setText(dialog.selected_comune_name)

    def clear_comune(self):
        """Cancella il comune selezionato."""
        self.comune_id = None
        self.comune_display.setText("Nessun comune selezionato")

    def do_search(self):
        """Reimposta la pagina a 1 ed esegue la ricerca."""
        self.current_page = 1
        self.load_data()
    def show_details(self):
        """Mostra i dettagli della partita selezionata."""
        # Ottiene l'ID della partita selezionata
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Attenzione",
                                "Seleziona una partita dalla lista.")
            return

        # Ottiene l'ID dalla prima colonna della riga selezionata
        row = selected_items[0].row()
        partita_id_item = self.results_table.item(row, 0)

        if partita_id_item and partita_id_item.text().isdigit():
            partita_id = int(partita_id_item.text())

            # Ottiene i dettagli della partita
            partita = self.db_manager.get_partita_details(partita_id)

            if partita:
                # Crea e mostra una finestra di dialogo per i dettagli
                details_dialog = PartitaDetailsDialog(partita, self)
                details_dialog.exec_()
            else:
                QMessageBox.warning(
                    self, "Errore", f"Non è stato possibile recuperare i dettagli della partita ID {partita_id}.")
        else:
            QMessageBox.warning(self, "Errore", "ID partita non valido.")
    # ======================================================================
    # ECCO LO SLOT CHE STAI CERCANDO DI POSIZIONARE
    # È un metodo della stessa classe che contiene il pulsante e la tabella.
    # ======================================================================
    @pyqtSlot()
    def apri_dialog_modifica_immobile(self):
        """
        Slot che viene eseguito quando si clicca il pulsante "Modifica".
        Apre il dialogo di modifica per l'immobile selezionato.
        """
        selected_rows = self.tabella_immobili.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Nessuna Selezione", "Per favore, seleziona un immobile dalla tabella da modificare.")
            return

        # Prendi la riga selezionata (anche se sono multiple, consideriamo solo la prima)
        riga_selezionata = selected_rows[0].row()
        
        # Recupera l'ID dell'immobile che abbiamo salvato in precedenza
        primo_item_nella_riga = self.tabella_immobili.item(riga_selezionata, 0)
        if not primo_item_nella_riga:
            QMessageBox.critical(self, "Errore", "Impossibile recuperare i dati dalla riga selezionata.")
            return
            
        immobile_id = primo_item_nella_riga.data(Qt.UserRole)

        # Crea e lancia il dialogo, passando tutti i parametri necessari
        dialog = ModificaImmobileDialog(
            db_manager=self.db_manager,
            immobile_id=immobile_id,
            comune_id_partita=self.comune_id_attuale, # Usa l'ID del comune di questo widget
            parent=self  # Il parent è questo widget stesso
        )

        # Esegui il dialogo. Il codice si ferma qui finché il dialogo non viene chiuso.
        # Usiamo exec_() per compatibilità con tutti i nomi
        if dialog.exec_() == QDialog.Accepted:
            # Se l'utente ha premuto "Salva" e le modifiche sono state salvate,
            # aggiorna la tabella per mostrare i nuovi dati.
            print("Modifiche salvate. Aggiornamento della vista in corso...")
            self.carica_dati_immobili()
        else:
            print("Operazione di modifica annullata dall'utente.")


class InserimentoPartitaWidget(QWidget):
    import_csv_requested = pyqtSignal()

    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(f"CatastoGUI.{self.__class__.__name__}")
        self._initUI()
        self.load_initial_data() # Carichiamo i dati necessari come i comuni

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        form_group = QGroupBox("Dati Nuova Partita")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        
        # --- CAMPI DEL FORM AGGIORNATI SECONDO LO SCHEMA ---
        self.comune_combo = QComboBox()
        form_layout.addRow("Comune (*):", self.comune_combo)

        self.numero_partita_spin = QSpinBox()
        self.numero_partita_spin.setRange(1, 999999)
        form_layout.addRow("Numero Partita (*):", self.numero_partita_spin)

        self.suffisso_edit = QLineEdit()
        self.suffisso_edit.setPlaceholderText("Es. bis, A (opzionale)")
        self.suffisso_edit.setMaxLength(20)
        form_layout.addRow("Suffisso Partita:", self.suffisso_edit)

        self.data_impianto_edit = QDateEdit(calendarPopup=True)
        self.data_impianto_edit.setDisplayFormat("yyyy-MM-dd")
        self.data_impianto_edit.setDate(QDate.currentDate())
        form_layout.addRow("Data Impianto (*):", self.data_impianto_edit)

        # NUOVO: Campo per data_chiusura (opzionale)
        self.data_chiusura_check = QCheckBox("Imposta data chiusura")
        self.data_chiusura_check.toggled.connect(self._toggle_data_chiusura)
        self.data_chiusura_edit = QDateEdit(calendarPopup=True)
        self.data_chiusura_edit.setDisplayFormat("yyyy-MM-dd")
        self.data_chiusura_edit.setEnabled(False) # Inizia disabilitato
        data_chiusura_layout = QHBoxLayout()
        data_chiusura_layout.addWidget(self.data_chiusura_check)
        data_chiusura_layout.addWidget(self.data_chiusura_edit)
        form_layout.addRow("Data Chiusura:", data_chiusura_layout)
        
        # CORRETTO: Campo per numero_provenienza (testuale)
        self.numero_provenienza_edit = QLineEdit()
        self.numero_provenienza_edit.setPlaceholderText("Numero o testo di riferimento (opzionale)")
        self.numero_provenienza_edit.setMaxLength(50)
        form_layout.addRow("Numero Provenienza:", self.numero_provenienza_edit)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(["principale", "secondaria"])
        form_layout.addRow("Tipo (*):", self.tipo_combo)

        self.stato_combo = QComboBox()
        self.stato_combo.addItems(["attiva", "inattiva"])
        form_layout.addRow("Stato (*):", self.stato_combo)

        # Pulsanti di azione per il form manuale
        btn_salva = QPushButton("Salva Nuova Partita")
        btn_salva.clicked.connect(self._salva_partita)
        btn_pulisci = QPushButton("Pulisci Campi")
        btn_pulisci.clicked.connect(self._pulisci_campi)
        manual_actions_layout = QHBoxLayout()
        manual_actions_layout.addStretch()
        manual_actions_layout.addWidget(btn_salva)
        manual_actions_layout.addWidget(btn_pulisci)
        form_layout.addRow(manual_actions_layout)
        main_layout.addWidget(form_group)

        # Sezione per l'importazione CSV
        import_group = QGroupBox("Importazione Massiva")
        # --- MODIFICA QUI: usiamo un QHBoxLayout ---
        import_layout = QHBoxLayout(import_group)
        
        import_button = QPushButton("📂 Importa Partite da File CSV...")
        import_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        import_button.clicked.connect(self.import_csv_requested.emit)

        # Creiamo il nuovo pulsante di aiuto
        info_button_partite = QPushButton("Info Formato")
        info_button_partite.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxQuestion))
        info_button_partite.clicked.connect(self._mostra_info_formato_csv)

        import_layout.addWidget(import_button)
        import_layout.addWidget(info_button_partite)
        import_layout.addStretch()
        # --- FINE MODIFICA ---
        main_layout.addWidget(import_group)

        main_layout.addStretch()
        self.setLayout(main_layout)
        
    def _mostra_info_formato_csv(self):
        """Mostra un dialogo con le informazioni sul formato CSV per le partite."""
        info_text = """
        <h3>Formato CSV per Importazione Partite</h3>
        <p>Il file CSV deve rispettare le seguenti regole:</p>
        <ul>
            <li>Utilizzare il punto e virgola (<b>;</b>) come delimitatore.</li>
            <li>La prima riga deve contenere le intestazioni delle colonne.</li>
        </ul>
        <p><b>Colonne Richieste (*):</b></p>
        <ul>
            <li><b>numero_partita</b> (*): Numero intero della partita.</li>
            <li><b>data_impianto</b> (*): Data in formato YYYY-MM-DD.</li>
            <li><b>stato</b> (*): Testo, 'attiva' o 'inattiva'.</li>
            <li><b>tipo</b> (*): Testo, 'principale' o 'secondaria'.</li>
        </ul>
        <p><b>Colonne Opzionali:</b></p>
        <ul>
            <li><b>suffisso_partita</b>: Suffisso testuale (es. A, bis).</li>
            <li><b>data_chiusura</b>: Data in formato YYYY-MM-DD.</li>
            <li><b>numero_provenienza</b>: Testo o numero di riferimento.</li>
        </ul>
        <hr>
        <p><b>Esempio di contenuto del file:</b></p>
        <pre style="background-color:#f0f0f0; padding:5px;"><code>numero_partita;suffisso_partita;data_impianto;stato;tipo
        1005;A;1980-05-20;attiva;principale
        1006;;1975-11-10;inattiva;principale</code></pre>
        """
        QMessageBox.information(self, "Guida Formato CSV - Partite", info_text)

    def load_initial_data(self):
        """Metodo per caricare i dati necessari, come la lista dei comuni."""
        try:
            comuni = self.db_manager.get_elenco_comuni_semplice()
            self.comune_combo.clear()
            self.comune_combo.addItem("--- Seleziona un comune ---", None)
            for id_comune, nome in comuni:
                self.comune_combo.addItem(nome, id_comune)
        except DBMError as e:
            QMessageBox.critical(self, "Errore Caricamento", f"Impossibile caricare l'elenco dei comuni:\n{e}")
    
    def _toggle_data_chiusura(self, checked):
        """Abilita o disabilita il QDateEdit per la data di chiusura."""
        self.data_chiusura_edit.setEnabled(checked)
        if checked:
            self.data_chiusura_edit.setDate(QDate.currentDate())
        else:
            self.data_chiusura_edit.setDate(QDate()) # Data nulla

    def _pulisci_campi(self):
        self.comune_combo.setCurrentIndex(0)
        self.numero_partita_spin.setValue(1)
        self.suffisso_edit.clear()
        self.data_impianto_edit.setDate(QDate.currentDate())
        self.data_chiusura_check.setChecked(False) # Disattiva e resetta la data chiusura
        self.numero_provenienza_edit.clear()
        self.tipo_combo.setCurrentIndex(0)
        self.stato_combo.setCurrentIndex(0)
        
    def _salva_partita(self):
        comune_id = self.comune_combo.currentData()
        if not comune_id:
            QMessageBox.warning(self, "Dati Mancanti", "È necessario selezionare un comune.")
            self.comune_combo.setFocus()
            return

        # Recupera i dati dai campi, inclusi i nuovi
        data_impianto = self.data_impianto_edit.date().toPyDate()
        data_chiusura = self.data_chiusura_edit.date().toPyDate() if self.data_chiusura_check.isChecked() else None
        numero_provenienza = self.numero_provenienza_edit.text().strip() or None

        # Validazione temporale prima di inviare al DB
        if data_chiusura and data_chiusura < data_impianto:
            QMessageBox.warning(self, "Date Non Valide", "La data di chiusura non può essere precedente alla data di impianto.")
            self.data_chiusura_edit.setFocus()
            return

        try:
            new_id = self.db_manager.create_partita(
                comune_id=comune_id,
                numero_partita=self.numero_partita_spin.value(),
                tipo=self.tipo_combo.currentText(),
                stato=self.stato_combo.currentText(),
                data_impianto=data_impianto,
                suffisso_partita=self.suffisso_edit.text().strip() or None,
                data_chiusura=data_chiusura,
                numero_provenienza=numero_provenienza
            )
            QMessageBox.information(self, "Successo", f"Partita creata con successo con ID: {new_id}.")
            self._pulisci_campi()
        except (DBMError, DBUniqueConstraintError, DBDataError) as e:
            QMessageBox.critical(self, "Errore Salvataggio", f"Impossibile salvare la partita:\n{e}")


class OperazioniPartitaWidget(QWidget):
    # Aggiungi questo __init__ se non c'è
    def __init__(self, db_manager: CatastoDBManager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"CatastoGUI.{self.__class__.__name__}") # AGGIUNGI QUESTA RIGA
        self.db_manager = db_manager
        self.selected_partita_id_source: Optional[int] = None
        self.selected_partita_comune_id_source: Optional[int] = None
        self.selected_partita_comune_nome_source: Optional[str] = None
        self.selected_immobile_id_transfer: Optional[int] = None
        self._pp_temp_nuovi_possessori: List[Dict[str, Any]] = []

        self.partita_destinazione_valida: bool = False

        self._initUI()

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # --- 1. Selezione Partita Sorgente (Comune a tutti i tab sottostanti) ---
        source_partita_group = QGroupBox("Selezione Partita Sorgente")
        source_partita_layout = QGridLayout(source_partita_group)

        source_partita_layout.addWidget(QLabel("ID Partita Sorgente:"), 0, 0)
        self.source_partita_id_spinbox = QSpinBox()
        self.source_partita_id_spinbox.setRange(
            1, 9999999)  # Range ampio per ID
        self.source_partita_id_spinbox.setToolTip(
            "Inserisci l'ID della partita o usa 'Cerca'")
        source_partita_layout.addWidget(self.source_partita_id_spinbox, 0, 1)

        self.btn_cerca_source_partita = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_FileDialogContentsView), " Cerca Partita...")
        self.btn_cerca_source_partita.setToolTip(
            "Cerca una partita esistente da usare come sorgente")
        self.btn_cerca_source_partita.clicked.connect(
            self._cerca_partita_sorgente)
        source_partita_layout.addWidget(self.btn_cerca_source_partita, 0, 2)

        # Pulsante per caricare la partita dall'ID inserito nello SpinBox
        self.btn_load_source_partita_from_id = QPushButton(QApplication.style().standardIcon(QStyle.SP_ArrowRight), " Carica da ID")
        self.btn_load_source_partita_from_id.setToolTip("Carica i dettagli della partita usando l'ID inserito")
        self.btn_load_source_partita_from_id.clicked.connect(self._load_partita_sorgente_from_spinbox)
        source_partita_layout.addWidget(self.btn_load_source_partita_from_id, 0, 3)

        self.source_partita_info_label = QLabel(
            "Nessuna partita sorgente selezionata.")
        self.source_partita_info_label.setWordWrap(True)
        self.source_partita_info_label.setStyleSheet(
            "QLabel { padding: 5px; background-color: #e8f0fe; border: 1px solid #d0e0ff; border-radius: 3px; min-height: 2em; }")
        source_partita_layout.addWidget(
            self.source_partita_info_label, 1, 0, 1, 4)  # Span su 4 colonne
        main_layout.addWidget(source_partita_group)

        # --- 2. QTabWidget per le diverse operazioni ---
        self.operazioni_tabs = QTabWidget()
        main_layout.addWidget(self.operazioni_tabs, 1)

        # --- Creazione dei Tab ---
        self._crea_tab_duplica_partita()
        self._crea_tab_trasferisci_immobile()
        self._crea_tab_passaggio_proprieta()

        self.setLayout(main_layout)

    def _crea_tab_duplica_partita(self):
        duplica_widget = QWidget()
        duplica_main_layout = QVBoxLayout(duplica_widget)
        duplica_group = QGroupBox("Opzioni per la Duplicazione")
        
        # Usiamo un GridLayout per un layout più pulito
        duplica_form_layout = QGridLayout(duplica_group)
        duplica_form_layout.setSpacing(10)

        # Riga 0: Nuovo Numero e Nuovo Suffisso
        duplica_form_layout.addWidget(QLabel("Nuovo Numero Partita (*):"), 0, 0)
        self.nuovo_numero_partita_spinbox = QSpinBox()
        self.nuovo_numero_partita_spinbox.setRange(1, 9999999)
        duplica_form_layout.addWidget(self.nuovo_numero_partita_spinbox, 0, 1)

        # --- CAMPO SUFFISSO AGGIUNTO QUI ---
        duplica_form_layout.addWidget(QLabel("Suffisso Nuova Partita (opz.):"), 0, 2)
        self.duplica_suffisso_partita_edit = QLineEdit()
        self.duplica_suffisso_partita_edit.setPlaceholderText("Es. bis, A")
        self.duplica_suffisso_partita_edit.setMaxLength(20)
        duplica_form_layout.addWidget(self.duplica_suffisso_partita_edit, 0, 3)
        
        # Colonna "elastica" per non allargare i campi
        duplica_form_layout.setColumnStretch(4, 1)

        # Riga 1 e 2: Checkbox
        self.duplica_mantieni_poss_check = QCheckBox("Mantieni Possessori Originali nella Nuova Partita")
        self.duplica_mantieni_poss_check.setChecked(True)
        duplica_form_layout.addWidget(self.duplica_mantieni_poss_check, 1, 0, 1, 4) # Span su 4 colonne

        self.duplica_mantieni_imm_check = QCheckBox("Copia gli Immobili Originali nella Nuova Partita")
        self.duplica_mantieni_imm_check.setChecked(False)
        duplica_form_layout.addWidget(self.duplica_mantieni_imm_check, 2, 0, 1, 4)

        # Riga 3: Pulsante
        self.btn_esegui_duplicazione = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogApplyButton), " Esegui Duplicazione")
        self.btn_esegui_duplicazione.clicked.connect(self._esegui_duplicazione_partita)
        duplica_form_layout.addWidget(self.btn_esegui_duplicazione, 3, 0, 1, 4, Qt.AlignRight)

        duplica_main_layout.addWidget(duplica_group)
        duplica_main_layout.addStretch(1)
        self.operazioni_tabs.addTab(duplica_widget, "Duplica Partita")

    def _crea_tab_trasferisci_immobile(self):
        transfer_widget = QWidget()
        transfer_main_layout = QVBoxLayout(transfer_widget)
        transfer_group = QGroupBox("Dettagli Trasferimento Immobile")
        transfer_form_layout = QFormLayout(transfer_group)
        transfer_form_layout.setSpacing(10)

        # ... (Tabella self.immobili_partita_sorgente_table e self.immobile_id_transfer_label come prima) ...
        transfer_form_layout.addRow(
            QLabel("Immobili nella Partita Sorgente (selezionarne uno):"))
        self.immobili_partita_sorgente_table = QTableWidget()
        # Rimuovere setColumnCount e setHorizontalHeaderLabels da qui se _carica_immobili_partita_sorgente lo fa dinamicamente
        self.immobili_partita_sorgente_table.setSelectionMode(
            QTableWidget.SingleSelection)
        self.immobili_partita_sorgente_table.setSelectionBehavior(
            QTableWidget.SelectRows)
        self.immobili_partita_sorgente_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.immobili_partita_sorgente_table.setFixedHeight(180)
        self.immobili_partita_sorgente_table.itemSelectionChanged.connect(
            self._immobile_sorgente_selezionato)
        transfer_form_layout.addRow(self.immobili_partita_sorgente_table)

        self.immobile_id_transfer_label = QLabel(
            "Nessun immobile selezionato dalla lista sottostante.")
        self.immobile_id_transfer_label.setStyleSheet(
            "font-style: italic; color: #555;")
        transfer_form_layout.addRow(self.immobile_id_transfer_label)

        # --- Modifiche per Partita Destinazione ---
        # Contenitore per spinbox e nuovo pulsante
        dest_partita_id_container = QWidget()
        dest_partita_id_layout = QHBoxLayout(dest_partita_id_container)
        dest_partita_id_layout.setContentsMargins(0, 0, 0, 0)
        dest_partita_id_layout.setSpacing(5)

        self.dest_partita_id_spinbox = QSpinBox()
        self.dest_partita_id_spinbox.setRange(1, 9999999)
        self.dest_partita_id_spinbox.setToolTip(
            "Inserisci l'ID della partita di destinazione o usa 'Cerca'")
        # Il '1' dà più stretch allo spinbox
        dest_partita_id_layout.addWidget(self.dest_partita_id_spinbox, 1)

        # NUOVO PULSANTE "Carica ID"
        self.btn_carica_dest_partita_da_id = QPushButton(
            "Carica ID")  # Testo breve, o icona SP_ArrowRight
        self.btn_carica_dest_partita_da_id.setToolTip(
            "Verifica e carica i dettagli della partita con l'ID inserito")
        self.btn_carica_dest_partita_da_id.clicked.connect(
            self._load_partita_destinazione_from_spinbox)
        dest_partita_id_layout.addWidget(self.btn_carica_dest_partita_da_id)

        self.btn_cerca_dest_partita = QPushButton(
            "Cerca...")  # Testo più breve
        self.btn_cerca_dest_partita.setToolTip(
            "Cerca una partita esistente da usare come destinazione")
        self.btn_cerca_dest_partita.clicked.connect(
            self._cerca_partita_destinazione)
        dest_partita_id_layout.addWidget(self.btn_cerca_dest_partita)

        transfer_form_layout.addRow(
            "ID Partita Destinazione (*):", dest_partita_id_container)
        # --- Fine Modifiche per Partita Destinazione ---

        self.dest_partita_info_label = QLabel(
            "Nessuna partita destinazione selezionata o verificata.")  # Testo iniziale modificato
        self.dest_partita_info_label.setStyleSheet(
            "font-style: italic; color: #555; padding: 3px; background-color: #E8F0FE; border: 1px solid #B0C4DE; border-radius: 3px;")
        self.dest_partita_info_label.setWordWrap(True)
        transfer_form_layout.addRow(self.dest_partita_info_label)

        self.transfer_registra_var_check = QCheckBox(
            "Registra Variazione Catastale per questo Trasferimento")
        self.transfer_registra_var_check.setChecked(
            True)  # Default a True potrebbe essere sensato
        transfer_form_layout.addRow(self.transfer_registra_var_check)

        self.btn_esegui_trasferimento = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogApplyButton), " Esegui Trasferimento Immobile")
        self.btn_esegui_trasferimento.clicked.connect(
            self._esegui_trasferimento_immobile)
        self.btn_esegui_trasferimento.setEnabled(False)  # Inizia disabilitato
        transfer_form_layout.addRow(self.btn_esegui_trasferimento)

        transfer_main_layout.addWidget(transfer_group)
        transfer_main_layout.addStretch(1)
        self.operazioni_tabs.addTab(transfer_widget, "Trasferisci Immobile")

        # Connetti i segnali per aggiornare lo stato del pulsante "Esegui Trasferimento"
        self.dest_partita_id_spinbox.valueChanged.connect(
            self._update_transfer_button_state_conditionally)
        self.immobili_partita_sorgente_table.itemSelectionChanged.connect(
            self._update_transfer_button_state_conditionally)

    def _crea_tab_passaggio_proprieta(self):
        # --- Tab Passaggio Proprietà (Voltura) ---
        passaggio_widget_main_container = QWidget()
        passaggio_tab_layout = QVBoxLayout(passaggio_widget_main_container)
        passaggio_scroll = QScrollArea(passaggio_widget_main_container)
        passaggio_scroll.setWidgetResizable(True)
        passaggio_scroll_content_widget = QWidget()
        passaggio_main_layout_scroll = QVBoxLayout(
            passaggio_scroll_content_widget)
        passaggio_main_layout_scroll.setSpacing(15)

        
        dati_atto_group = QGroupBox(
            "Dati Nuova Partita e Atto di Trasferimento")
        passaggio_form_layout = QFormLayout(dati_atto_group)
        passaggio_form_layout.setSpacing(10)

        # ... (campi esistenti prima di tipo atto/contratto) ...
        self.pp_nuova_partita_numero_spinbox = QSpinBox()
        self.pp_nuova_partita_numero_spinbox.setRange(1, 9999999)
        passaggio_form_layout.addRow(
            "Numero Nuova Partita (*):", self.pp_nuova_partita_numero_spinbox)
        self.pp_nuova_partita_comune_label = QLabel(
            "Il comune sarà lo stesso della partita sorgente.")
        passaggio_form_layout.addRow(
            "Comune Nuova Partita:", self.pp_nuova_partita_comune_label)
         # NUOVO CAMPO: Suffisso Partita per Passaggio Proprietà
        self.pp_suffisso_nuova_partita_edit = QLineEdit()
        self.pp_suffisso_nuova_partita_edit.setPlaceholderText("Es. bis, ter, A, B (opzionale)")
        self.pp_suffisso_nuova_partita_edit.setMaxLength(20)
        passaggio_form_layout.addRow("Suffisso Nuova Partita (opz.):", self.pp_suffisso_nuova_partita_edit) # AGGIUNTO
            

        self.pp_tipo_variazione_combo = QComboBox()
        tipi_variazione_validi = ['Vendita', 'Acquisto', 'Successione',
                                  'Variazione', 'Frazionamento', 'Divisione', 'Trasferimento', 'Altro']
        self.pp_tipo_variazione_combo.addItems(tipi_variazione_validi)
        if tipi_variazione_validi:
            self.pp_tipo_variazione_combo.setCurrentIndex(0)
        passaggio_form_layout.addRow(
            "Tipo Variazione (*):", self.pp_tipo_variazione_combo)

        self.pp_data_variazione_edit = QDateEdit(calendarPopup=True)
        self.pp_data_variazione_edit.setDisplayFormat("yyyy-MM-dd")
        self.pp_data_variazione_edit.setDate(QDate.currentDate())
        passaggio_form_layout.addRow(
            "Data Variazione (*):", self.pp_data_variazione_edit)
        
        # --- MODIFICA QUI: SOSTITUISCI QLineEdit con QComboBox ---
        self.pp_tipo_contratto_combo = QComboBox() # CAMBIATO IN COMBOBOX
        # Lista dei tipi di atto/contratto comuni
        tipi_atto_validi = [
            "Atto di Compravendita",
            "Dichiarazione di Successione",
            "Atto di Donazione",
            "Sentenza Giudiziale",
            "Atto di Divisione",
            "Verbale di Asta Pubblica",
            "Permuta",
            "Usucapione",
            "Altro Atto Pubblico",
            "Scrittura Privata"
        ]
        self.pp_tipo_contratto_combo.addItems(tipi_atto_validi)
        # Se vuoi un valore iniziale diverso o "Seleziona tipo..." puoi aggiungerlo
        self.pp_tipo_contratto_combo.insertItem(0, "Seleziona Tipo...") # Aggiunge un placeholder
        self.pp_tipo_contratto_combo.setCurrentIndex(0) # Seleziona il placeholder inizialmente
        
        passaggio_form_layout.addRow(
            "Tipo Atto/Contratto (*):", self.pp_tipo_contratto_combo) # USATO IL NUOVO WIDGET
        # --- FINE MODIFICA ---

        self.pp_data_contratto_edit = QDateEdit(calendarPopup=True)
        self.pp_data_contratto_edit.setDisplayFormat("yyyy-MM-dd")
        self.pp_data_contratto_edit.setDate(QDate.currentDate())
        passaggio_form_layout.addRow(
            "Data Atto/Contratto (*):", self.pp_data_contratto_edit)
        self.pp_notaio_edit = QLineEdit()
        passaggio_form_layout.addRow(
            "Notaio/Autorità Emittente:", self.pp_notaio_edit)
        self.pp_repertorio_edit = QLineEdit()
        passaggio_form_layout.addRow(
            "N. Repertorio/Protocollo:", self.pp_repertorio_edit)
        self.pp_note_variazione_edit = QTextEdit()
        self.pp_note_variazione_edit.setFixedHeight(60)
        passaggio_form_layout.addRow(
            "Note Variazione:", self.pp_note_variazione_edit)
        passaggio_main_layout_scroll.addWidget(dati_atto_group)

        immobili_transfer_group_pp = QGroupBox(
            "Immobili da Includere nella Nuova Partita")
        immobili_transfer_layout_pp = QVBoxLayout(immobili_transfer_group_pp)
        self.pp_trasferisci_tutti_immobili_check = QCheckBox(
            "Includi TUTTI gli immobili dalla partita sorgente")
        self.pp_trasferisci_tutti_immobili_check.setChecked(True)
        self.pp_trasferisci_tutti_immobili_check.toggled.connect(
            self._toggle_selezione_immobili_pp)
        immobili_transfer_layout_pp.addWidget(
            self.pp_trasferisci_tutti_immobili_check)
        self.pp_immobili_da_selezionare_table = QTableWidget()
        self.pp_immobili_da_selezionare_table.setColumnCount(4)
        self.pp_immobili_da_selezionare_table.setHorizontalHeaderLabels(
            ["Sel.", "ID Imm.", "Natura", "Località"])
        self.pp_immobili_da_selezionare_table.setSelectionMode(
            QTableWidget.NoSelection)
        self.pp_immobili_da_selezionare_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.pp_immobili_da_selezionare_table.setFixedHeight(150)
        self.pp_immobili_da_selezionare_table.setVisible(False)
        immobili_transfer_layout_pp.addWidget(
            self.pp_immobili_da_selezionare_table)
        passaggio_main_layout_scroll.addWidget(immobili_transfer_group_pp)

        nuovi_poss_group = QGroupBox("Nuovi Possessori per la Nuova Partita")
        nuovi_poss_layout = QVBoxLayout(nuovi_poss_group)
        self.pp_nuovi_possessori_table = QTableWidget()
        self.pp_nuovi_possessori_table.setColumnCount(4)
        self.pp_nuovi_possessori_table.setHorizontalHeaderLabels(
            ["ID Poss.", "Nome Completo", "Titolo (*)", "Quota"])
        self.pp_nuovi_possessori_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.pp_nuovi_possessori_table.setSelectionMode(
            QTableWidget.SingleSelection)
        self.pp_nuovi_possessori_table.horizontalHeader(
        ).setSectionResizeMode(QHeaderView.ResizeToContents)
        self.pp_nuovi_possessori_table.horizontalHeader().setStretchLastSection(True)
        self.pp_nuovi_possessori_table.setFixedHeight(150)
        nuovi_poss_layout.addWidget(self.pp_nuovi_possessori_table)
        nuovi_poss_buttons_layout = QHBoxLayout()
        self.pp_btn_aggiungi_nuovo_possessore = QPushButton(
            # O QStyle.SP_FileLinkIcon o QStyle.SP_ToolBarAddButton
            QApplication.style().standardIcon(QStyle.SP_FileDialogNewFolder),
            " Aggiungi Possessore..."
        )
        self.pp_btn_aggiungi_nuovo_possessore.setToolTip(
            "Aggiungi un nuovo possessore (o seleziona uno esistente) alla lista per la nuova partita")
        self.pp_btn_aggiungi_nuovo_possessore.clicked.connect(
            self._pp_aggiungi_nuovo_possessore)
        nuovi_poss_buttons_layout.addWidget(
            self.pp_btn_aggiungi_nuovo_possessore)

       # CORREZIONE ICONA QUI:
        self.pp_btn_rimuovi_nuovo_possessore = QPushButton(
            # O QStyle.SP_DialogDiscardButton
            QApplication.style().standardIcon(QStyle.SP_TrashIcon),
            " Rimuovi Selezionato"
        )
        self.pp_btn_rimuovi_nuovo_possessore = QPushButton(QApplication.style(
            # Esempio Icona
        ).standardIcon(QStyle.SP_TrashIcon), " Rimuovi Selezionato")
        self.pp_btn_rimuovi_nuovo_possessore.clicked.connect(
            self._pp_rimuovi_nuovo_possessore_selezionato)
        nuovi_poss_buttons_layout.addWidget(
            self.pp_btn_rimuovi_nuovo_possessore)
        nuovi_poss_buttons_layout.addStretch()
        nuovi_poss_layout.addLayout(nuovi_poss_buttons_layout)
        passaggio_main_layout_scroll.addWidget(nuovi_poss_group)

        self.pp_btn_esegui_passaggio = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogApplyButton), " Esegui Passaggio Proprietà")
        self.pp_btn_esegui_passaggio.clicked.connect(
            self._esegui_passaggio_proprieta)
        passaggio_main_layout_scroll.addWidget(
            self.pp_btn_esegui_passaggio, 0, Qt.AlignRight)
        passaggio_main_layout_scroll.addStretch(1)

        passaggio_scroll.setWidget(passaggio_scroll_content_widget)
        passaggio_tab_layout.addWidget(passaggio_scroll)
        self.operazioni_tabs.addTab(
            passaggio_widget_main_container, "Passaggio Proprietà (Voltura)")

    # --- Metodi Helper e Handler ---

    def _load_partita_destinazione_from_spinbox(self):
        partita_id_dest = self.dest_partita_id_spinbox.value()
        self.dest_partita_info_label.setText("Verifica ID partita destinazione...")
        self.partita_destinazione_valida = False

        if partita_id_dest <= 0:
            self.dest_partita_info_label.setText("<font color='red'>ID partita destinazione non valido.</font>")
            self._update_transfer_button_state_conditionally()
            return

        partita_details = self.db_manager.get_partita_details(partita_id_dest)

        if partita_details:
            stato = partita_details.stato
            comune = partita_details.comune_nome or 'N/D'
            numero = partita_details.numero_partita
            # Usa il suffisso, se non c'è stringa vuota
            suffisso = partita_details.suffisso_partita
            suffisso_display = f" (suffisso: {suffisso})" if suffisso else ""

            if self.selected_partita_id_source is not None and partita_id_dest == self.selected_partita_id_source:
                self.dest_partita_info_label.setText(f"<font color='red'>Errore: La destinazione non può essere uguale alla sorgente.</font>")
                self.partita_destinazione_valida = False
            elif stato != 'attiva':
                self.dest_partita_info_label.setText(f"<font color='red'>Errore: La partita N.{numero}{suffisso_display} non è attiva.</font>")
                self.partita_destinazione_valida = False
            else:
                self.dest_partita_info_label.setText(f"Destinazione: N. {numero}{suffisso_display} (Comune: {comune}, ID: {partita_id_dest})")
                self.partita_destinazione_valida = True
        else:
            self.dest_partita_info_label.setText(f"<font color='red'>Partita destinazione con ID {partita_id_dest} non trovata.</font>")
            self.partita_destinazione_valida = False

        self._update_transfer_button_state_conditionally()

    def _cerca_partita_destinazione(self):
        dialog = PartitaSearchDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_partita_id:
            selected_id = dialog.selected_partita_id
            self.dest_partita_id_spinbox.setValue(
                selected_id)  # Imposta lo spinbox
            # Chiama la logica di caricamento e validazione
            self._load_partita_destinazione_from_spinbox()
        # else: Non fare nulla se l'utente annulla, la label non cambia o è già impostata
        # self._update_transfer_button_state_conditionally() # _load_partita_destinazione_from_spinbox lo fa già

    def _update_transfer_button_state_conditionally(self):
        """Abilita il pulsante 'Esegui Trasferimento' solo se tutte le condizioni sono soddisfatte."""
        is_enabled = False
        immobile_selezionato = self.selected_immobile_id_transfer is not None
        # Verifica solo che un ID sia nello spinbox
        id_partita_dest_inserito = self.dest_partita_id_spinbox.value() > 0

        partita_dest_diversa_da_sorgente = True
        if self.selected_partita_id_source is not None and id_partita_dest_inserito:
            partita_dest_diversa_da_sorgente = (
                self.dest_partita_id_spinbox.value() != self.selected_partita_id_source)

        if immobile_selezionato and id_partita_dest_inserito and \
           self.partita_destinazione_valida and partita_dest_diversa_da_sorgente:
            is_enabled = True

        self.btn_esegui_trasferimento.setEnabled(is_enabled)

        # Aggiorna tooltip per guidare l'utente
        if not is_enabled:
            reasons = []
            if not immobile_selezionato:
                reasons.append(
                    "selezionare un immobile dalla tabella sorgente")
            if not id_partita_dest_inserito:
                reasons.append(
                    "inserire un ID per la partita destinazione e caricarne i dettagli")
            elif not self.partita_destinazione_valida:
                reasons.append(
                    "la partita destinazione non è valida o non è attiva (controllare messaggio sopra)")
            if not partita_dest_diversa_da_sorgente and id_partita_dest_inserito:
                reasons.append(
                    "la partita destinazione deve essere diversa dalla sorgente")

            if reasons:
                self.btn_esegui_trasferimento.setToolTip(
                    "Per abilitare: " + " e ".join(reasons) + ".")
            # Caso in cui tutti i singoli check passano ma la combinazione logica di is_enabled è False (improbabile con la logica sopra)
            else:
                self.btn_esegui_trasferimento.setToolTip(
                    "Verificare tutti i campi per il trasferimento.")
        else:
            self.btn_esegui_trasferimento.setToolTip(
                "Esegue il trasferimento dell'immobile selezionato alla partita destinazione.")

    # Modifichi anche _immobile_sorgente_selezionato per chiamare l'aggiornamento del pulsante

    def _immobile_sorgente_selezionato(self):
        # ... (logica esistente per impostare self.selected_immobile_id_transfer e self.immobile_id_transfer_label)
        selected_rows = self.immobili_partita_sorgente_table.selectionModel().selectedRows()
        if not selected_rows:
            self.selected_immobile_id_transfer = None
            self.immobile_id_transfer_label.setText(
                "Nessun immobile selezionato dalla lista.")
        else:
            row = selected_rows[0].row()
            # ID Imm.
            id_item = self.immobili_partita_sorgente_table.item(row, 0)
            natura_item = self.immobili_partita_sorgente_table.item(
                row, 1)  # Natura

            if id_item and id_item.text().isdigit():
                self.selected_immobile_id_transfer = int(id_item.text())
                natura_text = natura_item.text() if natura_item else "N/D"
                self.immobile_id_transfer_label.setText(
                    f"Immobile da trasferire: ID {self.selected_immobile_id_transfer} (Natura: {natura_text})")
            else:
                self.selected_immobile_id_transfer = None
                self.immobile_id_transfer_label.setText(
                    "Selezione immobile non valida.")

        self._update_transfer_button_state_conditionally()

    def _cerca_partita_sorgente(self):
        """Apre il dialogo per cercare una partita sorgente."""
        # ... (suo codice esistente)
        dialog = PartitaSearchDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_partita_id:
            self.source_partita_id_spinbox.setValue(
                dialog.selected_partita_id)  # Imposta lo spinbox
            self.selected_partita_id_source = dialog.selected_partita_id   # Imposta l'ID
            self._aggiorna_info_partita_sorgente()  # Carica i dettagli
        
            if not self.selected_partita_id_source:  # Resetta solo se non c'era già una selezione
                self.source_partita_info_label.setText(
                    "Nessuna partita sorgente selezionata.")
                self.selected_partita_comune_id_source = None
                self.selected_partita_comune_nome_source = None
                if hasattr(self, 'immobili_partita_sorgente_table'):
                    self.immobili_partita_sorgente_table.setRowCount(0)
                if hasattr(self, 'pp_immobili_da_selezionare_table'):
                    self.pp_immobili_da_selezionare_table.setRowCount(0)
                if hasattr(self, 'pp_nuova_partita_comune_label'):
                    self.pp_nuova_partita_comune_label.setText(
                        "Il comune sarà lo stesso della partita sorgente.")

    def _aggiorna_info_partita_sorgente(self):
        """
        Recupera e visualizza i dettagli della partita sorgente (selected_partita_id_source)
        e popola le UI dipendenti (es. tabella immobili per trasferimento).
        """
        # Pulisci le UI dipendenti prima di caricarne di nuove o se non c'è sorgente
        if hasattr(self, 'immobili_partita_sorgente_table'):
            self.immobili_partita_sorgente_table.setRowCount(0)
            if hasattr(self, 'selected_immobile_id_transfer'):
                self.selected_immobile_id_transfer = None
            if hasattr(self, 'immobile_id_transfer_label'):
                self.immobile_id_transfer_label.setText(
                    "Nessun immobile selezionato.")

        if hasattr(self, 'pp_immobili_da_selezionare_table'):  # Per il tab Passaggio Proprietà
            self.pp_immobili_da_selezionare_table.setRowCount(0)

        if hasattr(self, 'pp_nuova_partita_comune_label'):
            self.pp_nuova_partita_comune_label.setText(
                "Il comune sarà lo stesso della partita sorgente.")

        if self.selected_partita_id_source and self.selected_partita_id_source > 0:
            partita_details = self.db_manager.get_partita_details(
                self.selected_partita_id_source)
            if partita_details:
                self.selected_partita_comune_id_source = partita_details.comune_id
                self.selected_partita_comune_nome_source = partita_details.comune_nome

                self.source_partita_info_label.setText(
                    f"Partita Sorgente: N. {partita_details.numero_partita} "
                    f"(Comune: {self.selected_partita_comune_nome_source} [ID: {self.selected_partita_comune_id_source}], Partita ID: {self.selected_partita_id_source})"
                )
                immobili = partita_details.immobili

                # Popola la tabella immobili nel tab "Trasferisci Immobile"
                if hasattr(self, '_carica_immobili_partita_sorgente'):
                    self._carica_immobili_partita_sorgente(immobili)

                # Popola la tabella immobili nel tab "Passaggio Proprietà"
                if hasattr(self, '_pp_carica_immobili_per_selezione'):
                    self._pp_carica_immobili_per_selezione(immobili)

                # Aggiorna etichetta comune nel tab "Passaggio Proprietà"
                if hasattr(self, 'pp_nuova_partita_comune_label') and self.selected_partita_comune_nome_source and self.selected_partita_comune_id_source:
                    self.pp_nuova_partita_comune_label.setText(
                        f"{self.selected_partita_comune_nome_source} (ID: {self.selected_partita_comune_id_source})"
                    )
            else:  # Partita non trovata
                self.source_partita_info_label.setText(
                    f"Partita sorgente con ID {self.selected_partita_id_source} non trovata o errore nel recupero dettagli.")
                self.selected_partita_id_source = None  # Resetta se non trovata
                self.selected_partita_comune_id_source = None
                self.selected_partita_comune_nome_source = None
        else:  # Nessun ID sorgente valido
            self.source_partita_info_label.setText(
                "Nessuna partita sorgente selezionata o ID non valido.")
            self.selected_partita_id_source = None
            self.selected_partita_comune_id_source = None
            self.selected_partita_comune_nome_source = None

        # Aggiorna lo stato dei pulsanti che dipendono dalla selezione della partita sorgente/destinazione
        if hasattr(self, '_update_transfer_button_state_conditionally'):
            self._update_transfer_button_state_conditionally()
        # Aggiungere chiamate simili per aggiornare lo stato dei pulsanti negli altri sotto-tab se necessario

    def _esegui_duplicazione_partita(self):
        self.logger.info("Avvio _esegui_duplicazione_partita.")

        if self.selected_partita_id_source is None:
            QMessageBox.warning(self, "Selezione Mancante", "Selezionare una partita sorgente prima di duplicare.")
            return
        if self.selected_partita_comune_id_source is None:
            QMessageBox.warning(self, "Errore Interno", "Comune della partita sorgente non determinato.")
            return

        nuovo_numero = self.nuovo_numero_partita_spinbox.value()
        # --- LETTURA VALORE SUFFISSO ---
        nuovo_suffisso = self.duplica_suffisso_partita_edit.text().strip() or None

        if nuovo_numero <= 0:
            QMessageBox.warning(self, "Dati Non Validi", "Il nuovo numero di partita deve essere un valore positivo.")
            return

        # --- VERIFICA UNICITÀ CON SUFFISSO ---
        try:
            existing_partita = self.db_manager.search_partite(
                comune_id=self.selected_partita_comune_id_source,
                numero_partita=nuovo_numero,
                suffisso_partita=nuovo_suffisso
            )
            if existing_partita:
                suffisso_display = f" (suffisso: {nuovo_suffisso})" if nuovo_suffisso else ""
                QMessageBox.warning(self, "Errore Duplicazione",
                                    f"Esiste già una partita con il numero {nuovo_numero}{suffisso_display} "
                                    f"nel comune '{self.selected_partita_comune_nome_source}'.")
                return
        except DBMError as e:
            QMessageBox.critical(self, "Errore Verifica Partita", f"Errore durante la verifica del numero partita:\n{str(e)}")
            return
        
        mant_poss = self.duplica_mantieni_poss_check.isChecked()
        mant_imm = self.duplica_mantieni_imm_check.isChecked()
        
        try:
            # --- CHIAMATA AL DB MANAGER CON SUFFISSO ---
            success = self.db_manager.duplicate_partita(
                partita_id_originale=self.selected_partita_id_source,
                nuovo_numero_partita=nuovo_numero,
                mantenere_possessori=mant_poss,
                mantenere_immobili=mant_imm,
                nuovo_suffisso=nuovo_suffisso
            )
            
            if success:
                suffisso_display = f" (suffisso: {nuovo_suffisso})" if nuovo_suffisso else ""
                QMessageBox.information(self, "Successo",
                                        f"Partita ID {self.selected_partita_id_source} duplicata con successo "
                                        f"in una nuova partita N. {nuovo_numero}{suffisso_display}.")
                self.nuovo_numero_partita_spinbox.setValue(1)
                self.duplica_suffisso_partita_edit.clear()
            else:
                QMessageBox.critical(self, "Errore Operazione", "La duplicazione della partita non è stata completata.")
        except DBMError as e:
            QMessageBox.critical(self, "Errore Duplicazione", f"Impossibile duplicare la partita:\n{str(e)}")
        except Exception as e_gen:
            self.logger.critical(f"Errore imprevisto durante la duplicazione: {e_gen}", exc_info=True)
            QMessageBox.critical(self, "Errore Imprevisto", f"Errore di sistema:\n{str(e_gen)}")


    def _carica_immobili_partita_sorgente(self, immobili_data: List[Dict[str, Any]]):
        table = self.immobili_partita_sorgente_table

        # --- NUOVE INTESTAZIONI ---
        nuove_colonne = ["ID Imm.", "Natura",
                         "Classificazione", "Consistenza", "Località Completa"]
        table.setColumnCount(len(nuove_colonne))
        table.setHorizontalHeaderLabels(nuove_colonne)
        # --- FINE NUOVE INTESTAZIONI ---

        table.setRowCount(0)
        table.setSortingEnabled(False)
        self.selected_immobile_id_transfer = None
        self.immobile_id_transfer_label.setText(
            "Nessun immobile selezionato dalla lista sottostante.")

        if immobili_data:
            table.setRowCount(len(immobili_data))
            for row, immobile in enumerate(immobili_data):
                col = 0
                table.setItem(row, col, QTableWidgetItem(
                    str(immobile.get('id', 'N/D'))))
                col += 1
                table.setItem(row, col, QTableWidgetItem(
                    immobile.get('natura', 'N/D')))
                col += 1

                # --- NUOVE COLONNE ---
                table.setItem(row, col, QTableWidgetItem(
                    immobile.get('classificazione', 'N/D')))
                col += 1
                table.setItem(row, col, QTableWidgetItem(
                    immobile.get('consistenza', 'N/D')))
                col += 1
                # --- FINE NUOVE COLONNE ---

                loc_nome = immobile.get('localita_nome', '')
                loc_tipo = immobile.get('localita_tipo', '')
                loc_text = loc_nome
                if loc_tipo:
                    loc_text += f" ({loc_tipo})"
                table.setItem(row, col, QTableWidgetItem(loc_text.strip()))
                col += 1

            table.resizeColumnsToContents()  # Adatta dopo aver popolato
            # O imposta larghezze specifiche per una migliore leggibilità
            # table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
            # table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive) # Natura
            # table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # Località
        else:
            table.setRowCount(1)
            no_imm_item = QTableWidgetItem(
                "Nessun immobile associato a questa partita sorgente.")
            no_imm_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, 0, no_imm_item)
            # Occupa tutte le colonne
            table.setSpan(0, 0, 1, table.columnCount())

        table.setSortingEnabled(True)

    def _esegui_trasferimento_immobile(self):
        if self.selected_immobile_id_transfer is None:
            QMessageBox.warning(self, "Selezione Mancante",
                                "Selezionare un immobile dalla partita sorgente da trasferire.")
            return
        id_partita_dest = self.dest_partita_id_spinbox.value()
        if id_partita_dest <= 0:
            QMessageBox.warning(
                self, "Dati Non Validi", "Selezionare o inserire un ID partita di destinazione valido.")
            return
        if self.selected_partita_id_source is not None and id_partita_dest == self.selected_partita_id_source:
            QMessageBox.warning(self, "Operazione Non Valida",
                                "La partita di destinazione non può essere uguale alla partita sorgente.")
            return

        registra_var = self.transfer_registra_var_check.isChecked()
        try:
            success = self.db_manager.transfer_immobile(
                self.selected_immobile_id_transfer, id_partita_dest, registra_var
            )
            if success:
                QMessageBox.information(self, "Successo",
                                        f"Immobile ID {self.selected_immobile_id_transfer} trasferito "
                                        f"alla partita ID {id_partita_dest} con successo.")
                self._aggiorna_info_partita_sorgente()  # Ricarica immobili sorgente
                self.dest_partita_id_spinbox.setValue(
                    self.dest_partita_id_spinbox.minimum())
                self.dest_partita_info_label.setText(
                    "Nessuna partita destinazione selezionata.")
                self.transfer_registra_var_check.setChecked(False)
        except DBMError as e:
            QMessageBox.critical(self, "Errore Trasferimento",
                                 f"Errore durante il trasferimento dell'immobile:\n{str(e)}")
        except Exception as e_gen:
            logging.getLogger("CatastoGUI").critical(
                f"Errore imprevisto trasferimento immobile: {e_gen}", exc_info=True)
            QMessageBox.critical(self, "Errore Imprevisto",
                                 f"Errore:\n{type(e_gen).__name__}: {str(e_gen)}")

    def _toggle_selezione_immobili_pp(self, checked: bool):
        if hasattr(self, 'pp_immobili_da_selezionare_table'):
            self.pp_immobili_da_selezionare_table.setVisible(not checked)
            if checked and hasattr(self, '_pp_pulisci_selezione_immobili_specifici'):
                self._pp_pulisci_selezione_immobili_specifici()

    def _pp_pulisci_selezione_immobili_specifici(self):
        if hasattr(self, 'pp_immobili_da_selezionare_table'):
            table = self.pp_immobili_da_selezionare_table
            for row in range(table.rowCount()):
                cell_widget = table.cellWidget(row, 0)
                if isinstance(cell_widget, QCheckBox):
                    cell_widget.setChecked(False)

    def _pp_carica_immobili_per_selezione(self, immobili_data: List[Dict[str, Any]]):
        if not hasattr(self, 'pp_immobili_da_selezionare_table'):
            logging.getLogger("CatastoGUI").error(
                "Tabella 'pp_immobili_da_selezionare_table' non inizializzata.")
            return
        table = self.pp_immobili_da_selezionare_table
        table.setRowCount(0)
        table.setSortingEnabled(False)
        if immobili_data:
            table.setRowCount(len(immobili_data))
            for row, immobile in enumerate(immobili_data):
                chk = QCheckBox()
                chk.setProperty("immobile_id", immobile.get('id'))
                table.setCellWidget(row, 0, chk)
                id_i = QTableWidgetItem(str(immobile.get('id', 'N/D')))
                id_i.setFlags(id_i.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, id_i)
                nat_i = QTableWidgetItem(immobile.get('natura', 'N/D'))
                nat_i.setFlags(nat_i.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 2, nat_i)
                loc_t = immobile.get('localita_nome', '')
                loc_i = QTableWidgetItem(loc_t)
                loc_i.setFlags(loc_i.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 3, loc_i)
            # Configurazione resize mode per le colonne
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # Checkbox
            table.setColumnWidth(0, 35)
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeToContents)  # ID
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Natura
            table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.Stretch)  # Località
        else:
            table.setRowCount(1)
            msg_item = QTableWidgetItem(
                "Nessun immobile disponibile nella partita sorgente per la selezione.")
            msg_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, 0, msg_item)
            table.setSpan(0, 0, 1, table.columnCount())
        table.setSortingEnabled(True)

    def _pp_aggiungi_nuovo_possessore(self):
        if not self.selected_partita_comune_id_source:
            QMessageBox.warning(
                self, "Comune Mancante", "Selezionare una partita sorgente per determinare il comune di riferimento dei nuovi possessori.")
            return
        dialog_sel_poss = PossessoreSelectionDialog(
            self.db_manager, self.selected_partita_comune_id_source, self)
        dialog_sel_poss.setWindowTitle(
            "Seleziona o Crea Nuovo Possessore per Nuova Partita")
        possessore_info_completa_sel = None
        if dialog_sel_poss.exec_() == QDialog.Accepted:
            if hasattr(dialog_sel_poss, 'selected_possessore') and dialog_sel_poss.selected_possessore:
                poss_id_sel = dialog_sel_poss.selected_possessore.get('id')
                if poss_id_sel:
                    dettagli_poss_db = self.db_manager.get_possessore_full_details(
                        poss_id_sel)
                    if dettagli_poss_db:
                        possessore_info_completa_sel = dettagli_poss_db
                    else:
                        QMessageBox.warning(
                            self, "Errore", f"Impossibile recuperare dettagli per possessore ID {poss_id_sel}.")
                        return
                else:
                    QMessageBox.warning(
                        self, "Errore", "Nessun ID possessore valido dalla selezione.")
                    return
            else:
                logging.getLogger("CatastoGUI").warning(
                    "PossessoreSelectionDialog non ha restituito 'selected_possessore'.")
                return
        else:
            logging.getLogger("CatastoGUI").info(
                "Aggiunta possessore per PP annullata (selezione/creazione).")
            return

        if not possessore_info_completa_sel or possessore_info_completa_sel.id is None:
            QMessageBox.warning(
                self, "Errore", "Dati del possessore non validi.")
            return

        dettagli_leg = DettagliLegamePossessoreDialog.get_details_for_new_legame(
            nome_possessore=possessore_info_completa_sel.nome_completo,
            tipo_partita_attuale='principale', parent=self
        )
        if dettagli_leg:
            self._pp_temp_nuovi_possessori.append({
                "possessore_id": possessore_info_completa_sel.id,
                "nome_completo": possessore_info_completa_sel.nome_completo,
                "cognome_nome": possessore_info_completa_sel.cognome_nome,
                "paternita": possessore_info_completa_sel.paternita,
                "comune_riferimento_id": possessore_info_completa_sel.comune_id,
                "attivo": possessore_info_completa_sel.attivo,
                "titolo": dettagli_leg["titolo"],
                "quota": dettagli_leg["quota"]
            })
            self._pp_aggiorna_tabella_nuovi_possessori()
        else:
            logging.getLogger("CatastoGUI").info(
                "Aggiunta dettagli legame per PP annullata.")

    def _pp_rimuovi_nuovo_possessore_selezionato(self):
        selected_rows = self.pp_nuovi_possessori_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(
                self, "Nessuna Selezione", "Seleziona un possessore dalla lista dei nuovi possessori da rimuovere.")
            return
        row_to_remove = selected_rows[0].row()
        if 0 <= row_to_remove < len(self._pp_temp_nuovi_possessori):
            del self._pp_temp_nuovi_possessori[row_to_remove]
            self._pp_aggiorna_tabella_nuovi_possessori()

    def _pp_aggiorna_tabella_nuovi_possessori(self):
        table = self.pp_nuovi_possessori_table
        table.setRowCount(0)
        table.setSortingEnabled(False)
        if self._pp_temp_nuovi_possessori:
            table.setRowCount(len(self._pp_temp_nuovi_possessori))
            for r, pd in enumerate(self._pp_temp_nuovi_possessori):
                table.setItem(r, 0, QTableWidgetItem(
                    str(pd.get("possessore_id"))))
                table.setItem(r, 1, QTableWidgetItem(pd.get("nome_completo")))
                table.setItem(r, 2, QTableWidgetItem(pd.get("titolo")))
                table.setItem(r, 3, QTableWidgetItem(pd.get("quota", "")))
            table.resizeColumnsToContents()
        table.setSortingEnabled(True)

    def _load_partita_sorgente_from_spinbox(self):
        """
        Carica i dettagli della partita sorgente usando l'ID
        inserito nello QSpinBox self.source_partita_id_spinbox.
        """
        partita_id_val = self.source_partita_id_spinbox.value()
        if partita_id_val > 0:
            self.selected_partita_id_source = partita_id_val  # Imposta l'ID della sorgente
            # Chiamata al metodo esistente che carica e visualizza i dettagli della partita sorgente
            # e popola anche la tabella degli immobili nel tab "Trasferisci Immobile"
            self._aggiorna_info_partita_sorgente()
        else:
            QMessageBox.warning(
                self, "ID Non Valido", "Inserire un ID partita sorgente valido (maggiore di zero).")
            # Potrebbe voler resettare le info se l'ID non è valido
            self.selected_partita_id_source = None
            # Chiamata per pulire le label e le tabelle
            self._aggiorna_info_partita_sorgente()

    # --- MODIFICA IN _esegui_passaggio_proprieta PER LEGGERE DA COMBOBOX ---
    def _esegui_passaggio_proprieta(self):
        self.logger.info("Avvio _esegui_passaggio_proprieta.")

        # --- 1. Validazione Dati Partita Sorgente ---
        if self.selected_partita_id_source is None or self.selected_partita_comune_id_source is None:
            QMessageBox.warning(self, "Selezione Mancante", "Selezionare una partita sorgente valida prima di procedere.")
            return

        # --- 2. Validazione Dati Nuova Partita ---
        nuova_part_num = self.pp_nuova_partita_numero_spinbox.value()
        suffisso_nuova_partita = self.pp_suffisso_nuova_partita_edit.text().strip() or None # Leggi il suffisso
        if nuova_part_num <= 0:
            QMessageBox.warning(self, "Dati Mancanti", "Il 'Numero Nuova Partita' non può essere zero o negativo.")
            self.pp_nuova_partita_numero_spinbox.setFocus()
            self.pp_nuova_partita_numero_spinbox.selectAll()
            return

        try:
                # La ricerca di esistenza deve ora usare anche il suffisso
                existing_partita_check = self.db_manager.search_partite(
                    comune_id=self.selected_partita_comune_id_source,
                    numero_partita=nuova_part_num,
                    suffisso_partita=suffisso_nuova_partita # PASSA IL SUFFISSO ALLA RICERCA
                )
                if existing_partita_check:
                    QMessageBox.warning(self, "Errore Creazione Partita",
                                        f"Esiste già una partita con il numero {nuova_part_num} "
                                        f"{('('+suffisso_nuova_partita+')' if suffisso_nuova_partita else '')} "
                                        f"nel comune '{self.selected_partita_comune_nome_source}'. Scegliere un numero/suffisso diverso.")
                    self.pp_nuova_partita_numero_spinbox.setFocus()
                    return
        except DBMError as e:
            self.logger.error(f"Errore DB durante la verifica di esistenza della nuova partita: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Verifica Partita",
                                 f"Errore durante la verifica di disponibilità del numero partita:\n{str(e)}")
            return
        except Exception as e:
            self.logger.critical(f"Errore imprevisto durante la verifica di esistenza della nuova partita: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Imprevisto", f"Si è verificato un errore inatteso durante la verifica del numero partita:\n{str(e)}")
            return


        # --- 3. Validazione Dati Atto/Contratto ---
        tipo_variazione = self.pp_tipo_variazione_combo.currentText()
        if not tipo_variazione or tipo_variazione.strip() == "Seleziona Tipo...": # Assicurati che non sia il placeholder
            QMessageBox.warning(self, "Dati Atto Mancanti", "Selezionare un 'Tipo Variazione' valido.")
            self.pp_tipo_variazione_combo.setFocus()
            return

        data_variazione_q = self.pp_data_variazione_edit.date()
        if not data_variazione_q.isValid():
            QMessageBox.warning(self, "Dati Atto Mancanti", "La 'Data Variazione' è obbligatoria e deve essere valida.")
            self.pp_data_variazione_edit.setFocus()
            return
        data_variazione = data_variazione_q.toPyDate()

        # Leggi il tipo di contratto dalla QComboBox e validalo
        tipo_contratto = self.pp_tipo_contratto_combo.currentText()
        if tipo_contratto == "Seleziona Tipo..." or not tipo_contratto.strip():
            QMessageBox.warning(self, "Dati Atto Mancanti", "Selezionare un 'Tipo Atto/Contratto' valido.")
            self.pp_tipo_contratto_combo.setFocus()
            return
        
        data_contratto_q = self.pp_data_contratto_edit.date()
        if not data_contratto_q.isValid():
            QMessageBox.warning(self, "Dati Atto Mancanti", "La 'Data Atto/Contratto' è obbligatoria e deve essere valida.")
            self.pp_data_contratto_edit.setFocus()
            return
        data_contratto = data_contratto_q.toPyDate()
        
        # Spesso il contratto precede o coincide con la variazione catastale
        if data_contratto > data_variazione:
            reply = QMessageBox.warning(self, "Attenzione Date", 
                                        "La Data dell'Atto/Contratto inserita è successiva alla Data di Variazione Catastale.\n\nÈ corretto?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.pp_data_contratto_edit.setFocus()
                return

        # Altri campi opzionali
        notaio = self.pp_notaio_edit.text().strip() or None
        repertorio = self.pp_repertorio_edit.text().strip() or None
        note_v = self.pp_note_variazione_edit.toPlainText().strip() or None
        suffisso_nuova_partita=suffisso_nuova_partita # AGGIUNTO

        # --- 4. Validazione Nuovi Possessori ---
        if not self._pp_temp_nuovi_possessori:
            QMessageBox.warning(self, "Possessori Mancanti", "Aggiungere almeno un nuovo possessore per la nuova partita.")
            # Puoi anche impostare il focus al pulsante "Aggiungi Possessore" qui
            return
        
        # Prepara la lista di possessori per il DB, includendo i dettagli del legame
        lista_possessori_per_db = []
        for poss_data_ui in self._pp_temp_nuovi_possessori:
            # Assicurati che tutte le chiavi necessarie alla procedura SQL siano presenti nel dizionario
            lista_possessori_per_db.append({
                "possessore_id": poss_data_ui.get("possessore_id"),
                "nome_completo": poss_data_ui.get("nome_completo"),
                "cognome_nome": poss_data_ui.get("cognome_nome"), # Potrebbe non essere sempre presente o obbligatorio
                "paternita": poss_data_ui.get("paternita"),       # Potrebbe non essere sempre presente o obbligatorio
                "comune_id": poss_data_ui.get("comune_riferimento_id"), # ID del comune di riferimento del possessore
                "attivo": poss_data_ui.get("attivo", True),
                "titolo": poss_data_ui.get("titolo"),
                "quota": poss_data_ui.get("quota")
            })
        self.logger.debug(f"PP: Lista possessori inviata al DBManager: {lista_possessori_per_db}")


        # --- 5. Validazione e Selezione Immobili da Trasferire ---
        imm_ids_trasf: List[int] = []
        if self.pp_trasferisci_tutti_immobili_check.isChecked():
            # Se la checkbox "Includi TUTTI" è spuntata, raccogli tutti gli ID immobili dal table model
            source_table_immobili = self.immobili_partita_sorgente_table # Questa tabella è popolata con gli immobili della sorgente
            for r in range(source_table_immobili.rowCount()):
                id_itm_widget = source_table_immobili.item(r, 0) # Assumendo ID Imm. è nella prima colonna
                if id_itm_widget and id_itm_widget.text().isdigit():
                    imm_ids_trasf.append(int(id_itm_widget.text()))
            
            if not imm_ids_trasf:
                QMessageBox.warning(self, "Immobili Mancanti", "La partita sorgente non contiene immobili da trasferire, ma 'Includi TUTTI' è selezionato.")
                return

        else:
            # Altrimenti, raccogli solo gli ID degli immobili selezionati individualmente nella tabella
            sel_tbl_imm = self.pp_immobili_da_selezionare_table
            for r in range(sel_tbl_imm.rowCount()):
                chk_widget = sel_tbl_imm.cellWidget(r, 0) # La checkbox è nella colonna 0
                if isinstance(chk_widget, QCheckBox) and chk_widget.isChecked():
                    id_itm_widget = sel_tbl_imm.item(r, 1) # L'ID immobile è nella colonna 1 (dopo la checkbox)
                    if id_itm_widget and id_itm_widget.text().isdigit():
                        imm_ids_trasf.append(int(id_itm_widget.text()))
            
            if not imm_ids_trasf:
                QMessageBox.warning(self, "Immobili Mancanti", "Nessun immobile è stato selezionato per il trasferimento. Selezionare almeno un immobile o spuntare 'Includi TUTTI'.")
                return

        self.logger.debug(f"PP: Immobili da trasferire IDs: {imm_ids_trasf}")

        # --- 6. Esecuzione della Procedura nel DBManager ---
        try:
            success = self.db_manager.registra_passaggio_proprieta(
                partita_origine_id=self.selected_partita_id_source,
                comune_id_nuova_partita=self.selected_partita_comune_id_source,
                numero_nuova_partita=nuova_part_num,
                tipo_variazione=tipo_variazione,
                data_variazione=data_variazione,
                tipo_contratto=tipo_contratto,
                data_contratto=data_contratto,
                notaio=notaio,
                repertorio=repertorio,
                nuovi_possessori_list=lista_possessori_per_db,
                immobili_da_trasferire_ids=imm_ids_trasf if imm_ids_trasf else None, # Passa None se lista vuota
                note_variazione=note_v
            )

            # --- 7. Gestione del Successo o Fallimento ---
            if success:
                QMessageBox.information(
                    self, "Successo", "Passaggio di proprietà registrato con successo. La nuova partita è stata creata e gli immobili trasferiti.")
                self.logger.info("Passaggio di proprietà eseguito con successo.")
                self._pulisci_campi_passaggio_proprieta() # Chiama un metodo per pulire i campi
                # Ricarica i dati della partita sorgente per riflettere i cambiamenti (es. immobili rimossi)
                self._aggiorna_info_partita_sorgente()
            else:
                # Questo blocco else dovrebbe essere raggiunto solo se il db_manager restituisce False
                # senza sollevare eccezioni, ma le eccezioni sono preferibili.
                self.logger.error("registra_passaggio_proprieta ha restituito False senza eccezioni.")
                QMessageBox.critical(self, "Errore Operazione", "Il passaggio di proprietà non è stato completato (errore sconosciuto). Controllare i log.")

        except (DBUniqueConstraintError, DBDataError, DBMError) as e:
            self.logger.error(f"Errore DB durante la registrazione del passaggio di proprietà: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Operazione",
                                 f"Impossibile registrare il passaggio di proprietà a causa di un errore nel database:\n{str(e)}")
        except Exception as e_gen:
            self.logger.critical(f"Errore imprevisto durante l'esecuzione del passaggio di proprietà: {e_gen}", exc_info=True)
            QMessageBox.critical(self, "Errore Critico Imprevisto",
                                 f"Si è verificato un errore di sistema inatteso durante l'operazione:\n{type(e_gen).__name__}: {str(e_gen)}")

    # --- NUOVO METODO: Per pulire i campi del tab Passaggio Proprietà dopo il successo ---
    def _pulisci_campi_passaggio_proprieta(self):
        self.pp_nuova_partita_numero_spinbox.setValue(self.pp_nuova_partita_numero_spinbox.minimum())
        self.pp_tipo_variazione_combo.setCurrentIndex(0)
        self.pp_data_variazione_edit.setDate(QDate.currentDate())
        self.pp_tipo_contratto_combo.setCurrentIndex(0) # Resetta la ComboBox
        self.pp_data_contratto_edit.setDate(QDate.currentDate())
        self.pp_notaio_edit.clear()
        self.pp_repertorio_edit.clear()
        self.pp_note_variazione_edit.clear()
        self.pp_trasferisci_tutti_immobili_check.setChecked(True) # Reimposta a default
        self._pp_temp_nuovi_possessori.clear() # Pulisci la lista interna
        self._pp_aggiorna_tabella_nuovi_possessori() # Aggiorna la tabella visualizzata
        self.logger.info("Campi del form Passaggio Proprietà puliti.")


    def seleziona_e_carica_partita_sorgente(self, partita_id: int):
        """Imposta l'ID della partita sorgente e carica i suoi dettagli."""
        logging.getLogger("CatastoGUI").info(
            f"OperazioniPartitaWidget: Impostazione partita sorgente ID: {partita_id} da chiamata esterna.")
        self.source_partita_id_spinbox.setValue(partita_id)
        # Usa il metodo esistente per caricare i dati
        self._load_partita_sorgente_from_spinbox()


