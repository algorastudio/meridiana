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
from models.localita import Localita
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

class LocalitaMixin:
    def get_elenco_localita_per_esportazione(self, comune_id: Optional[int] = None) -> List[Localita]:
        """Recupera un elenco completo di località per l'esportazione."""
        query = f"""
            SELECT l.id, l.nome, tl.nome AS tipo, c.nome AS comune_nome
            FROM {self.schema}.localita l
            JOIN {self.schema}.comune c ON l.comune_id = c.id
            LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id
        """
        params = []
        if comune_id:
            query += " WHERE l.comune_id = %s"
            params.append(comune_id)
        query += " ORDER BY c.nome, l.nome;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, params)
                    return [Localita.from_dict(dict(row)) for row in cur.fetchall()]
        except Exception as e:
            raise DBMError(f"Impossibile recuperare l'elenco delle località: {e}") from e
    
    def get_localita_by_comune(self, comune_id: int, filter_text: Optional[str] = None) -> List[Localita]:
        """Recupera località per comune_id, unendo il nome del tipo dalla nuova tabella."""
        if not isinstance(comune_id, int) or comune_id <= 0:
            raise DBDataError("ID comune non valido.")

        # --- INIZIO CORREZIONE: Query aggiornata con JOIN ---
        query_base = f"""
            SELECT 
                loc.id, 
                loc.nome,
                tl.nome AS tipo
            FROM {self.schema}.localita loc
            LEFT JOIN {self.schema}.tipo_localita tl ON loc.tipo_id = tl.id
            WHERE loc.comune_id = %s AND loc.archiviato = FALSE
        """

        params: List[Union[int, str]] = [comune_id]

        if filter_text:
            query_base += " AND loc.nome ILIKE %s"
            params.append(f"%{filter_text}%")

        query = query_base + " ORDER BY tl.nome, loc.nome;"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, tuple(params))
                    results = [Localita.from_dict(dict(row)) for row in cur.fetchall()]
                    self.logger.info(f"Recuperate {len(results)} località per comune ID {comune_id} (filtro: '{filter_text}').")
                    return results
        except Exception as e:
            self.logger.error(f"Errore DB in get_localita_by_comune: {e}", exc_info=True)
            return [] # Restituisce lista vuota in caso di errore
    def create_localita(self, comune_id: int, nome: str, tipo_id: int) -> int:
        """
        Inserisce una nuova località usando tipo_id (FK) e gestisce i conflitti.
        Il civico, se presente, va già incluso nel nome (es. "Via Roma 11A").
        """
        if not all([isinstance(comune_id, int), comune_id > 0, isinstance(nome, str), nome.strip(), isinstance(tipo_id, int), tipo_id > 0]):
            raise DBDataError("Parametri per l'inserimento della località non validi.")

        query_insert = f"INSERT INTO {self.schema}.localita (comune_id, nome, tipo_id) VALUES (%s, %s, %s) ON CONFLICT (comune_id, nome) DO NOTHING RETURNING id;"
        query_select = f"SELECT id FROM {self.schema}.localita WHERE comune_id = %s AND nome = %s;"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query_insert, (comune_id, nome.strip(), tipo_id))
                    insert_result = cur.fetchone()

                    if insert_result and insert_result['id']:
                        localita_id = insert_result['id']
                        self.logger.info(f"Località '{nome}' inserita con successo. ID: {localita_id}.")
                    else:
                        cur.execute(query_select, (comune_id, nome.strip()))
                        select_result = cur.fetchone()
                        if select_result and select_result['id']:
                            localita_id = select_result['id']
                            self.logger.info(f"Località '{nome}' già esistente trovata. ID: {localita_id}.")
                        else:
                            raise DBMError(f"Logica inconsistente: impossibile inserire o trovare la località '{nome}'.")
            return localita_id
        except Exception as e:
            self.logger.error(f"Errore in create_localita per '{nome}': {e}", exc_info=True)
            raise DBMError(f"Errore database durante l'operazione sulla località: {e}") from e

    def get_localita_details(self, localita_id: int) -> Optional[Localita]:
        """Recupera i dettagli di una singola località, incluso il nome del comune."""
        if not isinstance(localita_id, int) or localita_id <= 0: return None

        query = f"""
            SELECT loc.id, loc.nome, tl.nome AS tipo, loc.tipo_id, loc.comune_id, com.nome AS comune_nome
            FROM {self.schema}.localita loc
            LEFT JOIN {self.schema}.tipo_localita tl ON loc.tipo_id = tl.id
            JOIN {self.schema}.comune com ON loc.comune_id = com.id
            WHERE loc.id = %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, (localita_id,))
                    result = cur.fetchone()
                    return Localita.from_dict(dict(result)) if result else None
        except Exception as e:
            self.logger.error(f"Errore DB in get_localita_details per ID {localita_id}: {e}", exc_info=True)
            return None
    def update_localita(self, localita_id: int, dati_modificati: Dict[str, Any]) -> bool:
        """Aggiorna i dati di una località esistente, usando tipo_id."""
        if not (isinstance(localita_id, int) and localita_id > 0): raise DBDataError("ID località non valido.")
        if not isinstance(dati_modificati, dict) or not dati_modificati: raise DBDataError("Dati per aggiornamento non validi.")

        set_clauses = []
        params = []

        if "nome" in dati_modificati and dati_modificati["nome"] and dati_modificati["nome"].strip():
            set_clauses.append("nome = %s")
            params.append(dati_modificati["nome"].strip())

        # --- MODIFICA CHIAVE QUI ---
        if "tipo_id" in dati_modificati and dati_modificati["tipo_id"] is not None:
            set_clauses.append("tipo_id = %s")
            params.append(dati_modificati["tipo_id"])
        # --- FINE MODIFICA ---

        if not set_clauses:
            self.logger.info(f"Nessun campo valido fornito per aggiornare località ID {localita_id}.")
            return True

        set_clauses.append("data_modifica = CURRENT_TIMESTAMP")
        query = f"UPDATE {self.schema}.localita SET {', '.join(set_clauses)} WHERE id = %s;"
        params.append(localita_id)

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Nessuna località trovata con ID {localita_id} da aggiornare.")
            self.logger.info(f"Località ID {localita_id} aggiornata con successo.")
            return True
        except Exception as e:
            self.logger.error(f"Errore DB aggiornando località ID {localita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare la località: {e}") from e


    
    def archivia_localita(self, localita_id: int) -> None:
        if not isinstance(localita_id, int) or localita_id <= 0:
            raise DBDataError("ID località non valido.")
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"CALL {self.schema}.archivia_localita(%s);", (localita_id,))
            self.logger.info(f"Località ID {localita_id} archiviata.")
        except psycopg2.errors.RaiseException as e:
            raise DBNotFoundError(str(e)) from e
        except Exception as e:
            self.logger.error(f"Errore archiviazione località {localita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile archiviare la località: {e}") from e

