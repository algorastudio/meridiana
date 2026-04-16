# CLAUDE.md — Meridiana

Guida per Claude Code su questo progetto.

## Panoramica

**Meridiana** è un'applicazione desktop per la gestione degli archivi catastali storici italiani,
sviluppata da Marco Santoro e concessa in comodato d'uso gratuito all'**Archivio di Stato di Savona**.

- **Stack**: Python 3.12 + PyQt5 + PostgreSQL 14+
- **Branch attivo**: `claude/archive-savona-version-L9NIe`
- **Versione**: 1.2.1

---

## Struttura del progetto

```
meridiana/
├── catasto_db_manager.py   # Unico punto di accesso al DB (pool psycopg2)
├── dialogs.py              # Tutti i QDialog (Modifica, Selezione, Creazione)
├── gui_widgets.py          # Widget principali montati nei tab dell'app
├── gui_main.py             # Finestra principale, menu, status bar
├── app_paths.py            # Percorsi app (cross-platform + PyInstaller)
├── app_utils.py            # Utilità generali
├── config.py               # Configurazione DB e logging
├── custom_widgets.py       # Widget Qt minori
├── sql_scripts/            # Tutti gli script SQL (schema + migration)
│   └── setup_server.py     # Bootstrap DB: esegue gli script in ordine
├── tests/                  # Suite pytest
├── docs/                   # Documentazione utente e changelog
├── resources/              # Icone, logo, EULA, manuale PDF
└── styles/                 # Temi QSS (16 temi)
```

---

## Architettura

### Flusso dati

```
GUI Widgets / Dialogs
        │ chiamate dirette
        ▼
CatastoDBManager          ← unico layer DB, nessun ORM
        │ psycopg2 pool
        ▼
PostgreSQL (schema: catasto)
        │ stored procedures
        ▼
Operazioni atomiche
```

### Gestione connessioni

Tutte le operazioni DB usano il context manager `_get_connection()`:
- **Auto-commit** al termine del blocco `with`
- **Auto-rollback** in caso di eccezione
- Non chiamare `conn.commit()` manualmente dentro i metodi del db_manager

### Eccezioni DB personalizzate

```python
DBDataError          # dati non validi (input errato)
DBUniqueConstraintError  # violazione vincolo UNIQUE
DBNotFoundError      # record non trovato
DBMError             # errore generico DB
```

---

## Convenzioni CRUD

### Naming metodi (db_manager)

| Operazione | Pattern | Return |
|-----------|---------|--------|
| CREATE    | `create_xxx(...)` | `int` (ID del nuovo record) |
| READ      | `get_xxx(...)` / `search_xxx(...)` | `List[Dict]` o `Dict` |
| UPDATE    | `update_xxx(id, dati: Dict)` | `bool` |
| DELETE fisico | `delete_xxx(id)` | `bool` |
| Archiviazione | `archivia_xxx(id)` | `None` (solleva eccezione se non trovato) |

### Soft delete (archiviazione logica)

Le entità principali **non si cancellano mai fisicamente** (archivio storico).
Usare sempre `archivia_xxx()` invece di `delete_xxx()` per: `comune`, `partita`, `possessore`, `localita`.

I record archiviati non appaiono nelle ricerche standard (`archiviato = FALSE` / `attivo = TRUE`).
Per ripristinarli: stored procedure `ripristina_xxx(id)` via psql.

### Validazione

- **Business logic** (date coerenti, vincoli di dominio) → sempre nel `db_manager`
- **Presentazione** (campo vuoto, formato data) → può stare nell'UI
- Helper: `CatastoDBManager._valida_intervallo_date(inizio, fine, label_i, label_f)`

---

## Database

### Connessione

```python
# config.py legge da variabili d'ambiente o usa i default
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'catasto_storico')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASS', '')
DB_PORT = os.getenv('DB_PORT', '5432')
```

### Bootstrap (primo avvio su DB nuovo)

```bash
python sql_scripts/setup_server.py
```

### Migrazione su DB esistente

Eseguire solo gli script mancanti in ordine numerico:

```bash
psql -U postgres -d catasto_storico -f sql_scripts/21_soft_delete.sql
```

### Script SQL — ordine di esecuzione

Gli script sono numerati da `02` a `21`. Il bootstrap li esegue tutti in ordine.
Per migrazioni su DB esistenti, eseguire solo gli script nuovi.

---

## Test

```bash
# Tutti i test (richiede DB di test attivo)
pytest tests/

# Con output verboso
pytest tests/ -v

# Solo i test DB
pytest tests/catasto-test-database.py -v
```

I test richiedono un database PostgreSQL raggiungibile con le credenziali in `conftest.py`.

---

## Build Windows

La CI/CD (GitHub Actions) genera automaticamente l'installer su tag `v*`:

```bash
git tag v1.2.1
git push origin v1.2.1
```

Per build manuale locale (su Windows):
```bash
pyinstaller meridiana.spec
# poi Inno Setup su Meridiana_Installer.iss
```

---

## Note per lo sviluppo

- Il file `version.txt` contiene i metadati versione per l'installer Windows — aggiornarlo ad ogni release
- I temi QSS sono in `styles/` — modificabili senza rebuild
- I log dell'app sono in `~/.meridiana/logs/meridiana_gui.log` (rotante 5 MB)
- Non aggiungere `print()` nel codice di produzione — usare `self.logger`
- Non lasciare credenziali hardcoded in nessun file (vedi storia: `.wolf69326vHRVvmRzsID.py`)
