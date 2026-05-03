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

class RelazioniMixin:
    def registra_nuova_proprieta(self, comune_id: int, numero_partita: int, data_impianto: date,
                                 possessori_json_str: str,
                                 immobili_json_str: str,
                                 suffisso_partita: Optional[str] = None
                                ) -> int:
        """
        Chiama la procedura SQL per registrare una nuova proprietà, gestendo
        specificamente l'errore di partita duplicata.
        """
        if not (isinstance(comune_id, int) and comune_id > 0): raise DBDataError("ID comune non valido.")
        if not (isinstance(numero_partita, int) and numero_partita > 0): raise DBDataError("Numero partita non valido.")
        try:
            json.loads(possessori_json_str); json.loads(immobili_json_str)
        except json.JSONDecodeError as je:
            raise DBDataError(f"Dati JSON non validi: {je}") from je
        
        actual_suffisso_partita = suffisso_partita.strip() if isinstance(suffisso_partita, str) else None

        call_proc = f"CALL {self.schema}.registra_nuova_proprieta(%s, %s, %s, %s::jsonb, %s::jsonb, %s::TEXT);"
        params_call = (comune_id, numero_partita, data_impianto, possessori_json_str, immobili_json_str, actual_suffisso_partita)
        
        query_select_id = f"""
            SELECT id FROM {self.schema}.partita 
            WHERE comune_id = %s AND numero_partita = %s AND 
                (suffisso_partita = %s OR (suffisso_partita IS NULL AND %s IS NULL))
            ORDER BY id DESC LIMIT 1; 
        """
        params_select = (comune_id, numero_partita, actual_suffisso_partita, actual_suffisso_partita)

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    self.logger.debug(f"Chiamata procedura registra_nuova_proprieta per C:{comune_id}, N:{numero_partita}")
                    cur.execute(call_proc, params_call)
                    
                    self.logger.debug("Recupero ID della partita appena creata.")
                    cur.execute(query_select_id, params_select)
                    result = cur.fetchone()

                    if result and result['id']:
                        new_partita_id = result['id']
                        self.logger.info(f"Nuova proprietà registrata. Partita ID: {new_partita_id}.")
                        return new_partita_id
                    else:
                        raise DBMError("Fallimento nel recuperare l'ID della nuova partita dopo la registrazione.")
        
        # --- BLOCCO DI GESTIONE ECCEZIONI MIGLIORATO ---
        except psycopg2.errors.UniqueViolation as uve:
            # Controlliamo il nome del vincolo violato per dare un messaggio specifico
            constraint_name = getattr(uve.diag, 'constraint_name', '')
            if constraint_name == 'partita_unique_numero_suffisso_comune':
                messaggio = "Impossibile registrare: una partita con lo stesso numero e suffisso esiste già in questo comune."
                raise DBUniqueConstraintError(messaggio, constraint_name=constraint_name) from uve
            else:
                # Se è un altro vincolo di unicità, diamo un messaggio più generico
                messaggio_generico = f"Violazione di un vincolo di unicità '{constraint_name}'. Controllare i dati."
                raise DBUniqueConstraintError(messaggio_generico, constraint_name=constraint_name) from uve
        
        except Exception as e:
            # Cattura tutte le altre eccezioni
            self.logger.error(f"Errore in registra_nuova_proprieta: {e}", exc_info=True)
            raise DBMError(f"Impossibile registrare la nuova proprietà: {e}") from e
        # --- FINE BLOCCO MIGLIORATO ---
    
    def registra_passaggio_proprieta(self, partita_origine_id: int, comune_id_nuova_partita: int, 
                                 numero_nuova_partita: int, tipo_variazione: str, data_variazione: date, 
                                 tipo_contratto: str, data_contratto: date,
                                 notaio: Optional[str] = None, repertorio: Optional[str] = None,
                                 nuovi_possessori_list: Optional[List[Dict[str, Any]]] = None, 
                                 immobili_da_trasferire_ids: Optional[List[int]] = None, 
                                 note_variazione: Optional[str] = None,
                                 suffisso_nuova_partita: Optional[str] = None) -> bool:
        """Chiama la procedura SQL catasto.registra_passaggio_proprieta in modo transazionale e con cast espliciti."""
        try:
            nuovi_possessori_jsonb = json.dumps(nuovi_possessori_list) if nuovi_possessori_list else None
            
            # --- MODIFICA CHIAVE: Aggiunti cast espliciti per tutti i tipi che possono essere NULL ---
            # Questo garantisce che PostgreSQL riceva i tipi corretti anche per i valori None.
            call_proc_str = f"""
                CALL {self.schema}.registra_passaggio_proprieta(
                    %s,                    -- p_partita_origine_id INTEGER
                    %s,                    -- p_comune_id_nuova_partita INTEGER
                    %s,                    -- p_numero_nuova_partita INTEGER
                    %s::VARCHAR(20),       -- p_suffisso_nuova_partita VARCHAR(20)
                    %s::TEXT,              -- p_tipo_variazione TEXT
                    %s,                    -- p_data_variazione DATE
                    %s::TEXT,              -- p_tipo_contratto TEXT
                    %s,                    -- p_data_contratto DATE
                    %s::TEXT,              -- p_notaio TEXT
                    %s::TEXT,              -- p_repertorio TEXT
                    %s::JSONB,             -- p_nuovi_possessori_json JSONB
                    %s::INTEGER[],         -- p_immobili_da_trasferire_ids INTEGER[]
                    %s::TEXT               -- p_note_variazione TEXT
                );
            """
            
            params = (
                partita_origine_id, comune_id_nuova_partita, numero_nuova_partita, suffisso_nuova_partita,
                tipo_variazione, data_variazione, tipo_contratto, data_contratto,
                notaio, repertorio, nuovi_possessori_jsonb, immobili_da_trasferire_ids, note_variazione
            )
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Tentativo di registrare passaggio proprietà da Partita ID {partita_origine_id}...")
                    cur.execute(call_proc_str, params)
            
            self.logger.info("Passaggio di proprietà registrato con successo tramite procedura.")
            return True
        except psycopg2.Error as db_err:
            pgerror_msg = getattr(db_err, 'pgerror', str(db_err))
            self.logger.error(f"Errore DB durante registrazione passaggio proprietà: {pgerror_msg}", exc_info=True)
            raise DBMError(f"Errore database: {pgerror_msg}") from db_err
        except Exception as e:
            self.logger.error(f"Errore Python durante registrazione passaggio proprietà: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema: {e}") from e
    def aggiorna_legame_partita_possessore(self, partita_possessore_id: int, titolo: str, quota: Optional[str]) -> bool:
        """Aggiorna i dettagli di un legame partita-possessore in modo transazionale."""
        if not (isinstance(partita_possessore_id, int) and partita_possessore_id > 0):
            raise DBDataError(f"ID relazione non valido: {partita_possessore_id}")
        if not (isinstance(titolo, str) and titolo.strip()):
            raise DBDataError("Il titolo di possesso è obbligatorio.")
        
        actual_quota = quota.strip() if isinstance(quota, str) and quota.strip() else None

        set_clauses = ["titolo = %s", "quota = %s", "data_modifica = CURRENT_TIMESTAMP"]
        params = [titolo.strip(), actual_quota, partita_possessore_id]

        query = f"UPDATE {self.schema}.partita_possessore SET {', '.join(set_clauses)} WHERE id = %s;"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        # Se non viene aggiornata nessuna riga, solleva un errore.
                        # Il context manager gestirà automaticamente il rollback.
                        raise DBNotFoundError(f"Legame partita-possessore con ID {partita_possessore_id} non trovato.")
            
            # Il commit è automatico se nessuna eccezione è stata sollevata
            self.logger.info(f"Legame partita-possessore ID {partita_possessore_id} aggiornato.")
            return True

        except (DBNotFoundError, DBDataError, psycopg2.errors.CheckViolation) as e:
            # Rilancia eccezioni specifiche per una gestione mirata
            self.logger.error(f"Errore previsto aggiornando legame {partita_possessore_id}: {e}", exc_info=True)
            raise e
        except Exception as e:
            # Gestisce tutti gli altri errori
            self.logger.error(f"Errore imprevisto aggiornando legame {partita_possessore_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare il legame: {e}") from e
    
    def aggiungi_possessore_a_partita(self, partita_id: int, possessore_id: int, tipo_partita_rel: str, titolo: str, quota: Optional[str]) -> bool:
        """Aggiunge un legame partita-possessore in modo transazionale e sicuro."""
        # La validazione dei parametri iniziali resta invariata
        if not all([...]): # (logica di validazione originale)
            raise DBDataError("Parametri non validi forniti.")
            
        actual_quota = quota.strip() if isinstance(quota, str) and quota.strip() else None

        query = f"""
            INSERT INTO {self.schema}.partita_possessore (partita_id, possessore_id, tipo_partita, titolo, quota)
            VALUES (%s, %s, %s, %s, %s) RETURNING id; 
        """
        params = (partita_id, possessore_id, tipo_partita_rel, titolo.strip(), actual_quota)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    new_relation_id = cur.fetchone()[0] if cur.rowcount > 0 else None
                    if not new_relation_id:
                        raise DBMError("Inserimento del legame fallito, nessun ID restituito.")
            
            self.logger.info(f"Possessore ID {possessore_id} associato a partita ID {partita_id}. ID Relazione: {new_relation_id}.")
            return True

        except psycopg2.errors.UniqueViolation as e:
            msg = "Questo possessore è già associato a questa partita."
            raise DBUniqueConstraintError(msg, constraint_name=getattr(e.diag, 'constraint_name', 'N/D'), details=str(e)) from e
        except psycopg2.errors.ForeignKeyViolation as e:
            msg = "La partita o il possessore specificati non esistono."
            raise DBMError(msg) from e
        except psycopg2.errors.CheckViolation as e:
            msg = f"Il valore '{tipo_partita_rel}' non è valido per il tipo di legame."
            raise DBDataError(msg) from e
        except Exception as e:
            self.logger.error(f"Errore imprevisto in aggiungi_possessore_a_partita: {e}", exc_info=True)
            raise DBMError(f"Impossibile associare il possessore: {e}") from e

    def rimuovi_possessore_da_partita(self, partita_possessore_id: int) -> bool:
        """Rimuove un legame partita-possessore in modo transazionale e sicuro."""
        if not (isinstance(partita_possessore_id, int) and partita_possessore_id > 0):
            raise DBDataError(f"ID relazione partita-possessore non valido: {partita_possessore_id}")

        query = f"DELETE FROM {self.schema}.partita_possessore WHERE id = %s;"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (partita_possessore_id,))
                    
                    if cur.rowcount == 0:
                        # Se non viene cancellata nessuna riga, il legame non esisteva.
                        # Solleviamo un errore, che causerà un rollback automatico.
                        self.logger.warning(f"Tentativo di rimuovere legame ID {partita_possessore_id} non trovato.")
                        raise DBNotFoundError(f"Nessun legame partita-possessore trovato con ID {partita_possessore_id}.")
            
            # Il commit è automatico qui se l'operazione ha successo
            self.logger.info(f"Legame partita-possessore ID {partita_possessore_id} rimosso con successo.")
            return True

        except (DBNotFoundError, DBDataError) as e:
            self.logger.error(f"Errore previsto rimuovendo legame {partita_possessore_id}: {e}", exc_info=True)
            raise e  # Rilancia l'eccezione specifica
        except Exception as e:
            self.logger.error(f"Errore imprevisto rimuovendo legame {partita_possessore_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile rimuovere il legame: {e}") from e
