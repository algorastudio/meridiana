# CLAUDE.md — Meridiana

Guida per Claude Code su questo progetto.

## Panoramica

**Meridiana** è un'applicazione desktop per la gestione degli archivi catastali storici italiani,
sviluppata da Marco Santoro e concessa in comodato d'uso gratuito all'**Archivio di Stato di Savona**.

- **Stack**: Python 3.13 + PyQt5 + PostgreSQL 14+
- **Branch attivo**: `claude/archive-savona-version-L9NIe`
- **Versione**: 1.3.0

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
├── models/                 # Dataclass di dominio (Partita, Possessore, Immobile, …)
├── db_modules/             # Mixin per ogni entità (partite, possessori, immobili, …)
├── views/                  # Widget per sezione (partite, possessori_immobili, strumenti, …)
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
        │ getattr() su Dataclass
        ▼
    models/           ← Partita, Possessore, Immobile, Variazione, …
        ▲ costruzione
        │
db_modules/ Mixin     ← partite_mixin, possessori_mixin, immobili_mixin, …
        │ psycopg2 pool
        ▼
PostgreSQL (schema: catasto)
        │ stored procedures
        ▼
Operazioni atomiche
```

**Regola chiave**: i metodi `db_manager` che gestiscono entità principali restituiscono
**Dataclass** (non `Dict`). La UI accede agli attributi via `getattr(obj, 'attr', default)`.
I dizionari puri rimangono solo per: utenti, periodi storici, report consistenza, buffer UI locali.

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
| READ entità principale | `get_xxx_details(id)` | `Optional[Dataclass]` |
| READ lista entità | `search_xxx(...)` / `get_xxx_by_yyy(...)` | `List[Dataclass]` |
| READ tipologiche/report | `get_xxx(...)` | `List[Dict]` o `Dict` |
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

### Test suite completa (v1.2.1)

**File principale**: `tests/test_db_manager.py` (855 linee, 100+ test methods)

Copertura:
- CRUD operations (Comune, Possessore, Partita, Localita, TipoLocalita)
- Soft delete (archiviazione logica) con esclusione da ricerche
- Validazione date (intervalli, inversioni)
- Import CSV (gestione errori, duplicati)
- Ricerca avanzata (fuzzy search, filtri)
- Legami Partita-Possessore
- Dashboard & statistiche
- Exception handling

**Fixture**: `tests/conftest.py`
- `db_manager`: connessione pool PostgreSQL
- `clean_db`: database pulito per ogni test
- `sample_data`: dataset completo (comune, possessore, partita, localita)
- `tipo_localita_id`: tipo di località per test
- `temp_csv_possessori`: file CSV per import test

### Esecuzione

```bash
# Tutti i test
pytest tests/

# Con output verboso
pytest tests/ -v

# Solo test db_manager (new suite)
pytest tests/test_db_manager.py -v

# Test specifico
pytest tests/test_db_manager.py::TestComuneCRUD::test_create_comune_successo -v

# Con coverage
pytest tests/test_db_manager.py --cov=catasto_db_manager --cov-report=html
```

**Prerequisiti**: Database PostgreSQL raggiungibile con credenziali in `conftest.py` (vedi `test_db_setup` fixture).

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

## Pattern Dataclass (v1.3.0+)

### Regola fondamentale

La UI **non chiama mai `.get('chiave')`** su oggetti restituiti da metodi `db_manager` che
gestiscono entità principali. Usare sempre `getattr(obj, 'attr', default)`.

```python
# ✅ CORRETTO — oggetto è un Dataclass
nome = getattr(possessore, 'nome_completo', '')
immobile_id = getattr(immobile, 'id', None)

# ❌ SBAGLIATO — AttributeError a runtime
nome = possessore.get('nome_completo', '')  # Dataclass non ha .get()
```

### Quale metodo restituisce cosa?

```python
# → Dataclass (usare getattr)
db.get_partita_details(id)          # → Optional[Partita]
db.search_partite(...)              # → List[Partita]
db.get_possessore_full_details(id)  # → Optional[Possessore]
db.get_immobile_details(id)         # → Optional[Immobile]
db.get_variazioni_by_partita(id)    # → List[Variazione]

# → Dict (usare .get() normale)
db.get_utenti()                     # → List[Dict]
db.get_utente_by_id(id)             # → Optional[Dict]
db.get_historical_periods()         # → List[Dict]
db.get_periodo_storico_details(id)  # → Optional[Dict]
db.get_report_consistenza_patrimoniale(id)  # → Dict[str, List[Dict]]
```

### Conversione Dataclass → Dict

Quando un Dataclass deve essere inserito in strutture dict-based (es. buffer locali, JSON):

```python
import dataclasses

# Da Dataclass a dict
immobile_dict = dataclasses.asdict(immobile)  # ricorsivo

# Da dict a Dataclass (pattern manuale nei mixin)
immobile = Immobile(**row)  # dove row viene da cursor.fetchone()
```

### Buffer locali nelle widget (restano dict puri)

`RegistrazioneProprietaWidget.possessori_data` e `immobili_data` sono **sempre liste di dict**.
Quando si aggiunge un `Immobile` dataclass dalla cache, convertirlo subito:

```python
# In _add_existing_immobile:
self.immobili_data.append({
    'id': getattr(imm_details, 'id', None),
    'natura': getattr(imm_details, 'natura', ''),
    # ...
})
```

---

## Bug fix noti (v1.2.1)

### Migrazione tipo_localita (Script 20)

Script 20 ha migrato `localita.tipo` (text) → `localita.tipo_id` (FK a `tipo_localita`).

**Bug fix applicati:**

1. **`sql_scripts/17_funzione_ricerca_immobili.sql`**
   - Era: `l.tipo AS localita_tipo` (colonna non esiste)
   - Ora: `LEFT JOIN catasto.tipo_localita tl ON l.tipo_id = tl.id` → `tl.nome AS localita_tipo`

2. **`catasto_db_manager.py:get_localita_details()`**
   - Era: `SELECT loc.tipo`
   - Ora: `LEFT JOIN catasto.tipo_localita tl ON loc.tipo_id = tl.id` → `tl.nome AS tipo`

3. **`catasto_db_manager.py:get_immobile_details()`**
   - Era: `l.tipo AS localita_tipo`
   - Ora: `LEFT JOIN catasto.tipo_localita tl ON l.tipo_id = tl.id` → `tl.nome AS localita_tipo`

**Test coverage**: `tests/test_db_manager.py::TestBugFixesTipoLocalita`

---

## Note per lo sviluppo

- Il file `version.txt` contiene i metadati versione per l'installer Windows — aggiornarlo ad ogni release
- I temi QSS sono in `styles/` — modificabili senza rebuild
- I log dell'app sono in `~/.meridiana/logs/meridiana_gui.log` (rotante 5 MB)
- Non aggiungere `print()` nel codice di produzione — usare `self.logger`
- Non lasciare credenziali hardcoded in nessun file (vedi storia: `.wolf69326vHRVvmRzsID.py`)
- Prima di modificare query SQL che usano `localita`, controllare se usano `l.tipo` (rimosso) o `l.tipo_id` (corretto)
- **Non usare `.get()` su Dataclass**: in caso di errore `AttributeError: 'Xxx' object has no attribute 'get'`, convertire con `getattr(obj, 'attr', default)`
