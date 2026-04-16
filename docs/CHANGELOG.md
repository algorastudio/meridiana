# Changelog — Meridiana

## [1.2.1] — 2026-04-16

Versione preparata per la consegna in comodato d'uso all'**Archivio di Stato di Savona**.

### Pulizia del codice

- Eliminato file temporaneo `.wolf69326vHRVvmRzsID.py` (copia obsoleta di `gui_main.py` con password hardcoded)
- Rimossi 18 marker `INIZIO/FINE METODO MANCANTE/DA RIPRISTINARE` da `dialogs.py` (i metodi erano già presenti e funzionanti)
- Rimossi 2 metodi `_pulisci_campi_creazione_localita` duplicati nelle classi `LocalitaSelectionDialog`
- Sostituito `print()` di debug con `logger.error()` in `dialogs.py` (`ModificaImmobileDialog`)
- Rimosso blocco `__main__` di test con password hardcoded da `catasto_db_manager.py`
- Rimosso commento residuo `FINE AGGIUNTA METODO MANCANTE` da `gui_main.py`
- Rimosso blocco di codice morto (53 righe commentate con triple-quote) da `gui_widgets.py`

### Archiviazione logica — soft delete (Area 2)

In un archivio storico i dati non si cancellano mai fisicamente. Implementato sistema di
archiviazione logica per le quattro entità principali.

**Database** (`sql_scripts/21_soft_delete.sql` — da eseguire su DB esistenti):
- Aggiunta colonna `archiviato BOOLEAN DEFAULT FALSE` + `data_archiviazione TIMESTAMPTZ` su: `comune`, `partita`, `localita`
- Aggiunta colonna `data_archiviazione TIMESTAMPTZ` su `possessore` (usa già il campo `attivo`)
- Stored procedures: `archivia_xxx` e `ripristina_xxx` per tutte e quattro le entità
- Indici su `archiviato` / `attivo` per performance di ricerca

**db_manager** (`catasto_db_manager.py`):
- Aggiunti metodi: `archivia_comune`, `archivia_partita`, `archivia_possessore`, `archivia_localita`
- Query di elenco/ricerca aggiornate con filtro `archiviato = FALSE` / `attivo = TRUE`:
  `get_all_comuni_details`, `get_elenco_comuni_semplice`, `get_possessori_by_comune`,
  `search_possessori_by_term_globally`, `get_localita_by_comune`, `search_partite`

**UI** (`dialogs.py`):
- Pulsante **"Archivia..."** con dialogo di conferma aggiunto in:
  `ModificaPartitaDialog`, `ModificaPossessoreDialog`, `ModificaComuneDialog`, `ModificaLocalitaDialog`

### Naming CRUD uniforme (Area 3)

- Rinominato `aggiungi_comune` → `create_comune` (16 chiamanti aggiornati)
- Rinominato `insert_localita` → `create_localita` (5 chiamanti aggiornati)
- Corretti i return type di `update_partita`, `update_possessore`, `update_localita`: ora restituiscono `bool` invece di `None` (corregge bug nei test)

### Validazione business logic centralizzata (Area 4)

- Aggiunto helper statico `_valida_intervallo_date` in `CatastoDBManager`
- Controllo `data_soppressione >= data_istituzione` in `create_comune` e `update_comune`
- Controllo `data_chiusura >= data_impianto` in `create_partita` e `update_partita`
- L'UI rimane responsabile solo della presentazione (campi vuoti, formato data)

---

## [1.2.0] — 2025-05-18

Versione stabile con pipeline CI/CD completa.

- Pipeline GitHub Actions: test su Ubuntu + PostgreSQL 14, build installer Windows
- Installer `.exe` generato da PyInstaller + Inno Setup
- Gestione utenti con bcrypt, sistema di audit log
- Reportistica: esportazione PDF, XLS, CSV per tutte le entità principali
- 16 temi grafici, dashboard con statistiche in tempo reale
- Ricerca fuzzy con indici GIN su PostgreSQL
- Gestione periodi storici (Regno Sardegna, Regno Italia, Repubblica)
- Sistema di backup/restore integrato
