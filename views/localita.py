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

class InserimentoLocalitaWidget(QWidget):
    def __init__(self, db_manager, parent=None):
        super(InserimentoLocalitaWidget, self).__init__(parent)
        self.db_manager = db_manager
        self.comune_id = None
        self._initUI()
        # Non carichiamo i tipi qui, ma quando un comune viene selezionato

    def _initUI(self):
        # ... (la UI rimane quasi identica)
        layout = QVBoxLayout(self)
        form_group = QGroupBox("Inserimento Nuova Località")
        form_layout = QGridLayout(form_group)
        comune_label = QLabel("Comune (*):")
        self.comune_button = QPushButton("Seleziona Comune...")
        self.comune_button.clicked.connect(self.select_comune)
        self.comune_display = QLabel("Nessun comune selezionato")
        form_layout.addWidget(comune_label, 0, 0)
        form_layout.addWidget(self.comune_button, 0, 1)
        form_layout.addWidget(self.comune_display, 0, 2)
        nome_label = QLabel("Nome località (*):")
        self.nome_edit = QLineEdit()
        form_layout.addWidget(nome_label, 1, 0)
        form_layout.addWidget(self.nome_edit, 1, 1, 1, 2)
        tipo_label = QLabel("Tipo (*):")
        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Seleziona prima un comune...", None)
        self.tipo_combo.setEnabled(False)
        form_layout.addWidget(tipo_label, 2, 0)
        form_layout.addWidget(self.tipo_combo, 2, 1)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        insert_button = QPushButton("Inserisci Località")
        insert_button.clicked.connect(self.create_localita)
        layout.addWidget(insert_button)
        summary_group = QGroupBox("Località nel Comune Selezionato")
        summary_layout = QVBoxLayout(summary_group)
        self.refresh_button = QPushButton("Aggiorna Lista")
        self.refresh_button.clicked.connect(self.refresh_localita)
        self.localita_table = QTableWidget()
        self.localita_table.setColumnCount(3)
        self.localita_table.setHorizontalHeaderLabels(["ID", "Nome", "Tipo"])
        self.localita_table.setAlternatingRowColors(True)
        self.localita_table.horizontalHeader().setStretchLastSection(True)
        summary_layout.addWidget(self.refresh_button)
        summary_layout.addWidget(self.localita_table)
        layout.addWidget(summary_group)
        self.setLayout(layout)

    def _load_tipi_localita(self):
        """Carica dinamicamente le tipologie di località nel ComboBox."""
        self.tipo_combo.clear()
        try:
            tipi = self.db_manager.get_tipi_localita()
            if tipi:
                self.tipo_combo.addItem("--- Seleziona Tipo ---", None)
                for tipo in tipi:
                    self.tipo_combo.addItem(tipo['nome'], tipo['id'])
                self.tipo_combo.setEnabled(True)
            else:
                self.tipo_combo.addItem("Nessuna tipologia definita", None)
                self.tipo_combo.setEnabled(False)
        except DBMError as e:
            self.tipo_combo.addItem("Errore caricamento", None)
            self.tipo_combo.setEnabled(False)
            QMessageBox.critical(self, "Errore", f"Impossibile caricare le tipologie di località:\n{e}")

    def select_comune(self):
        # ... (invariato)
        dialog = ComuneSelectionDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_comune_id:
            self.comune_id = dialog.selected_comune_id
            self.comune_display.setText(dialog.selected_comune_name)
            self._load_tipi_localita() # Carica i tipi dopo aver selezionato il comune
            self.refresh_localita()

    def create_localita(self):
        if not self.comune_id:
            QMessageBox.warning(self, "Errore", "Seleziona un comune prima di inserire una località.")
            self.comune_button.setFocus()
            return

        nome = self.nome_edit.text().strip()
        tipo_id = self.tipo_combo.currentData()

        if not nome:
            QMessageBox.warning(self, "Dati Mancanti", "Il nome della località è obbligatorio.")
            self.nome_edit.setFocus()
            return
        if tipo_id is None:
            QMessageBox.warning(self, "Dati Mancanti", "Selezionare una tipologia valida.")
            self.tipo_combo.setFocus()
            return

        try:
            localita_id = self.db_manager.create_localita(self.comune_id, nome, tipo_id)
            QMessageBox.information(self, "Successo", f"Località '{nome}' inserita con ID: {localita_id}")
            self.nome_edit.clear()
            self.refresh_localita()
        except (DBMError, DBDataError, DBUniqueConstraintError) as e:
            QMessageBox.critical(self, "Errore Inserimento", str(e))

    def refresh_localita(self):
        self.localita_table.setRowCount(0)
        if not self.comune_id:
            return

        try:
            localita_list = self.db_manager.get_localita_by_comune(self.comune_id)
            if not localita_list:
                return
            self.localita_table.setRowCount(len(localita_list))
            for i, loc in enumerate(localita_list):
                self.localita_table.setItem(i, 0, QTableWidgetItem(str(loc.get('id', ''))))
                self.localita_table.setItem(i, 1, QTableWidgetItem(loc.get('nome', '') or ''))
                self.localita_table.setItem(i, 2, QTableWidgetItem(loc.get('tipo', '') or ''))
            self.localita_table.resizeColumnsToContents()
        except Exception as e:
            logging.getLogger("CatastoGUI").error(
                f"Errore caricamento località per comune ID {self.comune_id}: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore", f"Impossibile caricare le località:\n{e}")

