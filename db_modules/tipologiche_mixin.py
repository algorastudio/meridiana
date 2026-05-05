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
class TipologicheMixin:
    def get_tipi_localita(self) -> List[Dict[str, Any]]:
        """Recupera tutte le tipologie di località disponibili."""
        query = "SELECT id, nome, descrizione FROM catasto.tipo_localita ORDER BY nome;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore nel recuperare i tipi di località: {e}", exc_info=True)
            raise DBMError("Impossibile recuperare le tipologie di località.") from e

    def gestisci_tipo_localita(self, tipo_id: Optional[int], nome: str, descrizione: Optional[str] = None) -> int:
        """Crea o aggiorna una tipologia di località."""
        if not nome or not nome.strip():
            raise DBDataError("Il nome della tipologia non può essere vuoto.")
        
        nome = nome.strip()
        descrizione = descrizione.strip() if descrizione else None

        if tipo_id: # Modalità aggiornamento
            query = "UPDATE catasto.tipo_localita SET nome = %s, descrizione = %s WHERE id = %s RETURNING id;"
            params = (nome, descrizione, tipo_id)
        else: # Modalità inserimento
            query = "INSERT INTO catasto.tipo_localita (nome, descrizione) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING RETURNING id;"
            params = (nome, descrizione)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    # Se ON CONFLICT non ha fatto nulla, l'ID non viene restituito. Potremmo voler gestire questo caso.
                    raise DBUniqueConstraintError(f"Una tipologia con nome '{nome}' esiste già.")
        except psycopg2.errors.UniqueViolation:
            raise DBUniqueConstraintError(f"Una tipologia con nome '{nome}' esiste già.") from None
        except Exception as e:
            self.logger.error(f"Errore in gestisci_tipo_localita: {e}", exc_info=True)
            raise DBMError("Operazione sulla tipologia di località fallita.") from e

    # Potresti voler aggiungere anche un metodo per l'eliminazione
    def elimina_tipo_localita(self, tipo_id: int) -> bool:
        """Elimina una tipologia di località, solo se non è utilizzata."""
        query = "DELETE FROM catasto.tipo_localita WHERE id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (tipo_id,))
                    return cur.rowcount > 0
        except psycopg2.errors.ForeignKeyViolation:
            raise DBMError("Impossibile eliminare: questa tipologia è utilizzata da una o più località.") from None
        except Exception as e:
            self.logger.error(f"Errore in elimina_tipo_localita: {e}", exc_info=True)
            raise DBMError("Eliminazione della tipologia fallita.") from e

    def get_titoli_possesso(self) -> List[Dict[str, Any]]:
        """Recupera tutti i titoli di possesso disponibili."""
        query = f"SELECT id, nome, descrizione FROM {self.schema}.titolo_possesso ORDER BY nome;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore nel recuperare i titoli di possesso: {e}", exc_info=True)
            raise DBMError("Impossibile recuperare i titoli di possesso.") from e

    def gestisci_titolo_possesso(self, titolo_id: Optional[int], nome: str, descrizione: Optional[str] = None) -> int:
        """Crea o aggiorna un titolo di possesso."""
        if not nome or not nome.strip():
            raise DBDataError("Il nome del titolo di possesso non può essere vuoto.")
        nome = nome.strip()
        descrizione = descrizione.strip() if descrizione else None
        if titolo_id:
            query = f"UPDATE {self.schema}.titolo_possesso SET nome = %s, descrizione = %s WHERE id = %s RETURNING id;"
            params = (nome, descrizione, titolo_id)
        else:
            query = f"INSERT INTO {self.schema}.titolo_possesso (nome, descrizione) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING RETURNING id;"
            params = (nome, descrizione)
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    raise DBUniqueConstraintError(f"Un titolo con nome '{nome}' esiste già.")
        except psycopg2.errors.UniqueViolation:
            raise DBUniqueConstraintError(f"Un titolo con nome '{nome}' esiste già.") from None
        except (DBDataError, DBUniqueConstraintError):
            raise
        except Exception as e:
            self.logger.error(f"Errore in gestisci_titolo_possesso: {e}", exc_info=True)
            raise DBMError("Operazione sul titolo di possesso fallita.") from e

    def elimina_titolo_possesso(self, titolo_id: int) -> bool:
        """Elimina un titolo di possesso."""
        query = f"DELETE FROM {self.schema}.titolo_possesso WHERE id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (titolo_id,))
                    return cur.rowcount > 0
        except Exception as e:
            self.logger.error(f"Errore in elimina_titolo_possesso: {e}", exc_info=True)
            raise DBMError("Eliminazione del titolo di possesso fallita.") from e

    # In catasto_db_manager.py, SOSTITUISCI il metodo get_immobili_by_comune

    def get_historical_periods(self) -> List[Dict[str, Any]]:
        """
        Recupera i periodi storici definiti dalla tabella 'periodo_storico' in modo sicuro.
        """
        query = f"SELECT id, nome, anno_inizio, anno_fine, descrizione FROM {self.schema}.periodo_storico ORDER BY anno_inizio;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query)
                    results = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"Recuperati {len(results)} periodi storici.")
                    return results
        except Exception as e:
            self.logger.error(f"Errore DB in get_historical_periods: {e}", exc_info=True)
            return []
    

    def update_periodo_storico(self, periodo_id: int, dati_modificati: Dict[str, Any]) -> bool:
        """Aggiorna i dati di un periodo storico esistente in modo transazionale e sicuro."""
        if not isinstance(periodo_id, int) or periodo_id <= 0:
            raise DBDataError(f"ID periodo storico non valido: {periodo_id}")
        if not dati_modificati:
            raise DBDataError("Nessun dato fornito per l'aggiornamento.")

        set_clauses, params = [], []
        campi_permessi = {"nome": "nome", "anno_inizio": "anno_inizio", "anno_fine": "anno_fine", "descrizione": "descrizione"}

        for key, col in campi_permessi.items():
            if key in dati_modificati:
                valore = dati_modificati[key]
                if key == "nome" and not (valore and str(valore).strip()):
                    raise DBDataError("Il nome del periodo storico non può essere vuoto.")
                
                set_clauses.append(f"{col} = %s")
                params.append(valore if not isinstance(valore, str) else valore.strip())

        if not set_clauses:
            self.logger.info(f"Nessun campo aggiornabile fornito per periodo ID {periodo_id}.")
            return True

        # Se la sua tabella 'periodo_storico' avesse una colonna 'data_modifica', andrebbe aggiunta qui:
        # set_clauses.append("data_modifica = CURRENT_TIMESTAMP")
        
        query = f"UPDATE {self.schema}.periodo_storico SET {', '.join(set_clauses)} WHERE id = %s;"
        params.append(periodo_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Periodo storico con ID {periodo_id} non trovato o dati identici.")
            
            self.logger.info(f"Periodo storico ID {periodo_id} aggiornato con successo.")
            return True

        except (DBNotFoundError, DBDataError, DBUniqueConstraintError, psycopg2.errors.CheckViolation) as e:
            self.logger.error(f"Errore previsto aggiornando periodo storico {periodo_id}: {e}", exc_info=True)
            raise e  # Rilancia l'eccezione specifica
        except Exception as e:
            self.logger.error(f"Errore imprevisto DB aggiornando periodo storico {periodo_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare il periodo storico: {e}") from e

    def aggiungi_periodo_storico(self, nome: str, anno_inizio: int, anno_fine: Optional[int], descrizione: Optional[str]) -> int:
        """Crea un nuovo periodo storico nel database."""
        if not nome or not nome.strip():
            raise DBDataError("Il nome del periodo non può essere vuoto.")
        if anno_fine is not None and anno_fine < anno_inizio:
            raise DBDataError("L'anno di fine non può essere precedente a quello di inizio.")

        query = """
            INSERT INTO catasto.periodo_storico (nome, anno_inizio, anno_fine, descrizione)
            VALUES (%s, %s, %s, %s) RETURNING id;
        """
        params = (nome.strip(), anno_inizio, anno_fine, descrizione)

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    raise DBMError("Creazione del periodo storico fallita.")
        except psycopg2.errors.UniqueViolation:
            raise DBUniqueConstraintError(f"Un periodo storico con nome '{nome}' esiste già.") from None
        except Exception as e:
            self.logger.error(f"Errore DB in aggiungi_periodo_storico: {e}", exc_info=True)
            raise DBMError("Impossibile creare il periodo storico.") from e

    def elimina_periodo_storico(self, periodo_id: int) -> bool:
        """Elimina un periodo storico, solo se non è utilizzato."""
        query = "DELETE FROM catasto.periodo_storico WHERE id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (periodo_id,))
                    if cur.rowcount == 0:
                        raise DBNotFoundError(f"Nessun periodo storico trovato con ID {periodo_id}.")
                    return True
        except psycopg2.errors.ForeignKeyViolation:
            raise DBMError("Impossibile eliminare: questo periodo è utilizzato da uno o più comuni.") from None
        except Exception as e:
            self.logger.error(f"Errore DB in elimina_periodo_storico: {e}", exc_info=True)
            raise DBMError("Eliminazione del periodo storico fallita.") from e

    def get_periodo_storico_details(self, periodo_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di un singolo periodo storico in modo sicuro."""
        if not isinstance(periodo_id, int) or periodo_id <= 0:
            self.logger.error(f"ID periodo storico non valido: {periodo_id}")
            return None

        query = f"SELECT * FROM {self.schema}.periodo_storico WHERE id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, (periodo_id,))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Errore DB in get_periodo_storico_details (ID: {periodo_id}): {e}", exc_info=True)
            return None

    # All'interno della classe CatastoDBManager in catasto_db_manager.py

