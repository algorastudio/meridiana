# Performance Testing Script

## Descrizione

Script SQL (`99_performance_test_data.sql`) per generare una base dati realistica di performance testing per **Meridiana v1.2.1**.

### Dati Generati

| Entità | Quantità | Note |
|--------|----------|------|
| **Comuni** | ~100 | Distribuzione su provincia Savona (fittizia) |
| **Possessori** | ~20.000 | Distribuiti sui comuni (200 per comune in media) |
| **Località** | ~300-400 | 3-4 per comune (Via, Piazza, Corso) |
| **Partite** | ~100.000 | 1.000 per comune |
| **Legami Partita-Possessore** | ~250.000-300.000 | ~25% di probabilità per ogni coppia possibile |
| **Immobili** | ~100.000-120.000 | ~1.2 per partita (abitazioni, negozi, terreni, etc.) |

### Tempo di Esecuzione

- **Generazione dati**: 2-5 minuti (PostgreSQL 14+ su hardware moderno)
- **VACUUM ANALYZE**: 1-2 minuti
- **Totale**: ~5-7 minuti

---

## Come Usare

### Prerequisiti

1. Database PostgreSQL 14+ già creato con schema `catasto_storico`
2. Script di setup iniziale già eseguito (`02_creazione-schema-tabelle.sql`, ecc.)
3. Connessione al DB con privilegi `SUPERUSER` o `OWNER`

### Esecuzione

#### Opzione 1: Da shell (consigliato per il primo run)

```bash
# Connessione diretta
psql -U postgres -d catasto_storico -f sql_scripts/99_performance_test_data.sql

# Con verbosity
psql -U postgres -d catasto_storico -f sql_scripts/99_performance_test_data.sql -E
```

#### Opzione 2: Da Python (usando catasto_db_manager)

```python
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_PORT
import psycopg2

conn = psycopg2.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME,
    port=DB_PORT
)

with open('sql_scripts/99_performance_test_data.sql', 'r') as f:
    sql = f.read()

with conn.cursor() as cur:
    cur.execute(sql)

conn.close()
print("✓ Dati di testing generati con successo")
```

#### Opzione 3: Da GUI (menu Impostazioni, se implementato)

Non ancora integrato nella GUI — usare opzione 1 o 2.

---

## Cosa lo Script Fa (Step-by-Step)

### STEP 0: Pulizia
- Disabilita temporaneamente i trigger
- Cancella tutti i record da tabelle principali (partita, possessore, immobile, etc.)
- Preserva comuni già presenti (se necessario)

### STEP 1: Comuni (100)
- Genera nomi `Comune_001` a `Comune_100`
- Provincia: `Savona` (fittizia)
- Codici catastali: `S001` a `S100`

### STEP 2: Possessori (~20.000)
- Nomi casuali con varianti (Rossi, Bianchi, Verdi, etc.)
- Distribuiti casualmente sui comuni
- ~95% attivi, ~5% inattivi

### STEP 3: Località (300-400)
- 3-4 per comune
- Via, Piazza, Corso
- Nomi tratti da città italiane reali

### STEP 4: Partite (100.000)
- 1.000 per comune
- Data impianto casuale (ultimi 50 anni)
- Stato: attiva (95%), inattiva (5%)
- Tipo: principale (85%), secondaria (15%)

### STEP 5: Legami Partita-Possessore
- ~25% di probabilità per ogni coppia
- Titoli: proprietà esclusiva (70%), usufruttuario (15%), conduttore (10%), altro (5%)
- Quote casuali (30% dei legami)

### STEP 6: Immobili (~100.000-120.000)
- ~1.2 per partita
- Natura: abitazione (40%), negozio (20%), terreno (15%), etc.
- Classificazione: prima-quinta categoria
- Numero piani e vani casuali

### STEP 7: Statistiche Finali
- Report riepilogativo in output
- Calcolo metriche medie per comune

### STEP 8: Optimizzazione
- VACUUM e ANALYZE per aggiornare le statistiche query planner

### STEP 9: Benchmark
- 4 query EXPLAIN ANALYZE di esempio per profiling

---

## Output Atteso

```
WARNING:  INIZIO GENERAZIONE DATI DI TEST - Questa operazione cancella i dati esistenti
...
WARNING:  
    ========================================================================
    DATI DI PERFORMANCE TESTING INSERITI CON SUCCESSO
    ========================================================================

    Comuni:             100
    Possessori:         20000
    Località:           300
    Partite:            100000
    Legami P-P:         250000
    Immobili:           120000

    Metriche medie per comune:
    - Possessori/Comune: 200
    - Partite/Comune: 1000
    - Immobili/Comune: 1200
    - Località/Comune: 3

    ========================================================================
    READY FOR PERFORMANCE TESTING
    ========================================================================
```

---

## Test Case di Esempio

Dopo aver eseguito lo script, provare:

### 1. Ricerca Partite per Comune
```sql
-- Selezionare un comune e visualizzare partite
SELECT p.id, p.numero_partita, p.suffisso_partita, p.stato
FROM catasto.partita p
WHERE p.comune_id = 1
LIMIT 20;
```

### 2. Ricerca Possessori Globale
```sql
-- Ricerca fuzzy (richiede pg_trgm)
SELECT id, nome_completo, comune_id
FROM catasto.possessore
WHERE nome_completo ILIKE '%Rossi%'
LIMIT 100;
```

### 3. Immobili per Partita
```sql
SELECT i.id, i.natura, i.classificazione, l.nome as localita
FROM catasto.immobile i
JOIN catasto.localita l ON i.localita_id = l.id
WHERE i.partita_id = 1;
```

### 4. Dashboard - Conteggi Totali
```sql
SELECT
    (SELECT COUNT(*) FROM catasto.comune) as num_comuni,
    (SELECT COUNT(*) FROM catasto.partita) as num_partite,
    (SELECT COUNT(*) FROM catasto.possessore) as num_possessori,
    (SELECT COUNT(*) FROM catasto.immobile) as num_immobili;
```

### 5. Performance - Tempi di Query
```bash
# Misurare il tempo di una query semplice
time psql -U postgres -d catasto_storico -c "
    SELECT COUNT(*) FROM catasto.partita WHERE stato='attiva';"

# Output atteso: < 100ms
```

---

## Pulizia Dati

Per rimuovere i dati di test e tornare a uno stato pulito:

```bash
psql -U postgres -d catasto_storico -c "
    DELETE FROM catasto.variazione;
    DELETE FROM catasto.contratto;
    DELETE FROM catasto.partita_relazione;
    DELETE FROM catasto.partita_possessore;
    DELETE FROM catasto.immobile;
    DELETE FROM catasto.partita;
    DELETE FROM catasto.localita;
    DELETE FROM catasto.possessore;
    DELETE FROM catasto.comune WHERE id > 1;
    VACUUM ANALYZE;
"
```

---

## Customizzazione

Se vuoi generare altri volumi di dati, modifica queste linee nello script:

```sql
-- STEP 1: Cambia "100" in numero desiderato
FROM generate_series(1, 100) g(n)

-- STEP 2: Cambia "20000" in numero desiderato
SELECT
    ROW_NUMBER() OVER () as rn,
    ...
FROM (
    SELECT DISTINCT (generate_series(1, 20000)) as n  -- <- QUI
) g

-- STEP 4: Cambia "1000" per partite per comune
CROSS JOIN generate_series(1, 1000) g(n)  -- <- QUI

-- STEP 5: Cambia probabilità di legami
WHERE RANDOM() < 0.25  -- Aumenta per più legami (es. 0.40)
```

---

## Monitoring

Durante l'esecuzione, in un altro terminale:

```bash
# Monitorare le insert in tempo reale
watch -n 2 'psql -U postgres -d catasto_storico -c "
    SELECT
        (SELECT COUNT(*) FROM catasto.comune) as comuni,
        (SELECT COUNT(*) FROM catasto.possessore) as possessori,
        (SELECT COUNT(*) FROM catasto.partita) as partite,
        (SELECT COUNT(*) FROM catasto.immobile) as immobili;"'
```

---

## Troubleshooting

### Errore: "insufficient memory"
- Aumenta `work_mem` in postgresql.conf: `SET work_mem = '256MB';`
- Riduci il numero di dati generati

### Errore: "Connection timeout"
- Aumenta `statement_timeout`: `SET statement_timeout = '10min';` all'inizio dello script

### Script lento
- Esegui VACUUM ANALYZE manualmente prima di rilanciare:
  ```bash
  psql -U postgres -d catasto_storico -c "VACUUM ANALYZE;"
  ```

---

## Licenza

Come il resto di Meridiana — concesso in comodato gratuito all'Archivio di Stato di Savona.

---

*Generato da Claude Code per Meridiana v1.2.1 - Performance Testing Framework*
