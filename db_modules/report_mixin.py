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
class ReportMixin:
    def get_report_consistenza_patrimoniale(self, comune_id: int) -> Dict[str, List[Dict]]:
        """
        Genera i dati per un report di consistenza patrimoniale per un dato comune.
        Logica corretta: trova le proprietà nel comune e poi raggruppa per possessore.
        """
        if not comune_id:
            raise DBDataError("È necessario specificare un comune per questo report.")

        report_data = {}

        # 1. Trova tutti i possessori unici che hanno partite nel comune specificato
        query_possessori = f"""
            SELECT DISTINCT pos.id, pos.nome_completo
            FROM {self.schema}.possessore pos
            JOIN {self.schema}.partita_possessore pp ON pos.id = pp.possessore_id
            JOIN {self.schema}.partita p ON pp.partita_id = p.id
            WHERE p.comune_id = %s AND pos.attivo = TRUE
            ORDER BY pos.nome_completo;
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query_possessori, (comune_id,))
                    possessori_nel_comune = [dict(row) for row in cur.fetchall()]

            # 2. Per ogni possessore trovato, recupera i dettagli delle sue partite in quel comune
            for p in possessori_nel_comune:
                possessore_id = p['id']
                possessore_nome = p['nome_completo']

                # Questa funzione recupera tutte le partite di un possessore
                tutte_le_partite = self.get_partite_per_possessore(possessore_id)

                # Filtriamo in Python per mantenere solo quelle del comune richiesto
                partite_nel_comune_selezionato = []
                for partita in tutte_le_partite:
                    # Dobbiamo unire i dati del comune per poter filtrare.
                    # Modifichiamo get_partite_per_possessore per includere comune_id.
                    if partita.get('comune_id') == comune_id:
                        partite_nel_comune_selezionato.append(partita)

                if partite_nel_comune_selezionato:
                    report_data[possessore_nome] = partite_nel_comune_selezionato

            return report_data

        except Exception as e:
            self.logger.error(f"Errore DB durante generazione report consistenza per comune ID {comune_id}: {e}", exc_info=True)
            raise DBMError(f"Impossibile generare il report di consistenza: {e}") from e


    def genera_report_proprieta(self, partita_id: int) -> Optional[str]:
        """Genera il report di proprietà immobiliare in Python (senza stored procedure)."""
        if not isinstance(partita_id, int) or partita_id <= 0:
            self.logger.error(f"ID partita non valido: {partita_id}")
            return None

        s = self.schema
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # Partita + comune
                    cur.execute(f"""
                        SELECT p.*, c.nome AS comune_nome
                        FROM {s}.partita p
                        JOIN {s}.comune c ON p.comune_id = c.id
                        WHERE p.id = %s
                    """, (partita_id,))
                    partita = cur.fetchone()
                    if not partita:
                        return f"Partita con ID {partita_id} non trovata"

                    # Possessori
                    cur.execute(f"""
                        SELECT pos.nome_completo, pp.titolo, pp.quota
                        FROM {s}.partita_possessore pp
                        JOIN {s}.possessore pos ON pp.possessore_id = pos.id
                        WHERE pp.partita_id = %s
                        ORDER BY pos.nome_completo
                    """, (partita_id,))
                    possessori = cur.fetchall()

                    # Immobili (senza civico, rimosso in script 22)
                    cur.execute(f"""
                        SELECT i.id, i.natura, i.numero_piani, i.numero_vani,
                               i.consistenza, i.classificazione,
                               tl.nome AS tipo_localita,
                               l.nome AS nome_localita
                        FROM {s}.immobile i
                        JOIN {s}.localita l ON i.localita_id = l.id
                        LEFT JOIN {s}.tipo_localita tl ON l.tipo_id = tl.id
                        WHERE i.partita_id = %s
                        ORDER BY l.nome, i.natura
                    """, (partita_id,))
                    immobili = cur.fetchall()

                    # Variazioni
                    cur.execute(f"""
                        SELECT v.tipo, v.data_variazione, p2.numero_partita AS partita_dest,
                               c2.nome AS comune_dest,
                               con.tipo AS tipo_contratto, con.data_contratto,
                               con.notaio, con.repertorio
                        FROM {s}.variazione v
                        LEFT JOIN {s}.partita p2 ON v.partita_destinazione_id = p2.id
                        LEFT JOIN {s}.comune c2 ON p2.comune_id = c2.id
                        LEFT JOIN {s}.contratto con ON v.id = con.variazione_id
                        WHERE v.partita_origine_id = %s
                        ORDER BY v.data_variazione DESC
                    """, (partita_id,))
                    variazioni = cur.fetchall()

            sep = "=" * 60
            sep2 = "-" * 20
            r = f"{sep}\n                REPORT PROPRIETA IMMOBILIARE\n"
            r += f"                     CATASTO STORICO ANNI '50\n{sep}\n\n"
            r += f"COMUNE: {partita['comune_nome']}\n"
            r += f"PARTITA N.: {partita['numero_partita']}\n"
            r += f"TIPO: {partita['tipo']}\n"
            r += f"DATA IMPIANTO: {partita['data_impianto'] or 'N/D'}\n"
            r += f"STATO: {partita['stato']}\n"
            if partita['data_chiusura']:
                r += f"DATA CHIUSURA: {partita['data_chiusura']}\n"
            if partita['numero_provenienza']:
                r += f"PROVENIENZA: Partita n. {partita['numero_provenienza']}\n"
            r += "\n"

            r += f"{sep2} INTESTATARI {sep2}\n"
            for p in possessori:
                r += f"- {p['nome_completo']}"
                if p['titolo'] == 'comproprieta' and p['quota']:
                    r += f" (quota: {p['quota']})"
                r += "\n"
            r += "\n"

            r += f"{sep2} IMMOBILI {sep2}\n"
            for i in immobili:
                r += f"Immobile ID: {i['id']}\n"
                r += f"  Natura: {i['natura'] or 'N/D'}\n"
                loc = i['nome_localita'] or 'N/D'
                tipo_loc = i['tipo_localita'] or 'N/D'
                r += f"  Localita: {loc} ({tipo_loc})\n"
                if i['numero_piani']:
                    r += f"  Piani: {i['numero_piani']}\n"
                if i['numero_vani']:
                    r += f"  Vani: {i['numero_vani']}\n"
                if i['consistenza']:
                    r += f"  Consistenza: {i['consistenza']}\n"
                if i['classificazione']:
                    r += f"  Classificazione: {i['classificazione']}\n"
                r += "\n"

            r += f"{sep2} VARIAZIONI {sep2}\n"
            for v in variazioni:
                r += f"Variazione: {v['tipo'] or 'N/D'} del {v['data_variazione'] or 'N/D'}\n"
                if v['partita_dest']:
                    r += f"  Nuova partita: {v['partita_dest']} (Comune: {v['comune_dest'] or 'N/D'})\n"
                if v['tipo_contratto']:
                    r += f"  Contratto: {v['tipo_contratto']} del {v['data_contratto'] or 'N/D'}\n"
                    if v['notaio']:
                        r += f"  Notaio: {v['notaio']}\n"
                    if v['repertorio']:
                        r += f"  Repertorio: {v['repertorio']}\n"
                r += "\n"

            r += f"{sep}\n"
            r += f"Report generato il: {date.today()}\n"
            r += "Il presente report ha valore puramente storico e documentale.\n"
            r += f"{sep}\n"

            self.logger.info(f"Report di proprietà generato per partita ID {partita_id}.")
            return r

        except Exception as e:
            self.logger.error(f"Errore DB in genera_report_proprieta (ID: {partita_id}): {e}", exc_info=True)
            return None
    def genera_report_genealogico(self, partita_id: int) -> Optional[str]:
        """Chiama la funzione SQL catasto.genera_report_genealogico in modo sicuro."""
        if not isinstance(partita_id, int) or partita_id <= 0:
            self.logger.error(f"ID partita non valido: {partita_id}")
            return None

        query = f"SELECT {self.schema}.genera_report_genealogico(%s);"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (partita_id,))
                    result = cur.fetchone()
                    return str(result[0]) if result and result[0] is not None else None
        except Exception as e:
            self.logger.error(f"Errore DB in genera_report_genealogico (ID: {partita_id}): {e}", exc_info=True)
            return None
    def genera_report_possessore(self, possessore_id: int) -> Optional[str]:
        """Chiama la funzione SQL catasto.genera_report_possessore in modo sicuro."""
        if not isinstance(possessore_id, int) or possessore_id <= 0:
            self.logger.error(f"ID possessore non valido: {possessore_id}")
            return None
                
        query = f"SELECT {self.schema}.genera_report_possessore(%s);"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (possessore_id,))
                    result = cur.fetchone()
                    return str(result[0]) if result and result[0] is not None else None
        except Exception as e:
            self.logger.error(f"Errore DB in genera_report_possessore (ID: {possessore_id}): {e}", exc_info=True)
            return None
    def genera_report_consultazioni(self, data_inizio: Optional[date] = None, 
                                data_fine: Optional[date] = None,
                                richiedente: Optional[str] = None) -> str:
        """Chiama la funzione SQL catasto.genera_report_consultazioni in modo sicuro."""
        query = f"SELECT {self.schema}.genera_report_consultazioni(%s, %s, %s);"
        params = (data_inizio, data_fine, richiedente)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    self.logger.debug(f"Esecuzione genera_report_consultazioni con filtri: {params}")
                    cur.execute(query, params)
                    result = cur.fetchone()
                    if result and result[0] is not None:
                        self.logger.info("Report consultazioni generato.")
                        return str(result[0])
                    else:
                        self.logger.warning("Nessun report consultazioni generato o risultato NULL.")
                        return "Nessun dato trovato per i criteri specificati."
        except Exception as e:
            self.logger.error(f"Errore in genera_report_consultazioni: {e}", exc_info=True)
            return "Errore durante la generazione del report."

    def get_report_comune(self, comune_id: int) -> Optional[Dict]: # Usa comune_id
        """Chiama la funzione SQL genera_report_comune (MODIFICATA per comune_id)."""
        try:
            # Funzione SQL aggiornata per comune_id
            query = "SELECT * FROM genera_report_comune(%s)"
            if self.execute_query(query, (comune_id,)): return self.fetchone()
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_report_comune: {db_err}"); return None
        except Exception as e: logger.error(f"Errore Python get_report_comune: {e}"); return None

    def get_property_genealogy(self, partita_id: int) -> List[Dict]:
        """Chiama la funzione SQL albero_genealogico_proprieta in modo sicuro."""
        query = f"SELECT * FROM {self.schema}.albero_genealogico_proprieta(%s)"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, (partita_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Errore DB in get_property_genealogy (ID: {partita_id}): {e}", exc_info=True)
            return []

    def get_cadastral_stats_by_period(self, comune_id: Optional[int] = None, year_start: int = 1900, # Usa comune_id
                                       year_end: Optional[int] = None) -> List[Dict]:
        """Chiama la funzione SQL statistiche_catastali_periodo (MODIFICATA per comune_id)."""
        logger.warning("La funzione SQL 'statistiche_catastali_periodo' potrebbe non essere aggiornata per comune_id.")
        try:
            # Assumiamo funzione SQL aggiornata per comune_id
            if year_end is None: year_end = datetime.now().year
            query = "SELECT * FROM statistiche_catastali_periodo(%s, %s, %s)"
            params = (comune_id, year_start, year_end) # Passa ID
            if self.execute_query(query, params): return self.fetchall()
        except psycopg2.errors.UndefinedFunction: logger.warning("Funzione 'statistiche_catastali_periodo' non trovata."); return []
        except psycopg2.Error as db_err: logger.error(f"Errore DB get_cadastral_stats_by_period: {db_err}"); return []
        except Exception as e: logger.error(f"Errore Python get_cadastral_stats_by_period: {e}"); return []
        return []

