# -*- coding: utf-8 -*-
import bcrypt
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QHBoxLayout, QPushButton, QMessageBox,
                             QFormLayout, QFrame)
from PyQt5.QtCore import Qt

from custom_widgets import QPasswordLineEdit
from catasto_db_manager import CatastoDBManager
from catasto_db_manager import DBMError, DBDataError

logger = logging.getLogger("CatastoGUI")


def _hash_password(password: str) -> str:
    """Genera un hash sicuro per la password usando bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verifica se la password fornita corrisponde all'hash memorizzato."""
    try:
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_hash.encode('utf-8'))
    except ValueError:
        logger.error(f"Hash non valido durante la verifica: {stored_hash[:10]}...")
        return False
    except Exception as e:
        logger.error(f"Errore imprevisto durante la verifica bcrypt: {e}")
        return False


def validate_password_strength(password: str, cfg: Dict) -> Tuple[bool, str]:
    """
    Verifica che la password rispetti la policy di sicurezza.
    Restituisce (ok, messaggio_errore). Se ok=True, messaggio è ''.
    """
    min_len = int(cfg.get('min_lunghezza_password', 12))
    richiedi_maiuscole = int(cfg.get('richiedi_maiuscole', 1))
    richiedi_numeri = int(cfg.get('richiedi_numeri', 1))
    richiedi_speciali = int(cfg.get('richiedi_speciali', 1))

    errors = []
    if len(password) < min_len:
        errors.append(f"almeno {min_len} caratteri")
    if richiedi_maiuscole and not re.search(r'[A-Z]', password):
        errors.append("almeno una lettera maiuscola")
    if richiedi_numeri and not re.search(r'\d', password):
        errors.append("almeno un numero")
    if richiedi_speciali and not re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:\'",.<>?/\\`~]', password):
        errors.append("almeno un carattere speciale (!@#$...)")

    if errors:
        return False, "La password deve contenere:\n- " + "\n- ".join(errors)
    return True, ''


class CambioPasswordDialog(QDialog):
    """Dialog obbligatorio al primo accesso o dopo reset admin."""

    def __init__(self, db_manager: CatastoDBManager, utente_id: int,
                 username: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.utente_id = utente_id
        self.username = username
        self._cfg = {}
        try:
            self._cfg = db_manager.get_security_config()
        except Exception:
            pass

        self.setWindowTitle("Cambio Password Obbligatorio")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"Benvenuto <b>{username}</b>.<br>"
            "Per motivi di sicurezza devi impostare una nuova password prima di continuare."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        form = QFormLayout()
        self.new_pass_edit = QPasswordLineEdit()
        self.new_pass_edit.setPlaceholderText("Nuova password")
        self.confirm_pass_edit = QPasswordLineEdit()
        self.confirm_pass_edit.setPlaceholderText("Conferma password")
        form.addRow("Nuova password:", self.new_pass_edit)
        form.addRow("Conferma:", self.confirm_pass_edit)
        layout.addLayout(form)

        # Mostra requisiti
        min_len = int(self._cfg.get('min_lunghezza_password', 12))
        req_parts = [f"Minimo {min_len} caratteri"]
        if int(self._cfg.get('richiedi_maiuscole', 1)):
            req_parts.append("Almeno una maiuscola")
        if int(self._cfg.get('richiedi_numeri', 1)):
            req_parts.append("Almeno un numero")
        if int(self._cfg.get('richiedi_speciali', 1)):
            req_parts.append("Almeno un carattere speciale")
        n_storico = int(self._cfg.get('storico_password', 5))
        req_parts.append(f"Non uguale alle ultime {n_storico} password")

        req_label = QLabel("<small>" + " &nbsp;|&nbsp; ".join(req_parts) + "</small>")
        req_label.setWordWrap(True)
        layout.addWidget(req_label)

        btn_layout = QHBoxLayout()
        self.btn_confirm = QPushButton("Conferma Cambio Password")
        self.btn_confirm.setDefault(True)
        self.btn_confirm.clicked.connect(self._do_change)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

    def _do_change(self):
        new_pass = self.new_pass_edit.text()
        confirm = self.confirm_pass_edit.text()

        if new_pass != confirm:
            QMessageBox.warning(self, "Errore", "Le password non coincidono.")
            self.confirm_pass_edit.clear()
            self.confirm_pass_edit.setFocus()
            return

        ok, msg = validate_password_strength(new_pass, self._cfg)
        if not ok:
            QMessageBox.warning(self, "Password Non Valida", msg)
            return

        try:
            new_hash = _hash_password(new_pass)
            self.db_manager.update_password_with_history(
                self.utente_id, new_hash, new_pass
            )
            QMessageBox.information(self, "Successo", "Password aggiornata con successo.")
            self.accept()
        except DBDataError as e:
            QMessageBox.warning(self, "Password Non Valida", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiornare la password:\n{e}")


class LoginDialog(QDialog):
    def __init__(self, db_manager: CatastoDBManager, client_ip: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.client_ip = client_ip
        self.logged_in_user_id: Optional[int] = None
        self.logged_in_user_info: Optional[Dict] = None
        self.current_session_id_from_dialog: Optional[str] = None

        self.setWindowTitle("Login - Meridiana 1.3.0")
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

        credentials = self.db_manager.get_user_credentials(username)

        if not credentials:
            QMessageBox.warning(self, "Login Fallito", "Username o Password errati.")
            logger.warning(f"Login fallito: utente '{username}' non trovato.")
            self.username_edit.selectAll()
            self.username_edit.setFocus()
            return

        user_id = credentials.get('id')

        # Verifica utente attivo
        if not credentials.get('attivo', False):
            QMessageBox.warning(self, "Login Fallito", "Utente non attivo. Contattare l'amministratore.")
            logger.warning(f"Login fallito: utente '{username}' non attivo.")
            return

        # Verifica blocco temporaneo
        locked_until = credentials.get('locked_until')
        if locked_until is not None:
            # Normalizza a timezone-aware per il confronto
            now = datetime.now(timezone.utc)
            if hasattr(locked_until, 'tzinfo') and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                remaining = int((locked_until - now).total_seconds() / 60) + 1
                QMessageBox.warning(
                    self, "Account Bloccato",
                    f"L'account e' temporaneamente bloccato dopo troppi tentativi falliti.\n\n"
                    f"Riprova tra circa {remaining} minuto/i oppure contatta l'amministratore."
                )
                logger.warning(f"Login bloccato per '{username}' fino a {locked_until}.")
                return

        # Verifica password
        stored_hash = credentials.get('password_hash')
        if not stored_hash or not _verify_password(stored_hash, password):
            # Registra tentativo fallito
            if user_id is not None:
                result = self.db_manager.record_failed_login(user_id)
                if result.get('bloccato'):
                    durata = self.db_manager.get_security_config().get('durata_blocco_minuti', 15)
                    QMessageBox.warning(
                        self, "Account Bloccato",
                        f"Troppi tentativi falliti. L'account e' stato bloccato per {durata} minuti.\n"
                        "Contatta l'amministratore per uno sblocco immediato."
                    )
                else:
                    max_t = self.db_manager.get_security_config().get('max_tentativi_falliti', 5)
                    tentativi = result.get('tentativi', 0)
                    rimasti = max(0, max_t - tentativi)
                    QMessageBox.warning(
                        self, "Login Fallito",
                        f"Username o Password errati.\n"
                        f"Tentativi rimasti prima del blocco: {rimasti}."
                    )
            else:
                QMessageBox.warning(self, "Login Fallito", "Username o Password errati.")
            logger.warning(f"Login fallito (password errata) per utente '{username}'.")
            self.password_edit.clear()
            self.password_edit.setFocus()
            return

        # Login riuscito — azzera contatore
        if user_id is not None:
            self.db_manager.reset_failed_attempts(user_id)

        try:
            session_uuid = self.db_manager.register_access(
                user_id=user_id,
                action='login',
                esito=True,
                indirizzo_ip=self.client_ip,
                application_name='CatastoAppGUI'
            )

            if not session_uuid:
                QMessageBox.critical(
                    self, "Login Fallito",
                    "Errore critico: impossibile registrare la sessione di accesso."
                )
                return

            self.logged_in_user_id = user_id
            self.logged_in_user_info = credentials
            self.current_session_id_from_dialog = session_uuid

            if not self.db_manager.set_audit_session_variables(user_id, session_uuid):
                QMessageBox.critical(
                    self, "Errore Audit",
                    "Impossibile impostare le informazioni di sessione per l'audit."
                )
                return

            # Cambio password obbligatorio
            if credentials.get('password_must_change'):
                dlg = CambioPasswordDialog(
                    self.db_manager, user_id,
                    credentials.get('username', username), self
                )
                if dlg.exec_() != QDialog.Accepted:
                    QMessageBox.information(
                        self, "Login Annullato",
                        "Il cambio password e' obbligatorio. Login annullato."
                    )
                    return
                # Aggiorna credentials dopo il cambio
                self.logged_in_user_info = self.db_manager.get_user_credentials(username) or credentials

            QMessageBox.information(
                self, "Login Riuscito",
                f"Benvenuto {credentials.get('nome_completo', username)}!"
            )
            self.accept()

        except DBMError as e:
            QMessageBox.critical(self, "Errore di Login (DB)",
                                 f"Errore durante il processo di login:\n{e}")
            logger.error(f"DBMError durante il login per '{username}': {e}")
        except Exception as e:
            QMessageBox.critical(self, "Errore Imprevisto",
                                 f"Errore di sistema durante il login:\n{e}")
            logger.error(f"Errore imprevisto durante il login per '{username}': {e}", exc_info=True)
