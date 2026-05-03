# -*- coding: utf-8 -*-
import bcrypt
import logging
from typing import Optional, Dict
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QHBoxLayout, QPushButton, QMessageBox)

from custom_widgets import QPasswordLineEdit
from catasto_db_manager import CatastoDBManager
from catasto_db_manager import DBMError

def _hash_password(password: str) -> str:
    """Genera un hash sicuro per la password usando bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode('utf-8')

def _verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verifica se la password fornita corrisponde all'hash memorizzato."""
    try:
        stored_hash_bytes = stored_hash.encode('utf-8')
        provided_password_bytes = provided_password.encode('utf-8')
        return bcrypt.checkpw(provided_password_bytes, stored_hash_bytes)
    except ValueError:
        logging.getLogger("CatastoGUI").error(
            f"Tentativo di verifica con hash non valido: {stored_hash[:10]}...")
        return False
    except Exception as e:
        logging.getLogger("CatastoGUI").error(
            f"Errore imprevisto durante la verifica bcrypt: {e}")
        return False

class LoginDialog(QDialog):
    # --- INIZIO MODIFICA 1 ---
    # Aggiungiamo 'client_ip' come parametro all'init
    def __init__(self, db_manager: CatastoDBManager, client_ip: str, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.db_manager = db_manager
        self.client_ip = client_ip # Salviamo l'IP come attributo dell'istanza
        self.logged_in_user_id: Optional[int] = None
        self.logged_in_user_info: Optional[Dict] = None
        # NUOVO attributo per conservare l'UUID
        self.current_session_id_from_dialog: Optional[str] = None

        self.setWindowTitle("Login - Meridiana 1.2.1")
        self.setMinimumWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Username:"), 0, 0)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Inserisci username")
        form_layout.addWidget(self.username_edit, 0, 1)

        form_layout.addWidget(QLabel("Password:"), 1, 0)
        self.password_edit = QPasswordLineEdit()
        form_layout.addWidget(self.password_edit, 1, 1)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self.handle_login)

        self.cancel_button = QPushButton("Esci")
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.login_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        self.username_edit.setFocus()

    def handle_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username or not password:
            QMessageBox.warning(self, "Login Fallito",
                                "Username e password sono obbligatori.")
            return

        credentials = self.db_manager.get_user_credentials(
            username)  # Presumiamo restituisca anche 'id' utente app
        login_success = False
        user_id_app = None  # ID utente dell'applicazione

        if credentials:
            # ID dell'utente dalla tabella 'utente'
            user_id_app = credentials.get('id')
            stored_hash = credentials.get('password_hash')
            is_active = credentials.get('attivo', False)

            if not is_active:
                QMessageBox.warning(self, "Login Fallito",
                                    "Utente non attivo.")
                logging.getLogger("CatastoGUI").warning(
                    f"Login GUI fallito (utente '{username}' non attivo).")
                return  # Non procedere oltre se l'utente non è attivo

            # Usa la tua funzione di verifica
            if stored_hash and _verify_password(stored_hash, password):
                login_success = True
                logging.getLogger("CatastoGUI").info(
                    f"Verifica password GUI OK per utente '{username}' (ID App: {user_id_app})")
            else:
                QMessageBox.warning(self, "Login Fallito",
                                    "Username o Password errati.")
                logging.getLogger("CatastoGUI").warning(
                    f"Login GUI fallito (pwd errata) per utente '{username}'.")
                self.password_edit.selectAll()
                self.password_edit.setFocus()
                return
        else:
            # Messaggio generico
            QMessageBox.warning(self, "Login Fallito",
                                "Username o Password errati.")
            logging.getLogger("CatastoGUI").warning(
                f"Login GUI fallito (utente '{username}' non trovato).")
            self.username_edit.selectAll()
            self.username_edit.setFocus()
            return

        if login_success and user_id_app is not None:
            try:
                 # --- INIZIO MODIFICA 2 ---
                # Usiamo self.client_ip invece della variabile globale non definita
                session_uuid_returned = self.db_manager.register_access(
                    user_id=user_id_app,
                    action='login',
                    esito=True,
                    indirizzo_ip=self.client_ip, # <-- USA L'ATTRIBUTO DI ISTANZA
                    application_name='CatastoAppGUI'
                )
                # --- FINE MODIFICA 2 ---

                if session_uuid_returned:
                    self.logged_in_user_id = user_id_app
                    # Contiene tutti i dati dell'utente, incluso 'id'
                    self.logged_in_user_info = credentials
                    self.current_session_id_from_dialog = session_uuid_returned  # Salva l'UUID

                    # Imposta le variabili di sessione PostgreSQL per l'audit
                    # user_id_app è l'ID dell'utente da 'utente.id'
                    # session_uuid_returned è l'UUID dalla tabella 'sessioni_accesso.id_sessione'
                    if not self.db_manager.set_audit_session_variables(user_id_app, session_uuid_returned):
                        QMessageBox.critical(
                            self, "Errore Audit", "Impossibile impostare le informazioni di sessione per l'audit. Il login non può procedere.")
                        # Considera di non fare self.accept() qui se questo è un errore bloccante
                        return

                    QMessageBox.information(self, "Login Riuscito",
                                            f"Benvenuto {self.logged_in_user_info.get('nome_completo', username)}!")
                    self.accept()  # Chiude il dialogo e segnala successo
                else:
                    # register_access ha fallito nel restituire un session_id
                    QMessageBox.critical(
                        self, "Login Fallito", "Errore critico: Impossibile registrare la sessione di accesso nel database.")
                    logging.getLogger("CatastoGUI").error(
                        f"Login GUI OK per utente '{username}' ma fallita registrazione della sessione (nessun UUID sessione restituito).")

            except DBMError as e_dbm:  # Cattura DBMError da register_access o set_audit_session_variables
                QMessageBox.critical(
                    self, "Errore di Login (DB)", f"Errore durante il processo di login:\n{str(e_dbm)}")
                logging.getLogger("CatastoGUI").error(
                    f"DBMError durante il login per {username}: {str(e_dbm)}")
            except Exception as e_gen:  # Altri errori imprevisti
                QMessageBox.critical(
                    self, "Errore Imprevisto", f"Errore di sistema durante il login:\n{str(e_gen)}")
                logging.getLogger("CatastoGUI").error(
                    f"Errore imprevisto durante il login per {username}: {str(e_gen)}", exc_info=True)
