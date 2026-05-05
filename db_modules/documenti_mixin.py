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
from models.documento import Documento
import shutil # Per trovare i percorsi degli eseguibili
from contextlib import contextmanager
from db_modules.base_manager import (
    DBMError,
    DBUniqueConstraintError,
    DBNotFoundError,
    DBDataError
)
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
class DocumentiMixin:
    def search_historical_documents(self, title: Optional[str] = None, doc_type: Optional[str] = None,
                                    period_id: Optional[int] = None, year_start: Optional[int] = None,
                                    year_end: Optional[int] = None, partita_id: Optional[int] = None) -> List[Documento]:
        """Chiama la funzione SQL ricerca_documenti_storici (SQL aggiornata per join)."""
        try:
            # Funzione SQL aggiornata per join corretti
            query = "SELECT * FROM ricerca_documenti_storici(%s, %s, %s, %s, %s, %s)"
            params = (title, doc_type, period_id, year_start, year_end, partita_id)
            if self.execute_query(query, params): 
                results = self.fetchall()
                return [Documento.from_dict(dict(row)) for row in results]
        except psycopg2.Error as db_err: logger.error(f"Errore DB search_historical_documents: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python search_historical_documents: {e}"); return []
        return []
    

    def link_document_to_partita(self, document_id: int, partita_id: int,
                                 relevance: str = 'correlata', notes: Optional[str] = None) -> bool:
        """Collega un documento storico a una partita."""
        if relevance not in ['primaria', 'secondaria', 'correlata']: logger.error(f"Rilevanza non valida: '{relevance}'"); return False
        query = """
            INSERT INTO documento_partita (documento_id, partita_id, rilevanza, note) VALUES (%s, %s, %s, %s)
            ON CONFLICT (documento_id, partita_id) DO UPDATE SET rilevanza = EXCLUDED.rilevanza, note = EXCLUDED.note
        """
        try:
            if self.execute_query(query, (document_id, partita_id, relevance, notes)): self.commit(); logger.info(f"Link creato/aggiornato Doc {document_id} - Partita {partita_id}."); return True
            return False
        except psycopg2.Error as db_err: logger.error(f"Errore DB link doc-partita: {db_err}"); return False
        except Exception as e: logger.error(f"Errore Python link doc-partita: {e}"); self.rollback(); return False
        
    # All'interno della classe CatastoDBManager, nel file catasto_db_manager.py

    def aggiungi_documento_storico(self, titolo: str, tipo_documento: str, percorso_file: str,
                              descrizione: Optional[str] = None, anno: Optional[int] = None,
                              periodo_id: Optional[int] = None, 
                              metadati_json: Optional[str] = None) -> int:
        """Inserisce un nuovo record nella tabella documento_storico in modo sicuro."""
        query = f"""
            INSERT INTO {self.schema}.documento_storico 
                (titolo, tipo_documento, percorso_file, descrizione, anno, periodo_id, metadati)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id;
        """
        params = (titolo, tipo_documento, percorso_file, descrizione, anno, periodo_id, metadati_json)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    self.logger.info(f"Aggiunta documento: {titolo}")
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if not result:
                        raise DBMError("Creazione del documento fallita, nessun ID restituito.")
                    doc_id = result['id']
            
            self.logger.info(f"Documento storico ID {doc_id} aggiunto con successo.")
            return doc_id
            
        except Exception as e:
            self.logger.error(f"Errore DB aggiungendo documento storico '{titolo}': {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiungere il documento: {e}") from e

    def collega_documento_a_partita(self, documento_id: int, partita_id: int, 
                               rilevanza: str, note: Optional[str] = None) -> bool:
        """Inserisce o aggiorna un record nella tabella di collegamento documento_partita."""
        if rilevanza not in ['primaria', 'secondaria', 'correlata']:
            raise DBDataError(f"Valore di rilevanza non valido: {rilevanza}.")
        
        query = f"""
            INSERT INTO {self.schema}.documento_partita
                (documento_id, partita_id, rilevanza, note)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (documento_id, partita_id) DO UPDATE SET 
                rilevanza = EXCLUDED.rilevanza, 
                note = EXCLUDED.note;
        """
        params = (documento_id, partita_id, rilevanza, note)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Collegamento doc ID {documento_id} a partita ID {partita_id}.")
                    cur.execute(query, params)
            
            self.logger.info("Documento collegato/aggiornato alla partita con successo.")
            return True
        except Exception as e:
            self.logger.error(f"Errore DB collegando doc {documento_id} a partita {partita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile collegare il documento: {e}") from e

    # In catasto_db_manager.py, SOSTITUISCI il metodo get_documenti_per_partita

    def get_documenti_per_partita(self, partita_id: int) -> List[Documento]:
        """Recupera l'elenco dei documenti associati a una partita in modo sicuro."""
        # --- INIZIO CORREZIONE: Aggiunti dp.documento_id e dp.partita_id alla SELECT ---
        query = f"""
            SELECT
                ds.id as documento_id, ds.titolo, ds.tipo_documento, ds.percorso_file, ds.anno,
                dp.rilevanza, dp.note as note_legame, ps.nome as nome_periodo,
                dp.documento_id AS rel_documento_id, 
                dp.partita_id AS rel_partita_id
            FROM {self.schema}.documento_storico ds
            JOIN {self.schema}.documento_partita dp ON ds.id = dp.documento_id
            LEFT JOIN {self.schema}.periodo_storico ps ON ds.periodo_id = ps.id
            WHERE dp.partita_id = %s
            ORDER BY ds.anno DESC, ds.titolo;
        """
        # --- FINE CORREZIONE ---
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (partita_id,))
                    documenti = [Documento.from_dict(dict(row)) for row in cur.fetchall()]
                    self.logger.info(f"Recuperati {len(documenti)} documenti per partita ID {partita_id}.")
                    return documenti
        except Exception as e:
            self.logger.error(f"Errore DB recuperando documenti per partita ID {partita_id}: {e}", exc_info=True)
            return []

    def scollega_documento_da_partita(self, documento_id: int, partita_id: int) -> bool:
        """Rimuove un legame documento-partita in modo transazionale e sicuro."""
        if not (isinstance(documento_id, int) and documento_id > 0):
            raise DBDataError(f"ID documento non valido: {documento_id}")
        if not (isinstance(partita_id, int) and partita_id > 0):
            raise DBDataError(f"ID partita non valido: {partita_id}")

        query = f"DELETE FROM {self.schema}.documento_partita WHERE documento_id = %s AND partita_id = %s;"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (documento_id, partita_id))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Nessun legame trovato tra doc ID {documento_id} e partita ID {partita_id}.")
            
            self.logger.info(f"Legame tra doc {documento_id} e partita {partita_id} rimosso.")
            return True
        except DBNotFoundError as e:
            self.logger.warning(e)
            raise e
        except Exception as e:
            self.logger.error(f"Errore DB scollegando doc {documento_id} da partita {partita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile scollegare il documento: {e}") from e
                
    # ========================================================================
    # NUOVA SEZIONE: LOGICA DI RICERCA FUZZY UNIFICATA (VERSIONE FINALE v3)
    # ========================================================================

