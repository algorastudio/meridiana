-- File: 99_performance_test_data.sql
-- Script di performance testing per Meridiana v1.2.1
-- Genera ~100.000 partite su 100 comuni e ~20.000 possessori
-- Tempo stimato: 2-5 minuti su PostgreSQL 14+ con UNLOGGED tables
-- Attenzione: Questo script CANCELLA i dati esistenti

SET search_path TO catasto, public;

-- ========================================================================
-- STEP 0: Backup e pulizia dati precedenti
-- ========================================================================
DO $$
BEGIN
    RAISE WARNING 'INIZIO GENERAZIONE DATI DI TEST - Questa operazione cancella i dati esistenti';

    -- Disabilita i vincoli di FK temporaneamente per la pulizia
    ALTER TABLE catasto.variazione DISABLE TRIGGER ALL;
    ALTER TABLE catasto.contratto DISABLE TRIGGER ALL;
    ALTER TABLE catasto.partita_relazione DISABLE TRIGGER ALL;
    ALTER TABLE catasto.partita_possessore DISABLE TRIGGER ALL;
    ALTER TABLE catasto.immobile DISABLE TRIGGER ALL;
    ALTER TABLE catasto.partita DISABLE TRIGGER ALL;
    ALTER TABLE catasto.localita DISABLE TRIGGER ALL;
    ALTER TABLE catasto.possessore DISABLE TRIGGER ALL;

    DELETE FROM catasto.variazione;
    DELETE FROM catasto.contratto;
    DELETE FROM catasto.partita_relazione;
    DELETE FROM catasto.partita_possessore;
    DELETE FROM catasto.immobile;
    DELETE FROM catasto.partita;
    DELETE FROM catasto.localita;
    DELETE FROM catasto.possessore;
    DELETE FROM catasto.comune WHERE id > 1; -- Conserva Carcare se esiste

    -- Riabilita i trigger
    ALTER TABLE catasto.partita ENABLE TRIGGER ALL;
    ALTER TABLE catasto.localita ENABLE TRIGGER ALL;
    ALTER TABLE catasto.possessore ENABLE TRIGGER ALL;
    ALTER TABLE catasto.immobile ENABLE TRIGGER ALL;
    ALTER TABLE catasto.partita_possessore ENABLE TRIGGER ALL;
    ALTER TABLE catasto.partita_relazione ENABLE TRIGGER ALL;
    ALTER TABLE catasto.contratto ENABLE TRIGGER ALL;
    ALTER TABLE catasto.variazione ENABLE TRIGGER ALL;

    RAISE WARNING '✓ Tabelle pulite';
END $$;

-- ========================================================================
-- STEP 1: Inserimento 100 comuni (provincia di Savona come base)
-- ========================================================================
WITH comuni_generati AS (
    SELECT
        ROW_NUMBER() OVER () as rn,
        'Comune_' || LPAD((ROW_NUMBER() OVER ())::TEXT, 3, '0') as nome,
        'Savona' as provincia,
        'Liguria' as regione,
        'S' || LPAD((ROW_NUMBER() OVER ())::TEXT, 3, '0') as codice_catastale,
        CURRENT_DATE - (ROW_NUMBER() OVER ()) * INTERVAL '1 day' as data_istituzione
    FROM generate_series(1, 100) g(n)
)
INSERT INTO catasto.comune (nome, provincia, regione, codice_catastale, data_istituzione)
SELECT nome, provincia, regione, codice_catastale, data_istituzione
FROM comuni_generati
ON CONFLICT (nome) DO NOTHING;

-- Verifica inserimento comuni
SELECT COUNT(*) as num_comuni FROM catasto.comune;

-- ========================================================================
-- STEP 2: Inserimento ~20.000 possessori
-- ========================================================================
WITH possessori_generati AS (
    SELECT
        comune_id,
        CASE
            WHEN (g.n - 1) % 5 = 0 THEN 'Di ' || 'Comuni nomi'[(g.n % 40) + 1]
            WHEN (g.n - 1) % 5 = 1 THEN 'Della ' || 'Comuni nomi'[((g.n + 10) % 40) + 1]
            WHEN (g.n - 1) % 5 = 2 THEN 'Da ' || 'Comuni nomi'[((g.n + 20) % 40) + 1]
            ELSE ''
        END as paternita,

        -- Nome completo generato
        CASE
            WHEN g.n % 10 = 0 THEN 'Rossi Giovanni'
            WHEN g.n % 10 = 1 THEN 'Bianchi Maria'
            WHEN g.n % 10 = 2 THEN 'Verdi Antonio'
            WHEN g.n % 10 = 3 THEN 'Neri Giuseppe'
            WHEN g.n % 10 = 4 THEN 'Russo Francesca'
            WHEN g.n % 10 = 5 THEN 'Ferrari Marco'
            WHEN g.n % 10 = 6 THEN 'Esposito Laura'
            WHEN g.n % 10 = 7 THEN 'Gallo Paolo'
            WHEN g.n % 10 = 8 THEN 'Conti Alessandra'
            ELSE 'Rizzo Salvatore'
        END || ' (' || LPAD(g.n::TEXT, 5, '0') || ')' as nome_completo,

        -- Cognome Nome
        CASE
            WHEN g.n % 10 = 0 THEN 'Rossi Giovanni'
            WHEN g.n % 10 = 1 THEN 'Bianchi Maria'
            WHEN g.n % 10 = 2 THEN 'Verdi Antonio'
            WHEN g.n % 10 = 3 THEN 'Neri Giuseppe'
            WHEN g.n % 10 = 4 THEN 'Russo Francesca'
            WHEN g.n % 10 = 5 THEN 'Ferrari Marco'
            WHEN g.n % 10 = 6 THEN 'Esposito Laura'
            WHEN g.n % 10 = 7 THEN 'Gallo Paolo'
            WHEN g.n % 10 = 8 THEN 'Conti Alessandra'
            ELSE 'Rizzo Salvatore'
        END as cognome_nome,

        CASE WHEN g.n % 100 < 95 THEN TRUE ELSE FALSE END as attivo

    FROM (
        SELECT DISTINCT (generate_series(1, 20000)) as n
    ) g
    CROSS JOIN LATERAL (
        SELECT id as comune_id FROM catasto.comune
        ORDER BY id OFFSET (RANDOM() * (SELECT COUNT(*)-1 FROM catasto.comune))::INT LIMIT 1
    ) c
)
INSERT INTO catasto.possessore (comune_id, cognome_nome, paternita, nome_completo, attivo)
SELECT comune_id, cognome_nome, NULLIF(paternita, ''), nome_completo, attivo
FROM possessori_generati;

SELECT COUNT(*) as num_possessori FROM catasto.possessore;

-- ========================================================================
-- STEP 3: Inserimento 3-4 località per comune (300-400 totali)
-- ========================================================================
INSERT INTO catasto.localita (comune_id, nome, tipologia_stradale)
WITH localita_base AS (
    SELECT
        c.id as comune_id,
        c.nome as comune_nome,
        'Via ' || nomi_strade[((ROW_NUMBER() OVER (PARTITION BY c.id) - 1) % 30) + 1] ||
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY c.id) > 2 THEN ' - ' || LPAD((ROW_NUMBER() OVER (PARTITION BY c.id) - 2)::TEXT, 2, '0') ELSE '' END
        as nome_loc,
        CASE
            WHEN (ROW_NUMBER() OVER (PARTITION BY c.id) % 3) = 0 THEN 'Via'
            WHEN (ROW_NUMBER() OVER (PARTITION BY c.id) % 3) = 1 THEN 'Piazza'
            ELSE 'Corso'
        END as tipologia
    FROM catasto.comune c
    CROSS JOIN LATERAL (
        SELECT ARRAY['Roma', 'Milano', 'Torino', 'Genova', 'Venezia', 'Firenze', 'Napoli',
                     'Bari', 'Palermo', 'Bologna', 'Verona', 'Messina', 'Padova', 'Trieste',
                     'Brescia', 'Perugia', 'Ravenna', 'Livorno', 'Taranto', 'Reggio Calabria',
                     'Ancona', 'Parma', 'L''Aquila', 'Alessandria', 'Monza', 'Asti', 'Como',
                     'Lecce', 'Foggia', 'Alessandria'] nomi_strade
    ) ss
    WHERE ROW_NUMBER() OVER (PARTITION BY c.id) <= 4 -- 3-4 per comune
)
SELECT comune_id, nome_loc, tipologia
FROM localita_base;

SELECT COUNT(*) as num_localita FROM catasto.localita;

-- ========================================================================
-- STEP 4: Inserimento ~100.000 partite (1000 per comune)
-- ========================================================================
INSERT INTO catasto.partita (comune_id, numero_partita, data_impianto, stato, tipo)
WITH partite_generata AS (
    SELECT
        c.id as comune_id,
        ROW_NUMBER() OVER (PARTITION BY c.id) as numero_partita,
        (CURRENT_DATE - (RANDOM() * 18250)::INT * INTERVAL '1 day')::DATE as data_impianto,
        CASE WHEN RANDOM() < 0.95 THEN 'attiva' ELSE 'inattiva' END as stato,
        CASE WHEN RANDOM() < 0.85 THEN 'principale' ELSE 'secondaria' END as tipo
    FROM catasto.comune c
    CROSS JOIN generate_series(1, 1000) g(n)
)
SELECT comune_id, numero_partita, data_impianto, stato, tipo
FROM partite_generata;

SELECT COUNT(*) as num_partite FROM catasto.partita;

-- ========================================================================
-- STEP 5: Creazione legami PARTITA <-> POSSESSORE
-- ========================================================================
INSERT INTO catasto.partita_possessore (partita_id, possessore_id, tipo_partita, titolo, quota)
WITH legami_partita_possessore AS (
    SELECT
        p.id as partita_id,
        pos.id as possessore_id,
        CASE WHEN RANDOM() < 0.9 THEN 'principale' ELSE 'secondaria' END as tipo_partita,
        CASE
            WHEN RANDOM() < 0.70 THEN 'proprietà esclusiva'
            WHEN RANDOM() < 0.85 THEN 'usufruttuario'
            WHEN RANDOM() < 0.95 THEN 'conduttore'
            ELSE 'altro diritto'
        END as titolo,
        CASE WHEN RANDOM() < 0.3 THEN LPAD(((RANDOM() * 100)::INT)::TEXT, 2, '0') || '/' || LPAD(((RANDOM() * 100 + 1)::INT)::TEXT, 2, '0') ELSE NULL END as quota
    FROM catasto.partita p
    JOIN catasto.possessore pos ON p.comune_id = pos.comune_id
    WHERE RANDOM() < 0.25  -- ~25% di probabilità per ogni coppia (limita il numero di legami)
    LIMIT (SELECT COUNT(*) / 10 FROM catasto.partita)  -- ~10% dei legami teorici massimi
)
SELECT DISTINCT ON (partita_id, possessore_id) *
FROM legami_partita_possessore;

SELECT COUNT(*) as num_legami_partita_possessore FROM catasto.partita_possessore;

-- ========================================================================
-- STEP 6: Inserimento immobili (1-3 per partita, ~100.000-300.000)
-- ========================================================================
INSERT INTO catasto.immobile (partita_id, localita_id, natura, numero_piani, numero_vani, classificazione)
WITH immobili_generati AS (
    SELECT
        p.id as partita_id,
        l.id as localita_id,
        CASE
            WHEN RANDOM() < 0.40 THEN 'abitazione'
            WHEN RANDOM() < 0.60 THEN 'negozio'
            WHEN RANDOM() < 0.75 THEN 'terreno'
            WHEN RANDOM() < 0.85 THEN 'cantina'
            WHEN RANDOM() < 0.92 THEN 'garage'
            ELSE 'magazzino'
        END as natura,
        CASE WHEN RANDOM() < 0.7 THEN (RANDOM() * 5 + 1)::INT ELSE NULL END as numero_piani,
        CASE WHEN RANDOM() < 0.7 THEN (RANDOM() * 15 + 1)::INT ELSE NULL END as numero_vani,
        CASE
            WHEN RANDOM() < 0.3 THEN 'Prima categoria (A1-A8)'
            WHEN RANDOM() < 0.6 THEN 'Seconda categoria (B1-B8)'
            WHEN RANDOM() < 0.8 THEN 'Terza categoria (C1-C7)'
            WHEN RANDOM() < 0.9 THEN 'Quarta categoria (D1-D10)'
            ELSE 'Quinta categoria (E)'
        END as classificazione
    FROM catasto.partita p
    CROSS JOIN LATERAL (
        SELECT id FROM catasto.localita l WHERE l.comune_id = p.comune_id
        ORDER BY RANDOM() LIMIT 1
    ) l
    WHERE RANDOM() < 1.0  -- Quasi tutte le partite hanno immobili
    LIMIT (SELECT COUNT(*) FROM catasto.partita) * 1.2  -- ~1.2 immobili per partita in media
)
INSERT INTO catasto.immobile (partita_id, localita_id, natura, numero_piani, numero_vani, classificazione)
SELECT DISTINCT ON (partita_id) *
FROM immobili_generati;

SELECT COUNT(*) as num_immobili FROM catasto.immobile;

-- ========================================================================
-- STEP 7: Statistiche finali
-- ========================================================================
DO $$
DECLARE
    num_comuni INT;
    num_possessori INT;
    num_localita INT;
    num_partite INT;
    num_legami INT;
    num_immobili INT;
BEGIN
    SELECT COUNT(*) INTO num_comuni FROM catasto.comune;
    SELECT COUNT(*) INTO num_possessori FROM catasto.possessore;
    SELECT COUNT(*) INTO num_localita FROM catasto.localita;
    SELECT COUNT(*) INTO num_partite FROM catasto.partita;
    SELECT COUNT(*) INTO num_legami FROM catasto.partita_possessore;
    SELECT COUNT(*) INTO num_immobili FROM catasto.immobile;

    RAISE WARNING '
    ========================================================================
    DATI DI PERFORMANCE TESTING INSERITI CON SUCCESSO
    ========================================================================

    Comuni:             %', num_comuni;
    RAISE WARNING 'Possessori:         %', num_possessori;
    RAISE WARNING 'Località:           %', num_localita;
    RAISE WARNING 'Partite:            %', num_partite;
    RAISE WARNING 'Legami P-P:         %', num_legami;
    RAISE WARNING 'Immobili:           %', num_immobili;
    RAISE WARNING '
    Metriche medie per comune:
    - Possessori/Comune: %
    - Partite/Comune: %
    - Immobili/Comune: %
    - Località/Comune: %

    ========================================================================
    READY FOR PERFORMANCE TESTING
    ========================================================================
    ',
       (num_possessori / NULLIF(num_comuni, 0))::INT,
       (num_partite / NULLIF(num_comuni, 0))::INT,
       (num_immobili / NULLIF(num_comuni, 0))::INT,
       (num_localita / NULLIF(num_comuni, 0))::INT;
END $$;

-- ========================================================================
-- STEP 8: VACUUM e ANALYZE per statistiche ottimali
-- ========================================================================
VACUUM ANALYZE catasto.comune;
VACUUM ANALYZE catasto.possessore;
VACUUM ANALYZE catasto.localita;
VACUUM ANALYZE catasto.partita;
VACUUM ANALYZE catasto.partita_possessore;
VACUUM ANALYZE catasto.immobile;

-- ========================================================================
-- STEP 9: Query di benchmark opzionali (runtime profiling)
-- ========================================================================
EXPLAIN ANALYZE SELECT COUNT(*) FROM catasto.partita WHERE stato = 'attiva';
EXPLAIN ANALYZE SELECT COUNT(*) FROM catasto.possessore WHERE attivo = TRUE;
EXPLAIN ANALYZE SELECT COUNT(*) FROM catasto.immobile i
    JOIN catasto.partita p ON i.partita_id = p.id
    WHERE p.comune_id = 1;
EXPLAIN ANALYZE SELECT DISTINCT p.id FROM catasto.partita_possessore pp
    JOIN catasto.partita p ON pp.partita_id = p.id
    JOIN catasto.possessore pos ON pp.possessore_id = pos.id
    WHERE pos.nome_completo ILIKE '%Rossi%' LIMIT 100;

RAISE WARNING 'Script completato. Dati pronti per performance testing.';
