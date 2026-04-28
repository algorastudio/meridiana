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

class InserimentoPossessoreWidget(LazyLoadedWidget):
    import_csv_requested = pyqtSignal()

    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)  # Chiama il costruttore della classe base
        self.db_manager = db_manager
        self.comuni_list_data: List[Dict[str, Any]] = []
        # Il logger e il flag _data_loaded sono gestiti dalla classe base

        self._initUI()

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        form_group = QGroupBox("Dati del Nuovo Possessore")
        form_layout = QGridLayout(form_group)
        form_layout.setColumnStretch(1, 1)

        form_layout.addWidget(QLabel("Cognome e Nome (*):"), 0, 0)
        self.cognome_nome_edit = QLineEdit()
        self.cognome_nome_edit.setPlaceholderText("Es. Rossi Mario, Bianchi Giovanni")
        form_layout.addWidget(self.cognome_nome_edit, 0, 1)

        form_layout.addWidget(QLabel("Paternità (es. fu Carlo):"), 1, 0)
        self.paternita_edit = QLineEdit()
        form_layout.addWidget(self.paternita_edit, 1, 1)

        self.btn_genera_nome_completo = QPushButton("Genera Nome Completo")
        self.btn_genera_nome_completo.clicked.connect(self._genera_e_imposta_nome_completo)
        form_layout.addWidget(self.btn_genera_nome_completo, 2, 1, Qt.AlignLeft)

        form_layout.addWidget(QLabel("Nome Completo (generato) (*):"), 3, 0)
        self.nome_completo_edit = QLineEdit()
        self.nome_completo_edit.setPlaceholderText("Verrà generato o inserire manualmente")
        form_layout.addWidget(self.nome_completo_edit, 3, 1)

        form_layout.addWidget(QLabel("Comune di Riferimento (*):"), 4, 0)
        self.comune_combo = QComboBox()
        self.comune_combo.addItem("Caricamento comuni...", None)
        self.comune_combo.setEnabled(False)
        form_layout.addWidget(self.comune_combo, 4, 1)

        self.attivo_checkbox = QCheckBox("Attivo")
        self.attivo_checkbox.setChecked(True)
        form_layout.addWidget(self.attivo_checkbox, 5, 1)

        main_layout.addWidget(form_group)

        import_group = QGroupBox("Azioni Aggiuntive")
        import_layout = QHBoxLayout(import_group)
        self.import_button = QPushButton("📂 Importa Possessori da CSV..."); 
        self.import_button.clicked.connect(self.import_csv_requested.emit)
        self.info_button_possessori = QPushButton("Info Formato CSV"); 
        self.info_button_possessori.clicked.connect(self._mostra_info_formato_csv)
        import_layout.addWidget(self.import_button)
        import_layout.addWidget(self.info_button_possessori)
        import_layout.addStretch()
        main_layout.addWidget(import_group)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salva Nuovo Possessore")
        self.save_button.clicked.connect(self._salva_possessore)
        self.clear_button = QPushButton("Pulisci Campi")
        self.clear_button.clicked.connect(self._pulisci_campi_possessore)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)
        main_layout.addLayout(button_layout)

        main_layout.addStretch(1)
        self.setLayout(main_layout)

    def _load_data_on_first_show(self):
        """Metodo per il lazy loading: carica i comuni la prima volta che il tab viene visualizzato."""
        self.logger.info("InserimentoPossessoreWidget: Esecuzione lazy loading dei comuni...")
        self._load_comuni_for_combo()

    def _load_comuni_for_combo(self):
        """Carica e popola il QComboBox con l'elenco dei comuni."""
        self.comune_combo.clear()
        try:
            comuni = self.db_manager.get_elenco_comuni_semplice()
            if comuni:
                self.comune_combo.setEnabled(True)
                self.comune_combo.addItem("--- Seleziona un comune ---", None)
                for comune_id, nome in comuni:
                    self.comune_combo.addItem(nome, userData=comune_id)
            else:
                self.comune_combo.addItem("Nessun comune registrato", None)
                self.comune_combo.setEnabled(False)
        except DBMError as e:
            self.logger.error(f"Errore caricamento comuni: {e}")
            self.comune_combo.addItem("Errore caricamento", None)
            self.comune_combo.setEnabled(False)
    def _mostra_info_formato_csv(self):
        """Mostra un dialogo con le informazioni sul formato CSV per i possessori."""
        info_text = """
        <h3>Formato CSV per Importazione Possessori</h3>
        <p>Il file CSV deve rispettare le seguenti regole:</p>
        <ul>
            <li>Utilizzare il punto e virgola (<b>;</b>) come delimitatore.</li>
            <li>La prima riga deve contenere le intestazioni delle colonne.</li>
            <li>Le virgolette doppie (") sono gestite correttamente.</li>
        </ul>
        <p><b>Colonne Richieste:</b></p>
        <ul>
            <li><b>cognome_nome</b>: Il cognome e nome separati da spazio (es. Rossi Mario).</li>
            <li><b>nome_completo</b>: Il nome completo come deve apparire, includendo la paternità.</li>
        </ul>
        <p><b>Colonne Opzionali:</b></p>
        <ul>
            <li><b>paternita</b>: La paternità (es. fu Carlo).</li>
        </ul>
        <hr>
        <p><b>Esempio di contenuto del file:</b></p>
        <pre style="background-color:#f0f0f0; padding:5px;"><code>cognome_nome;paternita;nome_completo
        Rossi Mario;fu Giovanni;Rossi Mario fu Giovanni
        Bianchi Giuseppe;;Bianchi Giuseppe</code></pre>
        """
        QMessageBox.information(self, "Guida Formato CSV - Possessori", info_text)

    def _genera_e_imposta_nome_completo(self):
        """
        Genera il nome completo concatenando "Cognome Nome" e "Paternità"
        e lo imposta nel campo nome_completo_edit.
        """
        cognome_nome = self.cognome_nome_edit.text().strip()
        paternita = self.paternita_edit.text().strip()
        nome_completo_generato = cognome_nome # Inizia con cognome e nome

        if cognome_nome and paternita: # Aggiungi paternità solo se entrambi sono presenti
            nome_completo_generato += f" {paternita}" # Es. "Rossi Mario fu Giovanni"
        elif cognome_nome and not paternita: # Solo cognome e nome
            pass # nome_completo_generato è già corretto
        elif not cognome_nome and paternita: # Solo paternità (improbabile ma gestito)
            nome_completo_generato = paternita 
        else: # Entrambi vuoti
            nome_completo_generato = ""
            
        self.nome_completo_edit.setText(nome_completo_generato.strip())

    def _pulisci_campi_possessore(self):
        """Pulisce i campi del form possessore."""
        self.cognome_nome_edit.clear()
        self.paternita_edit.clear()
        self.nome_completo_edit.clear()
        if self.comune_combo.count() > 0:
            self.comune_combo.setCurrentIndex(0) # O -1 per nessuna selezione se preferito
        self.attivo_checkbox.setChecked(True)
        self.cognome_nome_edit.setFocus()

    def _salva_possessore(self):
        # Ora 'cognome_nome' è l'input primario per nome/cognome
        # 'nome_completo' è quello generato o corretto dall'utente
        cognome_nome_input = self.cognome_nome_edit.text().strip() # Usato per DB e per generare nome completo se serve
        paternita_input = self.paternita_edit.text().strip()
        nome_completo_input = self.nome_completo_edit.text().strip() # Questo è il valore da salvare

        idx_comune = self.comune_combo.currentIndex()
        comune_id_selezionato_data = self.comune_combo.itemData(idx_comune)
        comune_id_selezionato: Optional[int] = None
        if comune_id_selezionato_data is not None:
            try:
                comune_id_selezionato = int(comune_id_selezionato_data)
            except ValueError:
                QMessageBox.warning(self, "Errore Interno", "ID comune selezionato non valido.")
                return

        attivo = self.attivo_checkbox.isChecked()

        if not nome_completo_input: # Il nome completo (generato o manuale) rimane obbligatorio
            QMessageBox.warning(self, "Dati Mancanti", "Il campo 'Nome Completo' è obbligatorio. Utilizzare 'Genera Nome Completo' o inserirlo manualmente.")
            self.nome_completo_edit.setFocus()
            return
        if not cognome_nome_input: # Rendiamo anche questo obbligatorio per coerenza
            QMessageBox.warning(self, "Dati Mancanti", "Il campo 'Cognome e Nome' è obbligatorio.")
            self.cognome_nome_edit.setFocus()
            return
        if comune_id_selezionato is None:
            QMessageBox.warning(self, "Dati Mancanti", "Selezionare un comune di riferimento.")
            self.comune_combo.setFocus()
            return

        try:
            new_possessore_id = self.db_manager.create_possessore(
                nome_completo=nome_completo_input,
                paternita=paternita_input if paternita_input else None,
                comune_riferimento_id=comune_id_selezionato,
                attivo=attivo,
                cognome_nome=cognome_nome_input # Passa il campo cognome_nome al DB manager
            )

            if new_possessore_id is not None:
                QMessageBox.information(self, "Successo",
                                        f"Possessore '{nome_completo_input}' creato con successo. ID: {new_possessore_id}.")
                self._pulisci_campi_possessore()
                # Qui potresti emettere un segnale se altri widget devono essere aggiornati
            # else: create_possessore solleva eccezioni
        # ... (stessa gestione eccezioni di prima per _salva_possessore) ...
        except DBUniqueConstraintError as uve:
            logging.getLogger("CatastoGUI").warning(f"Errore di unicità salvando possessore '{nome_completo_input}': {uve.message}")
            QMessageBox.critical(self, "Errore di Unicità", f"Impossibile creare il possessore:\n{uve.message}")
        except DBDataError as dde:
            logging.getLogger("CatastoGUI").warning(f"Errore dati per possessore '{nome_completo_input}': {dde.message}")
            QMessageBox.warning(self, "Dati Non Validi", f"Impossibile creare il possessore:\n{dde.message}")
        except DBMError as dbe:
            logging.getLogger("CatastoGUI").error(f"Errore database salvando possessore '{nome_completo_input}': {dbe.message}", exc_info=True)
            QMessageBox.critical(self, "Errore Database", f"Si è verificato un errore durante la creazione del possessore:\n{dbe.message}")
        except Exception as e:
            logging.getLogger("CatastoGUI").critical(f"Errore critico imprevisto salvando possessore '{nome_completo_input}': {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Critico Imprevisto", f"Errore di sistema imprevisto:\n{type(e).__name__}: {e}")



# --- Scheda per Localita ---
class RicercaAvanzataImmobiliWidget(QWidget):
    def __init__(self, db_manager: CatastoDBManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_comune_id: Optional[int] = None
        self.selected_localita_id: Optional[int] = None

        main_layout = QVBoxLayout(self)

        criteria_group = QGroupBox("Criteri di Ricerca Avanzata Immobili")
        criteria_layout = QGridLayout(criteria_group)

        # Riga 0: Comune
        criteria_layout.addWidget(QLabel("Comune:"), 0, 0)
        self.comune_display_label = QLabel("Qualsiasi comune")
        criteria_layout.addWidget(self.comune_display_label, 0, 1)
        self.btn_seleziona_comune = QPushButton("Seleziona...")
        self.btn_seleziona_comune.clicked.connect(
            self._seleziona_comune_per_ricerca)
        criteria_layout.addWidget(self.btn_seleziona_comune, 0, 2)
        self.btn_reset_comune = QPushButton("Reset")
        self.btn_reset_comune.clicked.connect(self._reset_comune_ricerca)
        criteria_layout.addWidget(self.btn_reset_comune, 0, 3)

        # Riga 1: Località
        criteria_layout.addWidget(QLabel("Località:"), 1, 0)
        self.localita_display_label = QLabel("Qualsiasi località")
        criteria_layout.addWidget(self.localita_display_label, 1, 1)
        self.btn_seleziona_localita = QPushButton("Seleziona...")
        self.btn_seleziona_localita.clicked.connect(
            self._seleziona_localita_per_ricerca)
        self.btn_seleziona_localita.setEnabled(False)
        criteria_layout.addWidget(self.btn_seleziona_localita, 1, 2)
        self.btn_reset_localita = QPushButton("Reset")
        self.btn_reset_localita.clicked.connect(self._reset_localita_ricerca)
        criteria_layout.addWidget(self.btn_reset_localita, 1, 3)

        # Riga 2: Natura e Classificazione
        criteria_layout.addWidget(QLabel("Natura Immobile:"), 2, 0)
        self.natura_edit = QLineEdit()
        self.natura_edit.setPlaceholderText(
            "Es. Casa, Terreno (lascia vuoto per qualsiasi)")
        criteria_layout.addWidget(self.natura_edit, 2, 1, 1, 3)

        criteria_layout.addWidget(QLabel("Classificazione:"), 3, 0)
        self.classificazione_edit = QLineEdit()
        self.classificazione_edit.setPlaceholderText(
            "Es. Abitazione civile, Oliveto (lascia vuoto per qualsiasi)")
        criteria_layout.addWidget(self.classificazione_edit, 3, 1, 1, 3)

        # Riga 4: Consistenza (come testo per ricerca parziale)
        criteria_layout.addWidget(QLabel("Testo Consistenza:"), 4, 0)
        self.consistenza_search_edit = QLineEdit()
        self.consistenza_search_edit.setPlaceholderText(
            "Es. 120, are, vani (ricerca parziale)")
        criteria_layout.addWidget(self.consistenza_search_edit, 4, 1, 1, 3)

        # Riga 5: Numero Piani
        criteria_layout.addWidget(QLabel("Piani Min:"), 5, 0)
        self.piani_min_spinbox = QSpinBox()
        self.piani_min_spinbox.setMinimum(0)
        self.piani_min_spinbox.setValue(0)
        criteria_layout.addWidget(self.piani_min_spinbox, 5, 1)
        criteria_layout.addWidget(QLabel("Piani Max:"), 5, 2)
        self.piani_max_spinbox = QSpinBox()
        self.piani_max_spinbox.setMinimum(0)
        self.piani_max_spinbox.setMaximum(99)
        self.piani_max_spinbox.setValue(0)
        self.piani_max_spinbox.setSpecialValueText("Qualsiasi")
        criteria_layout.addWidget(self.piani_max_spinbox, 5, 3)

        # Riga 6: Numero Vani
        criteria_layout.addWidget(QLabel("Vani Min:"), 6, 0)
        self.vani_min_spinbox = QSpinBox()
        self.vani_min_spinbox.setMinimum(0)
        self.vani_min_spinbox.setValue(0)
        criteria_layout.addWidget(self.vani_min_spinbox, 6, 1)
        criteria_layout.addWidget(QLabel("Vani Max:"), 6, 2)
        self.vani_max_spinbox = QSpinBox()
        self.vani_max_spinbox.setMinimum(0)
        self.vani_max_spinbox.setMaximum(999)
        self.vani_max_spinbox.setValue(0)
        self.vani_max_spinbox.setSpecialValueText("Qualsiasi")
        criteria_layout.addWidget(self.vani_max_spinbox, 6, 3)

        # Riga 7: Nome Possessore (NUOVO CAMPO)
        criteria_layout.addWidget(QLabel("Nome Possessore:"), 7, 0)
        self.nome_possessore_edit = QLineEdit()
        self.nome_possessore_edit.setPlaceholderText(
            "Ricerca parziale nome possessore (lascia vuoto per qualsiasi)")
        criteria_layout.addWidget(self.nome_possessore_edit, 7, 1, 1, 3)

        main_layout.addWidget(criteria_group)

        self.btn_esegui_ricerca_immobili = QPushButton(
            "Esegui Ricerca Immobili")
        self.btn_esegui_ricerca_immobili.setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_esegui_ricerca_immobili.clicked.connect(
            self._esegui_ricerca_effettiva)
        main_layout.addWidget(self.btn_esegui_ricerca_immobili)

        results_group = QGroupBox("Risultati Ricerca")
        results_layout = QVBoxLayout(results_group)
        self.risultati_immobili_table = QTableWidget()
        # Colonne basate sulla funzione SQL cerca_immobili_avanzato
        self.risultati_immobili_table.setColumnCount(10)
        self.risultati_immobili_table.setHorizontalHeaderLabels([
            "ID Imm.", "Part. N.", "Comune", "Località", "Natura",
            "Class.", "Consist.", "Piani", "Vani", "Possessori"
        ])
        self.risultati_immobili_table.setEditTriggers(
            QTableWidget.NoEditTriggers)
        self.risultati_immobili_table.setSelectionBehavior(
            QTableWidget.SelectRows)
        self.risultati_immobili_table.setAlternatingRowColors(True)
        self.risultati_immobili_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)  # ResizeToContents
        self.risultati_immobili_table.horizontalHeader(
        ).setStretchLastSection(True)  # Ultima colonna stretch
        self.risultati_immobili_table.setSortingEnabled(True)
        results_layout.addWidget(self.risultati_immobili_table)
        main_layout.addWidget(results_group)

        self.setLayout(main_layout)

    def _seleziona_comune_per_ricerca(self):
        dialog = ComuneSelectionDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_comune_id:
            self.selected_comune_id = dialog.selected_comune_id
            self.comune_display_label.setText(
                f"{dialog.selected_comune_name} (ID: {self.selected_comune_id})")
            self.btn_seleziona_localita.setEnabled(True)
            self._reset_localita_ricerca()
        elif not self.selected_comune_id:
            self.comune_display_label.setText("Qualsiasi comune")
            self.btn_seleziona_localita.setEnabled(False)

    def _reset_comune_ricerca(self):
        self.selected_comune_id = None
        self.comune_display_label.setText("Qualsiasi comune")
        self.btn_seleziona_localita.setEnabled(False)
        self._reset_localita_ricerca()

    def _seleziona_localita_per_ricerca(self):
        if not self.selected_comune_id:
            QMessageBox.warning(
                self, "Comune Mancante", "Seleziona prima un comune per filtrare le località.")
            return

        # Apre LocalitaSelectionDialog in MODALITÀ SELEZIONE
        dialog = LocalitaSelectionDialog(self.db_manager, self.selected_comune_id, self,
                                         selection_mode=True)

        if dialog.exec_() == QDialog.Accepted:  # Se l'utente ha premuto "Seleziona" nel dialogo
            if dialog.selected_localita_id is not None and dialog.selected_localita_name is not None:
                self.selected_localita_id = dialog.selected_localita_id
                self.localita_display_label.setText(
                    f"{dialog.selected_localita_name} (ID: {self.selected_localita_id})")
                logging.getLogger("CatastoGUI").info(
                    f"RicercaAvanzataImmobili: Località selezionata ID: {self.selected_localita_id}, Nome: {dialog.selected_localita_name}")
            else:
                # Questo caso è improbabile se _conferma_selezione funziona, ma per sicurezza
                logging.getLogger("CatastoGUI").warning(
                    "RicercaAvanzataImmobili: LocalitaSelectionDialog accettato ma nessun ID/nome località valido è stato restituito.")
                # Potrebbe essere utile resettare qui, o lasciare la selezione precedente.
                # self._reset_localita_ricerca()
        # else: # Dialogo annullato (premuto "Annulla" o chiuso)
            # Non fare nulla, la selezione precedente (o nessuna selezione) rimane.
            # Non è necessario chiamare self._reset_localita_ricerca() a meno che non sia il comportamento desiderato.
            logging.getLogger("CatastoGUI").info(
                "Selezione località annullata o dialogo chiuso.")

    def _reset_localita_ricerca(self):
        self.selected_localita_id = None
        self.localita_display_label.setText("Qualsiasi località")

    def _esegui_ricerca_effettiva(self):
        p_comune_id = self.selected_comune_id
        p_localita_id = self.selected_localita_id
        p_natura = self.natura_edit.text().strip() or None
        p_classificazione = self.classificazione_edit.text().strip() or None
        # Campo unico per ricerca testuale consistenza
        p_consistenza_search = self.consistenza_search_edit.text().strip() or None

        p_piani_min = self.piani_min_spinbox.value(
        ) if self.piani_min_spinbox.value() > 0 else None
        p_piani_max = self.piani_max_spinbox.value() if self.piani_max_spinbox.value(
        ) != 0 else None  # 0 è speciale "Qualsiasi"

        p_vani_min = self.vani_min_spinbox.value(
        ) if self.vani_min_spinbox.value() > 0 else None
        p_vani_max = self.vani_max_spinbox.value(
        ) if self.vani_max_spinbox.value() != 0 else None

        p_nome_possessore = self.nome_possessore_edit.text().strip() or None

        # --- STAMPE DI DEBUG DA AGGIUNGERE/DECOMMENTARE ---
        print("-" * 30)
        print("DEBUG GUI: Parametri inviati a ricerca_avanzata_immobili_gui:")
        print(f"  comune_id: {p_comune_id} (tipo: {type(p_comune_id)})")
        print(f"  localita_id: {p_localita_id} (tipo: {type(p_localita_id)})")
        print(f"  natura_search: '{p_natura}' (tipo: {type(p_natura)})")
        print(
            f"  classificazione_search: '{p_classificazione}' (tipo: {type(p_classificazione)})")
        print(
            f"  consistenza_search: '{p_consistenza_search}' (tipo: {type(p_consistenza_search)})")
        print(f"  piani_min: {p_piani_min} (tipo: {type(p_piani_min)})")
        print(f"  piani_max: {p_piani_max} (tipo: {type(p_piani_max)})")
        print(f"  vani_min: {p_vani_min} (tipo: {type(p_vani_min)})")
        print(f"  vani_max: {p_vani_max} (tipo: {type(p_vani_max)})")
        print(
            f"  nome_possessore_search: '{p_nome_possessore}' (tipo: {type(p_nome_possessore)})")
        print("-" * 30)
        # --- FINE STAMPE DI DEBUG ---

        try:
            immobili_trovati = self.db_manager.ricerca_avanzata_immobili_gui(
                comune_id=p_comune_id,
                localita_id=p_localita_id,
                natura_search=p_natura,
                classificazione_search=p_classificazione,
                consistenza_search=p_consistenza_search,
                piani_min=p_piani_min,
                piani_max=p_piani_max,
                vani_min=p_vani_min,
                vani_max=p_vani_max,
                nome_possessore_search=p_nome_possessore,
                data_inizio_possesso_search=None,  # Non ancora in GUI
                data_fine_possesso_search=None    # Non ancora in GUI
            )

            self.risultati_immobili_table.setRowCount(0)
            if immobili_trovati:
                self.risultati_immobili_table.setRowCount(
                    len(immobili_trovati))
                for row_idx, immobile in enumerate(immobili_trovati):
                    col = 0
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(str(immobile.get('id_immobile', ''))))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(str(immobile.get('numero_partita', ''))))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(immobile.get('comune_nome', '')))
                    col += 1
                    localita_display = f"{immobile.get('localita_nome', '')}"
                    if immobile.get('localita_tipo'):
                        localita_display += f" ({immobile.get('localita_tipo')})"
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(localita_display.strip()))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(immobile.get('natura', '')))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(immobile.get('classificazione', '')))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(immobile.get('consistenza', '')))
                    col += 1
                    self.risultati_immobili_table.setItem(row_idx, col, QTableWidgetItem(str(
                        immobile.get('numero_piani', '')) if immobile.get('numero_piani') is not None else ''))
                    col += 1
                    self.risultati_immobili_table.setItem(row_idx, col, QTableWidgetItem(str(
                        immobile.get('numero_vani', '')) if immobile.get('numero_vani') is not None else ''))
                    col += 1
                    self.risultati_immobili_table.setItem(
                        row_idx, col, QTableWidgetItem(immobile.get('possessori_attuali', '')))
                    col += 1  # Campo dalla funzione SQL

                # self.risultati_immobili_table.resizeColumnsToContents() # Potrebbe essere lento con molti dati
                QMessageBox.information(
                    self, "Ricerca Completata", f"Trovati {len(immobili_trovati)} immobili.")
            else:
                QMessageBox.information(
                    self, "Ricerca Completata", "Nessun immobile trovato con i criteri specificati.")
        except AttributeError as ae:
            logging.getLogger("CatastoGUI").error(
                f"Metodo di ricerca immobili non trovato nel db_manager: {ae}", exc_info=True)
            QMessageBox.critical(
                self, "Errore Interno", f"Funzionalità di ricerca non implementata correttamente nel gestore DB: {ae}")
        except Exception as e:
            logging.getLogger("CatastoGUI").error(
                f"Errore durante la ricerca avanzata immobili: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Ricerca",
                                 f"Si è verificato un errore imprevisto: {e}")

# In gui_widgets.py, SOSTITUISCI l'intera classe InserimentoComuneWidget con questa:

class RegistrazioneProprietaWidget(LazyLoadedWidget):
    partita_creata_per_operazioni_collegate = pyqtSignal(int, int)

    def __init__(self, db_manager: 'CatastoDBManager', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.comune_id: Optional[int] = None
        self.possessori_data: List[Dict[str, Any]] = []
        self.immobili_data: List[Dict[str, Any]] = []
        self.localita_cache: List[Dict[str, Any]] = []
        self.possessori_cache: List[Dict[str, Any]] = []
        self.immobili_cache: List[Dict[str, Any]] = []
        self._initUI()

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        container_widget = QWidget(); layout = QVBoxLayout(container_widget)
        scroll_area.setWidget(container_widget)
        
        # --- 1. DATI PARTITA (LAYOUT COMPATTO) ---
        form_group = QGroupBox("1. Dati della Nuova Partita")
        form_layout = QGridLayout(form_group)
        self.comune_display = QLabel("Nessun comune selezionato."); self.comune_display.setStyleSheet("font-weight: bold;")
        self.comune_button = QPushButton("Seleziona Comune..."); self.comune_button.clicked.connect(self._select_comune)
        form_layout.addWidget(QLabel("Comune (*):"), 0, 0); form_layout.addWidget(self.comune_display, 0, 1, 1, 2)
        form_layout.addWidget(self.comune_button, 0, 3)
        
        # --- INIZIO MODIFICA LAYOUT ---
        self.num_partita_edit = QSpinBox(); self.num_partita_edit.setRange(1, 9999999)
        self.suffisso_partita_edit = QLineEdit(); self.suffisso_partita_edit.setPlaceholderText("Es. A"); self.suffisso_partita_edit.setMaximumWidth(80)
        self.data_edit = QDateEdit(calendarPopup=True); self.data_edit.setDate(QDate.currentDate()); self.data_edit.setDisplayFormat("yyyy-MM-dd")
        
        partita_line_layout = QHBoxLayout()
        partita_line_layout.addWidget(QLabel("Numero Partita (*):")); partita_line_layout.addWidget(self.num_partita_edit)
        partita_line_layout.addWidget(QLabel("Suffisso:")); partita_line_layout.addWidget(self.suffisso_partita_edit)
        partita_line_layout.addStretch()
        form_layout.addLayout(partita_line_layout, 1, 0, 1, 4)
        
        form_layout.addWidget(QLabel("Data Impianto (*):"), 2, 0); form_layout.addWidget(self.data_edit, 2, 1)
        # --- FINE MODIFICA LAYOUT ---
        
        layout.addWidget(form_group)

        # --- 2. POSSESSORI (FLUSSO MIGLIORATO) ---
        possessori_group = QGroupBox("2. Possessori Associati")
        possessori_layout = QVBoxLayout(possessori_group)
        self.possessori_table = QTableWidget(); self.possessori_table.setColumnCount(4); self.possessori_table.setHorizontalHeaderLabels(["ID", "Nome Completo", "Titolo", "Quota"])
        self.possessori_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); self.possessori_table.setMinimumHeight(120)
        self.btn_rem_poss = QPushButton("Rimuovi Selezionato"); self.btn_rem_poss.clicked.connect(self.remove_possessore)
        possessori_layout.addWidget(self.possessori_table); possessori_layout.addWidget(self.btn_rem_poss, 0, Qt.AlignRight)
        
        add_poss_group = QGroupBox("Aggiungi Possessore"); add_poss_layout = QGridLayout(add_poss_group)
        self.possessore_search_combo = QComboBox(); self.possessore_search_combo.setEditable(True); self.possessore_search_combo.setPlaceholderText("Cerca possessore esistente...")
        self.possessore_search_combo.completer().setCompletionMode(QCompleter.PopupCompletion); self.possessore_search_combo.completer().setFilterMode(Qt.MatchContains)
        self.btn_add_selected_poss = QPushButton("Aggiungi Selezionato"); self.btn_add_selected_poss.clicked.connect(self._add_selected_possessore)
        self.btn_create_new_poss = QPushButton("Crea Nuovo..."); self.btn_create_new_poss.clicked.connect(self._create_and_add_new_possessore)
        add_poss_layout.addWidget(QLabel("Cerca:"), 0, 0); add_poss_layout.addWidget(self.possessore_search_combo, 0, 1)
        add_poss_layout.addWidget(self.btn_add_selected_poss, 0, 2); add_poss_layout.addWidget(self.btn_create_new_poss, 0, 3)
        possessori_layout.addWidget(add_poss_group); layout.addWidget(possessori_group)

        # --- 3. IMMOBILI (FLUSSO MIGLIORATO) ---
        immobili_group = QGroupBox("3. Immobili Associati"); immobili_layout = QVBoxLayout(immobili_group)
        self.immobili_table = QTableWidget(); self.immobili_table.setColumnCount(5); self.immobili_table.setHorizontalHeaderLabels(["Natura", "Località", "Classificazione", "Consistenza", "Piani/Vani"])
        self.immobili_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.immobili_table.setMinimumHeight(120)
        self.btn_rem_imm = QPushButton("Rimuovi Selezionato"); self.btn_rem_imm.clicked.connect(self.remove_immobile)
        immobili_layout.addWidget(self.immobili_table); immobili_layout.addWidget(self.btn_rem_imm, 0, Qt.AlignRight)
        add_imm_tabs = QTabWidget(); add_imm_tabs.addTab(self._create_add_immobile_esistente_tab(), "Aggiungi Esistente"); add_imm_tabs.addTab(self._create_add_immobile_nuovo_tab(), "Crea Nuovo")
        immobili_layout.addWidget(add_imm_tabs); layout.addWidget(immobili_group)

        # --- 4. REGISTRAZIONE FINALE ---
        self.btn_registra_proprieta = QPushButton("Registra Nuova Proprietà e Tutti i Componenti"); self.btn_registra_proprieta.clicked.connect(self._salva_proprieta)
        self.btn_registra_proprieta.setStyleSheet("font-weight: bold; padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb;"); 
        self.btn_registra_proprieta.setEnabled(False) # Inizia disabilitato
        layout.addWidget(self.btn_registra_proprieta); layout.addStretch(1)
        
        self._update_registra_button_state()

    # --- NUOVO METODO PER AGGIORNARE LO STATO DEL PULSANTE ---
    def _update_registra_button_state(self):
        """
        Abilita il pulsante di registrazione finale solo se tutte le 
        condizioni necessarie sono soddisfatte.
        """
        is_ready = bool(
            self.comune_id and      # Deve essere selezionato un comune
            self.possessori_data and  # La lista possessori non deve essere vuota
            self.immobili_data       # La lista immobili non deve essere vuota
        )
        self.btn_registra_proprieta.setEnabled(is_ready)

        if is_ready:
            self.btn_registra_proprieta.setToolTip("Pronto per registrare la proprietà nel database.")
        else:
            reasons = []
            if not self.comune_id: reasons.append("selezionare un comune")
            if not self.possessori_data: reasons.append("aggiungere almeno un possessore")
            if not self.immobili_data: reasons.append("aggiungere almeno un immobile")
            tooltip_text = f"Per abilitare, è necessario: {', '.join(reasons)}."
            self.btn_registra_proprieta.setToolTip(tooltip_text)

    
    def _create_add_immobile_esistente_tab(self):
        widget = QWidget(); layout = QGridLayout(widget)
        self.imm_search_combo = QComboBox(); self.imm_search_combo.setEditable(True); self.imm_search_combo.setPlaceholderText("Seleziona prima un comune...")
        self.imm_search_combo.setEnabled(False); self.imm_search_combo.completer().setCompletionMode(QCompleter.PopupCompletion); self.imm_search_combo.completer().setFilterMode(Qt.MatchContains)
        self.btn_add_existing_imm = QPushButton("Aggiungi Selezionato"); self.btn_add_existing_imm.clicked.connect(self._add_existing_immobile)
        layout.addWidget(QLabel("Cerca Immobile:"), 0, 0); layout.addWidget(self.imm_search_combo, 0, 1); layout.addWidget(self.btn_add_existing_imm, 0, 2)
        return widget

    def _create_add_immobile_nuovo_tab(self):
        widget = QWidget(); layout = QGridLayout(widget)
        self.imm_natura_edit = QLineEdit(); layout.addWidget(QLabel("Natura (*):"), 0, 0); layout.addWidget(self.imm_natura_edit, 0, 1)
        self.imm_localita_combo = QComboBox(); self.imm_localita_combo.setPlaceholderText("Seleziona prima un comune..."); self.imm_localita_combo.setEnabled(False)
        layout.addWidget(QLabel("Località (*):"), 0, 2); layout.addWidget(self.imm_localita_combo, 0, 3)
        self.imm_classificazione_edit = QLineEdit(); layout.addWidget(QLabel("Classificazione:"), 1, 0); layout.addWidget(self.imm_classificazione_edit, 1, 1)
        self.imm_consistenza_edit = QLineEdit(); layout.addWidget(QLabel("Consistenza:"), 1, 2); layout.addWidget(self.imm_consistenza_edit, 1, 3)
        self.imm_piani_spin = QSpinBox(); self.imm_piani_spin.setRange(0, 99); layout.addWidget(QLabel("Piani:"), 2, 0); layout.addWidget(self.imm_piani_spin, 2, 1)
        self.imm_vani_spin = QSpinBox(); self.imm_vani_spin.setRange(0, 99); layout.addWidget(QLabel("Vani:"), 2, 2); layout.addWidget(self.imm_vani_spin, 2, 3)
        self.btn_add_inline_immobile = QPushButton("Aggiungi alla Lista"); self.btn_add_inline_immobile.clicked.connect(self._add_inline_immobile)
        layout.addWidget(self.btn_add_inline_immobile, 3, 3, Qt.AlignRight)
        return widget

    def _load_data_on_first_show(self):
        """
        Metodo per il lazy loading. Carica la lista globale dei possessori
        la prima volta che questo widget viene visualizzato.
        """
        self.logger.info("Esecuzione lazy loading per RegistrazioneProprietaWidget...")
        self._load_possessori_for_combo()

    def _select_comune(self):
        dialog = ComuneSelectionDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_comune_id:
            self.comune_id = dialog.selected_comune_id
            self.comune_display.setText(f"{dialog.selected_comune_name} (ID: {self.comune_id})")
            self.logger.info(f"Comune selezionato ID: {self.comune_id}. Caricamento dati dipendenti...")
            self._load_localita_for_combo()
            self._load_immobili_for_combo()
            self._load_possessori_for_combo()
            self._update_registra_button_state()

    def _load_possessori_for_combo(self):
        """Carica tutti i possessori per la combobox di ricerca."""
        if self.possessori_cache: # Non ricaricare se la cache è già piena
            return
        self.possessore_search_combo.clear(); self.possessore_search_combo.addItem("--- Cerca o Seleziona ---", None)
        try:
            self.possessori_cache = self.db_manager.search_possessori_by_term_globally(None, limit=5000)
            for poss in self.possessori_cache:
                self.possessore_search_combo.addItem(f"{poss['nome_completo']} (Comune: {poss['comune_riferimento_nome']})", poss['id'])
            self.logger.info(f"Caricati {len(self.possessori_cache)} possessori nella combobox.")
        except DBMError as e:
            self.logger.error(f"Errore caricamento possessori globali: {e}")

    def _load_localita_for_combo(self):
        self.imm_localita_combo.clear()
        self.imm_localita_combo.setEnabled(False)
        self.imm_localita_combo.addItem("--- Caricamento ---", None)
        if not self.comune_id: return
        try:
            self.localita_cache = self.db_manager.get_localita_by_comune(self.comune_id)
            self.imm_localita_combo.clear()
            if self.localita_cache:
                self.imm_localita_combo.addItem("--- Seleziona Località ---", None)
                for loc in self.localita_cache:
                    self.imm_localita_combo.addItem(f"{loc['nome']} ({loc.get('tipo', 'N/D')})", loc['id'])
                self.imm_localita_combo.setEnabled(True)
            else:
                self.imm_localita_combo.addItem("Nessuna località per questo comune", None)
        except DBMError as e: self.logger.error(f"Errore caricamento località: {e}")


    def _load_immobili_for_combo(self):
        self.imm_search_combo.clear()
        self.imm_search_combo.setEnabled(False)
        self.imm_search_combo.addItem("--- Caricamento ---", None)
        if not self.comune_id: return
        try:
            self.immobili_cache = self.db_manager.get_immobili_by_comune(self.comune_id)
            self.imm_search_combo.clear()
            if self.immobili_cache:
                self.imm_search_combo.addItem("--- Cerca Immobile Esistente ---", None)
                for imm in self.immobili_cache:
                    self.imm_search_combo.addItem(f"{imm['natura']} in {imm['localita_nome']}", imm['id'])
                self.imm_search_combo.setEnabled(True)
            else:
                self.imm_search_combo.addItem("Nessun immobile in questo comune", None)
        except DBMError as e: self.logger.error(f"Errore caricamento immobili: {e}")
     # Nuovi Metodi Slot per i pulsanti inline
    def _add_selected_possessore(self):
        possessore_id = self.possessore_search_combo.currentData()
        if not possessore_id: return QMessageBox.warning(self, "Selezione Mancante", "Seleziona un possessore.")

        # Evita duplicati
        if any(p['id'] == possessore_id for p in self.possessori_data):
            return QMessageBox.information(self, "Già Presente", "Questo possessore è già nella lista.")

        dettagli = DettagliLegamePossessoreDialog.get_details_for_new_legame(self.possessore_search_combo.currentText(), 'principale', self)
        if dettagli:
            self.possessori_data.append({"id": possessore_id, "nome_completo": self.possessore_search_combo.currentText(), **dettagli})
            self.update_possessori_table()


    def _create_and_add_new_possessore(self):
        dialog = CreatePossessoreDialog(self.db_manager, self)
        if dialog.exec_() == QDialog.Accepted and dialog.nuovo_possessore_dati:
            poss_info = dialog.nuovo_possessore_dati
            self._load_possessori_for_combo() # Ricarica la lista per includere il nuovo
            # Aggiungi direttamente alla lista della partita corrente
            dettagli = DettagliLegamePossessoreDialog.get_details_for_new_legame(poss_info.get('nome_completo'), 'principale', self)
            if dettagli:
                self.possessori_data.append({"id": poss_info['id'], "nome_completo": poss_info['nome_completo'], **dettagli})
                self.update_possessori_table()
    def _add_existing_immobile(self):
        immobile_id = self.imm_search_combo.currentData()
        if not immobile_id: return QMessageBox.warning(self, "Selezione Mancante", "Seleziona un immobile.")

        if any(i.get('id') == immobile_id for i in self.immobili_data):
            return QMessageBox.information(self, "Già Presente", "Questo immobile è già nella lista.")

        # Trova i dettagli dell'immobile dalla cache
        imm_details = next((i for i in self.immobili_cache if i['id'] == immobile_id), None)
        if imm_details:
            self.immobili_data.append(imm_details)
            self.update_immobili_table()

    def _add_inline_immobile(self):
        natura = self.imm_natura_edit.text().strip()
        localita_id = self.imm_localita_combo.currentData()
        if not natura or localita_id is None: return QMessageBox.warning(self, "Dati Mancanti", "Natura e Località sono obbligatori.")

        immobile_dict = {
            'natura': natura,
            'localita_id': localita_id,
            'localita_nome': self.imm_localita_combo.currentText(),
            'classificazione': self.imm_classificazione_edit.text().strip(),
            'consistenza': self.imm_consistenza_edit.text().strip(),
            'numero_piani': self.imm_piani_spin.value(),
            'numero_vani': self.imm_vani_spin.value()
        }  # (come prima)
        self.immobili_data.append(immobile_dict)
        self.update_immobili_table()
        self._pulisci_form_immobile()

    def _pulisci_form_immobile(self):
        self.imm_natura_edit.clear(); self.imm_classificazione_edit.clear(); self.imm_consistenza_edit.clear()
        self.imm_localita_combo.setCurrentIndex(0); self.imm_piani_spin.setValue(0); self.imm_vani_spin.setValue(0)
    
    def update_possessori_table(self):
        self.possessori_table.setRowCount(len(self.possessori_data))
        for i, dati in enumerate(self.possessori_data):
            self.possessori_table.setItem(i, 0, QTableWidgetItem(str(dati.get('id'))))
            self.possessori_table.setItem(i, 1, QTableWidgetItem(dati.get('nome_completo')))
            self.possessori_table.setItem(i, 2, QTableWidgetItem(dati.get('titolo')))
            self.possessori_table.setItem(i, 3, QTableWidgetItem(dati.get('quota')))
        self._update_registra_button_state()
        
    def update_immobili_table(self):
        self.immobili_table.setRowCount(len(self.immobili_data))
        for i, imm in enumerate(self.immobili_data):
            immobile = imm if isinstance(imm, dict) else imm.to_dict()  # Assicurati che sia un dizionario
            self.immobili_table.setItem(
                i, 0, QTableWidgetItem(immobile.get('natura', '')))
            self.immobili_table.setItem(i, 1, QTableWidgetItem(
                immobile.get('localita_nome', '')))
            self.immobili_table.setItem(i, 2, QTableWidgetItem(
                immobile.get('classificazione', '')))
            self.immobili_table.setItem(
                i, 3, QTableWidgetItem(immobile.get('consistenza', '')))

            piani_vani = ""
            if 'numero_piani' in immobile and immobile['numero_piani']:
                piani_vani += f"Piani: {immobile['numero_piani']}"
            if 'numero_vani' in immobile and immobile['numero_vani']:
                if piani_vani:
                    piani_vani += ", "
                piani_vani += f"Vani: {immobile['numero_vani']}"

            self.immobili_table.setItem(i, 4, QTableWidgetItem(piani_vani))
        self._update_registra_button_state()
    def remove_possessore(self):
        """Rimuove il possessore selezionato dalla lista."""
        selected_rows = self.possessori_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Attenzione",
                                "Seleziona un possessore da rimuovere.")
            return

        row = selected_rows[0].row()
        if 0 <= row < len(self.possessori_data):
            del self.possessori_data[row]
            self.update_possessori_table()
        self._update_registra_button_state()
        
    def remove_immobile(self):
        """Rimuove l'immobile selezionato dalla lista."""
        selected_rows = self.immobili_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Attenzione",
                                "Seleziona un immobile da rimuovere.")
            return

        row = selected_rows[0].row()
        if 0 <= row < len(self.immobili_data):
            del self.immobili_data[row]
            self.update_immobili_table()
        self._update_registra_button_state()
        
    
        
    def _salva_proprieta(self):
        self.logger.info("Avvio registrazione nuova proprietà...")
        if not self.comune_id:
            QMessageBox.warning(self, "Dati Mancanti", "Selezionare un comune.")
            return
        if not self.possessori_data:
            QMessageBox.warning(self, "Dati Mancanti", "Aggiungere almeno un possessore.")
            return
        if not self.immobili_data:
            QMessageBox.warning(self, "Dati Mancanti", "Aggiungere almeno un immobile.")
            return

        numero_partita = self.num_partita_edit.value()
        # Legge correttamente il valore del suffisso dalla UI
        suffisso_partita = self.suffisso_partita_edit.text().strip() or None 
        data_impianto_dt = self.data_edit.date().toPyDate()

        try:
            possessori_json_str = json.dumps(self.possessori_data)
            immobili_json_str = json.dumps(self.immobili_data)
        except TypeError as te:
            self.logger.error(f"Errore serializzazione JSON per nuova proprietà: {te}")
            QMessageBox.critical(self, "Errore Dati", f"Errore nella preparazione dei dati per il database: {te}")
            return

        try:
            # Chiamata al DB Manager, ora completa con tutti gli argomenti
            nuova_partita_id = self.db_manager.registra_nuova_proprieta(
                comune_id=self.comune_id,
                numero_partita=numero_partita,
                data_impianto=data_impianto_dt,
                possessori_json_str=possessori_json_str,
                immobili_json_str=immobili_json_str,
                suffisso_partita=suffisso_partita  # <<< QUESTA È LA RIGA MANCANTE, ORA AGGIUNTA
            )

            if nuova_partita_id is not None and self.comune_id is not None:
                suffisso_display = f" (Suffisso: {suffisso_partita})" if suffisso_partita else ""
                msg_success = f"Nuova proprietà (Partita N.{numero_partita}{suffisso_display}, ID: {nuova_partita_id}) registrata con successo."
                self.logger.info(msg_success)

                reply = QMessageBox.question(self, "Registrazione Completata",
                                             f"{msg_success}\n\nVuoi procedere con operazioni collegate (es. Duplicazione) su questa o un'altra partita?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                if reply == QMessageBox.Yes:
                    self.partita_creata_per_operazioni_collegate.emit(nuova_partita_id, self.comune_id)

                self._pulisci_form_registrazione()

        except (DBUniqueConstraintError, DBDataError, DBMError) as e_db:
            self.logger.error(f"Errore DB registrazione proprietà: {e_db}")
            QMessageBox.critical(self, "Errore Database", str(e_db))
        except Exception as e_gen:
            self.logger.critical(f"Errore imprevisto registrazione proprietà: {e_gen}", exc_info=True)
            QMessageBox.critical(self, "Errore Imprevisto", f"Errore: {type(e_gen).__name__}: {e_gen}")
        self.logger.info("Registrazione proprietà completata.")


    def _pulisci_form_registrazione(self):
       
        logging.getLogger("CatastoGUI").info(
            "Pulizia campi del form Registrazione Proprietà.")

        # Reset Comune selezionato
        self.comune_id = None
        self.comune_display_name = None  # Se usa una variabile per il nome del comune
        if hasattr(self, 'comune_display') and isinstance(self.comune_display, QLabel):
            self.comune_display.setText("Nessun comune selezionato")

        # Reset Numero Partita
        if hasattr(self, 'num_partita_edit') and isinstance(self.num_partita_edit, QSpinBox):
            # O un valore di default sensato come 1
            self.num_partita_edit.setValue(self.num_partita_edit.minimum())

        # Reset Data Impianto
        if hasattr(self, 'data_edit') and isinstance(self.data_edit, QDateEdit):
            self.data_edit.setDate(QDate.currentDate())

        # Reset liste dati interni
        self.possessori_data = []
        self.immobili_data = []

        # Aggiorna/Pulisci le tabelle UI dei possessori e immobili (se le ha)
        # Metodo che popola/pulisce la QTableWidget dei possessori
        if hasattr(self, 'update_possessori_table'):
            self.update_possessori_table()
        # Alternativa se non c'è update_xxx
        elif hasattr(self, 'possessori_table') and isinstance(self.possessori_table, QTableWidget):
            self.possessori_table.setRowCount(0)

        # Metodo che popola/pulisce la QTableWidget degli immobili
        if hasattr(self, 'update_immobili_table'):
            self.update_immobili_table()
        elif hasattr(self, 'immobili_table') and isinstance(self.immobili_table, QTableWidget):
            self.immobili_table.setRowCount(0)

        # Imposta il focus su un campo iniziale, ad esempio il pulsante per selezionare il comune
        if hasattr(self, 'comune_button') and isinstance(self.comune_button, QPushButton):
            self.comune_button.setFocus()
        elif hasattr(self, 'num_partita_edit'):  # O il campo numero partita
            self.num_partita_edit.setFocus()

        logging.getLogger("CatastoGUI").info(
            "Campi form Registrazione Proprietà puliti.")
   

