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

class ComuniMixin:
    def create_comune(self,
                        nome_comune: str,
                        provincia: str,
                        regione: str,
                        periodo_id: Optional[int] = None,
                        codice_catastale: Optional[str] = None,
                        data_istituzione: Optional[date] = None,
                        data_soppressione: Optional[date] = None,
                        note: Optional[str] = None,
                        utente: Optional[str] = None
                       ) -> int:
        
        if not nome_comune or not provincia or not regione:
            raise DBDataError("Nome, Provincia e Regione sono campi obbligatori.")
        self._valida_intervallo_date(data_istituzione, data_soppressione,
                                     "Data Istituzione", "Data Soppressione")

        query = f"""
            INSERT INTO {self.schema}.comune
                (nome, provincia, regione, periodo_id, codice_catastale, data_istituzione, data_soppressione, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        params = (
            nome_comune.strip(),
            provincia.strip(),
            regione.strip(),
            periodo_id,
            codice_catastale.strip() if codice_catastale else None,
            data_istituzione,
            data_soppressione,
            note.strip() if note else None
        )
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Esecuzione create_comune per: {nome_comune.strip()}")
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result and result[0] is not None:
                        new_comune_id = result[0]
                        self.logger.info(f"Comune '{nome_comune.strip()}' aggiunto con successo. ID: {new_comune_id}.")
                        return new_comune_id
                    else:
                        raise DBMError("Creazione del comune fallita, nessun ID restituito.")
        
        except psycopg2.errors.UniqueViolation as e:
            # Assumiamo che il vincolo di unicità sia sul nome
            raise DBUniqueConstraintError(f"Impossibile aggiungere il comune: il nome '{nome_comune}' esiste già.", details=str(e)) from e
        
        except Exception as e:
            self.logger.error(f"Errore generico in create_comune: {e}", exc_info=True)
            raise DBMError(f"Errore database durante l'aggiunta del comune: {e}") from e
    def registra_comune_nel_db(self, nome: str, provincia: str, regione: str) -> Optional[int]:
            comune_id: Optional[int] = None
            query_insert = """
            INSERT INTO catasto.comune (nome, provincia, regione)
            VALUES (%s, %s, %s)
            ON CONFLICT (nome) DO NOTHING
            RETURNING id;
            """
            query_select = "SELECT id FROM catasto.comune WHERE nome = %s;"

            try:
                if self.execute_query(query_insert, (nome, provincia, regione)):
                    # execute_query DEVE aver impostato self.cursor se ha restituito True
                    if self.cursor is None: # Controllo di sicurezza aggiuntivo
                        logger.error(f"Errore critico: self.cursor è None dopo execute_query riuscita per INSERT comune '{nome}'.")
                        self.rollback()
                        return None

                    risultato_insert = None
                    if self.cursor.description: # Verifica se la query poteva ritornare risultati
                        try:
                            risultato_insert = self.cursor.fetchone() # Prova a fare fetch
                        except psycopg2.ProgrammingError as pe: # Es. "no results to fetch"
                            logger.warning(f"Nessun risultato da fetchone() per INSERT comune '{nome}' (probabile ON CONFLICT DO NOTHING): {pe}")
                            risultato_insert = None

                    if risultato_insert and 'id' in risultato_insert:
                        comune_id = risultato_insert['id']
                        self.commit()
                        logger.info(f"Comune '{nome}' (ID: {comune_id}) inserito con successo nel database.")
                        return comune_id
                    else: # L'INSERT non ha inserito (ON CONFLICT DO NOTHING) o ID non recuperato
                        logger.info(f"Comune '{nome}' non inserito da INSERT (probabile conflitto). Tentativo di SELECT.")
                        if self.execute_query(query_select, (nome,)):
                            if self.cursor is None: # Controllo di sicurezza
                                logger.error(f"Errore critico: self.cursor è None dopo execute_query riuscita per SELECT comune '{nome}'.")
                                self.rollback()
                                return None
                            
                            risultato_select = self.fetchone() # fetchone() ora dovrebbe usare il cursore del SELECT
                            if risultato_select and 'id' in risultato_select:
                                comune_id = risultato_select['id']
                                self.commit() 
                                logger.info(f"Comune '{nome}' (ID: {comune_id}) già esistente, operazione confermata.")
                                return comune_id
                            else:
                                logger.error(f"Errore logico: Comune '{nome}' non inserito e non trovato dopo ON CONFLICT e successivo SELECT.")
                                self.rollback()
                                return None
                        else: # Errore durante il SELECT
                            # execute_query dovrebbe aver già gestito il rollback
                            logger.error(f"Errore DB nel selezionare il comune '{nome}' dopo un potenziale conflitto.")
                            return None
                else: # Errore durante l'INSERT iniziale
                    # execute_query dovrebbe aver già gestito il rollback
                    logger.error(f"Errore DB iniziale durante l'inserimento del comune '{nome}'.")
                    return None

            except psycopg2.Error as db_err:
                logger.error(f"Errore database (psycopg2) in registra_comune_nel_db per '{nome}': {db_err}")
                self.rollback()
                return None
            except AttributeError as ae: # Specifico per l'errore 'has no attribute cursor' se persiste
                logger.error(f"AttributeError in registra_comune_nel_db per '{nome}': {ae}. Controllare gestione self.cursor.")
                self.rollback()
                return None
            except Exception as e:
                logger.error(f"Errore Python generico in registra_comune_nel_db per '{nome}': {e}")
                self.rollback()
                return None
    def get_comuni(self, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        query = f"SELECT id, nome, provincia, regione FROM {self.schema}.comune"
        params = []
        if search_term:
            query += " WHERE nome ILIKE %s"
            params.append(f"%{search_term}%")
        query += " ORDER BY nome"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, params)
                    results = cur.fetchall()
                    self.logger.info(f"Recuperati {len(results)} comuni (search_term: '{search_term}').")
                    return [dict(row) for row in results]
        except Exception as e:
            self.logger.error(f"Errore DB in get_comuni: {e}", exc_info=True)
            # In caso di errore, restituisce una lista vuota per non bloccare la UI
            return []
    
    # In catasto_db_manager.py, dentro la classe CatastoDBManager
    def get_all_comuni_details(self):
        self.logger.info(">>> ESECUZIONE di get_all_comuni_details...")
        
        # --- QUERY AGGIORNATA PER SELEZIONARE TUTTE LE COLONNE NECESSARIE ---
        query = """
            SELECT 
                id, 
                nome AS nome_comune, 
                codice_catastale,
                provincia, 
                regione,
                data_istituzione,
                data_soppressione,
                note,
                data_creazione, 
                data_modifica
            FROM catasto.comune WHERE archiviato = FALSE ORDER BY nome;
        """
        # --- FINE QUERY AGGIORNATA ---

        self.logger.info(f"Query in esecuzione:\n\t\t\t{query}")
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    self.logger.info(f"--- RISULTATO RICEVUTO da db_manager: Tipo={type(results)}, Lunghezza={len(results)} ---")
                    return results
        except (Exception, psycopg2.Error) as error:
            self.logger.error(f"Errore DB in get_all_comuni_details: {error}", exc_info=True)
            return [] # Restituisci una lista vuota in caso di errore

    
    # In catasto_db_manager.py, aggiungi questi metodi

    def get_elenco_comuni_semplice(self) -> List[Tuple]:
        """
        Recupera un elenco di tutti i comuni (ID e nome) per popolare una scelta utente.
        """
        query = f"SELECT id, nome FROM {self.schema}.comune WHERE archiviato = FALSE ORDER BY nome"
        try:
            with self._get_connection() as conn:
                # Qui non usiamo DictCursor perché la firma del metodo prevede una lista di tuple
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            self.logger.error(f"Errore nel recuperare l'elenco dei comuni: {e}", exc_info=True)
            # Solleviamo un'eccezione personalizzata per informare il chiamante del fallimento
            raise DBMError("Impossibile recuperare l'elenco dei comuni.") from e
    # In catasto_db_manager.py, sostituisci la vecchia funzione con questa:

    def get_comune_by_id(self, comune_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di un comune tramite il suo ID."""
        if not isinstance(comune_id, int) or comune_id <= 0:
            self.logger.error(f"get_comune_by_id: ID comune non valido: {comune_id}")
            return None
        
        query = f"""
            SELECT id, nome AS nome_comune, provincia, regione, codice_catastale, periodo_id,
                   data_istituzione, data_soppressione, note
            FROM {self.schema}.comune
            WHERE id = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (comune_id,))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Errore DB in get_comune_by_id (ID: {comune_id}): {e}", exc_info=True)
            return None
    def update_comune(self, comune_id: int, dati_modificati: Dict[str, Any]) -> bool:
        """
        Aggiorna i dati di un comune esistente in modo transazionale e sicuro.
        """
        if not isinstance(comune_id, int) or comune_id <= 0:
            raise DBDataError(f"ID comune non valido per l'aggiornamento: {comune_id}")
        if not dati_modificati:
            self.logger.info(f"Nessun dato fornito per aggiornare comune ID {comune_id}.")
            return True
        self._valida_intervallo_date(
            dati_modificati.get("data_istituzione"),
            dati_modificati.get("data_soppressione"),
            "Data Istituzione", "Data Soppressione"
        )

        allowed_fields_map = {
            "nome": "nome", "provincia": "provincia", "regione": "regione",
            "codice_catastale": "codice_catastale", "periodo_id": "periodo_id",
            "data_istituzione": "data_istituzione", "data_soppressione": "data_soppressione",
            "note": "note"
        }
        set_clauses = [f"{col_db} = %s" for key_dict, col_db in allowed_fields_map.items() if key_dict in dati_modificati]
        params = [dati_modificati[key] for key in allowed_fields_map if key in dati_modificati]

        if not set_clauses:
            self.logger.info(f"Nessun campo valido fornito per aggiornare comune ID {comune_id}.")
            return True 

        set_clauses.append("data_modifica = CURRENT_TIMESTAMP")
        query = f"UPDATE {self.schema}.comune SET {', '.join(set_clauses)} WHERE id = %s"
        params.append(comune_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        # Se non sono state modificate righe, verifichiamo se il comune esiste.
                        # Se non esiste, solleviamo un errore che causerà un rollback automatico.
                        cur.execute(f"SELECT 1 FROM {self.schema}.comune WHERE id = %s", (comune_id,))
                        if not cur.fetchone():
                            raise DBNotFoundError(f"Comune con ID {comune_id} non trovato per l'aggiornamento.")
                        self.logger.info(f"Nessuna modifica effettiva per comune ID {comune_id} (dati già aggiornati).")
            
            # Il commit viene eseguito automaticamente qui se non ci sono state eccezioni
            self.logger.info(f"Comune ID {comune_id} aggiornato con successo.")
            return True
            
        except (DBNotFoundError, DBDataError, DBUniqueConstraintError, psycopg2.errors.ForeignKeyViolation) as e:
            self.logger.error(f"Errore previsto aggiornando comune ID {comune_id}: {e}", exc_info=True)
            # Rilancia l'eccezione specifica per una gestione mirata nell'UI
            raise e
        except Exception as e:
            self.logger.error(f"Errore imprevisto DB aggiornando comune ID {comune_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare il comune: {e}") from e
    
    def archivia_comune(self, comune_id: int) -> None:
        if not isinstance(comune_id, int) or comune_id <= 0:
            raise DBDataError("ID comune non valido.")
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"CALL {self.schema}.archivia_comune(%s);", (comune_id,))
            self.logger.info(f"Comune ID {comune_id} archiviato.")
        except psycopg2.errors.RaiseException as e:
            raise DBNotFoundError(str(e)) from e
        except Exception as e:
            self.logger.error(f"Errore archiviazione comune {comune_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile archiviare il comune: {e}") from e

    def get_statistiche_comune(self) -> List[Dict[str, Any]]:
        """Recupera dati dalla vista materializzata mv_statistiche_comune in modo sicuro."""
        query = f"SELECT * FROM {self.schema}.mv_statistiche_comune ORDER BY comune;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query)
                    results = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"Recuperate {len(results)} righe da mv_statistiche_comune.")
                    return results
        except Exception as e:
            self.logger.error(f"Errore DB in get_statistiche_comune: {e}", exc_info=True)
            return []

