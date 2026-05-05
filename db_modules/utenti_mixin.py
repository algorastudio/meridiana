import psycopg2
import psycopg2.errors # Importa specificamente gli errori
from psycopg2.extras import DictCursor
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE,ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql, extras, pool
import sys, csv
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple, Union
import json
import hashlib
import uuid
import os
from models.consultazione import Consultazione
import shutil # Per trovare i percorsi degli eseguibili
from contextlib import contextmanager
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
                             QVBoxLayout,QProgressDialog)
from PyQt5.QtCore import (QDate, QDateTime, QPoint, QProcess, QSettings, 
                          QSize, QStandardPaths, Qt, QTimer, QUrl, 
                          pyqtSignal,QProcessEnvironment,QObject)

COLONNE_POSSESSORI_DETTAGLI_NUM = 6 # Esempio: ID, Nome Compl, Cognome/Nome, Paternità, Quota, Titolo
COLONNE_POSSESSORI_DETTAGLI_LABELS = ["ID Poss.", "Nome Completo", "Cognome Nome", "Paternità", "Quota", "Titolo"]
logger = logging.getLogger(__name__)
class DBMError(Exception):
    """Classe base per errori specifici del DBManager."""
    pass
class DBUniqueConstraintError(DBMError):
    """Sollevata quando un vincolo di unicità viene violato."""
    def __init__(self, message, constraint_name=None, details=None):
        super().__init__(message)
        self.constraint_name = constraint_name
        self.details = details
class DBNotFoundError(DBMError):
    """Sollevata quando un record atteso non viene trovato per un'operazione."""
    pass
class DBDataError(DBMError):
    """Sollevata per errori relativi a dati o parametri forniti non validi."""
    pass

class UtentiMixin:
    def search_consultazioni(self, data_inizio: Optional[date] = None, data_fine: Optional[date] = None,
                             richiedente: Optional[str] = None, funzionario_autorizzante: Optional[str] = None) -> List[Consultazione]:
        """Chiama la funzione SQL cerca_consultazioni (invariata rispetto a comune_id)."""
        try:
            query = "SELECT * FROM cerca_consultazioni(%s, %s, %s, %s)"
            params = (data_inizio, data_fine, richiedente, funzionario_autorizzante)
            if self.execute_query(query, params): 
                results = self.fetchall()
                return [Consultazione.from_dict(dict(row)) for row in results]
        except psycopg2.Error as db_err: logger.error(f"Errore DB in search_consultazioni: {db_err}")
        except Exception as e: logger.error(f"Errore Python in search_consultazioni: {e}")
        return []

    # --- Metodi CRUD specifici (invariati rispetto a comune_id) ---
    def update_consultazione(self, consultazione_id: int, **kwargs) -> bool:
        """Chiama la procedura SQL aggiorna_consultazione."""
        params = {'p_id': consultazione_id, 'p_data': kwargs.get('data'), 'p_richiedente': kwargs.get('richiedente'),
                  'p_documento_identita': kwargs.get('documento_identita'), 'p_motivazione': kwargs.get('motivazione'),
                  'p_materiale_consultato': kwargs.get('materiale_consultato'), 'p_funzionario_autorizzante': kwargs.get('funzionario_autorizzante')}
        call_proc = "CALL aggiorna_consultazione(%(p_id)s, %(p_data)s, %(p_richiedente)s, %(p_documento_identita)s, %(p_motivazione)s, %(p_materiale_consultato)s, %(p_funzionario_autorizzante)s)"
        try:
            if self.execute_query(call_proc, params): self.commit(); logger.info(f"Consultazione ID {consultazione_id} aggiornata."); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB aggiornamento consultazione ID {consultazione_id}: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python aggiornamento consultazione ID {consultazione_id}: {e}"); self.rollback(); return False

    def delete_consultazione(self, consultazione_id: int) -> bool:
        """Chiama la procedura SQL elimina_consultazione."""
        call_proc = "CALL elimina_consultazione(%s)"
        try:
            if self.execute_query(call_proc, (consultazione_id,)): self.commit(); logger.info(f"Consultazione ID {consultazione_id} eliminata."); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB eliminazione consultazione ID {consultazione_id}: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python eliminazione consultazione ID {consultazione_id}: {e}"); self.rollback(); return False

    # --- Metodi per Workflow Complessi (MODIFICATI per comune_id) ---
    def registra_nuova_consultazione(self,
                                    data_consultazione: date,
                                    richiedente: str,
                                    materiale_consultato: str,
                                    funzionario_autorizzante: Optional[str],
                                    documento_identita: Optional[str] = None,
                                    motivazione: Optional[str] = None
                                    ) -> int:
        """
        Registra una nuova consultazione nel database in modo transazionale e sicuro.
        """
        if not all([data_consultazione, richiedente, materiale_consultato]):
            raise DBDataError("Data, Richiedente e Materiale Consultato sono campi obbligatori.")

        query = f"""
            INSERT INTO {self.schema}.consultazione
                (data, richiedente, documento_identita, motivazione, materiale_consultato, funzionario_autorizzante)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        params = (
            data_consultazione,
            richiedente.strip(),
            documento_identita.strip() if documento_identita else None,
            motivazione.strip() if motivazione else None,
            materiale_consultato.strip(),
            funzionario_autorizzante.strip() if funzionario_autorizzante else None
        )
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result and result[0] is not None:
                        new_id = result[0]
                        self.logger.info(f"Nuova consultazione registrata con successo. ID: {new_id}")
                        # Il commit è automatico all'uscita del blocco with
                        return new_id
                    else:
                        # Se non viene restituito un ID, solleva un'eccezione che causerà il rollback automatico
                        raise DBMError("Fallimento registrazione consultazione: nessun ID restituito.")
        except Exception as e:
            self.logger.error(f"Errore DB in registra_nuova_consultazione: {e}", exc_info=True)
            # Il rollback è automatico, rilanciamo un'eccezione chiara per il chiamante
            raise DBMError(f"Impossibile registrare la consultazione: {e}") from e

    # In catasto_db_manager.py, SOSTITUISCI il metodo registra_nuova_proprieta con questo:

    def registra_consultazione(self, data: date, richiedente: str, documento_identita: Optional[str],
                             motivazione: Optional[str], materiale_consultato: Optional[str],
                             funzionario_autorizzante: Optional[str]) -> bool:
        """Chiama la procedura SQL registra_consultazione (invariata rispetto a comune_id)."""
        try:
            call_proc = "CALL registra_consultazione(%s, %s, %s, %s, %s, %s)"
            params = (data, richiedente, documento_identita, motivazione, materiale_consultato, funzionario_autorizzante)
            if self.execute_query(call_proc, params): self.commit(); logger.info(f"Registrata consultazione: Richiedente '{richiedente}', Data {data}"); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB registrazione consultazione: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python registrazione consultazione: {e}"); self.rollback(); return False

    def set_session_app_user(self, user_id: Optional[int], client_ip: Optional[str] = None) -> bool:
        """
        Imposta variabili di sessione PostgreSQL per tracciamento usando il context manager.
        """
        self.logger.debug(f"Impostazione var sessione: app.user_id='{user_id}', app.ip_address='{client_ip}'")
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    user_id_str = str(user_id) if user_id is not None else None
                    ip_str = client_ip if client_ip is not None else None
                    
                    # Il terzo argomento 'false' rende l'impostazione valida per l'intera sessione
                    cur.execute("SELECT set_config('app.user_id', %s, false);", (user_id_str,))
                    cur.execute("SELECT set_config('app.ip_address', %s, false);", (ip_str,))
            
            # Il commit è automatico all'uscita del blocco 'with' senza errori
            self.logger.info(f"Variabili di sessione applicative impostate con successo.")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore DB impostando var sessione applicative: {e}", exc_info=True)
            # Il rollback è automatico, restituiamo False per indicare il fallimento
            return False
    def clear_session_app_user(self):
        """Resetta le variabili di sessione PostgreSQL 'app.user_id' e 'app.ip_address'."""
        self.logger.info("Reset variabili di sessione applicative (app.user_id, app.ip_address).")
        # Richiama set_session_app_user con None per resettarle.
        # In alternativa, si potrebbe usare RESET nome_variabile;
        return self.set_session_app_user(user_id=None, client_ip=None)

    def create_user(self, username: str, password_hash: str, nome_completo: str, email: str, ruolo: str) -> bool:
        """Chiama la procedura SQL crea_utente in modo transazionale e sicuro."""
        call_proc = f"CALL {self.schema}.crea_utente(%s, %s, %s, %s, %s)"
        params = (username, password_hash, nome_completo, email, ruolo)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.debug(f"Chiamata procedura crea_utente per username: {username}")
                    cur.execute(call_proc, params)
            
            # Il commit è automatico qui
            self.logger.info(f"Utente '{username}' creato con successo tramite procedura.")
            return True
            
        except psycopg2.errors.UniqueViolation as uve:
            # Il rollback è automatico
            constraint = getattr(uve.diag, 'constraint_name', 'N/D')
            self.logger.error(f"Errore creazione utente '{username}': Username o Email già esistente (vincolo: {constraint}).")
            raise DBUniqueConstraintError(f"Username '{username}' o Email '{email}' già esistente.", constraint_name=constraint) from uve
            
        except psycopg2.Error as db_err:
            # Il rollback è automatico
            self.logger.error(f"Errore DB creazione utente '{username}': {db_err}", exc_info=True)
            raise DBMError(f"Errore database durante la creazione dell'utente: {getattr(db_err, 'pgerror', str(db_err))}") from db_err
            
        except Exception as e:
            self.logger.error(f"Errore Python creazione utente '{username}': {e}", exc_info=True)
            raise DBMError(f"Errore di sistema imprevisto durante la creazione dell'utente: {e}") from e

    
    def get_user_credentials(self, username: str) -> Optional[Dict]:
        """Recupera credenziali e campi di sicurezza dell'utente dal database."""
        if not username:
            return None

        query = f"""
            SELECT id, username, password_hash, nome_completo, ruolo, attivo,
                   failed_attempts, locked_until, password_must_change, password_changed_at
            FROM {self.schema}.utente
            WHERE username = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (username,))
                    user_data = cur.fetchone()
                    if user_data:
                        return dict(user_data)
            return None
        except Exception as e:
            self.logger.error(f"Errore durante il recupero delle credenziali per '{username}': {e}", exc_info=True)
            return None

    def get_security_config(self) -> Dict[str, Any]:
        """Restituisce la configurazione di sicurezza come dizionario chiave→valore (int dove possibile)."""
        defaults = {
            'max_tentativi_falliti': 5,
            'durata_blocco_minuti': 15,
            'min_lunghezza_password': 12,
            'storico_password': 5,
            'richiedi_maiuscole': 1,
            'richiedi_numeri': 1,
            'richiedi_speciali': 1,
        }
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(f"SELECT chiave, valore FROM {self.schema}.config_sicurezza;")
                    for row in cur.fetchall():
                        try:
                            defaults[row['chiave']] = int(row['valore'])
                        except (ValueError, TypeError):
                            defaults[row['chiave']] = row['valore']
        except Exception as e:
            self.logger.warning(f"Impossibile leggere config_sicurezza, uso valori default: {e}")
        return defaults

    def record_failed_login(self, utente_id: int) -> Dict[str, Any]:
        """
        Incrementa il contatore tentativi falliti.
        Se raggiunge il limite, imposta locked_until.
        Restituisce {'bloccato': bool, 'tentativi': int, 'locked_until': datetime|None}.
        """
        cfg = self.get_security_config()
        max_tentativi = cfg.get('max_tentativi_falliti', 5)
        durata_minuti = cfg.get('durata_blocco_minuti', 15)

        query = f"""
            UPDATE {self.schema}.utente
            SET failed_attempts = failed_attempts + 1,
                locked_until = CASE
                    WHEN (failed_attempts + 1) >= %s
                    THEN NOW() + (%s || ' minutes')::INTERVAL
                    ELSE locked_until
                END
            WHERE id = %s
            RETURNING failed_attempts, locked_until;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (max_tentativi, durata_minuti, utente_id))
                    row = cur.fetchone()
                    if row:
                        return {
                            'bloccato': row['locked_until'] is not None,
                            'tentativi': row['failed_attempts'],
                            'locked_until': row['locked_until'],
                        }
        except Exception as e:
            self.logger.error(f"Errore in record_failed_login per utente {utente_id}: {e}", exc_info=True)
        return {'bloccato': False, 'tentativi': 0, 'locked_until': None}

    def reset_failed_attempts(self, utente_id: int) -> bool:
        """Azzera tentativi falliti e blocco dopo login riuscito. Aggiorna ultimo_accesso."""
        query = f"""
            UPDATE {self.schema}.utente
            SET failed_attempts = 0,
                locked_until    = NULL,
                ultimo_accesso  = NOW()
            WHERE id = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (utente_id,))
            return True
        except Exception as e:
            self.logger.error(f"Errore in reset_failed_attempts per utente {utente_id}: {e}", exc_info=True)
            return False

    def unlock_user(self, utente_id: int) -> bool:
        """Admin sblocca manualmente un utente (azzera contatore e locked_until)."""
        query = f"""
            UPDATE {self.schema}.utente
            SET failed_attempts = 0,
                locked_until    = NULL
            WHERE id = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (utente_id,))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Utente con ID {utente_id} non trovato.")
            self.logger.info(f"Utente ID {utente_id} sbloccato manualmente.")
            return True
        except DBNotFoundError as e:
            self.logger.warning(e)
            raise
        except Exception as e:
            self.logger.error(f"Errore in unlock_user per utente {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile sbloccare l'utente: {e}") from e

    def check_password_in_history(self, utente_id: int, new_hash: str, provided_password: str) -> bool:
        """
        Controlla se la password fornita è già presente negli ultimi N hash dello storico.
        Restituisce True se la password è già stata usata (non consentita).
        """
        import bcrypt
        cfg = self.get_security_config()
        storico_n = cfg.get('storico_password', 5)
        query = f"""
            SELECT password_hash FROM {self.schema}.password_history
            WHERE utente_id = %s
            ORDER BY changed_at DESC
            LIMIT %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (utente_id, storico_n))
                    for row in cur.fetchall():
                        stored = row['password_hash']
                        try:
                            if bcrypt.checkpw(provided_password.encode('utf-8'), stored.encode('utf-8')):
                                return True
                        except Exception:
                            pass
        except Exception as e:
            self.logger.error(f"Errore check_password_in_history per utente {utente_id}: {e}", exc_info=True)
        return False

    def update_password_with_history(self, utente_id: int, new_hash: str,
                                      provided_password: str,
                                      force_change: bool = False) -> bool:
        """
        Aggiorna la password applicando la policy di storico.
        - Verifica che la password non sia tra le ultime N
        - Aggiunge la vecchia password allo storico prima di aggiornare
        - Reimposta password_must_change = FALSE
        - Aggiorna password_changed_at
        Solleva DBDataError se la password è già stata usata.
        """
        if self.check_password_in_history(utente_id, new_hash, provided_password):
            cfg = self.get_security_config()
            n = cfg.get('storico_password', 5)
            raise DBDataError(
                f"La password scelta e' gia' stata usata di recente. "
                f"Scegli una password diversa dalle ultime {n}."
            )

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Aggiungi al storico
                    cur.execute(
                        f"INSERT INTO {self.schema}.password_history (utente_id, password_hash) VALUES (%s, %s);",
                        (utente_id, new_hash)
                    )
                    # Aggiorna la password
                    cur.execute(
                        f"""UPDATE {self.schema}.utente
                            SET password_hash = %s,
                                password_must_change = FALSE,
                                password_changed_at  = NOW(),
                                data_modifica        = NOW()
                            WHERE id = %s;""",
                        (new_hash, utente_id)
                    )
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Utente {utente_id} non trovato durante aggiornamento password.")
            self.logger.info(f"Password aggiornata con storico per utente ID {utente_id}.")
            return True
        except (DBDataError, DBNotFoundError):
            raise
        except Exception as e:
            self.logger.error(f"Errore update_password_with_history per utente {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare la password: {e}") from e

    def set_password_must_change(self, utente_id: int, must_change: bool = True) -> bool:
        """Imposta il flag password_must_change per un utente (usato dopo reset admin)."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {self.schema}.utente SET password_must_change = %s WHERE id = %s;",
                        (must_change, utente_id)
                    )
            return True
        except Exception as e:
            self.logger.error(f"Errore set_password_must_change per utente {utente_id}: {e}", exc_info=True)
            return False

    # Metodo ESISTENTE da MODIFICARE
    def register_access(self, user_id: int, action: str, esito: bool,
                    indirizzo_ip: Optional[str] = None,
                    dettagli: Optional[str] = None,
                    application_name: Optional[str] = None
                   ) -> Optional[str]:
        """
        Registra un evento di sessione in modo transazionale e sicuro.
        Genera e restituisce un UUID per la sessione in caso di login riuscito.
        """
        session_id_to_return: Optional[str] = None
        if action == 'login' and esito:
            session_id_to_return = str(uuid.uuid4())
            self.logger.info(f"Nuovo ID sessione generato per login utente {user_id}: {session_id_to_return}")
        elif action == 'fail_login':
            session_id_to_return = str(uuid.uuid4()) 
            self.logger.info(f"ID evento generato per fail_login utente {user_id}: {session_id_to_return}")

        call_proc_str = f"CALL {self.schema}.registra_evento_sessione(%s, %s, %s, %s, %s, %s, %s);"
        params = (
            user_id,
            session_id_to_return,
            action,
            esito,
            indirizzo_ip,
            application_name if application_name else self.application_name,
            dettagli
        )

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.debug(f"Chiamata a procedura registra_evento_sessione per utente {user_id}, azione {action}")
                    cur.execute(call_proc_str, params)
            
            # Il commit è automatico se la procedura ha successo
            self.logger.info(f"Evento sessione registrato: Utente ID {user_id}, Azione {action}, Esito {esito}.")
            return session_id_to_return

        except psycopg2.Error as db_err:
            # Il rollback è automatico in caso di errore
            pgerror_msg = getattr(db_err, 'pgerror', str(db_err))
            self.logger.error(f"Errore DB in register_access per utente {user_id}: {pgerror_msg}", exc_info=True)
            raise DBMError(f"Errore database durante la registrazione dell'evento: {pgerror_msg}") from db_err
        except Exception as e:
            self.logger.error(f"Errore Python in register_access per utente {user_id}: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema imprevisto durante la registrazione dell'evento: {e}") from e

   

    def logout_user(self, user_id: int, session_id: str, ip_address: Optional[str]) -> bool:
        """
        Esegue il logout e gestisce la potenziale perdita di connessione con il server.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    call_proc_str = f"CALL {self.schema}.logout_utente_sessione(%s, %s, %s, %s);"
                    params = (user_id, session_id, ip_address, self.application_name)
                    self.logger.debug(f"Chiamata a logout_utente_sessione per utente {user_id}, sessione {session_id[:8]}...")
                    cur.execute(call_proc_str, params)

                    self.logger.debug("Pulizia delle variabili di sessione per l'audit.")
                    cur.execute(f"SELECT set_config('{self.schema}.app_user_id', NULL, false);")
                    cur.execute(f"SELECT set_config('{self.schema}.session_id', NULL, false);")
            
            self.logger.info(f"Logout per utente ID {user_id}, sessione {session_id[:8]}... completato.")
            return True

        # --- CORREZIONE: Gestione esplicita della perdita di connessione ---
        except psycopg2.OperationalError as op_err:
            self.logger.critical(f"Logout fallito: persa la connessione con il server DB. Errore: {op_err}", exc_info=True)
            # Azione critica: il pool non è più valido. Chiudiamolo forzatamente.
            self.close_pool()
            return False # Segnala il fallimento
        # --- FINE CORREZIONE ---

        except Exception as e:
            self.logger.error(f"Errore durante il processo di logout per l'utente {user_id}: {e}", exc_info=True)
            return False
    def check_permission(self, utente_id: int, permesso_nome: str) -> bool:
        """Chiama la funzione SQL ha_permesso."""
        try:
            query = "SELECT ha_permesso(%s, %s) AS permesso"
            if self.execute_query(query, (utente_id, permesso_nome)): result = self.fetchone(); return result.get('permesso', False) if result else False
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB verifica permesso '{permesso_nome}' per utente ID {utente_id}: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python verifica permesso '{permesso_nome}' per utente ID {utente_id}: {e}"); return False
    # In catasto_db_manager.py, all'interno della classe CatastoDBManager

    # In catasto_db_manager.py, all'interno della classe CatastoDBManager

    def get_recent_session_logs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recupera gli ultimi N eventi di sessione (login, logout, etc.)
        unendo le informazioni con i nomi degli utenti.
        """
        self.logger.info(f"Recupero degli ultimi {limit} log di sessione.")
        
        # --- INIZIO MODIFICA DEFINITIVA ---
        # La query ora usa i nomi corretti delle colonne: 'data_login' e 'indirizzo_ip'
        query = f"""
            SELECT
                sa.data_login,
                sa.azione,
                sa.esito,
                sa.indirizzo_ip,
                u.username,
                u.nome_completo
            FROM {self.schema}.sessioni_accesso sa
            LEFT JOIN {self.schema}.utente u ON sa.utente_id = u.id
            ORDER BY sa.data_login DESC
            LIMIT %s;
        """
        # --- FINE MODIFICA DEFINITIVA ---

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (limit,))
                    results = [dict(row) for row in cur.fetchall()]
                    return results
        except Exception as e:
            self.logger.error(f"Errore durante il recupero dei log di sessione recenti: {e}", exc_info=True)
            return []
    def get_utenti(self, solo_attivi: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Recupera un elenco di utenti in modo sicuro, con filtro opzionale."""
        query = f"""
            SELECT id, username, nome_completo, email, ruolo, attivo, ultimo_accesso,
                   failed_attempts, locked_until, password_must_change
            FROM {self.schema}.utente
        """
        params = []

        if solo_attivi is not None:
            query += " WHERE attivo = %s"
            params.append(solo_attivi)

        query += " ORDER BY username;"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, tuple(params) if params else None)
                    results = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"Recuperati {len(results)} utenti.")
                    return results
        except Exception as e:
            self.logger.error(f"Errore DB durante il recupero degli utenti: {e}", exc_info=True)
            return []
    def get_utente_by_id(self, utente_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di un singolo utente tramite ID, in modo sicuro."""
        if not isinstance(utente_id, int) or utente_id <= 0:
            self.logger.error(f"get_utente_by_id: utente_id non valido: {utente_id}")
            return None

        query = f"SELECT id, username, nome_completo, email, ruolo, attivo FROM {self.schema}.utente WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, (utente_id,))
                    user_data = cur.fetchone()
                    if user_data:
                        return dict(user_data)
                    else:
                        self.logger.warning(f"Nessun utente trovato con ID: {utente_id}")
                        return None
        except Exception as e:
            self.logger.error(f"Errore DB in get_utente_by_id (ID: {utente_id}): {e}", exc_info=True)
            return None

    def update_user_details(self, utente_id: int, nome_completo: Optional[str] = None,
                        email: Optional[str] = None, ruolo: Optional[str] = None,
                        attivo: Optional[bool] = None) -> bool:
        """Aggiorna i dettagli di un utente in modo transazionale e sicuro."""
        if not any([nome_completo is not None, email is not None, ruolo is not None, attivo is not None]):
            self.logger.warning(f"Nessun dettaglio valido fornito per aggiornare utente ID {utente_id}.")
            return False

        fields_to_update, params = [], []
        if nome_completo is not None:
            fields_to_update.append("nome_completo = %s"); params.append(nome_completo)
        if email is not None:
            fields_to_update.append("email = %s"); params.append(email)
        if ruolo is not None:
            if ruolo not in ['admin', 'archivista', 'consultatore']:
                raise DBDataError(f"Ruolo non valido: {ruolo}")
            fields_to_update.append("ruolo = %s"); params.append(ruolo)
        if attivo is not None:
            fields_to_update.append("attivo = %s"); params.append(attivo)
        
        if not fields_to_update:
            return True # Nessuna modifica richiesta

        fields_to_update.append("data_modifica = CURRENT_TIMESTAMP")
        query = f"UPDATE {self.schema}.utente SET {', '.join(fields_to_update)} WHERE id = %s"
        params.append(utente_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Utente con ID {utente_id} non trovato per l'aggiornamento.")
            
            self.logger.info(f"Dettagli utente ID {utente_id} aggiornati.")
            return True
        except (DBNotFoundError, DBDataError, DBUniqueConstraintError) as e:
            self.logger.error(f"Errore previsto aggiornando utente {utente_id}: {e}", exc_info=True)
            raise e
        except Exception as e:
            self.logger.error(f"Errore imprevisto DB aggiornando utente {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare l'utente: {e}") from e    
   
    def reset_user_password(self, utente_id: int, new_password_hash: str) -> bool:
        """Resetta la password di un utente in modo transazionale e sicuro."""
        query = f"UPDATE {self.schema}.utente SET password_hash = %s, data_modifica = CURRENT_TIMESTAMP WHERE id = %s"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (new_password_hash, utente_id))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Utente con ID {utente_id} non trovato per reset password.")
            
            self.logger.info(f"Password resettata per utente ID {utente_id}.")
            return True
        except DBNotFoundError as e:
            self.logger.warning(e)
            raise e
        except Exception as e:
            self.logger.error(f"Errore DB durante il reset password per utente ID {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Errore database durante il reset password: {e}") from e

    def _update_user_active_status(self, utente_id: int, nuovo_stato_attivo: bool) -> bool:
        """Metodo helper per attivare o disattivare un utente in modo transazionale."""
        query = f"UPDATE {self.schema}.utente SET attivo = %s, data_modifica = CURRENT_TIMESTAMP WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (nuovo_stato_attivo, utente_id))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Utente con ID {utente_id} non trovato per aggiornamento stato.")
            
            status_str = "attivato" if nuovo_stato_attivo else "disattivato"
            self.logger.info(f"Utente ID {utente_id} {status_str}.")
            return True
        except (DBNotFoundError, DBMError) as e:
            self.logger.error(f"Errore previsto aggiornando stato utente {utente_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Errore imprevisto aggiornando stato utente {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare lo stato dell'utente: {e}") from e

    def deactivate_user(self, utente_id: int) -> bool:
        """Disattiva un utente. Utilizza _update_user_active_status."""
        return self._update_user_active_status(utente_id, False)

    def activate_user(self, utente_id: int) -> bool:
        """Riattiva un utente. Utilizza _update_user_active_status."""
        return self._update_user_active_status(utente_id, True)

    def delete_user_permanently(self, utente_id: int) -> bool:
        """Elimina fisicamente un utente in modo transazionale e sicuro."""
        utente_da_eliminare = self.get_utente_by_id(utente_id) # Usa il metodo già refattorizzato
        if not utente_da_eliminare:
            self.logger.warning(f"Tentativo di eliminare utente ID {utente_id} non trovato.")
            return False
                
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # La logica di controllo e l'eliminazione avvengono nella stessa transazione
                    if utente_da_eliminare.get('ruolo') == 'admin':
                        cur.execute(f"SELECT COUNT(*) AS count FROM {self.schema}.utente WHERE ruolo = 'admin' AND attivo = TRUE")
                        count_result = cur.fetchone()
                        if count_result and count_result['count'] <= 1:
                            self.logger.error(f"Tentativo di eliminare l'unico admin attivo (ID: {utente_id}). Operazione negata.")
                            # Non solleviamo un'eccezione, ma restituiamo False per bloccare l'operazione
                            # Il context manager eseguirà un rollback/commit innocuo.
                            return False
                    
                    # Se i controlli sono superati, procedi con l'eliminazione
                    cur.execute(f"DELETE FROM {self.schema}.utente WHERE id = %s", (utente_id,))
                    
                    if cur.rowcount == 0:
                        # Caso limite in cui l'utente viene eliminato tra il get iniziale e qui
                        raise DBNotFoundError(f"Utente ID {utente_id} scomparso prima dell'eliminazione finale.")

            # Il commit è automatico se tutto va a buon fine
            self.logger.info(f"Utente ID {utente_id} eliminato fisicamente con successo.")
            return True

        except Exception as e:
            self.logger.error(f"Errore durante l'eliminazione dell'utente ID {utente_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile eliminare l'utente: {e}") from e
    # --- Metodi Sistema Backup (Invariati rispetto a comune_id) ---
    # In catasto_db_manager.py, SOSTITUISCI la vecchia funzione get_audit_logs

    def close_user_session(self, session_id: str) -> bool:
        """
        Aggiorna la sessione di un utente nel database, impostando l'ora di fine (logout).

        Args:
            session_id: L'UUID della sessione da chiudere.

        Returns:
            True se la sessione è stata chiusa con successo, False altrimenti.
        """
        if not self.pool:
            logger.error("Impossibile chiudere la sessione utente: pool di connessioni non disponibile.")
            return False

        if not session_id:
            logger.warning("Nessun ID di sessione fornito, impossibile chiudere la sessione nel DB.")
            return False

        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                logger.info(f"Chiusura della sessione utente con ID: {session_id}")
                
                # Query per aggiornare la data_fine della sessione specificata
                # che non è ancora stata chiusa.
                query = """
                    UPDATE catasto.sessioni
                    SET data_fine = CURRENT_TIMESTAMP
                    WHERE id = %s AND data_fine IS NULL;
                """
                cur.execute(query, (session_id,))
                conn.commit()
                
                # psycopg2 fornisce rowcount per sapere se una riga è stata effettivamente aggiornata
                if cur.rowcount > 0:
                    logger.info(f"Sessione {session_id} chiusa con successo nel database.")
                else:
                    logger.warning(f"Tentativo di chiudere la sessione {session_id}, ma non è stata trovata o era già chiusa.")
                
                return True
        
        except (Exception, psycopg2.Error) as e:
            logger.error(f"Errore database durante la chiusura della sessione {session_id}: {e}")
            if conn:
                conn.rollback()
            return False
        
        finally:
            if conn:
                self.release_connection(conn)
    # In catasto_db_manager.py, aggiungi questo metodo alla classe

