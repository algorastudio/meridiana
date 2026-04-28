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

class PartiteMixin:
    def get_partite_by_comune_paginate(self, comune_id: int, limit: int = 100, offset: int = 0, filter_text: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Recupera le partite in modo paginato, restituendo anche il conteggio totale.
        Ritorna una tupla: (lista_record_pagina, totale_record_trovati).
        """
        if not isinstance(comune_id, int) or comune_id <= 0:
            raise DBDataError("ID comune non valido.")

        # 1. Costruzione della clausola FROM e WHERE (condivisa tra COUNT e SELECT)
        from_where_clause = f"FROM {self.schema}.partita p WHERE p.comune_id = %s"
        params: List[Union[int, str]] = [comune_id]

        # Applicazione dei filtri di ricerca, se presenti
        if filter_text:
            from_where_clause += " AND (CAST(p.numero_partita AS TEXT) ILIKE %s OR p.tipo ILIKE %s OR p.stato ILIKE %s OR p.suffisso_partita ILIKE %s)"
            filter_like = f"%{filter_text}%"
            params.extend([filter_like, filter_like, filter_like, filter_like])

        # 2. Query per il CONTEGGIO TOTALE (ignora LIMIT e OFFSET)
        count_query = f"SELECT COUNT(*) {from_where_clause}"

        # 3. Query per i DATI PAGINATI (applica LIMIT, OFFSET e ORDER BY)
        select_cols = f"""
            SELECT
                p.id, p.numero_partita, p.suffisso_partita, p.tipo, p.stato, p.data_impianto,
                (SELECT COUNT(*) FROM {self.schema}.partita_possessore pp WHERE pp.partita_id = p.id) as num_possessori,
                (SELECT COUNT(*) FROM {self.schema}.immobile i WHERE i.partita_id = p.id) as num_immobili,
                (SELECT COUNT(*) FROM {self.schema}.documento_partita dp WHERE dp.partita_id = p.id) as num_documenti_allegati
        """
        data_query = f"{select_cols} {from_where_clause} ORDER BY p.numero_partita, p.suffisso_partita LIMIT %s OFFSET %s"
        
        # Aggiungiamo i parametri specifici per la paginazione alla query dei dati
        data_params = params + [limit, offset]

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # Esegui prima il conteggio totale
                    cur.execute(count_query, tuple(params))
                    total_count = cur.fetchone()[0]

                    partite_list = []
                    # Inutile interrogare i dati se il conteggio è zero
                    if total_count > 0:
                        cur.execute(data_query, tuple(data_params))
                        partite_list = [dict(row) for row in cur.fetchall()]

                    self.logger.info(f"Paginazione: estratti {len(partite_list)} record su un totale di {total_count} (Offset: {offset}).")
                    return partite_list, total_count

        except Exception as e:
            self.logger.error(f"Errore DB in get_partite_by_comune_paginate: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema durante il recupero paginato delle partite: {e}") from e
    
    def get_partita_data_for_export(self, partita_id: int) -> Optional[Dict[str, Any]]:
        """
        Recupera i dati di una partita per l'esportazione chiamando una funzione SQL,
        in modo sicuro e transazionale.
        """
        if not isinstance(partita_id, int) or partita_id <= 0:
            self.logger.error(f"get_partita_data_for_export: ID partita non valido: {partita_id}")
            return None
            
        query = f"SELECT {self.schema}.esporta_partita_json(%s) AS partita_data;"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    self.logger.debug(f"Esecuzione get_partita_data_for_export per ID partita: {partita_id}")
                    cur.execute(query, (partita_id,))
                    result = cur.fetchone()
                    
                    if result and result['partita_data'] is not None:
                        self.logger.info(f"Dati per esportazione recuperati per partita ID {partita_id}.")
                        return result['partita_data']
                    else:
                        self.logger.warning(f"Nessun dato trovato per partita ID {partita_id} o il risultato era NULL.")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Errore DB in get_partita_data_for_export (ID: {partita_id}): {e}", exc_info=True)
            return None # Restituisce None in caso di qualsiasi errore
    def import_partite_from_csv(self, file_path: str, comune_id: int, comune_nome: str) -> Dict[str, list]:
        """
        Importa una lista di partite da un file CSV, gestendo gli errori riga per riga.
        Restituisce un dizionario con i risultati dettagliati ('success' e 'errors').
        """
        records_to_import = []
        try:
            with open(file_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                required_headers = {'numero_partita', 'data_impianto', 'stato', 'tipo'}
                if not required_headers.issubset(reader.fieldnames or []):
                    raise ValueError(f"Intestazioni mancanti nel CSV. Richieste: {', '.join(required_headers)}")
                for i, row in enumerate(reader):
                    if not all(row.get(key) for key in required_headers):
                        raise ValueError(f"Dati mancanti alla riga {i + 2}. Campi obbligatori: {', '.join(required_headers)}.")
                    records_to_import.append(row)
        except Exception as e:
            raise IOError(f"Errore leggendo il file CSV: {e}")

        if not records_to_import:
            return {"success": [], "errors": []}

        success_rows = []
        error_rows = []

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for i, record in enumerate(records_to_import):
                        line_num = i + 2
                        cur.execute("SAVEPOINT record_savepoint")
                        try:
                            numero_partita = int(record['numero_partita'])
                            suffisso_partita = record.get('suffisso_partita') or None
                            
                            cur.execute(
                                f"SELECT id FROM {self.schema}.partita WHERE comune_id = %s AND numero_partita = %s AND (suffisso_partita = %s OR (suffisso_partita IS NULL AND %s IS NULL))",
                                (comune_id, numero_partita, suffisso_partita, suffisso_partita)
                            )
                            if cur.fetchone():
                                suffisso_str = f" con suffisso '{suffisso_partita}'" if suffisso_partita else ""
                                raise ValueError(f"La partita n.{numero_partita}{suffisso_str} esiste già.")

                            cur.execute(
                                f"""
                                INSERT INTO {self.schema}.partita (comune_id, numero_partita, suffisso_partita, data_impianto, data_chiusura, numero_provenienza, stato, tipo)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                                """,
                                (comune_id, numero_partita, suffisso_partita, record['data_impianto'], record.get('data_chiusura') or None, record.get('numero_provenienza') or None, record['stato'], record['tipo'])
                            )
                            new_id = cur.fetchone()[0]
                            cur.execute("RELEASE SAVEPOINT record_savepoint")
                            record['id'] = new_id
                            record['comune_nome'] = comune_nome
                            success_rows.append(record)
                        
                        except (ValueError, psycopg2.Error, DBMError) as error:
                            cur.execute("ROLLBACK TO SAVEPOINT record_savepoint")
                            error_rows.append((line_num, record, str(error)))
            
            self.logger.info(f"Importazione CSV partite completata. Successi: {len(success_rows)}, Errori: {len(error_rows)}")
            return {"success": success_rows, "errors": error_rows}

        except Exception as e:
            self.logger.error(f"Errore critico durante l'importazione CSV delle partite: {e}", exc_info=True)
            raise DBMError(f"Errore critico di sistema durante l'importazione: {e}") from e
    def create_partita(self, comune_id: int, numero_partita: int, tipo: str, stato: str, data_impianto: date,
                       suffisso_partita: Optional[str] = None, data_chiusura: Optional[date] = None,
                       numero_provenienza: Optional[int] = None) -> int:
        """
        Crea una nuova, singola partita nel database e restituisce il suo ID.
        """
        if not all([comune_id, numero_partita, tipo, stato, data_impianto]):
            raise DBDataError("Comune, Numero Partita, Tipo, Stato e Data Impianto sono obbligatori.")
        self._valida_intervallo_date(data_impianto, data_chiusura, "Data Impianto", "Data Chiusura")

        query = f"""
            INSERT INTO {self.schema}.partita
                (comune_id, numero_partita, suffisso_partita, data_impianto, data_chiusura, numero_provenienza, stato, tipo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        params = (comune_id, numero_partita, suffisso_partita, data_impianto,
                  data_chiusura, numero_provenienza, stato, tipo)

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Pre-check esplicito: UNIQUE su (comune_id, numero_partita, suffisso_partita)
                    # non cattura duplicati con suffisso=NULL (PostgreSQL tratta NULL come distinto)
                    cur.execute(
                        f"SELECT id FROM {self.schema}.partita WHERE comune_id = %s AND numero_partita = %s AND suffisso_partita IS NOT DISTINCT FROM %s",
                        (comune_id, numero_partita, suffisso_partita)
                    )
                    if cur.fetchone():
                        raise DBUniqueConstraintError(f"Esiste già una partita con numero {numero_partita} in questo comune.")
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result and result[0]:
                        self.logger.info(f"Partita N.{numero_partita} creata con successo. ID: {result[0]}")
                        return result[0]
                    else:
                        raise DBMError("Creazione partita fallita, nessun ID restituito.")
        except psycopg2.errors.UniqueViolation as e:
            raise DBUniqueConstraintError(f"Esiste già una partita con questo numero e suffisso nel comune selezionato.") from e
        except (DBUniqueConstraintError, DBDataError):
            raise
        except Exception as e:
            self.logger.error(f"Errore DB durante la creazione della partita: {e}", exc_info=True)
            raise DBMError(f"Errore imprevisto durante la creazione della partita: {e}") from e
    

    # In catasto_db_manager.py

    def get_partite_per_possessore(self, possessore_id: int) -> List[Dict[str, Any]]:
            if not possessore_id > 0: raise DBDataError("ID possessore non valido.")
            query = f"""
                SELECT p.id, p.numero_partita, p.suffisso_partita, p.tipo, p.stato, 
                    c.id as comune_id, c.nome as comune_nome, pp.titolo, pp.quota
                FROM {self.schema}.partita p
                JOIN {self.schema}.comune c ON p.comune_id = c.id
                JOIN {self.schema}.partita_possessore pp ON p.id = pp.partita_id
                WHERE pp.possessore_id = %s ORDER BY c.nome, p.numero_partita;
            """
            try:
                with self._get_connection() as conn:
                    with conn.cursor(cursor_factory=DictCursor) as cur:
                        cur.execute(query, (possessore_id,))
                        return [dict(row) for row in cur.fetchall()]
            except Exception as e:
                self.logger.error(f"Errore in get_partite_per_possessore: {e}", exc_info=True)
                raise DBMError("Impossibile recuperare le partite per il possessore.") from e
    

    def get_partite_by_comune(self, comune_id: int, filter_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera le partite per un dato comune con un filtro opzionale."""
        if not isinstance(comune_id, int) or comune_id <= 0:
            raise DBDataError("ID comune non valido.")

        query_base = f"""
            SELECT
                p.id, p.numero_partita, p.suffisso_partita, p.tipo, p.stato, p.data_impianto,
                (SELECT COUNT(*) FROM {self.schema}.partita_possessore pp WHERE pp.partita_id = p.id) as num_possessori,
                (SELECT COUNT(*) FROM {self.schema}.immobile i WHERE i.partita_id = p.id) as num_immobili,
                (SELECT COUNT(*) FROM {self.schema}.documento_partita dp WHERE dp.partita_id = p.id) as num_documenti_allegati
            FROM {self.schema}.partita p
            WHERE p.comune_id = %s
        """
        params: List[Union[int, str]] = [comune_id]

        if filter_text:
            query_base += " AND (CAST(p.numero_partita AS TEXT) ILIKE %s OR p.tipo ILIKE %s OR p.stato ILIKE %s OR p.suffisso_partita ILIKE %s)"
            filter_like = f"%{filter_text}%"
            params.extend([filter_like, filter_like, filter_like, filter_like])

        query = query_base + " ORDER BY p.numero_partita, p.suffisso_partita;"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, tuple(params))
                    partite_list = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"Recuperate {len(partite_list)} partite per comune ID {comune_id}.")
                    return partite_list
        except Exception as e:
            self.logger.error(f"Errore DB in get_partite_by_comune: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema durante il recupero delle partite: {e}") from e
    def get_partita_details(self, partita_id: int) -> Optional[Dict[str, Any]]:
        """Recupera dettagli completi di una partita, usando una singola connessione e transazione."""
        if not isinstance(partita_id, int) or partita_id <= 0:
            return None

        partita_details: Dict[str, Any] = {}
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # 1. Info base partita (invariato)
                    query_partita = f"SELECT p.*, c.nome as comune_nome, c.id as comune_id FROM {self.schema}.partita p JOIN {self.schema}.comune c ON p.comune_id = c.id WHERE p.id = %s;"
                    cur.execute(query_partita, (partita_id,))
                    partita_base = cur.fetchone()
                    if not partita_base:
                        self.logger.warning(f"Partita ID {partita_id} non trovata.")
                        return None
                    partita_details.update(dict(partita_base))

                    # 2. Possessori (invariato)
                    query_poss = f"SELECT pos.id, pos.nome_completo, pp.titolo, pp.quota FROM {self.schema}.possessore pos JOIN {self.schema}.partita_possessore pp ON pos.id = pp.possessore_id WHERE pp.partita_id = %s ORDER BY pos.nome_completo;"
                    cur.execute(query_poss, (partita_id,))
                    partita_details['possessori'] = [dict(row) for row in cur.fetchall()]

                    # --- INIZIO CORREZIONE QUI ---
                    # 3. Immobili (query aggiornata con JOIN a tipo_localita)
                    query_imm = f"""
                        SELECT i.id, i.natura, i.numero_piani, i.numero_vani, i.consistenza,
                            i.classificazione, l.nome as localita_nome, tl.nome as localita_tipo
                        FROM {self.schema}.immobile i
                        JOIN {self.schema}.localita l ON i.localita_id = l.id
                        LEFT JOIN {self.schema}.tipo_localita tl ON l.tipo_id = tl.id
                        WHERE i.partita_id = %s
                        ORDER BY l.nome, i.natura;
                    """
                    # --- FINE CORREZIONE QUI ---
                    cur.execute(query_imm, (partita_id,))
                    partita_details['immobili'] = [dict(row) for row in cur.fetchall()]

                    # 4. Variazioni (invariato)
                    query_var = f"""
                        SELECT v.*, con.tipo as tipo_contratto, con.data_contratto, con.notaio, con.repertorio, con.note as contratto_note,
                            po.numero_partita AS origine_numero_partita, co.nome AS origine_comune_nome,
                            pd.numero_partita AS destinazione_numero_partita, cd.nome AS destinazione_comune_nome
                        FROM {self.schema}.variazione v 
                        LEFT JOIN {self.schema}.contratto con ON v.id = con.variazione_id
                        LEFT JOIN {self.schema}.partita po ON v.partita_origine_id = po.id
                        LEFT JOIN {self.schema}.comune co ON po.comune_id = co.id
                        LEFT JOIN {self.schema}.partita pd ON v.partita_destinazione_id = pd.id
                        LEFT JOIN {self.schema}.comune cd ON pd.comune_id = cd.id
                        WHERE v.partita_origine_id = %s OR v.partita_destinazione_id = %s
                        ORDER BY v.data_variazione DESC;
                    """
                    cur.execute(query_var, (partita_id, partita_id))
                    partita_details['variazioni'] = [dict(row) for row in cur.fetchall()]

            self.logger.info(f"Dettagli completi recuperati per partita ID {partita_id}.")
            return partita_details

        except Exception as e:
            self.logger.error(f"Errore DB in get_partita_details (ID: {partita_id}): {e}", exc_info=True)
            return None
    def update_partita(self, partita_id: int, dati_modificati: Dict[str, Any]) -> bool:
        """Aggiorna i dati di una partita esistente in modo transazionale e sicuro."""
        if not isinstance(partita_id, int) or partita_id <= 0:
            raise DBDataError(f"ID partita non valido: {partita_id}")
        if not dati_modificati:
            self.logger.info("Nessun dato fornito per l'aggiornamento della partita.")
            return True

        data_impianto = dati_modificati.get("data_impianto")
        data_chiusura = dati_modificati.get("data_chiusura")
        self._valida_intervallo_date(data_impianto, data_chiusura, "Data Impianto", "Data Chiusura")

        allowed_fields = ["numero_partita", "tipo", "stato", "data_impianto", "data_chiusura", "numero_provenienza"]
        set_clauses = [f"{field} = %s" for field in allowed_fields if field in dati_modificati]
        params = [dati_modificati[field] for field in allowed_fields if field in dati_modificati]

        if "suffisso_partita" in dati_modificati:
            set_clauses.append("suffisso_partita = %s")
            params.append(dati_modificati["suffisso_partita"])

        if not set_clauses:
            self.logger.info("Nessun campo valido fornito per l'aggiornamento della partita.")
            return True

        set_clauses.append("data_modifica = CURRENT_TIMESTAMP")
        params.append(partita_id)
        query = f"UPDATE {self.schema}.partita SET {', '.join(set_clauses)} WHERE id = %s;"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, tuple(params))
                    if cur.rowcount == 0:
                        # L'eccezione causerà un rollback automatico
                        raise DBNotFoundError(f"Nessuna partita trovata con ID {partita_id} per l'aggiornamento.")
            # Il commit è automatico qui
            self.logger.info(f"Partita ID {partita_id} aggiornata con successo.")
            return True
        except Exception as e:
            self.logger.error(f"Errore DB aggiornando partita ID {partita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile aggiornare la partita: {e}") from e

    def archivia_partita(self, partita_id: int) -> None:
        if not isinstance(partita_id, int) or partita_id <= 0:
            raise DBDataError("ID partita non valido.")
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"CALL {self.schema}.archivia_partita(%s);", (partita_id,))
            self.logger.info(f"Partita ID {partita_id} archiviata.")
        except psycopg2.errors.RaiseException as e:
            raise DBNotFoundError(str(e)) from e
        except Exception as e:
            self.logger.error(f"Errore archiviazione partita {partita_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile archiviare la partita: {e}") from e

    def search_partite(self, comune_id: Optional[int] = None, numero_partita: Optional[int] = None,
                    possessore: Optional[str] = None, immobile_natura: Optional[str] = None,
                    suffisso_partita: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Ricerca partite con filtri multipli, usando il nuovo pattern di connessione sicuro.
        """
        try:
            conditions, params, joins = ["p.archiviato = FALSE"], [], ""
            select_cols = "p.id, c.nome as comune_nome, p.numero_partita, p.suffisso_partita, p.tipo, p.stato"
            query_base = f"SELECT DISTINCT {select_cols} FROM {self.schema}.partita p JOIN {self.schema}.comune c ON p.comune_id = c.id"

            if possessore:
                joins += f" JOIN {self.schema}.partita_possessore pp ON p.id = pp.partita_id JOIN {self.schema}.possessore pos ON pp.possessore_id = pos.id"
                conditions.append("pos.nome_completo ILIKE %s")
                params.append(f"%{possessore}%")
            if immobile_natura:
                joins += f" JOIN {self.schema}.immobile i ON p.id = i.partita_id"
                conditions.append("i.natura ILIKE %s")
                params.append(f"%{immobile_natura}%")
            if comune_id is not None:
                conditions.append("p.comune_id = %s")
                params.append(comune_id)
            if numero_partita is not None:
                conditions.append("p.numero_partita = %s")
                params.append(numero_partita)
            if suffisso_partita is not None:
                if suffisso_partita.strip() == "":
                    conditions.append("p.suffisso_partita IS NULL")
                else:
                    conditions.append("p.suffisso_partita ILIKE %s")
                    params.append(f"%{suffisso_partita.strip()}%")

            query = query_base + joins
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY c.nome, p.numero_partita"

            self.logger.debug(f"search_partite - Query: {query} - Params: {tuple(params)}")

            # Esecuzione della query con il context manager
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(query, tuple(params))
                    results = [dict(row) for row in cur.fetchall()]
                    self.logger.info(f"search_partite - Trovate {len(results)} partite.")
                    return results

        except Exception as e:
            self.logger.error(f"Errore DB in search_partite: {e}", exc_info=True)
            return [] # Restituisce una lista vuota in caso di errore
            
    def search_partite_paginate(self, limit: int = 50, offset: int = 0, comune_id: Optional[int] = None, numero_partita: Optional[int] = None,
                    possessore: Optional[str] = None, immobile_natura: Optional[str] = None,
                    suffisso_partita: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Ricerca partite con filtri multipli e paginazione, restituendo i record e il totale.
        """
        try:
            conditions, params, joins = ["p.archiviato = FALSE"], [], ""
            select_cols = "p.id, c.nome as comune_nome, p.numero_partita, p.suffisso_partita, p.tipo, p.stato"
            
            from_clause = f"FROM {self.schema}.partita p JOIN {self.schema}.comune c ON p.comune_id = c.id"

            if possessore:
                joins += f" JOIN {self.schema}.partita_possessore pp ON p.id = pp.partita_id JOIN {self.schema}.possessore pos ON pp.possessore_id = pos.id"
                conditions.append("pos.nome_completo ILIKE %s")
                params.append(f"%{possessore}%")
            if immobile_natura:
                joins += f" JOIN {self.schema}.immobile i ON p.id = i.partita_id"
                conditions.append("i.natura ILIKE %s")
                params.append(f"%{immobile_natura}%")
            if comune_id is not None:
                conditions.append("p.comune_id = %s")
                params.append(comune_id)
            if numero_partita is not None:
                conditions.append("p.numero_partita = %s")
                params.append(numero_partita)
            if suffisso_partita is not None:
                if suffisso_partita.strip() == "":
                    conditions.append("p.suffisso_partita IS NULL")
                else:
                    conditions.append("p.suffisso_partita ILIKE %s")
                    params.append(f"%{suffisso_partita.strip()}%")

            base_query = from_clause + joins
            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
                
            count_query = f"SELECT COUNT(DISTINCT p.id) {base_query} {where_clause}"
            
            data_query = f"SELECT DISTINCT {select_cols} {base_query} {where_clause} ORDER BY c.nome, p.numero_partita LIMIT %s OFFSET %s"
            data_params = params + [limit, offset]

            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(count_query, tuple(params))
                    total_count = cur.fetchone()[0]

                    results = []
                    if total_count > 0:
                        cur.execute(data_query, tuple(data_params))
                        results = [dict(row) for row in cur.fetchall()]
                        
                    self.logger.info(f"search_partite_paginate - Trovate {len(results)} partite su {total_count}.")
                    return results, total_count

        except Exception as e:
            self.logger.error(f"Errore DB in search_partite_paginate: {e}", exc_info=True)
            return [], 0
            
    def duplicate_partita(self, partita_id_originale: int, nuovo_numero_partita: int,
                      mantenere_possessori: bool = True, mantenere_immobili: bool = False,
                      nuovo_suffisso: Optional[str] = None) -> bool:
        """Chiama la procedura SQL per duplicare una partita in modo transazionale."""
        call_proc_str = f"CALL {self.schema}.duplica_partita(%s, %s, %s, %s, %s);"
        params = (partita_id_originale, nuovo_numero_partita, mantenere_possessori, mantenere_immobili, nuovo_suffisso)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.info(f"Tentativo di duplicare partita ID {partita_id_originale} in Nuovo N.{nuovo_numero_partita}")
                    cur.execute(call_proc_str, params)
            
            self.logger.info(f"Partita ID {partita_id_originale} duplicata con successo.")
            return True
        except psycopg2.Error as db_err:
            pgerror_msg = getattr(db_err, 'pgerror', str(db_err))
            self.logger.error(f"Errore DB durante duplicazione partita ID {partita_id_originale}: {pgerror_msg}", exc_info=True)
            raise DBMError(f"Errore database durante la duplicazione: {pgerror_msg}") from db_err
        except Exception as e:
            self.logger.error(f"Errore Python durante duplicazione partita ID {partita_id_originale}: {e}", exc_info=True)
            raise DBMError(f"Errore di sistema durante la duplicazione: {e}") from e

    def get_partite_complete_view(self, comune_id: Optional[int] = None, stato: Optional[str] = None, limit: int = 100) -> List[Dict]: # Usa comune_id
        """Recupera dati dalla vista materializzata mv_partite_complete (aggiornata), filtrando per ID."""
        try:
            params = []
            # La vista SQL è stata aggiornata per usare nome comune
            query = "SELECT * FROM mv_partite_complete" # La vista ha 'comune_nome'
            where_clauses = []
            if comune_id is not None:
                 # Filtra con JOIN
                 query = """
                     SELECT m.* FROM mv_partite_complete m
                     JOIN comune c ON m.comune_nome = c.nome
                     WHERE c.id = %s
                 """
                 params.append(comune_id)
                 if stato and stato.lower() in ['attiva', 'inattiva']:
                     query += " AND m.stato = %s"; params.append(stato.lower())
            elif stato and stato.lower() in ['attiva', 'inattiva']:
                 query += " WHERE stato = %s"; params.append(stato.lower())

            query += " ORDER BY comune_nome, numero_partita LIMIT %s"; params.append(limit)
            if self.execute_query(query, tuple(params)): return self.fetchall()
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_partite_complete_view: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python get_partite_complete_view: {e}"); return []

    def export_partita_json(self, partita_id: int) -> Optional[str]:
        """Chiama la funzione SQL esporta_partita_json (SQL aggiornata)."""
        try:
            # Funzione SQL aggiornata per fare JOIN
            query = "SELECT esporta_partita_json(%s) AS partita_json"
            if self.execute_query(query, (partita_id,)):
                result = self.fetchone()
                if result and result.get('partita_json'):
                     try: return json.dumps(result['partita_json'], indent=4, ensure_ascii=False)
                     except (TypeError, ValueError) as json_err: logger.error(f"Errore JSON export partita {partita_id}: {json_err}"); return str(result['partita_json'])
            logger.warning(f"Nessun JSON per partita ID {partita_id}.")
        except psycopg2.Error as db_err: logger.error(f"Errore DB export_partita_json (ID: {partita_id}): {db_err}")
        except Exception as e: logger.error(f"Errore Python export_partita_json (ID: {partita_id}): {e}")
        return None

    def get_report_annuale_partite(self, comune_id: int, anno: int) -> List[Dict]: # Usa comune_id
        """Chiama la funzione SQL report_annuale_partite (MODIFICATA per comune_id)."""
        try:
            # Funzione SQL aggiornata per comune_id
            query = "SELECT * FROM report_annuale_partite(%s, %s)"
            if self.execute_query(query, (comune_id, anno)): return self.fetchall()
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_report_annuale_partite: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python get_report_annuale_partite: {e}"); return []

