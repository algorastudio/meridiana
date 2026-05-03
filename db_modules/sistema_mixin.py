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
import uuid
import os
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

class SistemaMixin:
    def get_audit_log(self, tabella: Optional[str]=None, operazione: Optional[str]=None,
                      record_id: Optional[int]=None, data_inizio: Optional[date]=None,
                      data_fine: Optional[date]=None, utente_db: Optional[str]=None,
                      app_user_id: Optional[int]=None, session_id: Optional[str]=None,
                      limit: int=100) -> List[Dict]:
        """Recupera log di audit con filtri opzionali dalla vista v_audit_dettagliato."""
        try:
            conditions = []; params = []
            query = "SELECT * FROM v_audit_dettagliato"
            if tabella: conditions.append("tabella = %s"); params.append(tabella)
            if operazione and operazione.upper() in ['I', 'U', 'D']: conditions.append("operazione = %s"); params.append(operazione.upper())
            if record_id is not None: conditions.append("record_id = %s"); params.append(record_id)
            if data_inizio: conditions.append("timestamp >= %s"); params.append(data_inizio)
            if data_fine: data_fine_end_day = datetime.combine(data_fine, datetime.max.time()); conditions.append("timestamp <= %s"); params.append(data_fine_end_day)
            if utente_db: conditions.append("db_user = %s"); params.append(utente_db)
            # Attenzione: filtro su app_user_id deve usare alias tabella originale se vista non lo include direttamente con alias
            # La vista v_audit_dettagliato JOIN u ON al.app_user_id = u.id, quindi al.app_user_id non è direttamente selezionato
            # Modifichiamo la vista o filtriamo su app_username? Filtriamo su ID per ora, assumendo che la vista possa essere modificata o che funzioni.
            if app_user_id is not None: conditions.append("al.app_user_id = %s"); params.append(app_user_id) # Usa al.app_user_id (potrebbe richiedere modifica vista)
            if session_id: conditions.append("session_id = %s"); params.append(session_id)

            if conditions: query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC LIMIT %s"; params.append(limit)

            if self.execute_query(query, tuple(params)): return self.fetchall()
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_audit_log: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python get_audit_log: {e}"); return []
        return []

    def get_record_history(self, tabella: str, record_id: int) -> List[Dict]:
        """Chiama la funzione SQL get_record_history."""
        try:
            query = "SELECT * FROM get_record_history(%s, %s)"
            if self.execute_query(query, (tabella, record_id)): return self.fetchall()
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_record_history: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python get_record_history: {e}"); return []
        return []

    

    def get_audit_logs(self,
                    filters: Optional[Dict[str, Any]] = None,
                    page: int = 1,
                    page_size: int = 50,
                    sort_by: str = 'timestamp',
                    sort_order: str = 'DESC'
                    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recupera i record dalla vista v_audit_dettagliato con filtri, paginazione e ordinamento.
        """
        if filters is None:
            filters = {}

        query_conditions = []
        query_params = []

        # Costruzione delle condizioni WHERE in base ai filtri
        if filters.get("table_name"):
            query_conditions.append("tabella ILIKE %s")
            query_params.append(f"%{filters['table_name']}%")

        # --- NUOVO: Filtro per username ---
        if filters.get("username"):
            query_conditions.append("username ILIKE %s")
            query_params.append(f"%{filters['username']}%")
        # --- FINE NUOVO ---

        # ... (gli altri filtri come operation_char, record_id, date rimangono uguali) ...
        if filters.get("operation_char"):
            query_conditions.append("operazione = %s")
            query_params.append(filters["operation_char"])
        if filters.get("record_id") is not None:
            query_conditions.append("record_id = %s")
            query_params.append(filters["record_id"])
        if filters.get("start_datetime"):
            query_conditions.append("timestamp >= %s")
            query_params.append(filters["start_datetime"])
        if filters.get("end_datetime"):
            query_conditions.append("timestamp <= %s")
            query_params.append(filters["end_datetime"])

        where_clause = ""
        if query_conditions:
            where_clause = "WHERE " + " AND ".join(query_conditions)

        # La query ora interroga la VISTA, non la tabella diretta
        base_query = f"FROM {self.schema}.v_audit_dettagliato {where_clause}"
        count_query = f"SELECT COUNT(*) {base_query};"

        # Validazione e costruzione ORDER BY (invariato)
        allowed_sort_columns = ['id', 'timestamp', 'username', 'tabella', 'operazione', 'record_id']
        if sort_by not in allowed_sort_columns: sort_by = 'timestamp'
        if sort_order.upper() not in ['ASC', 'DESC']: sort_order = 'DESC'
        order_by_clause = f"ORDER BY {sort_by} {sort_order.upper()}"

        offset = (page - 1) * page_size

        # La query dei dati ora seleziona direttamente dalla vista
        data_query = f"""
            SELECT * {base_query}
            {order_by_clause}
            LIMIT %s OFFSET %s;
        """
        query_params_data = query_params + [page_size, offset]

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(count_query, query_params)
                    total_records = cur.fetchone()[0]

                    if total_records > 0:
                        cur.execute(data_query, query_params_data)
                        logs = [dict(row) for row in cur.fetchall()]
                    else:
                        logs = []

        except Exception as e:
            self.logger.error(f"Errore durante il recupero dei log di audit: {e}", exc_info=True)
            return [], 0

        return logs, total_records
    def register_backup_log(self, nome_file: str, utente: str, tipo: str, esito: bool,
                            percorso_file: str, dimensione_bytes: Optional[int] = None,
                            messaggio: Optional[str] = None) -> Optional[int]:
        """Chiama la funzione SQL registra_backup."""
        try:
            query = "SELECT registra_backup(%s, %s, %s, %s, %s, %s, %s)"
            params = (nome_file, utente, dimensione_bytes, tipo, esito, messaggio, percorso_file)
            if self.execute_query(query, params):
                 result = self.fetchone(); self.commit(); backup_id = result.get('registra_backup') if result else None
                 if backup_id: logger.info(f"Log backup registrato ID: {backup_id} per '{nome_file}'")
                 else: logger.error(f"registra_backup non ha restituito ID per '{nome_file}'.")
                 return backup_id
        except psycopg2.Error as db_err: logger.error(f"Errore DB reg log backup '{nome_file}': {db_err}")
        except Exception as e: logger.error(f"Errore Python reg log backup '{nome_file}': {e}"); self.rollback()
        return None
    
    # Assicurati che anche i metodi come _find_executable, get_backup_command_parts, 
    # get_restore_command_parts siano presenti come li avevamo definiti.
    # Non interagiscono direttamente con il pool per le loro query, ma usano parametri da self.conn_params_dict
    def _find_executable(self, name: str) -> Optional[str]:
        executable_path = shutil.which(name)
        if executable_path:
            self.logger.info(f"Trovato eseguibile '{name}' in: {executable_path}")
            return executable_path
        else:
            self.logger.warning(f"Eseguibile '{name}' non trovato nel PATH di sistema.")
            return None # Modificato da return "" per coerenza con Optional[str]


    def _resolve_executable_path(self, user_provided_path: str, default_name: str) -> Optional[str]:
        if user_provided_path and os.path.isabs(user_provided_path) and os.path.exists(user_provided_path) and os.path.isfile(user_provided_path):
            self.logger.info(f"Utilizzo del percorso eseguibile fornito: {user_provided_path}")
            return user_provided_path
        elif user_provided_path:
             self.logger.warning(f"Percorso fornito '{user_provided_path}' per '{default_name}' non valido. Tento ricerca nel PATH.")
        
        found_path_in_system = shutil.which(default_name)
        if found_path_in_system:
            self.logger.info(f"Trovato eseguibile '{default_name}' nel PATH: {found_path_in_system}")
            return found_path_in_system
        else:
            self.logger.error(f"Eseguibile '{default_name}' non trovato nel PATH e nessun percorso valido fornito.")
            # Fornire un messaggio all'utente nella GUI che il tool non è stato trovato e deve essere configurato
            return None
    def get_backup_command_parts(self,
                                 backup_file_path: str,
                                 pg_dump_executable_path_ui: str,
                                 format_type: str = "custom",
                                 include_blobs: bool = False
                                ) -> Optional[List[str]]:
        
        actual_pg_dump_path = self._resolve_executable_path(pg_dump_executable_path_ui, "pg_dump.exe")
        if not actual_pg_dump_path:
            return None

        # USA L'ATTRIBUTO CORRETTO: _main_db_conn_params
        db_user = self._main_db_conn_params.get("user")
        db_host = self._main_db_conn_params.get("host")
        db_port = str(self._main_db_conn_params.get("port"))
        db_name = self._main_db_conn_params.get("dbname")

        if not all([db_user, db_host, db_port, db_name]):
            self.logger.error("Parametri di connessione mancanti per il backup (da _main_db_conn_params).")
            return None

        command = [actual_pg_dump_path, "-U", db_user, "-h", db_host, "-p", db_port]
        
        if format_type == "custom": command.append("-Fc")
        elif format_type == "plain": command.append("-Fp")
        else:
            self.logger.error(f"Formato di backup non supportato: {format_type}"); return None
        command.extend(["--file", backup_file_path])
        if include_blobs: command.append("--blobs")
        command.append(db_name)
        self.logger.info(f"Comando di backup preparato: {' '.join(command)}")
        return command

    def get_restore_command_parts(self,
                                  backup_file_path: str,
                                  pg_tool_executable_path_ui: str
                                 ) -> Optional[List[str]]:
        # USA L'ATTRIBUTO CORRETTO: _main_db_conn_params
        db_user = self._main_db_conn_params.get("user")
        db_host = self._main_db_conn_params.get("host")
        db_port = str(self._main_db_conn_params.get("port"))
        db_name = self._main_db_conn_params.get("dbname")

        if not all([db_user, db_host, db_port, db_name]):
            self.logger.error("Parametri di connessione mancanti per il ripristino (da _main_db_conn_params).")
            return None

        command: List[str] = []
        _, file_extension = os.path.splitext(backup_file_path)
        file_extension = file_extension.lower()
        actual_pg_tool_path = None

        if file_extension in [".dump", ".backup", ".custom"]:
            actual_pg_tool_path = self._resolve_executable_path(pg_tool_executable_path_ui, "pg_restore.exe")
            if not actual_pg_tool_path: return None
            command = [actual_pg_tool_path, "-U", db_user, "-h", db_host, "-p", db_port, "-d", db_name]
            command.extend(["--clean", "--if-exists", "--verbose"]) # Opzioni comuni per pg_restore
            command.append(backup_file_path)
        elif file_extension == ".sql":
            actual_pg_tool_path = self._resolve_executable_path(pg_tool_executable_path_ui, "psql.exe")
            if not actual_pg_tool_path: return None
            command = [actual_pg_tool_path, "-U", db_user, "-h", db_host, "-p", db_port, "-d", db_name]
            command.extend(["-f", backup_file_path, "-v", "ON_ERROR_STOP=1"]) # Esegui script SQL con psql
        else:
            self.logger.error(f"Formato file di backup non riconosciuto o non supportato: '{file_extension}'"); return None
        self.logger.info(f"Comando di ripristino preparato: {' '.join(command)}")
        return command

    def cleanup_old_backup_logs(self, giorni_conservazione: int = 30) -> bool:
        """Chiama la procedura SQL pulizia_backup_vecchi."""
        try:
            call_proc = "CALL pulizia_backup_vecchi(%s)"
            if self.execute_query(call_proc, (giorni_conservazione,)): self.commit(); logger.info(f"Eseguita pulizia log backup più vecchi di {giorni_conservazione} giorni."); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB pulizia log backup: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python pulizia log backup: {e}"); self.rollback(); return False

    def generate_backup_script(self, backup_dir: str) -> Optional[str]:
        """Chiama la funzione SQL genera_script_backup_automatico."""
        try:
            query = "SELECT genera_script_backup_automatico(%s) AS script_content"
            if self.execute_query(query, (backup_dir,)): result = self.fetchone(); return result.get('script_content') if result else None
        except psycopg2.Error as db_err: logger.error(f"Errore DB gen script backup: {db_err}"); return None
        except Exception as e: logger.error(f"Errore Python gen script backup: {e}"); return None
        return None

    def get_backup_logs(self, limit: int = 20) -> List[Dict]:
        """Recupera gli ultimi N log di backup dal registro."""
        query = f"SELECT * FROM {self.schema}.backup_registro ORDER BY timestamp DESC LIMIT %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (limit,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore DB get_backup_logs: {e}", exc_info=True)
            return []

    
    # --- Metodi Ricerca Avanzata (MODIFICATI) ---

    def set_audit_session_variables(self, app_user_id: Optional[int], session_id: Optional[str]) -> bool:
        """Imposta le variabili di sessione PostgreSQL per l'audit log in modo sicuro."""
        if app_user_id is None or session_id is None:
            self.logger.warning("Tentativo di impostare variabili audit con None.")
            return False
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Il terzo argomento 'false' rende l'impostazione valida per l'intera sessione
                    cur.execute("SELECT set_config(%s, %s, false);", (f"{self.schema}.app_user_id", str(app_user_id)))
                    cur.execute("SELECT set_config(%s, %s, false);", (f"{self.schema}.session_id", session_id))
            
            # Il commit è gestito automaticamente dal context manager _get_connection
            self.logger.info(f"Variabili di sessione per audit impostate: app_user_id={app_user_id}, session_id={session_id[:8]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore DB impostando variabili audit: {e}", exc_info=True)
            return False

    
    def clear_audit_session_variables(self) -> bool:
        """Resetta le variabili di sessione per l'audit in modo sicuro."""
        self.logger.info("Reset variabili di sessione per audit...")
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Impostare a NULL è un modo esplicito e sicuro per resettare
                    cur.execute(f"SELECT set_config('{self.schema}.app_user_id', NULL, false);")
                    cur.execute(f"SELECT set_config('{self.schema}.session_id', NULL, false);")
            
            self.logger.info("Variabili di sessione per audit resettate con successo.")
            return True
        except Exception as e:
            self.logger.error(f"Errore DB resettando variabili audit: {e}", exc_info=True)
            return False

    def execute_sql_from_file(self, file_path: str) -> Tuple[bool, str]:
        """Esegue uno script SQL da un file in modo sicuro, gestendo l'autocommit."""
        if not os.path.exists(file_path):
            return False, f"File SQL non trovato: {file_path}"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            with self._get_connection() as conn:
                # Imposta il livello di isolamento per la singola operazione
                # Questo è il modo corretto di gestire l'autocommit con un pool
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cur:
                    self.logger.info(f"Esecuzione script SQL da file: {file_path}")
                    cur.execute(sql_content)
            
            self.logger.info(f"Script SQL {file_path} eseguito con successo.")
            return True, f"Script {os.path.basename(file_path)} eseguito con successo."

        except Exception as e:
            msg = f"Errore eseguendo script {file_path}: {e}"
            self.logger.error(msg, exc_info=True)
            # Il context manager gestisce già il rollback, ma in autocommit non è rilevante.
            # La connessione verrà comunque restituita correttamente al pool.
            return False, msg
    def cleanup_audit_logs(self, days_to_keep: int) -> int:
        """
        Elimina i record di audit_log più vecchi di un certo numero di giorni.
        Restituisce il numero di record eliminati.
        """
        if not isinstance(days_to_keep, int) or days_to_keep < 0:
            raise DBDataError("Il numero di giorni da conservare deve essere un intero non negativo.")

        query = f"""
            DELETE FROM {self.schema}.audit_log
            WHERE timestamp < NOW() - INTERVAL '{days_to_keep} days';
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    deleted_rows = cur.rowcount
            self.logger.info(f"Eliminati {deleted_rows} record di audit log più vecchi di {days_to_keep} giorni.")
            return deleted_rows
        except Exception as e:
            self.logger.error(f"Errore durante la pulizia dei log di audit: {e}", exc_info=True)
            raise DBMError(f"Impossibile pulire i log di audit: {e}") from e
    # In catasto_db_manager.py, dentro la classe CatastoDBManager

    def execute_restore_from_file_emergency(self, backup_file_path: str) -> Tuple[bool, str]:
        """
        Esegue un ripristino DRUPIDO E DISTRUTTIVO del database.
        1. CANCELLA il database esistente.
        2. LO RICREA vuoto.
        3. LO RIPRISTINA dal file di backup.
        Questa operazione richiede una connessione al database di manutenzione (es. 'postgres').
        """
        # Ottieni i parametri necessari dal gestore stesso
        db_user = self._main_db_conn_params.get("user")
        db_password = self._main_db_conn_params.get("password") # Richiede la password per i tool
        db_host = self._main_db_conn_params.get("host")
        db_port = str(self._main_db_conn_params.get("port"))
        db_name = self._main_db_conn_params.get("dbname")

        # Trova i percorsi degli eseguibili
        dropdb_path = self._resolve_executable_path(None, "dropdb.exe")
        createdb_path = self._resolve_executable_path(None, "createdb.exe")
        pg_restore_path = self._resolve_executable_path(None, "pg_restore.exe")

        if not all([dropdb_path, createdb_path, pg_restore_path]):
            msg = "Impossibile trovare gli eseguibili di PostgreSQL (dropdb, createdb, pg_restore) nel PATH di sistema."
            self.logger.error(msg)
            return False, msg

        # Comando per CANCELLARE il database esistente
        drop_command = [dropdb_path, "-U", db_user, "-h", db_host, "-p", db_port, "--if-exists", "-f", db_name]

        # Comando per RICREARE il database vuoto
        create_command = [createdb_path, "-U", db_user, "-h", db_host, "-p", db_port, "-T", "template0", db_name]

        # Comando per RIPRISTINARE il backup
        restore_command = [pg_restore_path, "-U", db_user, "-h", db_host, "-p", db_port, "-d", db_name, "--clean", "--if-exists", "-v", backup_file_path]

        commands = [
            ("Cancellazione DB esistente", drop_command),
            ("Creazione DB vuoto", create_command),
            ("Ripristino dati da backup", restore_command)
        ]

        # Imposta la variabile d'ambiente per la password
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        for description, command in commands:
            self.logger.info(f"Esecuzione emergenza: {description}...")
            process = QProcess()
            process.setProcessEnvironment(self.create_clean_environment()) # Usa un ambiente pulito
            # Crea un oggetto QProcessEnvironment
            env_process = QProcessEnvironment()
            for k, v in env.items():
                env_process.insert(k, v)

            # Imposta l'ambiente del processo
            process.setProcessEnvironment(env_process)

            process.start(command[0], command[1:])
            if not process.waitForFinished(-1):
                error_msg = f"Timeout o errore durante: {description}. Errore: {process.errorString()}"
                self.logger.error(error_msg)
                return False, error_msg

            exit_code = process.exitCode()
            if exit_code != 0:
                error_output = process.readAllStandardError().data().decode('utf-8', errors='ignore')
                error_msg = f"Fallimento durante '{description}' (codice: {exit_code}).\nErrore:\n{error_output}"
                self.logger.error(error_msg)
                return False, error_msg

        success_msg = f"Ripristino del database '{db_name}' completato con successo."
        self.logger.info(success_msg)
        return True, success_msg
    # In catasto_db_manager.py, aggiungi questi metodi alla classe CatastoDBManager

    def create_clean_environment(self) -> 'QProcessEnvironment':
        """Crea un ambiente pulito per QProcess, ereditando le variabili di sistema."""
        from PyQt5.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        return env
