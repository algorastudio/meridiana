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

class GestioneUtentiWidget(LazyLoadedWidget):
    def __init__(self, db_manager: 'CatastoDBManager', current_user_info: Optional[Dict], parent=None):
        super().__init__(parent)  # Chiama il costruttore della classe base
        self.db_manager = db_manager
        self.current_user_info = current_user_info
        self.is_admin = self.current_user_info.get('ruolo') == 'admin' if self.current_user_info else False
        
        self._initUI()
        # La chiamata a refresh_user_list() viene rimossa da qui

    def _initUI(self):
        """Crea e assembla i componenti dell'interfaccia utente."""
        layout = QVBoxLayout(self)

        # Pulsanti Azioni
        action_layout = QHBoxLayout()
        self.btn_crea_utente = QPushButton(QApplication.style().standardIcon(QStyle.SP_FileDialogNewFolder), " Crea Nuovo Utente")
        self.btn_crea_utente.clicked.connect(self.crea_nuovo_utente)
        self.btn_crea_utente.setEnabled(self.is_admin)
        self.btn_refresh_list = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), " Aggiorna Lista")
        self.btn_refresh_list.clicked.connect(self.refresh_user_list)
        
        action_layout.addWidget(self.btn_crea_utente)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_refresh_list)
        layout.addLayout(action_layout)

        # Tabella Utenti
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels(["ID", "Username", "Nome Completo", "Email", "Ruolo", "Stato"])
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setSelectionMode(QTableWidget.SingleSelection)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.itemSelectionChanged.connect(self._update_action_buttons_state)
        layout.addWidget(self.user_table)

        # Pulsanti di gestione per utente selezionato
        manage_layout = QHBoxLayout()
        self.btn_modifica_utente = QPushButton("Modifica Utente")
        self.btn_modifica_utente.clicked.connect(self.modifica_utente_selezionato)
        
        self.btn_reset_password = QPushButton("Resetta Password")
        self.btn_reset_password.clicked.connect(self.reset_password_utente_selezionato)
        
        self.btn_toggle_stato = QPushButton("Attiva/Disattiva Utente")
        self.btn_toggle_stato.clicked.connect(self.toggle_stato_utente_selezionato)
        
        self.btn_delete_utente = QPushButton("Elimina Utente")
        self.btn_delete_utente.clicked.connect(self.elimina_utente_selezionato)

        manage_layout.addWidget(self.btn_modifica_utente)
        manage_layout.addWidget(self.btn_reset_password)
        manage_layout.addWidget(self.btn_toggle_stato)
        manage_layout.addWidget(self.btn_delete_utente)
        layout.addLayout(manage_layout)
        
        # Imposta lo stato iniziale dei pulsanti
        self._update_action_buttons_state()

    def _load_data_on_first_show(self):
        """Carica la lista degli utenti la prima volta che il tab viene mostrato."""
        self.logger.info("GestioneUtentiWidget: Esecuzione lazy loading della lista utenti...")
        self.refresh_user_list()

    def refresh_user_list(self):
        """Carica o ricarica la lista degli utenti dal database e la visualizza."""
        self.logger.info("Aggiornamento della lista utenti in corso...")
        self.user_table.setSortingEnabled(False)
        self.user_table.setRowCount(0)
        try:
            utenti = self.db_manager.get_utenti()
            self.user_table.setRowCount(len(utenti))
            for row, user_data in enumerate(utenti):
                self.user_table.setItem(row, 0, QTableWidgetItem(str(user_data['id'])))
                self.user_table.setItem(row, 1, QTableWidgetItem(user_data['username']))
                self.user_table.setItem(row, 2, QTableWidgetItem(user_data['nome_completo']))
                self.user_table.setItem(row, 3, QTableWidgetItem(user_data.get('email', 'N/D')))
                self.user_table.setItem(row, 4, QTableWidgetItem(user_data['ruolo']))
                self.user_table.setItem(row, 5, QTableWidgetItem("Attivo" if user_data['attivo'] else "Non Attivo"))
            self.user_table.resizeColumnsToContents()
            self.logger.info("Lista utenti aggiornata con successo.")
        except DBMError as e:
            self.logger.error(f"Errore DB durante l'aggiornamento della lista utenti: {e}")
            QMessageBox.critical(self, "Errore Database", f"Impossibile caricare la lista degli utenti:\n{e}")
        finally:
            self.user_table.setSortingEnabled(True)

    def _update_action_buttons_state(self):
        """Abilita i pulsanti di gestione solo se un utente è selezionato."""
        has_selection = bool(self.user_table.selectedItems())
        self.btn_modifica_utente.setEnabled(has_selection and self.is_admin)
        self.btn_reset_password.setEnabled(has_selection and self.is_admin)
        self.btn_toggle_stato.setEnabled(has_selection and self.is_admin)
        self.btn_delete_utente.setEnabled(has_selection and self.is_admin)

    def crea_nuovo_utente(self):
        # CreateUserDialog come definito prima
        dialog = CreateUserDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh_user_list()
            QMessageBox.information(self, "Successo", "Nuovo utente creato.")

    def _get_selected_user_id(self) -> Optional[int]:
        selected_rows = self.user_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Nessuna Selezione",
                                "Per favore, seleziona un utente dalla lista.")
            return None
        try:
            return int(self.user_table.item(selected_rows[0].row(), 0).text())
        except (ValueError, AttributeError):
            QMessageBox.critical(
                self, "Errore", "Impossibile ottenere l'ID dell'utente selezionato.")
            return None

    def modifica_utente_selezionato(self):
        user_id = self._get_selected_user_id()
        if user_id is None:
            return

        utente_attuale = self.db_manager.get_utente_by_id(user_id)
        if not utente_attuale:
            QMessageBox.critical(
                self, "Errore", f"Utente con ID {user_id} non trovato.")
            return

        # Qui aprirebbe un dialogo per modificare i dettagli, simile a CreateUserDialog ma pre-popolato
        # Per semplicità, usiamo QInputDialog per alcuni campi
        nome_attuale = utente_attuale.get('nome_completo', '')
        new_nome, ok = QInputDialog.getText(
            self, "Modifica Nome", f"Nuovo nome completo (attuale: '{nome_attuale}'):", text=nome_attuale)
        if not ok:
            return  # Annullato

        email_attuale = utente_attuale.get('email', '')
        new_email, ok = QInputDialog.getText(
            self, "Modifica Email", f"Nuova email (attuale: '{email_attuale}'):", text=email_attuale)
        if not ok:
            return

        ruoli = ["admin", "archivista", "consultatore"]
        ruolo_attuale = utente_attuale.get('ruolo', 'consultatore')
        new_ruolo, ok = QInputDialog.getItem(self, "Modifica Ruolo", f"Nuovo ruolo (attuale: '{ruolo_attuale}'):", ruoli, ruoli.index(
            ruolo_attuale) if ruolo_attuale in ruoli else 0, False)
        if not ok:
            return

        update_params = {}
        if new_nome and new_nome != nome_attuale:
            update_params['nome_completo'] = new_nome
        if new_email and new_email != email_attuale:
            update_params['email'] = new_email
        if new_ruolo and new_ruolo != ruolo_attuale:
            update_params['ruolo'] = new_ruolo

        if update_params:
            if self.db_manager.update_user_details(user_id, **update_params):
                QMessageBox.information(
                    self, "Successo", "Dettagli utente aggiornati.")
                self.refresh_user_list()
            else:
                QMessageBox.critical(
                    self, "Errore", "Aggiornamento fallito. Controllare i log.")
        else:
            QMessageBox.information(
                self, "Info", "Nessuna modifica apportata.")

    def reset_password_utente_selezionato(self):
        user_id = self._get_selected_user_id()
        if user_id is None:
            return
        if user_id == self.current_user_info.get('id'):
            QMessageBox.warning(self, "Azione Non Permessa",
                                "Non puoi resettare la tua password da questa interfaccia.")
            return

        new_password, ok = QInputDialog.getText(
            self, "Reset Password", "Inserisci la nuova password temporanea:", QLineEdit.Password)
        if ok and new_password:
            new_password_confirm, ok_confirm = QInputDialog.getText(
                self, "Conferma Password", "Conferma la nuova password temporanea:", QLineEdit.Password)
            if ok_confirm and new_password == new_password_confirm:
                try:
                    new_hash = _hash_password(new_password)
                    if self.db_manager.reset_user_password(user_id, new_hash):
                        QMessageBox.information(
                            self, "Successo", f"Password per utente ID {user_id} resettata.")
                    else:
                        QMessageBox.critical(
                            self, "Errore", "Reset password fallito.")
                except Exception as e:
                    QMessageBox.critical(
                        self, "Errore Hashing", f"Errore durante l'hashing: {e}")
            elif ok_confirm:  # ma password non coincidono
                QMessageBox.warning(
                    self, "Errore", "Le password non coincidono.")
        elif ok:  # password vuota
            QMessageBox.warning(
                self, "Errore", "La password non può essere vuota.")

    def toggle_stato_utente_selezionato(self):
        user_id = self._get_selected_user_id()
        if user_id is None:
            return
        if user_id == self.current_user_info.get('id'):
            QMessageBox.warning(self, "Azione Non Permessa",
                                "Non puoi modificare lo stato del tuo account.")
            return

        utente_target = self.db_manager.get_utente_by_id(user_id)
        if not utente_target:
            QMessageBox.critical(self, "Errore", "Utente non trovato.")
            return

        nuovo_stato_attivo = not utente_target['attivo']
        azione_str = "RIATTIVARE" if nuovo_stato_attivo else "DISATTIVARE"

        reply = QMessageBox.question(self, "Conferma Stato",
                                     f"L'utente '{utente_target['username']}' è attualmente {'ATTIVO' if utente_target['attivo'] else 'NON ATTIVO'}.\n"
                                     f"Vuoi {azione_str} questo utente?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success = False
            if nuovo_stato_attivo:
                success = self.db_manager.activate_user(user_id)
            else:
                success = self.db_manager.deactivate_user(user_id)

            if success:
                QMessageBox.information(
                    self, "Successo", f"Stato utente '{utente_target['username']}' aggiornato.")
                self.refresh_user_list()
            else:
                QMessageBox.critical(
                    self, "Errore", "Aggiornamento stato fallito.")

    def elimina_utente_selezionato(self):
        user_id = self._get_selected_user_id()
        if user_id is None:
            return
        if user_id == self.current_user_info.get('id'):
            QMessageBox.warning(self, "Azione Non Permessa",
                                "Non puoi eliminare te stesso.")
            return

        utente_target = self.db_manager.get_utente_by_id(user_id)
        if not utente_target:
            QMessageBox.critical(self, "Errore", "Utente non trovato.")
            return

        reply = QMessageBox.warning(self, "Conferma Eliminazione",
                                    f"ATTENZIONE: Stai per eliminare PERMANENTEMENTE l'utente '{utente_target['username']}' (ID: {user_id}).\n"
                                    "Questa operazione è IRREVERSIBILE e i riferimenti nei log verranno impostati a NULL (se configurato).\n"
                                    "Sei assolutamente sicuro?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Ulteriore conferma digitando lo username
            confirm_username, ok = QInputDialog.getText(self, "Conferma Finale",
                                                        f"Per confermare l'eliminazione permanente di '{utente_target['username']}', riscrivi il suo username:")
            if ok and confirm_username == utente_target['username']:
                if self.db_manager.delete_user_permanently(user_id):
                    QMessageBox.information(
                        self, "Successo", f"Utente '{utente_target['username']}' eliminato permanentemente.")
                    self.refresh_user_list()
                else:
                    QMessageBox.critical(
                        self, "Errore", "Eliminazione fallita. Controllare i log (es. è l'unico admin attivo?).")
            elif ok:  # Username non corrispondente
                QMessageBox.warning(
                    self, "Annullato", "Username non corrispondente. Eliminazione annullata.")
            # else: l'utente ha premuto annulla su QInputDialog


class AuditLogViewerWidget(LazyLoadedWidget):
    def __init__(self, db_manager: CatastoDBManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        
        # Stato per la paginazione
        self.current_page = 1
        self.page_size = 100  # Record per pagina
        self.total_records = 0
        self.total_pages = 0
        self.current_filters = {}
        
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === SEZIONE 1: FILTRI (più compatta) ===
        filters_group = QGroupBox("Filtri Ricerca")
        filters_group.setMaximumHeight(140)
        filters_layout = QVBoxLayout(filters_group)
        
        # Prima riga di filtri
        filters_row1 = QHBoxLayout()
        filters_row1.setSpacing(10)
        
        # Tabella
        filters_row1.addWidget(QLabel("Tabella:"))
        self.filter_table_name_edit = QLineEdit()
        self.filter_table_name_edit.setPlaceholderText("Nome tabella...")
        self.filter_table_name_edit.setMaximumWidth(150)
        filters_row1.addWidget(self.filter_table_name_edit)
        
        # Username
        filters_row1.addWidget(QLabel("Utente:"))
        self.filter_app_user_id_edit = QLineEdit()
        self.filter_app_user_id_edit.setPlaceholderText("Username...")
        self.filter_app_user_id_edit.setMaximumWidth(150)
        filters_row1.addWidget(self.filter_app_user_id_edit)
        
        # Operazione
        filters_row1.addWidget(QLabel("Operazione:"))
        self.filter_operation_combo = QComboBox()
        self.filter_operation_combo.addItems(["Tutte", "INSERT", "UPDATE", "DELETE"])
        self.filter_operation_combo.setMaximumWidth(100)
        filters_row1.addWidget(self.filter_operation_combo)
        
        filters_row1.addStretch()
        
        # Seconda riga: Date
        filters_row2 = QHBoxLayout()
        filters_row2.setSpacing(10)
        
        filters_row2.addWidget(QLabel("Da:"))
        self.filter_start_datetime_edit = QDateTimeEdit()
        self.filter_start_datetime_edit.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.filter_start_datetime_edit.setCalendarPopup(True)
        self.filter_start_datetime_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.filter_start_datetime_edit.setMaximumWidth(150)
        filters_row2.addWidget(self.filter_start_datetime_edit)
        
        filters_row2.addWidget(QLabel("A:"))
        self.filter_end_datetime_edit = QDateTimeEdit()
        self.filter_end_datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.filter_end_datetime_edit.setCalendarPopup(True)
        self.filter_end_datetime_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.filter_end_datetime_edit.setMaximumWidth(150)
        filters_row2.addWidget(self.filter_end_datetime_edit)
        
        # Pulsanti filtro
        self.search_button = QPushButton("Applica")
        self.search_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.search_button.clicked.connect(self._apply_filters_and_search)
        self.search_button.setMaximumWidth(100)
        filters_row2.addWidget(self.search_button)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.reset_button.clicked.connect(self._reset_filters)
        self.reset_button.setMaximumWidth(100)
        filters_row2.addWidget(self.reset_button)
        
        filters_row2.addStretch()
        
        filters_layout.addLayout(filters_row1)
        filters_layout.addLayout(filters_row2)
        main_layout.addWidget(filters_group)

        # === SEZIONE 2: AZIONI (toolbar orizzontale) ===
        actions_toolbar = QHBoxLayout()
        actions_toolbar.setSpacing(10)
        
        # Gruppo Pulizia (a sinistra)
        cleanup_frame = QFrame()
        cleanup_frame.setFrameStyle(QFrame.StyledPanel)
        cleanup_layout = QHBoxLayout(cleanup_frame)
        cleanup_layout.setContentsMargins(10, 5, 10, 5)
        
        cleanup_layout.addWidget(QLabel("Elimina log più vecchi di:"))
        self.days_to_keep_spinbox = QSpinBox()
        self.days_to_keep_spinbox.setRange(1, 3650)
        self.days_to_keep_spinbox.setValue(90)
        self.days_to_keep_spinbox.setMaximumWidth(80)
        cleanup_layout.addWidget(self.days_to_keep_spinbox)
        
        self.days_unit_combo = QComboBox()
        self.days_unit_combo.addItems(["Giorni", "Mesi", "Anni"])
        self.days_unit_combo.setMaximumWidth(80)
        cleanup_layout.addWidget(self.days_unit_combo)
        
        self.btn_cleanup_logs = QPushButton("Pulisci")
        self.btn_cleanup_logs.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.btn_cleanup_logs.clicked.connect(self._confirm_and_cleanup_logs)
        cleanup_layout.addWidget(self.btn_cleanup_logs)
        
        actions_toolbar.addWidget(cleanup_frame)
        actions_toolbar.addStretch()
        
        # Gruppo Esportazione (a destra)
        export_frame = QFrame()
        export_frame.setFrameStyle(QFrame.StyledPanel)
        export_layout = QHBoxLayout(export_frame)
        export_layout.setContentsMargins(10, 5, 10, 5)
        
        self.export_csv_button = QPushButton("CSV")
        self.export_csv_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.export_csv_button.clicked.connect(self._handle_export_csv)
        export_layout.addWidget(self.export_csv_button)
        
        self.export_xls_button = QPushButton("Excel")
        self.export_xls_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.export_xls_button.clicked.connect(self._handle_export_xls)
        export_layout.addWidget(self.export_xls_button)
        
        actions_toolbar.addWidget(export_frame)
        main_layout.addLayout(actions_toolbar)

        # === SEZIONE 3: SPLITTER per tabella e dettagli ===
        splitter = QSplitter(Qt.Vertical)
        
        # Parte superiore: Tabella con paginazione
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)
        
        # Tabella risultati
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(8)
        self.log_table.setHorizontalHeaderLabels(["ID", "Data/Ora", "Utente", "Sessione", "Tabella", "Azione", "Record", "IP"])
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setSelectionMode(QTableWidget.SingleSelection)
        self.log_table.setAlternatingRowColors(True)
        
        # Configurazione colonne
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Data/Ora
        header.setSectionResizeMode(2, QHeaderView.Interactive)       # Utente
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Sessione
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # Tabella
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Azione
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Record
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # IP
        
        self.log_table.itemSelectionChanged.connect(self._display_log_details)
        table_layout.addWidget(self.log_table)
        
        # Controlli paginazione
        pagination_frame = QFrame()
        pagination_frame.setFrameStyle(QFrame.StyledPanel)
        pagination_frame.setMaximumHeight(40)
        pagination_layout = QHBoxLayout(pagination_frame)
        pagination_layout.setContentsMargins(5, 2, 5, 2)
        
        self.btn_first_page = QPushButton("<<")
        self.btn_first_page.setToolTip("Prima pagina")
        self.btn_first_page.setMaximumWidth(40)
        self.btn_first_page.clicked.connect(self._go_to_first_page)
        
        self.btn_prev_page = QPushButton("<")
        self.btn_prev_page.setToolTip("Pagina precedente")
        self.btn_prev_page.setMaximumWidth(40)
        self.btn_prev_page.clicked.connect(self._go_to_previous_page)
        
        self.page_info_label = QLabel("Pagina 1 / 1")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        self.page_info_label.setMinimumWidth(150)
        
        self.btn_next_page = QPushButton(">")
        self.btn_next_page.setToolTip("Pagina successiva")
        self.btn_next_page.setMaximumWidth(40)
        self.btn_next_page.clicked.connect(self._go_to_next_page)
        
        self.btn_last_page = QPushButton(">>")
        self.btn_last_page.setToolTip("Ultima pagina")
        self.btn_last_page.setMaximumWidth(40)
        self.btn_last_page.clicked.connect(self._go_to_last_page)
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.btn_first_page)
        pagination_layout.addWidget(self.btn_prev_page)
        pagination_layout.addWidget(self.page_info_label)
        pagination_layout.addWidget(self.btn_next_page)
        pagination_layout.addWidget(self.btn_last_page)
        pagination_layout.addStretch()
        
        table_layout.addWidget(pagination_frame)
        splitter.addWidget(table_widget)
        
        # Parte inferiore: Dettagli JSON
        details_widget = QWidget()
        details_widget.setMaximumHeight(200)
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        
        details_label = QLabel("Dettagli Modifica (seleziona una riga)")
        details_label.setStyleSheet("font-weight: bold; padding: 5px;")
        details_layout.addWidget(details_label)
        
        details_splitter = QSplitter(Qt.Horizontal)
        
        # Prima colonna
        before_widget = QWidget()
        before_layout = QVBoxLayout(before_widget)
        before_layout.setContentsMargins(5, 0, 5, 0)
        before_layout.addWidget(QLabel("Prima:"))
        self.details_before_text = QTextEdit()
        self.details_before_text.setReadOnly(True)
        self.details_before_text.setFont(QFont("Consolas", 9))
        before_layout.addWidget(self.details_before_text)
        
        # Seconda colonna
        after_widget = QWidget()
        after_layout = QVBoxLayout(after_widget)
        after_layout.setContentsMargins(5, 0, 5, 0)
        after_layout.addWidget(QLabel("Dopo:"))
        self.details_after_text = QTextEdit()
        self.details_after_text.setReadOnly(True)
        self.details_after_text.setFont(QFont("Consolas", 9))
        after_layout.addWidget(self.details_after_text)
        
        details_splitter.addWidget(before_widget)
        details_splitter.addWidget(after_widget)
        details_splitter.setSizes([400, 400])
        
        details_layout.addWidget(details_splitter)
        splitter.addWidget(details_widget)
        
        # Imposta proporzioni iniziali (70% tabella, 30% dettagli)
        splitter.setSizes([500, 200])
        
        main_layout.addWidget(splitter)

    def _load_data_on_first_show(self):
        """
        Carica i dati iniziali per il visualizzatore di log.
        Viene chiamato una sola volta quando il widget diventa visibile.
        """
        if self._data_loaded:
            return
            
        self.logger.info("AuditLogViewerWidget: Esecuzione lazy loading dei log di audit...")
        self._apply_filters_and_search()
        self._data_loaded = True
    def _get_days_from_ui_input(self) -> int:
        """Converte l'input dell'utente (giorni, mesi, anni) in giorni."""
        value = self.days_to_keep_spinbox.value()
        unit_index = self.days_unit_combo.currentIndex()
        if unit_index == 1: # Mesi
            return value * 30
        elif unit_index == 2: # Anni
            return value * 365
        return value # Giorni

    def _confirm_and_cleanup_logs(self):
        """Chiede conferma all'utente e poi avvia la pulizia dei log."""
        days_to_keep = self._get_days_from_ui_input()

        reply = QMessageBox.question(
            self,
            "Conferma Eliminazione Log di Audit",
            f"Sei sicuro di voler eliminare DEFINITIVAMENTE tutti i log di audit "
            f"più vecchi di {days_to_keep} giorni?\n\n"
            "Questa operazione non può essere annullata.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.logger.info(f"Avvio pulizia log di audit più vecchi di {days_to_keep} giorni.")
                QApplication.setOverrideCursor(Qt.WaitCursor)
                deleted_count = self.db_manager.cleanup_audit_logs(days_to_keep)
                QApplication.restoreOverrideCursor()

                QMessageBox.information(
                    self,
                    "Pulizia Completata",
                    f"Pulizia dei log di audit completata con successo.\n"
                    f"Eliminati {deleted_count} record."
                )
                self._apply_filters_and_search() # Ricarica la tabella
            except DBMError as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Errore Pulizia Log", f"Si è verificato un errore:\n{str(e)}")
            except Exception as e:
                QApplication.restoreOverrideCursor()
                self.logger.error(f"Errore inatteso durante la pulizia dei log: {e}", exc_info=True)
                QMessageBox.critical(self, "Errore Imprevisto", f"Errore di sistema:\n{str(e)}")


    def _apply_filters_and_search(self):
        """
        Raccoglie i filtri correnti dalla UI, reimposta la paginazione
        e avvia la ricerca dei log.
        """
        self.current_filters = {
            "table_name": self.filter_table_name_edit.text().strip() or None,
            "username": self.filter_app_user_id_edit.text().strip() or None, # Ora questo campo cerca per username
            "operation_char": None,
            "app_user_id": int(self.filter_app_user_id_edit.text()) if self.filter_app_user_id_edit.text().strip().isdigit() else None,
            "start_datetime": self.filter_start_datetime_edit.dateTime().toPyDateTime(),
            "end_datetime": self.filter_end_datetime_edit.dateTime().toPyDateTime(),
        }
        op_text = self.filter_operation_combo.currentText()
        if "INSERT" in op_text:
            self.current_filters["operation_char"] = "I"
        elif "UPDATE" in op_text:
            self.current_filters["operation_char"] = "U"
        elif "DELETE" in op_text:
            self.current_filters["operation_char"] = "D"

        # Quando si applica un nuovo filtro, si torna sempre alla prima pagina
        self.current_page = 1
        self._fetch_and_display_logs()

    def _reset_filters(self):
        self.filter_table_name_edit.clear(); self.filter_operation_combo.setCurrentIndex(0)
        self.filter_app_user_id_edit.clear(); self.filter_start_datetime_edit.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.filter_end_datetime_edit.setDateTime(QDateTime.currentDateTime())
        self._apply_filters_and_search()

    def _fetch_and_display_logs(self):
        self.log_table.setRowCount(0)
        if not self.db_manager or not self.db_manager.pool: return
        try:
            logs, self.total_records = self.db_manager.get_audit_logs(
                filters=self.current_filters, page=self.current_page, page_size=self.page_size
            )
            self.total_pages = (self.total_records + self.page_size - 1) // self.page_size if self.total_records > 0 else 1
            
            self.log_table.setRowCount(len(logs))
            for row_idx, log in enumerate(logs):
                item_id = QTableWidgetItem(str(log.get('id', ''))); item_id.setData(Qt.UserRole, log)
                ts = log.get('timestamp'); ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "N/D"
                session_id = log.get('session_id', ''); session_display = (session_id[:8] + '...') if session_id else ''
                self.log_table.setItem(row_idx, 0, item_id); self.log_table.setItem(row_idx, 1, QTableWidgetItem(ts_str))
                self.log_table.setItem(row_idx, 2, QTableWidgetItem(log.get('username', 'N/D'))) # Usa il campo 'username'
                self.log_table.setItem(row_idx, 4, QTableWidgetItem(log.get('tabella'))); self.log_table.setItem(row_idx, 5, QTableWidgetItem(log.get('operazione')))
                self.log_table.setItem(row_idx, 6, QTableWidgetItem(str(log.get('record_id', '')))); self.log_table.setItem(row_idx, 7, QTableWidgetItem(log.get('ip_address')))
            self._update_pagination_controls()
        except DBMError as e:
            QMessageBox.critical(self, "Errore Database", f"Impossibile caricare i log di audit:\n{e}")

    def _update_pagination_controls(self):
        self.page_info_label.setText(f"Pagina {self.current_page} / {self.total_pages} ({self.total_records} risultati)")
        self.btn_first_page.setEnabled(self.current_page > 1)
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < self.total_pages)
        self.btn_last_page.setEnabled(self.current_page < self.total_pages)

    def _go_to_first_page(self): self.current_page = 1; self._fetch_and_display_logs()
    def _go_to_previous_page(self): self.current_page -= 1; self._fetch_and_display_logs()
    def _go_to_next_page(self): self.current_page += 1; self._fetch_and_display_logs()
    def _go_to_last_page(self): self.current_page = self.total_pages; self._fetch_and_display_logs()

    def _display_log_details(self):
        selected = self.log_table.selectedItems()
        if not selected: self.details_before_text.clear(); self.details_after_text.clear(); return
        log_entry = self.log_table.item(selected[0].row(), 0).data(Qt.UserRole)
        d_before = log_entry.get('dati_prima'); d_after = log_entry.get('dati_dopo')
        self.details_before_text.setText(json.dumps(d_before, indent=4, ensure_ascii=False) if d_before else "")
        self.details_after_text.setText(json.dumps(d_after, indent=4, ensure_ascii=False) if d_after else "")

    def _handle_export_csv(self):
        logs, total = self.db_manager.get_audit_logs(filters=self.current_filters, page=1, page_size=10000) # Esporta fino a 10000 record
        if not logs: QMessageBox.warning(self, "Nessun Dato", "Nessun log da esportare per i filtri correnti."); return
        filename, _ = QFileDialog.getSaveFileName(self, "Esporta Log in CSV", f"audit_log_{date.today()}.csv", "File CSV (*.csv)")
        if not filename: return
        try:
            headers = logs[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers, delimiter=';'); writer.writeheader(); writer.writerows(logs)
            QMessageBox.information(self, "Successo", f"{len(logs)} record di audit esportati in CSV.")
        except Exception as e: QMessageBox.critical(self, "Errore Esportazione", f"Errore durante l'esportazione CSV:\n{e}")

    def _handle_export_xls(self):
        logs, total = self.db_manager.get_audit_logs(filters=self.current_filters, page=1, page_size=10000)
        if not logs: QMessageBox.warning(self, "Nessun Dato", "Nessun log da esportare."); return
        filename, _ = QFileDialog.getSaveFileName(self, "Esporta Log in Excel", f"audit_log_{date.today()}.xlsx", "File Excel (*.xlsx)")
        if not filename: return
        try:
            df = pd.DataFrame(logs); df.to_excel(filename, index=False, engine='openpyxl')
            QMessageBox.information(self, "Successo", f"{len(logs)} record di audit esportati in Excel.")
        except ImportError: QMessageBox.critical(self, "Libreria Mancante", "L'esportazione in Excel richiede 'pandas' e 'openpyxl'.")
        except Exception as e: QMessageBox.critical(self, "Errore Esportazione", f"Errore durante l'esportazione Excel:\n{e}")
# ... (Fine della classe AuditLogViewerWidget) ...

class BackupWidget(QWidget):
    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(f"CatastoGUI.{self.__class__.__name__}")
        self.setWindowTitle("Backup e Ripristino Database")

        # Processi per pg_dump e pg_restore
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_process_finished)

        self._init_ui()

    # --- NUOVO METODO: Gestisce l'output con colori ---
    def _log_to_output_box(self, message: str, level: str = "INFO"):
        """
        Scrive un messaggio nella casella di output con un colore basato sul livello.
        I livelli possibili sono: INFO, WARNING, ERROR, CRITICAL, SUCCESS, DEBUG.
        """
        color_map = {
            "INFO": "#34495e",    # Grigio scuro / Blu-grigio per routine
            "WARNING": "#e67e22", # Arancione per avvisi
            "ERROR": "#c0392b",   # Rosso scuro per errori
            "CRITICAL": "#e74c3c",# Rosso più vivo per critico
            "SUCCESS": "#27ae60", # Verde per successo
            "DEBUG": "#7f8c8d"    # Grigio chiaro per debug (normalmente non visibile all'utente)
        }
        
        display_color = color_map.get(level.upper(), "#34495e") # Default a grigio scuro
        
        # Aggiunge un timestamp al messaggio
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        formatted_message = f"<span style='color: {display_color};'>[{timestamp}] {message}</span>"
        
        self.output_text_edit.append(formatted_message)
        
        # Assicurati che l'output sia scrollato verso il basso
        self.output_text_edit.verticalScrollBar().setValue(self.output_text_edit.verticalScrollBar().maximum())

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Sezione Backup ---
        backup_group = QGroupBox("Backup Database")
        backup_layout = QFormLayout(backup_group)

        self.backup_file_path_edit = QLineEdit()
        self.backup_file_path_edit.setPlaceholderText(
            "Seleziona percorso e nome del file di backup...")
        self.backup_file_path_edit.setReadOnly(True)
        btn_browse_backup_path = QPushButton("Sfoglia...")
        btn_browse_backup_path.clicked.connect(
            self._browse_backup_file_save_path)
        backup_path_layout = QHBoxLayout()
        backup_path_layout.addWidget(self.backup_file_path_edit)
        backup_path_layout.addWidget(btn_browse_backup_path)
        backup_layout.addRow("File di Backup:", backup_path_layout)

        self.backup_format_combo = QComboBox()
        self.backup_format_combo.addItems([
            "Custom (compresso, per pg_restore - raccomandato)",
            "Plain SQL (testo semplice)"
        ])
        backup_layout.addRow("Formato Backup:", self.backup_format_combo)

        self.pg_dump_path_edit = QLineEdit()
        self.pg_dump_path_edit.setPlaceholderText(
            "Es. C:\\Program Files\\PostgreSQL\\17\\bin\\pg_dump.exe (opzionale)")
        backup_layout.addRow(
            "Percorso pg_dump (opz.C:\\Program Files\\PostgreSQL\\17\\bin\\pg_dump.exe):", self.pg_dump_path_edit)

        self.backup_button = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogSaveButton), "Esegui Backup")
        self.backup_button.clicked.connect(self._start_backup)
        backup_layout.addRow(self.backup_button)

        main_layout.addWidget(backup_group)

        # --- Sezione Ripristino ---
        restore_group = QGroupBox("Ripristino Database")
        restore_layout = QFormLayout(restore_group)

        self.restore_file_path_edit = QLineEdit()
        self.restore_file_path_edit.setPlaceholderText(
            "Seleziona il file di backup da ripristinare...")
        self.restore_file_path_edit.setReadOnly(True)
        btn_browse_restore_path = QPushButton("Sfoglia...")
        btn_browse_restore_path.clicked.connect(
            self._browse_restore_file_open_path)
        restore_path_layout = QHBoxLayout()
        restore_path_layout.addWidget(self.restore_file_path_edit)
        restore_path_layout.addWidget(btn_browse_restore_path)
        restore_layout.addRow("File di Backup:", restore_path_layout)

        self.pg_restore_path_edit = QLineEdit()
        self.pg_restore_path_edit.setPlaceholderText(
            "Es. ...\\bin\\pg_restore.exe o ...\\bin\\psql.exe (opz.)")
        restore_layout.addRow(
            "Percorso pg_restore/psql (opz.):", self.pg_restore_path_edit)

        self.restore_button = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogApplyButton), "Esegui Ripristino")
        self.restore_button.clicked.connect(self._start_restore)
        restore_layout.addRow(self.restore_button)
        restore_layout.addRow(QLabel(
            "<font color='red'><b>ATTENZIONE:</b> Il ripristino sovrascriverà i dati correnti nel database. Procedere con cautela.</font>"))

        main_layout.addWidget(restore_group)

        # --- Output e Progresso ---
        output_group = QGroupBox("Output Operazione")
        output_layout = QVBoxLayout(output_group)
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setLineWrapMode(
            QTextEdit.NoWrap)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        output_layout.addWidget(self.output_text_edit)
        output_layout.addWidget(self.progress_bar)
        main_layout.addWidget(output_group, 1)

        self.setLayout(main_layout)

    def _browse_backup_file_save_path(self):
        current_dbname = self.db_manager.get_current_dbname()
        default_db_name = current_dbname if current_dbname else "catasto_storico"

        default_filename = f"{default_db_name}_backup_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}"

        if self.backup_format_combo.currentIndex() == 0:
            filter_str = "File di Backup PostgreSQL Custom (*.dump *.backup);;Tutti i file (*)"
            default_filename += ".dump"
        else:
            filter_str = "File SQL (*.sql);;Tutti i file (*)"
            default_filename += ".sql"

        filePath, _ = QFileDialog.getSaveFileName(
            self, "Salva Backup Database", default_filename, filter_str)
        if filePath:
            self.backup_file_path_edit.setText(filePath)

    def _browse_restore_file_open_path(self):
        filter_str = "File di Backup PostgreSQL (*.dump *.backup *.sql);;File Custom (*.dump *.backup);;File SQL (*.sql);;Tutti i file (*)"
        filePath, _ = QFileDialog.getOpenFileName(
            self, "Seleziona File di Backup per Ripristino", "", filter_str)
        if filePath:
            self.restore_file_path_edit.setText(filePath)

    def _update_ui_for_process(self, is_running: bool):
        self.backup_button.setEnabled(not is_running)
        self.restore_button.setEnabled(not is_running)
        self.progress_bar.setVisible(is_running)
        if is_running:
            self.progress_bar.setRange(0, 0)
            self.output_text_edit.clear()
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)

    # --- Modificato: Utilizza _log_to_output_box ---
    @pyqtSlot()
    def _handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors='ignore')
        for line in data.splitlines():
            self._log_to_output_box(line, "INFO")

    # --- Modificato: Utilizza _log_to_output_box e analizza il contenuto ---
    @pyqtSlot()
    def _handle_stderr(self):
        data = self.process.readAllStandardError().data().decode(errors='ignore')
        for line in data.splitlines():
            lower_line = line.lower()
            if "warning" in lower_line or "avviso" in lower_line:
                self._log_to_output_box(line, "WARNING")
            elif "error" in lower_line or "errore" in lower_line or "failed" in lower_line or "fallito" in lower_line:
                self._log_to_output_box(line, "ERROR")
            else:
                self._log_to_output_box(line, "INFO") # Output standard in stderr che non è un errore/warning esplicito

    # --- Modificato: Utilizza _log_to_output_box ---
    @pyqtSlot(int, QProcess.ExitStatus)
    def _handle_process_finished(self, exitCode, exitStatus):
        is_restore = self.process.property("is_restore_operation")
        self.process.setProperty("is_restore_operation", False)

        self._log_to_output_box(f"Processo terminato. ExitCode: {exitCode}, ExitStatus: {exitStatus}, Operazione Ripristino: {is_restore}", "DEBUG")
        
        self._update_ui_for_process(False)

        operation_name_display = "Ripristino del database" if is_restore else "Backup del database"
        
        user_message_title = f"Esito {operation_name_display}"
        user_message_text = ""
        message_box_type = QMessageBox.Information

        if exitStatus == QProcess.CrashExit:
            user_message_title = f"Errore Grave durante il {operation_name_display}"
            user_message_text = (
                f"Si è verificato un errore inaspettato e grave durante il {operation_name_display}. "
                "Il processo è terminato in modo anomalo (crash). "
                "Controllare attentamente i dettagli nell'area 'Output Operazione' per informazioni tecniche. "
                "Si consiglia di riprovare l'operazione."
            )
            message_box_type = QMessageBox.Critical
            self._log_to_output_box(
                f"ERRORE CRITICO: Il processo di {operation_name_display.lower()} è terminato inaspettatamente (crash).", "CRITICAL")
            
        elif exitCode != 0:
            user_message_title = f"Operazione di {operation_name_display} Fallita"
            user_message_text = (
                f"L'operazione di {operation_name_display} è fallita con un codice d'errore ({exitCode}). "
                "Ciò indica che il comando esterno non è stato completato correttamente. "
                "Controllare i messaggi in rosso nell'area 'Output Operazione' per capire la causa dell'errore (ad es., password errata, permessi mancanti, file non trovato)."
            )
            message_box_type = QMessageBox.Warning
            self._log_to_output_box(
                f"FALLITO: Il processo di {operation_name_display.lower()} è terminato con codice d'errore: {exitCode}.", "ERROR")
        else: # exitCode == 0, il processo stesso ha terminato con successo
            user_message_title = f"Operazione di {operation_name_display} Completata"
            user_message_text = (
                f"L'operazione di {operation_name_display} è stata completata con successo. "
                "Si consiglia di controllare l'area 'Output Operazione' per eventuali messaggi informativi o di avviso da parte dello strumento."
            )
            message_box_type = QMessageBox.Information
            self._log_to_output_box(
                f"Comando di {operation_name_display.lower()} terminato (exit code 0).", "SUCCESS")
            
        # --- Gestione Riconnessione Pool e Messaggio Finale per l'Utente ---
        if is_restore:
            self._log_to_output_box("Tentativo di ripristinare le connessioni dell'applicazione al database...", "INFO")
            QApplication.processEvents()

            if self.db_manager and self.db_manager.reconnect_pool_if_needed():
                self._log_to_output_box("Connessioni dell'applicazione al database ripristinate con successo.", "INFO")
                if message_box_type == QMessageBox.Information:
                    user_message_text += "\nLe connessioni dell'applicazione al database sono state ripristinate. L'applicazione è ora pronta all'uso."
                else:
                    user_message_text += "\nATTENZIONE: Le connessioni dell'applicazione sono state ripristinate, ma si sono verificati errori durante il ripristino stesso. Verificare l'integrità dei dati."
                QMessageBox(message_box_type, user_message_title, user_message_text, QMessageBox.Ok, self).exec_()
                QMessageBox.information(self, "Verifica Importante",
                                         "Dopo un ripristino, si consiglia sempre di verificare l'integrità dei dati nel database. Se si riscontrano problemi, riavviare l'applicazione.")

            else: # Riconnessione pool fallita dopo un restore
                self._log_to_output_box(
                    "FALLITO: Impossibile ripristinare le connessioni al database. Si prega di RIAVVIARE L'APPLICAZIONE.", "CRITICAL")
                user_message_title = f"Errore Critico: Riconnessione Database Fallita"
                user_message_text = (
                    f"L'operazione di {operation_name_display} è terminata, ma l'applicazione non è riuscita a riconnettersi al database. "
                    "Questo è un errore critico. Si prega di chiudere e riavviare l'applicazione immediatamente."
                )
                QMessageBox.critical(self, user_message_title, user_message_text, QMessageBox.Ok, self).exec_()

        else: # Non è un'operazione di ripristino (es. Backup)
            QMessageBox(message_box_type, user_message_title, user_message_text, QMessageBox.Ok, self).exec_()


    # --- Modificato: Utilizza _log_to_output_box ---
    def _start_backup(self):
        backup_file = self.backup_file_path_edit.text()
        if not backup_file:
            QMessageBox.warning(
                self, "Percorso Mancante", "Selezionare un percorso e un nome file per il backup.")
            return

        if os.path.exists(backup_file):
            reply = QMessageBox.question(self, "Conferma Sovrascrittura",
                                        f"Il file '{os.path.basename(backup_file)}' esiste già.\nVuoi sovrascriverlo?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        db_user_for_prompt = self.db_manager.get_current_user() or "N/Utente"
        db_name_for_prompt = self.db_manager.get_current_dbname() or "N/Database"

        password, ok = QInputDialog.getText(self, "Autenticazione Database per Backup",
                                            f"Inserisci la password per l'utente '{db_user_for_prompt}' "
                                            f"sul database '{db_name_for_prompt}':",
                                            QLineEdit.Password)
        if not ok:
            self._log_to_output_box("Backup annullato dall'utente (dialogo password chiuso).", "INFO")
            return
        if not password.strip():
            QMessageBox.warning(self, "Password Mancante",
                                 "La password non può essere vuota.")
            self._log_to_output_box("Backup fallito: password non fornita.", "WARNING")
            self._update_ui_for_process(False)
            return

        self._update_ui_for_process(True)
        self.output_text_edit.clear()
        self._log_to_output_box(f"Avvio backup su: {backup_file}...", "INFO")

        command_parts = self.db_manager.get_backup_command_parts(
            backup_file_path=backup_file,
            pg_dump_executable_path_ui=self.pg_dump_path_edit.text().strip(),
            format_type="custom" if self.backup_format_combo.currentIndex() == 0 else "plain",
            include_blobs=False
        )

        if not command_parts:
            self._log_to_output_box(
                "ERRORE: Impossibile costruire il comando di backup. Verificare il percorso di pg_dump e i log.", "ERROR")
            self._update_ui_for_process(False)
            QMessageBox.critical(
                self, "Errore Comando", "Impossibile preparare il comando di backup. Controllare i log dell'applicazione.")
            return

        executable = command_parts[0]
        args = command_parts[1:]

        self._log_to_output_box(
            f"Comando da eseguire: {executable} {' '.join(args)}", "INFO")

        process_env = QProcessEnvironment.systemEnvironment() # Inizia con l'ambiente di sistema pulito
        self._log_to_output_box(
            f"Tentativo di impostare PGPASSWORD per l'utente '{db_user_for_prompt}'...", "INFO")
        try:
            process_env.insert("PGPASSWORD", password)
            self.process.setProcessEnvironment(process_env)
            self._log_to_output_box("PGPASSWORD impostata per questo processo.", "INFO")
        except Exception as e:
            self._log_to_output_box(
                f"ERRORE nell'impostare PGPASSWORD: {e}", "ERROR")
            self._log_to_output_box(
                "Il backup potrebbe fallire o rimanere bloccato.", "WARNING")

        self.process.setProperty("is_restore_operation", False)
        self.process.start(executable, args)

    # --- Modificato: Utilizza _log_to_output_box ---
    def _start_restore(self):
        restore_file = self.restore_file_path_edit.text()
        if not restore_file:
            QMessageBox.warning(
                self, "File Mancante", "Selezionare un file di backup da cui ripristinare.")
            return
        if not os.path.exists(restore_file):
            QMessageBox.critical(
                self, "Errore File", f"Il file di backup '{restore_file}' non è stato trovato.")
            return

        dbname_to_restore = self.db_manager.get_current_dbname() or "Database Sconosciuto"
        db_host_for_prompt = self.db_manager.get_connection_parameters().get('host', 'N/Host') # Uso get_connection_parameters per essere coerente
        db_user_for_prompt = self.db_manager.get_current_user() or "Utente Sconosciuto"

        if dbname_to_restore == "Database Sconosciuto":
            QMessageBox.critical(self, "Errore Configurazione",
                                 "Nome del database di destinazione non recuperabile.")
            return

        reply = QMessageBox.warning(self, "Conferma Ripristino Critico",
                                     f"<b>ATTENZIONE ESTREMA!</b>\n\n"
                                     f"Stai per ripristinare il database dal file:\n'{os.path.basename(restore_file)}'\n"
                                     f"sul database di destinazione:\n<b>'{dbname_to_restore}'</b> "
                                     f"(Host: {db_host_for_prompt}, Utente DB: {db_user_for_prompt}).\n\n"
                                     "<b>Questa operazione SOVRASCRIVERÀ tutti i dati correnti nel database di destinazione e NON PUÒ ESSERE ANNULLATA.</b>\n\n"
                                     "Si raccomanda VIVAMENTE di aver effettuato un backup recente e verificato del database corrente prima di procedere.\n\n"
                                     "Sei assolutamente sicuro di voler continuare?",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply == QMessageBox.Cancel:
            self._log_to_output_box("Ripristino annullato dall'utente (prima conferma).", "INFO")
            return

        text_confirm, ok = QInputDialog.getText(self, "Conferma Finale Ripristino Obbligatoria",
                                                 f"Per confermare il ripristino che sovrascriverà PERMANENTEMENTE il database '{dbname_to_restore}',\n"
                                                 f"digita il nome del database qui sotto (deve corrispondere esattamente):")
        if not ok:
            self._log_to_output_box("Ripristino annullato dall'utente (dialogo conferma nome DB chiuso).", "INFO")
            return
        if text_confirm.strip() != dbname_to_restore:
            QMessageBox.critical(self, "Ripristino Annullato",
                                 f"Il nome del database inserito ('{text_confirm.strip()}') non corrisponde a '{dbname_to_restore}'.\n"
                                 "Ripristino annullato per sicurezza.")
            self._log_to_output_box("Ripristino annullato: conferma nome database fallita.", "ERROR")
            return

        password, ok = QInputDialog.getText(self, "Autenticazione Database per Ripristino",
                                            f"Inserisci la password per l'utente '{db_user_for_prompt}' "
                                            f"per il database '{dbname_to_restore}':",
                                            QLineEdit.Password)
        if not ok:
            self._log_to_output_box("Ripristino annullato (dialogo password chiuso).", "INFO")
            return
        if not password.strip():
            QMessageBox.warning(
                self, "Password Mancante", "La password non può essere vuota per il ripristino.")
            self._log_to_output_box("Ripristino fallito: password non fornita.", "WARNING")
            self._update_ui_for_process(False)
            return

        self._update_ui_for_process(True)
        self.output_text_edit.clear()
        self._log_to_output_box(
            f"Avvio ripristino del database '{dbname_to_restore}' da: {restore_file}...", "INFO")
        self._log_to_output_box(
            "AVVISO: L'applicazione potrebbe non rispondere durante l'operazione di ripristino. Attendere il completamento.", "WARNING")
        QApplication.processEvents()

        self._log_to_output_box(
            "Tentativo di chiudere le connessioni attive dell'applicazione al database...", "INFO")
        QApplication.processEvents()
        if not self.db_manager.disconnect_pool_temporarily():
            QMessageBox.critical(self, "Errore Critico Ripristino",
                                 "Impossibile chiudere le connessioni esistenti al database prima del ripristino.\n"
                                 "L'operazione è stata annullata per sicurezza.")
            self._log_to_output_box(
                "FALLITO: Impossibile chiudere le connessioni al database. Ripristino annullato.", "ERROR")
            self._update_ui_for_process(False)
            return
        self._log_to_output_box("Connessioni dell'applicazione al database chiuse temporaneamente.", "INFO")
        QApplication.processEvents()

        command_parts = self.db_manager.get_restore_command_parts(
            backup_file_path=restore_file,
            pg_tool_executable_path_ui=self.pg_restore_path_edit.text().strip()
        )

        if not command_parts:
            self._log_to_output_box(
                "ERRORE: Impossibile costruire il comando di ripristino. Controllare il percorso dell'eseguibile e i log.", "ERROR")
            self._update_ui_for_process(False)
            self._log_to_output_box(
                "Tentativo di ripristinare le connessioni dell'applicazione (dopo fallimento preparazione comando)...", "INFO")
            if not self.db_manager.reconnect_pool_if_needed():
                self._log_to_output_box(
                    "FALLITO riconnessione pool. Riavviare l'app.", "CRITICAL")
            else:
                self._log_to_output_box("Connessioni applicazione ripristinate.", "INFO")
            QMessageBox.critical(
                self, "Errore Comando", "Impossibile preparare il comando di ripristino.")
            return

        executable = command_parts[0]
        args = command_parts[1:]
        self._log_to_output_box(
            f"Comando da eseguire: {executable} {' '.join(args)}", "INFO")

        process_env = QProcessEnvironment.systemEnvironment() # Inizia con l'ambiente di sistema
        self._log_to_output_box(
            f"Tentativo di impostare PGPASSWORD per l'utente '{db_user_for_prompt}'...", "INFO")
        try:
            process_env.insert("PGPASSWORD", password)
            self.process.setProcessEnvironment(process_env)
            self._log_to_output_box("PGPASSWORD impostata per questo processo.", "INFO")
        except Exception as e:
            self._log_to_output_box(
                f"ERRORE nell'impostare PGPASSWORD: {e}", "ERROR")

        self.process.setProperty("is_restore_operation", True)
        self.process.start(executable, args)

class GestionePeriodiStoriciWidget(LazyLoadedWidget):
    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        # Il self.logger è già gestito dalla classe base LazyLoadedWidget
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Gestione Periodi Storici")
        group_layout = QHBoxLayout(group)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nome Periodo", "Anno Inizio-Fine", "Descrizione"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        group_layout.addWidget(self.table)

        button_layout = QVBoxLayout()
        btn_refresh = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), " Aggiorna Lista")
        btn_refresh.clicked.connect(self.load_data) # Ora si collega al metodo corretto
        btn_add = QPushButton(QApplication.style().standardIcon(QStyle.SP_FileDialogNewFolder), " Aggiungi...")
        btn_add.clicked.connect(self._add_or_edit_item)
        btn_edit = QPushButton(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView), " Modifica...")
        btn_edit.clicked.connect(lambda: self._add_or_edit_item(edit_mode=True))
        btn_del = QPushButton(QApplication.style().standardIcon(QStyle.SP_TrashIcon), " Elimina")
        btn_del.clicked.connect(self._delete_item)
        
        button_layout.addWidget(btn_refresh)
        button_layout.addSpacing(20)
        button_layout.addWidget(btn_add)
        button_layout.addWidget(btn_edit)
        button_layout.addWidget(btn_del)
        button_layout.addStretch()
        group_layout.addLayout(button_layout)

        layout.addWidget(group)

    def _load_data_on_first_show(self):
        """Metodo per il lazy loading, chiamato la prima volta."""
        self.load_data()

    def load_data(self):
        """Carica o ricarica i dati dei periodi storici nella tabella."""
        self.logger.info("Caricamento dati per GestionePeriodiStoriciWidget...")
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        try:
            periodi = self.db_manager.get_historical_periods()
            self.table.setRowCount(len(periodi))
            for row, periodo in enumerate(periodi):
                # Salviamo l'intero dizionario del periodo nell'item ID per un facile accesso
                id_item = QTableWidgetItem(str(periodo['id']))
                id_item.setData(Qt.UserRole, periodo)
                self.table.setItem(row, 0, id_item)
                
                self.table.setItem(row, 1, QTableWidgetItem(periodo['nome']))
                
                anno_fine = periodo.get('anno_fine') or 'in corso'
                self.table.setItem(row, 2, QTableWidgetItem(f"{periodo['anno_inizio']} - {anno_fine}"))
                
                self.table.setItem(row, 3, QTableWidgetItem(periodo.get('descrizione', '')))
            self.table.resizeColumnsToContents()
        except DBMError as e:
            QMessageBox.critical(self, "Errore di Caricamento", str(e))
        finally:
            self.table.setSortingEnabled(True)

    def _add_or_edit_item(self, edit_mode=False):
        periodo_data = None
        if edit_mode:
            selected_items = self.table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Selezione Mancante", "Seleziona un periodo da modificare.")
                return
            # Prendi i dati salvati nell'item
            periodo_data = self.table.item(selected_items[0].row(), 0).data(Qt.UserRole)
        
        dialog = PeriodoStoricoEditDialog(self.db_manager, periodo_data, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_data() # Ricarica la lista dopo la modifica/aggiunta

    def _delete_item(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selezione Mancante", "Seleziona un periodo da eliminare.")
            return
        
        periodo_data = self.table.item(selected_items[0].row(), 0).data(Qt.UserRole)
        periodo_id = periodo_data['id']
        nome = periodo_data['nome']

        reply = QMessageBox.question(self, "Conferma Eliminazione", f"Sei sicuro di voler eliminare il periodo '{nome}'?\nQuesta operazione è possibile solo se il periodo non è utilizzato.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.elimina_periodo_storico(periodo_id)
                self.load_data()
            except DBMError as e:
                QMessageBox.critical(self, "Errore Eliminazione", str(e))
class GestioneTipiLocalitaWidget(LazyLoadedWidget):
    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Gestione Tipologie Località (Via, Piazza, Borgata, etc.)")
        group_layout = QHBoxLayout(group)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Nome Tipologia", "Descrizione"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        group_layout.addWidget(self.table, 2)

        button_layout = QVBoxLayout()
        btn_add = QPushButton("Aggiungi...")
        btn_add.clicked.connect(self._add_or_edit_item)
        btn_edit = QPushButton("Modifica...")
        btn_edit.clicked.connect(lambda: self._add_or_edit_item(edit_mode=True))
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete_item)
        
        # Aggiungiamo un pulsante di refresh manuale per coerenza
        btn_refresh = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), " Aggiorna")
        btn_refresh.clicked.connect(self.load_data)

        button_layout.addWidget(btn_add)
        button_layout.addWidget(btn_edit)
        button_layout.addWidget(btn_del)
        button_layout.addSpacing(20)
        button_layout.addWidget(btn_refresh)
        button_layout.addStretch()
        group_layout.addLayout(button_layout, 1)

        layout.addWidget(group)
        self.setLayout(layout)

    # --- INIZIO CORREZIONE ---

    def load_data(self):
        """
        Metodo pubblico per caricare o ricaricare i dati delle tipologie di località.
        """
        self.logger.info("Esecuzione di load_data in GestioneTipiLocalitaWidget.")
        self.table.setRowCount(0)
        try:
            tipi = self.db_manager.get_tipi_localita()
            for tipo in tipi:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(tipo['id'])))
                self.table.setItem(row, 1, QTableWidgetItem(tipo['nome']))
                self.table.setItem(row, 2, QTableWidgetItem(tipo.get('descrizione', '')))
            self.table.resizeColumnToContents(0) # Adatta solo la colonna ID
        except DBMError as e:
            QMessageBox.critical(self, "Errore Caricamento", str(e))

    def _load_data_on_first_show(self):
        """
        Metodo per il lazy loading, chiamato dalla classe base.
        Delega il lavoro al metodo pubblico `load_data`.
        """
        self.load_data()

    # --- FINE CORREZIONE ---

    def _add_or_edit_item(self, edit_mode=False):
        tipo_id, old_nome, old_desc = None, "", ""
        if edit_mode:
            selected_items = self.table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Selezione Mancante", "Seleziona una tipologia da modificare.")
                return
            row = selected_items[0].row()
            tipo_id = int(self.table.item(row, 0).text())
            old_nome = self.table.item(row, 1).text()
            old_desc = self.table.item(row, 2).text()
        
        nome, ok = QInputDialog.getText(self, "Tipologia Località", "Nome:", text=old_nome)
        if ok and nome:
            desc, ok2 = QInputDialog.getText(self, "Tipologia Località", "Descrizione (opzionale):", text=old_desc)
            if ok2:
                try:
                    self.db_manager.gestisci_tipo_localita(tipo_id, nome, desc)
                    self.load_data()
                except (DBMError, DBDataError, DBUniqueConstraintError) as e:
                    QMessageBox.critical(self, "Errore", str(e))

    def _delete_item(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selezione Mancante", "Seleziona una tipologia da eliminare.")
            return
        
        row = selected_items[0].row()
        tipo_id = int(self.table.item(row, 0).text())
        nome = self.table.item(row, 1).text()

        reply = QMessageBox.question(self, "Conferma Eliminazione", f"Sei sicuro di voler eliminare la tipologia '{nome}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.elimina_tipo_localita(tipo_id)
                self.load_data()
            except DBMError as e:
                QMessageBox.critical(self, "Errore Eliminazione", str(e))

class GestioneTitoliPossessoWidget(LazyLoadedWidget):
    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Gestione Titoli di Possesso (Proprietà, Usufrutto, Enfiteusi, etc.)")
        group_layout = QHBoxLayout(group)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Titolo", "Descrizione"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        group_layout.addWidget(self.table, 2)

        button_layout = QVBoxLayout()
        btn_add = QPushButton("Aggiungi...")
        btn_add.clicked.connect(self._add_or_edit_item)
        btn_edit = QPushButton("Modifica...")
        btn_edit.clicked.connect(lambda: self._add_or_edit_item(edit_mode=True))
        btn_del = QPushButton("Elimina")
        btn_del.clicked.connect(self._delete_item)
        btn_refresh = QPushButton(QApplication.style().standardIcon(QStyle.SP_BrowserReload), " Aggiorna")
        btn_refresh.clicked.connect(self.load_data)

        button_layout.addWidget(btn_add)
        button_layout.addWidget(btn_edit)
        button_layout.addWidget(btn_del)
        button_layout.addSpacing(20)
        button_layout.addWidget(btn_refresh)
        button_layout.addStretch()
        group_layout.addLayout(button_layout, 1)

        layout.addWidget(group)
        self.setLayout(layout)

    def load_data(self):
        self.table.setRowCount(0)
        try:
            titoli = self.db_manager.get_titoli_possesso()
            for t in titoli:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(t['id'])))
                self.table.setItem(row, 1, QTableWidgetItem(t['nome']))
                self.table.setItem(row, 2, QTableWidgetItem(t.get('descrizione', '') or ''))
            self.table.resizeColumnToContents(0)
        except DBMError as e:
            QMessageBox.critical(self, "Errore Caricamento", str(e))

    def _load_data_on_first_show(self):
        self.load_data()

    def _add_or_edit_item(self, edit_mode=False):
        titolo_id, old_nome, old_desc = None, "", ""
        if edit_mode:
            selected = self.table.selectedItems()
            if not selected:
                QMessageBox.warning(self, "Selezione Mancante", "Seleziona un titolo da modificare.")
                return
            row = selected[0].row()
            titolo_id = int(self.table.item(row, 0).text())
            old_nome = self.table.item(row, 1).text()
            old_desc = self.table.item(row, 2).text()

        nome, ok = QInputDialog.getText(self, "Titolo di Possesso", "Titolo:", text=old_nome)
        if ok and nome:
            desc, ok2 = QInputDialog.getText(self, "Titolo di Possesso", "Descrizione (opzionale):", text=old_desc)
            if ok2:
                try:
                    self.db_manager.gestisci_titolo_possesso(titolo_id, nome, desc)
                    self.load_data()
                except (DBMError, DBDataError, DBUniqueConstraintError) as e:
                    QMessageBox.critical(self, "Errore", str(e))

    def _delete_item(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Selezione Mancante", "Seleziona un titolo da eliminare.")
            return
        row = selected[0].row()
        titolo_id = int(self.table.item(row, 0).text())
        nome = self.table.item(row, 1).text()
        reply = QMessageBox.question(self, "Conferma Eliminazione",
                                     f"Eliminare il titolo '{nome}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.elimina_titolo_possesso(titolo_id)
                self.load_data()
            except DBMError as e:
                QMessageBox.critical(self, "Errore Eliminazione", str(e))


class RegistraConsultazioneWidget(QWidget):
    def __init__(self, db_manager: 'CatastoDBManager',
                 current_user_info: Optional[Dict[str, Any]],
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user_info = current_user_info

        self._initUI()

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        form_group = QGroupBox("Registra Nuova Consultazione")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.data_consultazione_edit = QDateEdit(
            calendarPopup=True)  # Nome UI: data_consultazione_edit
        self.data_consultazione_edit.setDate(QDate.currentDate())
        self.data_consultazione_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("Data Consultazione (*):",
                           self.data_consultazione_edit)  # Colonna DB: data

        self.richiedente_edit = QLineEdit()
        self.richiedente_edit.setPlaceholderText(
            "Nome e Cognome del richiedente")
        # Colonna DB: richiedente
        form_layout.addRow("Richiedente (*):", self.richiedente_edit)

        self.doc_id_edit = QLineEdit()
        self.doc_id_edit.setPlaceholderText(
            "Es. CI N. XXXXXX, Patente N. YYYYYY")
        # Colonna DB: documento_identita
        form_layout.addRow("Documento Identità (opz.):", self.doc_id_edit)

        self.motivazione_edit = QTextEdit()
        self.motivazione_edit.setPlaceholderText(
            "Motivazione della richiesta di consultazione")
        self.motivazione_edit.setFixedHeight(80)
        # Colonna DB: motivazione
        form_layout.addRow("Motivazione (opz.):", self.motivazione_edit)

        self.materiale_edit = QTextEdit()
        self.materiale_edit.setPlaceholderText(
            "Descrizione dettagliata del materiale consultato (es. Partita N. 123 Comune X, Mappa Foglio Y)")
        self.materiale_edit.setFixedHeight(120)
        # Colonna DB: materiale_consultato
        form_layout.addRow("Materiale Consultato (*):", self.materiale_edit)

        # Modificato da QLabel a QLineEdit per permettere modifica
        self.funzionario_edit = QLineEdit()
        if self.current_user_info and self.current_user_info.get('nome_completo'):
            self.funzionario_edit.setText(
                self.current_user_info.get('nome_completo'))
        else:
            self.funzionario_edit.setPlaceholderText("Nome del funzionario")
        # Colonna DB: funzionario_autorizzante
        form_layout.addRow("Funzionario Autorizzante (opz.):",
                           self.funzionario_edit)

        # Rimuoviamo note_interne dato che non c'è nella tabella
        # self.note_interne_edit = QTextEdit() ...
        # form_layout.addRow("Note Interne (opz.):", self.note_interne_edit)

        main_layout.addWidget(form_group)

        button_layout = QHBoxLayout()
        self.btn_registra_consultazione = QPushButton(QApplication.style(
        ).standardIcon(QStyle.SP_DialogSaveButton), " Registra Consultazione")
        self.btn_registra_consultazione.clicked.connect(
            self._salva_consultazione)
        self.btn_pulisci_campi = QPushButton(QApplication.style().standardIcon(
            QStyle.SP_DialogDiscardButton), " Pulisci Campi")
        self.btn_pulisci_campi.clicked.connect(self._pulisci_campi)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_registra_consultazione)
        button_layout.addWidget(self.btn_pulisci_campi)
        main_layout.addLayout(button_layout)

        main_layout.addStretch(1)
        self.setLayout(main_layout)
        self._pulisci_campi()  # Pulisce e imposta focus iniziale

    def _pulisci_form_registrazione(self):
        """Pulisce tutti i campi del form di registrazione proprietà."""
        self.comune_id = None
        self.comune_display.setText("Nessun comune selezionato")
        self.num_partita_edit.setValue(1)  # O il suo valore di default
        self.data_edit.setDate(QDate.currentDate())
        self.possessori_data = []
        self.immobili_data = []
        # Assumendo che questi metodi aggiornino le tabelle UI
        self.update_possessori_table()
        self.update_immobili_table()
        self.num_partita_edit.setFocus()  # Focus sul primo campo utile
        self.suffisso_partita_edit.clear() # Pulisci il suffisso

    def _pulisci_campi(self):
        self.data_consultazione_edit.setDate(QDate.currentDate())
        self.richiedente_edit.clear()
        self.doc_id_edit.clear()
        self.motivazione_edit.clear()
        self.materiale_edit.clear()

        # Precompila o pulisci funzionario_edit
        if self.current_user_info and self.current_user_info.get('nome_completo'):
            self.funzionario_edit.setText(
                self.current_user_info.get('nome_completo'))
        else:
            self.funzionario_edit.clear()

        self.richiedente_edit.setFocus()

    def _salva_consultazione(self):
        data_cons = self.data_consultazione_edit.date().toPyDate()  # Nome colonna DB: 'data'
        richiedente = self.richiedente_edit.text().strip()
        materiale = self.materiale_edit.toPlainText().strip()

        doc_id = self.doc_id_edit.text().strip() or None
        motivazione = self.motivazione_edit.toPlainText().strip() or None
        funzionario_testo = self.funzionario_edit.text().strip() or None  # Testo libero

        # Validazione UI
        if not richiedente:
            QMessageBox.warning(self, "Dati Mancanti",
                                "Il campo 'Richiedente' è obbligatorio.")
            self.richiedente_edit.setFocus()
            return
        if not materiale:  # Anche se nullabile nel DB, lo rendiamo obbligatorio nella UI
            QMessageBox.warning(
                self, "Dati Mancanti", "Il campo 'Materiale Consultato' è obbligatorio.")
            self.materiale_edit.setFocus()
            return

        try:
            consultazione_id = self.db_manager.registra_nuova_consultazione(
                data_consultazione=data_cons,
                richiedente=richiedente,
                materiale_consultato=materiale,
                funzionario_autorizzante=funzionario_testo,  # Passa il testo
                documento_identita=doc_id,
                motivazione=motivazione
                # note_interne non c'è più
            )
            if consultazione_id is not None:
                QMessageBox.information(
                    self, "Successo", f"Consultazione registrata con successo (ID: {consultazione_id}).")
                self._pulisci_campi()
            # else: errore gestito da eccezioni
        except (DBDataError, DBMError) as e:
            logging.getLogger("CatastoGUI").error(
                f"Errore durante la registrazione della consultazione: {str(e)}", exc_info=False)
            QMessageBox.critical(self, "Errore Registrazione", str(e))
        except Exception as e_gen:
            logging.getLogger("CatastoGUI").critical(
                f"Errore imprevisto registrazione consultazione: {e_gen}", exc_info=True)
            # # # QMessageBox.critical(self, "Errore Imprevisto", f"Errore di sistema: {e_gen}")


# In gui_widgets.py

# In gui_widgets.py, puoi commentare o eliminare la vecchia classe LandingPageWidget
# e aggiungere questa nuova classe.

