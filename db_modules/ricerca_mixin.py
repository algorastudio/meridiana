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

class RicercaMixin:
    def refresh_materialized_views(self, show_success_message: bool = False) -> bool:
        """Aggiorna tutte le viste materializzate del database in modo sicuro."""
        if not self.pool:
            self.logger.error("Pool di connessioni non inizializzato per refresh viste materializzate.")
            QMessageBox.critical(None, "Errore", "Pool di connessioni non attivo. Impossibile aggiornare le viste.")
            return False
        
        progress_dialog = QProgressDialog("Aggiornamento viste materializzate in corso...", "Annulla", 0, 0, None)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()

        # --- CORREZIONE QUI: Rimosso CONCURRENTLY per compatibilità universale ---
        query = f"""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN
                    SELECT schemaname, matviewname
                    FROM pg_matviews
                    WHERE schemaname = '{self.schema}'
                LOOP
                    EXECUTE 'REFRESH MATERIALIZED VIEW ' || quote_ident(r.schemaname) 
                    || '.' || quote_ident(r.matviewname);
                END LOOP;
            END $$;
        """
        # --- FINE CORREZIONE ---
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info("Esecuzione dello script di aggiornamento per le viste materializzate...")
                    cur.execute(query)
                    # --- AGGIUNGERE QUESTA RIGA ALLA FINE DEL BLOCCO 'try' ---
                    self.update_last_mv_refresh_timestamp() # Aggiorna il timestamp dopo il successo
                    # --- FINE AGGIUNTA ---
                
                    progress_dialog.close()
            if show_success_message:
                QMessageBox.information(None, "Successo", "Tutte le viste materializzate sono state aggiornate con successo.")
            
            self.logger.info("Viste materializzate aggiornate con successo.")
            return True
            
        except psycopg2.Error as db_err:
            progress_dialog.close()
            error_message = f"Errore DB durante l'aggiornamento delle viste: {db_err}"
            self.logger.error(error_message, exc_info=True)
            QMessageBox.critical(None, "Errore Aggiornamento Viste", error_message)
            return False
        except Exception as e:
            progress_dialog.close()
            error_message = f"Errore critico durante l'aggiornamento delle viste: {e}"
            self.logger.error(error_message, exc_info=True)
            QMessageBox.critical(None, "Errore Aggiornamento Viste", error_message)
            return False
    
    def get_historical_name(self, entity_type: str, entity_id: int, year: Optional[int] = None) -> Optional[Dict]:
        """Chiama la funzione SQL get_nome_storico in modo sicuro."""
        if year is None: year = datetime.now().year
        query = f"SELECT * FROM {self.schema}.get_nome_storico(%s, %s, %s)"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (entity_type, entity_id, year))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Errore DB in get_historical_name ({entity_type} ID {entity_id}): {e}", exc_info=True)
            return None
    def register_historical_name(self, entity_type: str, entity_id: int, name: str,
                             period_id: int, year_start: int, year_end: Optional[int] = None,
                             notes: Optional[str] = None) -> bool:
        """Chiama la procedura SQL registra_nome_storico in modo sicuro."""
        call_proc = f"CALL {self.schema}.registra_nome_storico(%s, %s, %s, %s, %s, %s, %s)"
        params = (entity_type, entity_id, name, period_id, year_start, year_end, notes)
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(call_proc, params)
            self.logger.info(f"Registrato nome storico '{name}' per {entity_type} ID {entity_id}.")
            return True
        except Exception as e:
            self.logger.error(f"Errore DB in register_historical_name: {e}", exc_info=True)
            raise DBMError(f"Impossibile registrare il nome storico: {e}") from e


    def search_all_entities_fuzzy(self, query_text: str,
                                search_possessori: bool = True,
                                search_localita: bool = True,
                                search_immobili: bool = True,
                                search_variazioni: bool = True,  # AGGIUNTO
                                search_contratti: bool = True,   # AGGIUNTO
                                search_partite: bool = True,     # AGGIUNTO
                                max_results_per_type: int = 50,
                                similarity_threshold: float = 0.3) -> Dict[str, List[Dict]]:
        """
        Metodo orchestratore per la ricerca fuzzy che riusa una singola connessione.
        """
        self.logger.info(f"Avvio ricerca fuzzy ottimizzata per: '{query_text}' con soglia {similarity_threshold}")
        
        all_results = {
            "possessore": [], "localita": [], "immobile": [],
            "variazione": [], "contratto": [], "partita": [] # AGGIUNTO
        }

        try:
            with self._get_connection() as conn:
                if search_possessori:
                    all_results["possessore"] = self._search_possessori_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                if search_localita:
                    all_results["localita"] = self._search_localita_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                if search_immobili:
                    all_results["immobile"] = self._search_immobili_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                # --- AGGIUNGERE QUESTE CHIAMATE ---
                if search_variazioni:
                    all_results["variazione"] = self._search_variazioni_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                if search_contratti:
                    all_results["contratto"] = self._search_contratti_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                if search_partite:
                    all_results["partita"] = self._search_partite_fuzzy_internal(conn, query_text, similarity_threshold, max_results_per_type)
                # --- FINE AGGIUNTE ---
            
            total_found = sum(len(v) for v in all_results.values())
            self.logger.info(f"Ricerca fuzzy completata. Trovati {total_found} risultati totali.")
            return all_results

        except psycopg2.pool.PoolError as pe:
            self.logger.error(f"Pool di connessioni esaurito durante la ricerca fuzzy: {pe}")
            return {}
        except Exception as e:
            self.logger.error(f"Errore critico durante search_all_entities_fuzzy: {e}", exc_info=True)
            return {}

    # --- METODI DI RICERCA INTERNI (con correzione finale a DictCursor e partita_id) ---

    def _search_variazioni_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per le variazioni (su tipo e nominativo di riferimento)."""
        # --- CORREZIONE: Sostituisce v.note (inesistente) con v.nominativo_riferimento (esistente) ---
        sql = f"""
            SELECT
                v.id AS entity_id,
                'Variazione ' || v.tipo || ' del ' || TO_CHAR(v.data_variazione, 'DD/MM/YYYY') AS display_text,
                'Rif: ' || COALESCE(v.nominativo_riferimento, 'N/D') || ' | Partita Origine: ' || po.numero_partita AS detail_text,
                greatest(
                    similarity(v.tipo, %s),
                    similarity(v.nominativo_riferimento, %s)
                ) AS similarity_score,
                CASE
                    WHEN similarity(v.tipo, %s) > similarity(v.nominativo_riferimento, %s) THEN 'tipo'
                    ELSE 'nominativo_riferimento'
                END AS search_field,
                v.tipo,
                v.data_variazione,
                v.nominativo_riferimento AS descrizione
            FROM {self.schema}.variazione v
            LEFT JOIN {self.schema}.partita po ON v.partita_origine_id = po.id
            WHERE greatest(
                    similarity(v.tipo, %s),
                    similarity(v.nominativo_riferimento, %s)
                ) >= %s
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, query, query, query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy variazioni: {e}", exc_info=True)
            return []
    def _search_localita_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per le località, usando la nuova tabella tipo_localita."""
        # --- INIZIO CORREZIONE ---
        # La query ora fa un JOIN con tipo_localita per ottenere il nome del tipo
        sql = f"""
            SELECT
                l.id AS entity_id,
                l.nome AS display_text,
                'Tipo: ' || COALESCE(tl.nome, 'N/D') || ' | Comune: ' || c.nome AS detail_text,
                similarity(l.nome, %s) AS similarity_score,
                'nome' AS search_field,
                l.nome,
                tl.nome AS tipo,
                c.nome as comune_nome,
                COALESCE(im.num_immobili, 0) as num_immobili
            FROM {self.schema}.localita l
            JOIN {self.schema}.comune c ON l.comune_id = c.id
            LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id -- <-- JOIN con la nuova tabella
            LEFT JOIN (
                SELECT localita_id, COUNT(*) as num_immobili
                FROM {self.schema}.immobile
                GROUP BY localita_id
            ) im ON l.id = im.localita_id
            WHERE similarity(l.nome, %s) >= %s
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        # --- FINE CORREZIONE ---
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy località: {e}", exc_info=True)
            return []

    def _search_possessori_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per i possessori, restituendo tutti i campi necessari."""
        sql = f"""
            SELECT
                p.id AS entity_id,
                p.nome_completo AS display_text,
                'Comune: ' || c.nome || ' | Partite: ' || COALESCE(ps.num_partite, 0) AS detail_text,
                greatest(similarity(p.nome_completo, %s), similarity(p.cognome_nome, %s)) AS similarity_score,
                CASE
                    WHEN similarity(p.nome_completo, %s) > similarity(p.cognome_nome, %s) THEN 'nome_completo'
                    ELSE 'cognome_nome'
                END AS search_field,
                p.nome_completo,
                c.nome as comune_nome,
                COALESCE(ps.num_partite, 0) as num_partite
            FROM {self.schema}.possessore p
            JOIN {self.schema}.comune c ON p.comune_id = c.id
            LEFT JOIN (
                SELECT possessore_id, COUNT(*) as num_partite
                FROM {self.schema}.partita_possessore
                GROUP BY possessore_id
            ) ps ON p.id = ps.possessore_id
            WHERE greatest(similarity(p.nome_completo, %s), similarity(p.cognome_nome, %s)) >= %s
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, query, query, query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy possessori: {e}", exc_info=True)
            return []
    def _search_immobili_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per gli immobili, includendo il suffisso della partita."""
        # --- MODIFICA: Aggiunto pa.suffisso_partita e aggiornato detail_text ---
        sql = f"""
            SELECT
                i.id AS entity_id,
                i.natura || ' - ' || i.classificazione AS display_text,
                'Partita N: ' || pa.numero_partita || COALESCE(' (' || pa.suffisso_partita || ')', '') || ' | Comune: ' || c.nome AS detail_text,
                greatest(similarity(i.natura, %s), similarity(i.classificazione, %s)) AS similarity_score,
                CASE
                    WHEN similarity(i.natura, %s) > similarity(i.classificazione, %s) THEN 'natura'
                    ELSE 'classificazione'
                END AS search_field,
                i.natura,
                i.classificazione,
                pa.numero_partita,
                pa.suffisso_partita, -- AGGIUNTO
                c.nome as comune_nome
            FROM {self.schema}.immobile i
            JOIN {self.schema}.partita pa ON i.partita_id = pa.id
            JOIN {self.schema}.comune c ON pa.comune_id = c.id
            WHERE greatest(similarity(i.natura, %s), similarity(i.classificazione, %s)) >= %s
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, query, query, query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy immobili: {e}", exc_info=True)
            return []
        
    def _search_contratti_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per i contratti (su tipo, notaio, note)."""
        sql = f"""
            SELECT
                con.id AS entity_id,
                'Contratto ' || con.tipo || ' del ' || TO_CHAR(con.data_contratto, 'DD/MM/YYYY') AS display_text,
                'Notaio: ' || COALESCE(con.notaio, 'N/D') || ' | Partita: ' || p.numero_partita AS detail_text,
                greatest(similarity(con.tipo, %s), similarity(con.notaio, %s), similarity(con.note, %s)) AS similarity_score,
                'contratto' AS search_field, -- Semplificato per ora
                con.tipo,
                con.data_contratto,
                p.numero_partita
            FROM {self.schema}.contratto con
            JOIN {self.schema}.variazione v ON con.variazione_id = v.id
            JOIN {self.schema}.partita p ON v.partita_origine_id = p.id
            WHERE greatest(similarity(con.tipo, %s), similarity(con.notaio, %s), similarity(con.note, %s)) >= %s
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, query, query, query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy contratti: {e}", exc_info=True)
            return []

    # In catasto_db_manager.py, SOSTITUISCI il metodo _search_partite_fuzzy_internal

    def _search_partite_fuzzy_internal(self, conn, query: str, threshold: float, limit: int) -> List[Dict]:
        """Ricerca fuzzy interna per le partite, ora include l'elenco dei possessori."""
        # --- MODIFICA: Aggiunto JOIN con possessori e aggregazione con string_agg ---
        sql = f"""
            SELECT
                p.id AS entity_id,
                'Partita N. ' || p.numero_partita || COALESCE(' (' || p.suffisso_partita || ')', '') AS display_text,
                'Comune: ' || c.nome || ' | Tipo: ' || p.tipo || ' | Stato: ' || p.stato AS detail_text,
                greatest(
                    similarity(CAST(p.numero_partita AS TEXT), %s),
                    similarity(p.tipo, %s),
                    similarity(p.suffisso_partita, %s)
                ) AS similarity_score,
                'partita' AS search_field,
                p.numero_partita,
                p.suffisso_partita,
                p.tipo as tipo_partita,
                c.nome as comune_nome,
                p.stato,
                p.data_impianto,
                -- Aggrega i nomi dei possessori in una singola stringa separata da virgola
                string_agg(pos.nome_completo, ', ') AS possessori_concatenati
            FROM {self.schema}.partita p
            JOIN {self.schema}.comune c ON p.comune_id = c.id
            -- LEFT JOIN per includere anche le partite senza possessori
            LEFT JOIN {self.schema}.partita_possessore pp ON p.id = pp.partita_id
            LEFT JOIN {self.schema}.possessore pos ON pp.possessore_id = pos.id
            WHERE greatest(
                    similarity(CAST(p.numero_partita AS TEXT), %s),
                    similarity(p.tipo, %s),
                    similarity(p.suffisso_partita, %s)
                ) >= %s
            -- Raggruppa per i campi della partita per permettere l'aggregazione dei possessori
            GROUP BY p.id, c.nome
            ORDER BY similarity_score DESC
            LIMIT %s;
        """
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (query, query, query, query, query, query, threshold, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore ricerca fuzzy partite: {e}", exc_info=True)
            return []
    def verify_gin_indices(self) -> Dict[str, Any]:
        """
        Verifica la presenza di indici GIN per la ricerca testuale nello schema specificato.
        Restituisce un dizionario con lo stato e il numero di indici trovati.
        """
        self.logger.info(f"Verifica degli indici GIN per lo schema '{self.schema}'...")
        query = """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = %s AND indexdef LIKE '%% USING gin %%';
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (self.schema,))
                    result = cur.fetchone()
                    count = result[0] if result else 0
                    self.logger.info(f"Trovati {count} indici GIN nello schema '{self.schema}'.")
                    return {'status': 'OK', 'gin_indices': count}
        except Exception as e:
            self.logger.error(f"Errore durante la verifica degli indici GIN: {e}", exc_info=True)
            return {'status': 'ERROR', 'message': str(e), 'gin_indices': 0}
    def get_last_mv_refresh_timestamp(self) -> Optional[datetime]:
        """Recupera il timestamp dell'ultimo aggiornamento delle viste materializzate."""
        query = f"SELECT value_timestamp FROM {self.schema}.app_metadata WHERE key = 'last_mv_refresh';"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    return result[0] if result else None
        except psycopg2.errors.UndefinedTable:
            self.logger.warning("Tabella 'app_metadata' non trovata. Creare la tabella per la funzionalità di refresh intelligente.")
            return None # La tabella potrebbe non esistere ancora
        except Exception as e:
            self.logger.error(f"Errore nel recuperare il timestamp di refresh: {e}", exc_info=True)
            return None
    # In catasto_db_manager.py, aggiungi questo nuovo metodo alla classe CatastoDBManager

    def get_dashboard_stats(self) -> Dict[str, int]:
        """Recupera le statistiche di base per la dashboard in un'unica query."""
        stats = {
            "total_comuni": 0,
            "total_partite": 0,
            "total_possessori": 0,
            "total_immobili": 0,
        }
        query = f"""
            SELECT 
                (SELECT COUNT(*) FROM {self.schema}.comune) AS total_comuni,
                (SELECT COUNT(*) FROM {self.schema}.partita) AS total_partite,
                (SELECT COUNT(*) FROM {self.schema}.possessore) AS total_possessori,
                (SELECT COUNT(*) FROM {self.schema}.immobile) AS total_immobili;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    if result:
                        stats.update(dict(result))
            return stats
        except Exception as e:
            self.logger.error(f"Errore durante il recupero delle statistiche per la dashboard: {e}", exc_info=True)
            return stats # Restituisce il dizionario con gli zeri in caso di errore
    def update_last_mv_refresh_timestamp(self):
        """Aggiorna il timestamp dell'ultimo refresh delle viste al tempo attuale (UTC)."""
        # Usiamo un "UPSERT" per inserire la chiave se non esiste, o aggiornarla se esiste.
        query = f"""
            INSERT INTO {self.schema}.app_metadata (key, value_timestamp)
            VALUES ('last_mv_refresh', NOW() at time zone 'utc')
            ON CONFLICT (key) DO UPDATE SET value_timestamp = EXCLUDED.value_timestamp;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
            self.logger.info("Timestamp di aggiornamento viste materializzate aggiornato con successo.")
        except Exception as e:
            self.logger.error(f"Errore nell'aggiornare il timestamp di refresh: {e}", exc_info=True)
