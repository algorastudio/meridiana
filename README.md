<div align="center">
  <img src="resources/logo_meridiana.png" alt="Logo Meridiana" width="180"/>

  # Meridiana
  ### Gestionale per Archivi Catastali Storici Italiani

  [![CI/CD](https://github.com/algorastudio/meridiana/actions/workflows/pipeline_meridiana.yml/badge.svg)](https://github.com/algorastudio/meridiana/actions/workflows/pipeline_meridiana.yml)
  ![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
  ![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql)
  ![Versione](https://img.shields.io/badge/versione-1.2.1-orange)
  ![Licenza](https://img.shields.io/badge/licenza-comodato%20d'uso-lightgrey)
</div>

---

**Meridiana** è un'applicazione desktop per la digitalizzazione e la gestione degli archivi catastali storici italiani. Sviluppata da **Marco Santoro** e concessa in comodato d'uso gratuito all'**Archivio di Stato di Savona**, l'applicazione consente di censire comuni, possessori, partite catastali, immobili e variazioni di proprietà, con pieno rispetto del principio archivistico della **non cancellazione** dei dati storici.

---

## Indice

- [Caratteristiche principali](#caratteristiche-principali)
- [Stack tecnologico](#stack-tecnologico)
- [Requisiti di sistema](#requisiti-di-sistema)
- [Installazione](#installazione)
- [Configurazione del database](#configurazione-del-database)
- [Avvio dell'applicazione](#avvio-dellapplicazione)
- [Struttura del progetto](#struttura-del-progetto)
- [Modello dei dati](#modello-dei-dati)
- [Funzionalità](#funzionalità)
- [Esportazione dati](#esportazione-dati)
- [Test automatici](#test-automatici)
- [Pipeline CI/CD](#pipeline-cicd)
- [Build installer Windows](#build-installer-windows)
- [Licenza](#licenza)

---

## Caratteristiche principali

- **Archivio non distruttivo**: le entità principali non vengono mai cancellate fisicamente; vengono *archiviate* (soft delete) e rimangono consultabili
- **Gestione periodi storici**: supporto nativo per la periodizzazione storica (es. Regno di Sardegna, Regno d'Italia, Repubblica)
- **Ricerca fuzzy avanzata**: indici GIN su PostgreSQL per ricerche testuali su possessori, partite e immobili
- **Multi-utente con audit log**: autenticazione bcrypt, ruoli utente, tracciamento completo di ogni operazione
- **Esportazione professionale**: CSV, Excel (`.xlsx`) e PDF con intestazioni istituzionali
- **16 temi grafici**: personalizzazione dell'interfaccia tramite fogli di stile QSS
- **Backup e ripristino integrati**: funzionalità di backup del database direttamente dall'interfaccia
- **Import da CSV**: caricamento massivo di possessori e partite da file CSV
- **Dashboard statistiche**: indicatori in tempo reale tramite viste materializzate PostgreSQL
- **Installer Windows**: build automatizzata con PyInstaller + Inno Setup

---

## Stack tecnologico

| Componente | Tecnologia |
|---|---|
| Linguaggio | Python 3.12 |
| Interfaccia grafica | PyQt5 5.15 |
| Database | PostgreSQL 14+ |
| Driver DB | psycopg2 (connection pooling) |
| Autenticazione | bcrypt |
| Esportazione PDF | fpdf2 |
| Esportazione Excel | openpyxl / pandas |
| Build Windows | PyInstaller + Inno Setup |
| Test | pytest |
| CI/CD | GitHub Actions |

---

## Requisiti di sistema

- **Sistema operativo**: Windows 10+ (installer), oppure Linux/macOS (da sorgente)
- **Python**: 3.12+
- **PostgreSQL**: 14 o superiore
- **RAM**: 4 GB consigliati
- **Disco**: ~200 MB per l'installazione (escluso il database)

---

## Installazione

### 1. Clona il repository

```bash
git clone https://github.com/algorastudio/meridiana.git
cd meridiana
```

### 2. Crea un ambiente virtuale e installa le dipendenze

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

---

## Configurazione del database

### Primo avvio (database nuovo)

Lo script `setup_server.py` esegue automaticamente tutti gli script SQL in ordine:

```bash
python sql_scripts/setup_server.py
```

Questo presuppone un'istanza PostgreSQL raggiungibile con le variabili d'ambiente configurate (vedi sotto).

### Variabili d'ambiente

Le credenziali del database vengono lette dalle variabili d'ambiente. Se non presenti, vengono usati i valori di default:

| Variabile | Default | Descrizione |
|---|---|---|
| `DB_HOST` | `localhost` | Hostname del server PostgreSQL |
| `DB_NAME` | `catasto_storico` | Nome del database |
| `DB_USER` | `postgres` | Utente PostgreSQL |
| `DB_PASS` | *(vuoto)* | Password |
| `DB_PORT` | `5432` | Porta |

In alternativa, la connessione si può configurare dall'interfaccia grafica al primo avvio.

### Migrazione da versione precedente

Se si dispone già di un database, eseguire solo gli script mancanti in ordine numerico:

```bash
psql -U postgres -d catasto_storico -f sql_scripts/21_soft_delete.sql
psql -U postgres -d catasto_storico -f sql_scripts/22_drop_civico_localita.sql
psql -U postgres -d catasto_storico -f sql_scripts/23_titoli_possesso.sql
```

---

## Avvio dell'applicazione

```bash
python gui_main.py
```

Al primo avvio viene mostrata la schermata di login. L'utente amministratore di default viene creato dallo script `sql_scripts/07a_bootstrap_admin.sql` durante l'inizializzazione del database.

---

## Struttura del progetto

```
meridiana/
├── catasto_db_manager.py   # Unico layer di accesso al DB (pool psycopg2)
├── dialogs.py              # Tutti i QDialog (Modifica, Selezione, Creazione)
├── gui_widgets.py          # Widget principali montati nei tab dell'app
├── gui_main.py             # Finestra principale, menu, status bar, login
├── app_paths.py            # Percorsi app (cross-platform + PyInstaller)
├── app_utils.py            # Utilità generali
├── config.py               # Configurazione DB e logging
├── custom_widgets.py       # Widget Qt minori riutilizzabili
├── requirements.txt        # Dipendenze Python
├── meridiana.spec          # Configurazione PyInstaller
├── Meridiana_Installer.iss # Script Inno Setup per l'installer Windows
├── version.txt             # Metadati versione per l'installer
├── sql_scripts/            # Script SQL numerati (schema + migrazioni)
│   └── setup_server.py     # Bootstrap DB: esegue tutti gli script in ordine
├── tests/                  # Suite pytest
│   ├── test_db_manager.py  # 100+ test del layer DB
│   └── conftest.py         # Fixture pytest
├── docs/                   # Documentazione utente e changelog
├── resources/              # Icone, logo, EULA, manuale PDF
└── styles/                 # 16 temi grafici QSS
```

---

## Modello dei dati

Il database utilizza lo schema `catasto` con le seguenti entità principali:

```
Comune ──────── Partita ──────── Immobile
                    │
                Possessore (legame con titolo di possesso e quota)
                    │
                Variazione / Contratto
                    │
                Consultazione (log accessi archivistici)
```

| Entità | Descrizione |
|---|---|
| `comune` | Comuni con date di istituzione/soppressione |
| `possessore` | Persone fisiche o giuridiche proprietarie |
| `partita` | Unità catastale con numerazione storica |
| `immobile` | Fabbricati e terreni associati a una partita |
| `localita` | Vie, contrade, borgate con tipo di ubicazione |
| `tipo_localita` | Tipologie di ubicazione configurabili |
| `variazione` | Trasferimenti di proprietà e mutazioni catastali |
| `contratto` | Atti notarili collegati alle variazioni |
| `titolo_possesso` | Titoli giuridici (proprietà esclusiva, usufrutto…) |
| `consultazione` | Registro delle consultazioni dell'archivio |
| `utente` | Utenti dell'applicazione con ruoli e password hash |

### Archiviazione logica (soft delete)

Le entità principali **non si cancellano mai fisicamente**. Per archiviarle si utilizza il pulsante "Archivia…" presente nelle finestre di modifica. I record archiviati vengono esclusi da tutte le ricerche standard; per ripristinarli è disponibile la stored procedure `ripristina_xxx(id)` da psql.

---

## Funzionalità

### Gestione entità
- Inserimento, modifica e archiviazione di comuni, possessori, partite, immobili e località
- Import massivo da file CSV (possessori, partite)
- Gestione dei legami possessore-partita con quota e titolo di possesso

### Ricerca
- Ricerca fuzzy multi-entità con operatore `%` su indici GIN PostgreSQL
- Filtri per comune, periodo storico, tipo immobile
- Ricerca avanzata immobili con filtri combinati
- Riepilogo proprietà per possessore

### Reportistica ed esportazione
- Esportazione in **CSV**, **Excel (.xlsx)** e **PDF** per tutte le entità
- Report consistenza patrimoniale per possessore
- Generazione automatica nella cartella `Documenti > Esportazioni Meridiana`

### Amministrazione (solo admin)
- Gestione utenti e reset password
- Viewer del log di audit (ogni operazione è tracciata)
- Gestione periodi storici
- Gestione tipi di località e titoli di possesso
- Backup e ripristino del database
- Registro consultazioni archivistiche

### Interfaccia
- 16 temi grafici selezionabili dal menu Visualizza
- Dashboard con statistiche in tempo reale
- Schermata di benvenuto con indicazione dello stato del server DB
- Log operativo integrato in ogni schermata

---

## Esportazione dati

Dal tab **Esportazioni** è possibile selezionare il tipo di dato e il comune di riferimento, quindi scegliere il formato:

| Formato | Utilizzo consigliato |
|---|---|
| CSV (`;` come separatore) | Import in altri sistemi o database |
| Excel `.xlsx` | Analisi, filtri e ordinamento dati |
| PDF | Stampa istituzionale con intestazione e piè di pagina |

---

## Test automatici

La suite pytest copre l'intero layer `CatastoDBManager` con oltre 100 test.

### Prerequisiti

Un'istanza PostgreSQL deve essere raggiungibile con le credenziali configurate in `tests/conftest.py` (o tramite variabili d'ambiente).

### Esecuzione

```bash
# Tutti i test
pytest tests/

# Solo il layer DB con output verboso
pytest tests/test_db_manager.py -v

# Un singolo test
pytest tests/test_db_manager.py::TestComuneCRUD::test_create_comune_successo -v

# Con report di copertura
pytest tests/test_db_manager.py --cov=catasto_db_manager --cov-report=html
```

### Copertura

| Area | Classi di test |
|---|---|
| CRUD (Comune, Possessore, Partita, Localita, TipoLocalita) | `TestComuneCRUD`, `TestPossessoreCRUD`, … |
| Soft delete | `TestSoftDelete*` |
| Validazione date e business logic | `TestValidazione*` |
| Import CSV | `TestImportCSV` |
| Ricerca fuzzy e avanzata | `TestRicerca*` |
| Legami Partita-Possessore | `TestLegami*` |
| Dashboard e statistiche | `TestDashboard` |
| Gestione eccezioni DB | `TestExceptionHandling` |
| Bug fix migrazione tipo_localita | `TestBugFixesTipoLocalita` |

---

## Pipeline CI/CD

La pipeline GitHub Actions si articola in tre fasi:

```
push / tag v* ─┐
               ▼
    [1] test-database-and-code
        Ubuntu + PostgreSQL 14
        pytest tests/
               │ (solo se successo)
               ▼
    [2] build-windows
        Windows + PyInstaller + Inno Setup
        (solo su tag v* o workflow_dispatch)
               │
               ▼
    [3] publish-release
        Crea GitHub Release con installer .exe allegato
        (solo su tag v*)
```

---

## Build installer Windows

Per generare un nuovo installer è sufficiente creare e pubblicare un tag:

```bash
git tag v1.2.1
git push origin v1.2.1
```

La CI produrrà automaticamente il file `Meridiana_*_Setup.exe` e lo pubblicherà come GitHub Release.

Per una build manuale locale (richiede Windows con Inno Setup installato):

```bash
pyinstaller meridiana.spec --clean --noconfirm
iscc Meridiana_Installer.iss
```

---

## Licenza

Copyright © 2025 **Marco Santoro**. Tutti i diritti riservati.

Il software è concesso in **comodato d'uso gratuito, esclusivo e non trasferibile** all'**Archivio di Stato di Savona** per le finalità istituzionali di gestione dell'archivio catastale storico, secondo i termini dell'[EULA allegata](resources/EULA.txt).

È vietata la distribuzione, la sublicenza, la modifica o la decompilazione del software senza esplicito consenso scritto dell'autore.

---

<div align="center">
  <sub>Meridiana 1.2.1 · Sviluppato da Marco Santoro · In gentile concessione all'Archivio di Stato di Savona</sub>
</div>
