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
from models.immobile import Immobile
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

class ImmobiliMixin:
    def get_immobili_by_comune(self, comune_id: int) -> List[Immobile]:
        """Recupera un elenco di tutti gli immobili presenti in un dato comune."""
        if not isinstance(comune_id, int) or comune_id <= 0:
            return []

        # --- INIZIO CORREZIONE: Aggiunto l.id AS localita_id alla query ---
        query = f"""
            SELECT 
                i.id, 
                i.natura, 
                l.nome AS localita_nome,
                tl.nome as tipo_localita,
                l.id as localita_id
            FROM {self.schema}.immobile i
            JOIN {self.schema}.partita p ON i.partita_id = p.id
            JOIN {self.schema}.localita l ON i.localita_id = l.id
            LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id
            WHERE p.comune_id = %s
            ORDER BY l.nome, i.natura;
        """
        # --- FINE CORREZIONE ---
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (comune_id,))
                    return [Immobile.from_dict(dict(row)) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore DB in get_immobili_by_comune per comune ID {comune_id}: {e}", exc_info=True)
            return []
    
    def get_elenco_immobili_per_esportazione(self, comune_id: Optional[int] = None) -> List[Immobile]:
        """Recupera un elenco completo di immobili per l'esportazione."""
        query = f"""
            SELECT 
                i.id AS id_immobile, i.natura, i.classificazione, i.consistenza,
                i.numero_piani, i.numero_vani, l.nome AS localita_nome,
                tl.nome AS localita_tipo, p.numero_partita,
                p.suffisso_partita, c.nome AS comune_nome
            FROM {self.schema}.immobile i
            JOIN {self.schema}.partita p ON i.partita_id = p.id
            JOIN {self.schema}.comune c ON p.comune_id = c.id
            JOIN {self.schema}.localita l ON i.localita_id = l.id
            LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id
        """
        params = []
        if comune_id:
            query += " WHERE p.comune_id = %s"
            params.append(comune_id)
        query += " ORDER BY c.nome, p.numero_partita, l.nome, i.natura;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, params)
                    return [Immobile.from_dict(dict(row)) for row in cur.fetchall()]
        except Exception as e:
            raise DBMError(f"Impossibile recuperare l'elenco degli immobili: {e}") from e

    def update_immobile(self, immobile_id: int, **kwargs) -> bool:
        """Chiama la procedura SQL aggiorna_immobile."""
        params = {'p_id': immobile_id, 'p_natura': kwargs.get('natura'), 'p_numero_piani': kwargs.get('numero_piani'),
                  'p_numero_vani': kwargs.get('numero_vani'), 'p_consistenza': kwargs.get('consistenza'),
                  'p_classificazione': kwargs.get('classificazione'), 'p_localita_id': kwargs.get('localita_id')}
        call_proc = "CALL aggiorna_immobile(%(p_id)s, %(p_natura)s, %(p_numero_piani)s, %(p_numero_vani)s, %(p_consistenza)s, %(p_classificazione)s, %(p_localita_id)s)"
        try:
            if self.execute_query(call_proc, params): self.commit(); logger.info(f"Immobile ID {immobile_id} aggiornato."); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB aggiornamento immobile ID {immobile_id}: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python aggiornamento immobile ID {immobile_id}: {e}"); self.rollback(); return False

    def delete_immobile(self, immobile_id):
        """
        Elimina un immobile dal database utilizzando una procedura memorizzata
        e gestendo la transazione in modo sicuro con il connection pool.
        """
        call_proc = "SELECT public.delete_immobile_by_id(%s);"
        conn = None  # Inizializza la variabile della connessione
        try:
            # 1. Ottieni una connessione dal pool
            conn = self.pool.getconn()
            
            # 2. Utilizza la connessione con un blocco 'with' per il cursore
            with conn.cursor() as cur:
                # 3. Esegui la query/procedura sul cursore
                cur.execute(call_proc, (immobile_id,))
                
                # 4. Esegui il commit sulla connessione
                conn.commit()
                
                logger.info(f"Immobile ID {immobile_id} eliminato con successo.")
                return True
                
        except Exception as e:
            # Se si verifica un errore, esegui il rollback
            if conn:
                conn.rollback()
            logger.error(f"Errore durante l'eliminazione dell'immobile ID {immobile_id}: {e}")
            return False
            
        finally:
            # 5. Rilascia SEMPRE la connessione al pool
            if conn:
                self.pool.putconn(conn)
    def search_immobili(self, partita_id: Optional[int] = None, comune_id: Optional[int] = None, # Usa comune_id
                        localita_id: Optional[int] = None, natura: Optional[str] = None,
                        classificazione: Optional[str] = None) -> List[Immobile]:
        """Chiama la funzione SQL cerca_immobili (MODIFICATA per comune_id)."""
        try:
            # Funzione SQL aggiornata per comune_id
            query = "SELECT * FROM cerca_immobili(%s, %s, %s, %s, %s)"
            params = (partita_id, comune_id, localita_id, natura, classificazione) # Passa ID
            if self.execute_query(query, params): 
                return [Immobile.from_dict(dict(row)) for row in self.fetchall()]
        except psycopg2.Error as db_err: logger.error(f"Errore DB in search_immobili: {db_err}")
        except Exception as e: logger.error(f"Errore Python in search_immobili: {e}")
        return []

    def get_immobile_details(self, immobile_id: int) -> Optional[Immobile]:
        """Recupera i dettagli completi di un singolo immobile in modo sicuro."""
        if not isinstance(immobile_id, int) or immobile_id <= 0:
            self.logger.error(f"get_immobile_details: immobile_id non valido: {immobile_id}")
            return None

        query = f"""
            SELECT
                i.id, i.partita_id, i.localita_id, i.natura, i.classificazione, i.consistenza,
                i.numero_piani, i.numero_vani,
                p.numero_partita, p.suffisso_partita,
                c.nome AS comune_nome,
                l.nome AS localita_nome, tl.nome AS localita_tipo
            FROM {self.schema}.immobile i
            JOIN {self.schema}.partita p ON i.partita_id = p.id
            JOIN {self.schema}.comune c ON p.comune_id = c.id
            JOIN {self.schema}.localita l ON i.localita_id = l.id
            LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id
            WHERE i.id = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, (immobile_id,))
                    immobile_data = cur.fetchone()
                    if immobile_data:
                        self.logger.info(f"Dettagli recuperati per immobile ID {immobile_id}.")
                        return Immobile.from_dict(dict(immobile_data))
                    else:
                        self.logger.warning(f"Nessun immobile trovato con ID {immobile_id}.")
                        return None
        except Exception as e:
            self.logger.error(f"Errore DB in get_immobile_details per ID {immobile_id}: {e}", exc_info=True)
            return None
    def get_immobili_per_tipologia(self, comune_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Recupera dati dalla vista materializzata mv_immobili_per_tipologia in modo sicuro."""
        params = []
        
        if comune_id is not None:
            query = f"""
                SELECT m.* FROM {self.schema}.mv_immobili_per_tipologia m
                JOIN {self.schema}.comune c ON m.comune_nome = c.nome
                WHERE c.id = %s
                ORDER BY m.comune_nome, m.classificazione LIMIT %s;
            """
            params = [comune_id, limit]
        else:
            query = f"SELECT * FROM {self.schema}.mv_immobili_per_tipologia ORDER BY comune_nome, classificazione LIMIT %s;"
            params = [limit]
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, tuple(params))
                    results = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"Recuperate {len(results)} righe da mv_immobili_per_tipologia.")
                    return results
        except Exception as e:
            self.logger.error(f"Errore DB in get_immobili_per_tipologia: {e}", exc_info=True)
            return []

    def transfer_immobile(self, immobile_id: int, nuova_partita_id: int, registra_variazione: bool = False) -> bool:
        """
        Chiama la procedura SQL per trasferire un immobile a una nuova partita in modo transazionale.
        """
        call_proc_str = f"CALL {self.schema}.trasferisci_immobile(%s, %s, %s);"
        params = (immobile_id, nuova_partita_id, registra_variazione)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Trasferimento immobile ID {immobile_id} a partita ID {nuova_partita_id}...")
                    cur.execute(call_proc_str, params)
            
            # Il commit è automatico qui se la procedura non ha sollevato eccezioni
            self.logger.info(f"Immobile ID {immobile_id} trasferito con successo.")
            return True
            
        except psycopg2.Error as db_err:
            # Il rollback è automatico
            pgerror_msg = getattr(db_err, 'pgerror', str(db_err))
            self.logger.error(f"Errore DB durante trasferimento immobile ID {immobile_id}: {pgerror_msg}", exc_info=True)
            raise DBMError(f"Errore database durante il trasferimento: {pgerror_msg}") from db_err
        except Exception as e:
            self.logger.error(f"Errore imprevisto durante trasferimento immobile ID {immobile_id}: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema imprevisto durante il trasferimento: {e}") from e
    def ricerca_avanzata_immobili_gui(self, comune_id: Optional[int] = None, localita_id: Optional[int] = None,
                                      natura_search: Optional[str] = None, classificazione_search: Optional[str] = None,
                                      consistenza_search: Optional[str] = None, # Ricerca testuale per consistenza
                                      piani_min: Optional[int] = None, piani_max: Optional[int] = None,
                                      vani_min: Optional[int] = None, vani_max: Optional[int] = None,
                                      nome_possessore_search: Optional[str] = None,
                                      data_inizio_possesso_search: Optional[date] = None, # Previsto per il futuro
                                      data_fine_possesso_search: Optional[date] = None    # Previsto per il futuro
                                     ) -> List[Immobile]:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # La stringa della query ora corrisponde ai 12 parametri della funzione SQL estesa
                    # I cast ::TIPODATO sono una buona pratica se i default nella funzione SQL non sono espliciti con ::TIPODATO
                    # o se si vuole essere estremamente sicuri.
                    # Se la funzione SQL ha DEFAULT NULL e tipi chiari, i cast qui potrebbero non essere strettamente necessari
                    # ma non fanno male.
                    query = f"""
                        SELECT * FROM {self.schema}.ricerca_avanzata_immobili(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """
                    # Nota: i parametri devono essere nell'ordine esatto definito dalla funzione SQL
                    params = (
                        comune_id, localita_id, natura_search, classificazione_search, consistenza_search,
                        piani_min, piani_max, vani_min, vani_max, nome_possessore_search,
                        data_inizio_possesso_search, data_fine_possesso_search
                    )

                    self.logger.debug(f"Chiamata a {self.schema}.ricerca_avanzata_immobili con parametri POSIZIONALI: {params}")
                    cur.execute(query, params)
                    results = [Immobile.from_dict(dict(row)) for row in cur.fetchall()]
                    self.logger.info(f"Ricerca avanzata immobili ha restituito {len(results)} risultati.")
                    return results
        except psycopg2.Error as e:
            self.logger.error(f"Errore DB specifico durante l'esecuzione di ricerca_avanzata_immobili_gui: {e}", exc_info=True)
            # Potresti voler sollevare un'eccezione personalizzata o gestire l'errore qui
            return []
        except Exception as e:
            self.logger.error(f"Errore generico durante ricerca_avanzata_immobili_gui: {e}", exc_info=True)
            return []
