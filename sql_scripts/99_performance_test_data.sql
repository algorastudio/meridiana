-- File: 99_performance_test_data.sql
-- Script di performance testing per Meridiana v1.2.1
-- Genera ~100.000 partite su 100 comuni, ~20.000 possessori,
-- ~300 localita e ~100.000+ immobili
-- Tempo stimato: 2-5 minuti su PostgreSQL 14+
-- ATTENZIONE: Questo script CANCELLA i dati esistenti nelle tabelle coinvolte

SET search_path TO catasto, public;
SET client_min_messages TO WARNING;

-- ========================================================================
-- STEP 0: Pulizia dati precedenti
-- ========================================================================
DO $$
BEGIN
    RAISE WARNING 'INIZIO GENERAZIONE DATI DI TEST - Questa operazione cancella i dati esistenti';

    DELETE FROM catasto.variazione;
    DELETE FROM catasto.contratto;
    DELETE FROM catasto.partita_relazione;
    DELETE FROM catasto.partita_possessore;
    DELETE FROM catasto.immobile;
    DELETE FROM catasto.partita;
    DELETE FROM catasto.localita;
    DELETE FROM catasto.possessore;
    DELETE FROM catasto.comune WHERE id > 1;

    RAISE WARNING 'Tabelle pulite';
END $$;

-- ========================================================================
-- STEP 1: Inserimento 100 comuni
-- ========================================================================
INSERT INTO catasto.comune (nome, provincia, regione, codice_catastale, data_istituzione)
SELECT
    'Comune_' || LPAD(n::TEXT, 3, '0'),
    'Savona',
    'Liguria',
    'S' || LPAD(n::TEXT, 3, '0'),
    (CURRENT_DATE - n * INTERVAL '1 day')::DATE
FROM generate_series(1, 100) g(n)
ON CONFLICT (nome) DO NOTHING;

SELECT COUNT(*) AS num_comuni FROM catasto.comune;

-- ========================================================================
-- STEP 2: Inserimento ~20.000 possessori distribuiti sui comuni
-- Usa ROW_NUMBER() per mappare n → id reale del comune
-- (gli id dei comuni possono essere >100 se la sequence è avanzata)
-- ========================================================================
WITH comuni_numerati AS (
    SELECT id, (ROW_NUMBER() OVER (ORDER BY id) - 1) AS rn
    FROM catasto.comune
),
tot AS (SELECT COUNT(*)::INT AS n_comuni FROM catasto.comune)
INSERT INTO catasto.possessore (comune_id, cognome_nome, paternita, nome_completo, attivo)
SELECT
    c.id AS comune_id,
    arr.cognomi[1 + ((g.n - 1) % 10)] || ' ' || arr.nomi[1 + ((g.n - 1) % 10)] AS cognome_nome,
    CASE
        WHEN g.n % 5 = 0 THEN 'fu ' || arr.nomi[1 + ((g.n + 3) % 10)]
        WHEN g.n % 5 = 1 THEN 'di ' || arr.nomi[1 + ((g.n + 7) % 10)]
        ELSE NULL
    END AS paternita,
    arr.cognomi[1 + ((g.n - 1) % 10)] || ' ' || arr.nomi[1 + ((g.n - 1) % 10)]
        || ' (' || LPAD(g.n::TEXT, 5, '0') || ')' AS nome_completo,
    (g.n % 100) < 95 AS attivo
FROM generate_series(1, 20000) g(n)
CROSS JOIN tot
JOIN comuni_numerati c ON c.rn = ((g.n - 1) % tot.n_comuni)
CROSS JOIN (
    SELECT
        ARRAY['Rossi','Bianchi','Verdi','Neri','Russo','Ferrari','Esposito','Gallo','Conti','Rizzo'] AS cognomi,
        ARRAY['Giovanni','Maria','Antonio','Giuseppe','Francesca','Marco','Laura','Paolo','Alessandra','Salvatore'] AS nomi
) arr;

SELECT COUNT(*) AS num_possessori FROM catasto.possessore;

-- ========================================================================
-- STEP 3: Inserimento 4 localita per comune (~400)
-- tipo_id è NOT NULL e FK a tipo_localita (Regione/Via/Borgata/Altro)
-- ========================================================================
-- Assicura l'esistenza dei tipi di default (idempotente)
INSERT INTO catasto.tipo_localita (nome) VALUES
    ('Regione'), ('Via'), ('Borgata'), ('Altro')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO catasto.localita (comune_id, nome, tipologia_stradale, tipo_id)
SELECT
    c.id AS comune_id,
    arr.tipi_descr[1 + ((s.idx - 1) % 3)] || ' ' || arr.nomi_strade[1 + ((c.id + s.idx - 1) % 30)]
        || CASE WHEN s.idx > 3 THEN ' ' || s.idx::TEXT ELSE '' END AS nome,
    arr.tipi_descr[1 + ((s.idx - 1) % 3)] AS tipologia_stradale,
    tl.id AS tipo_id
FROM catasto.comune c
CROSS JOIN generate_series(1, 4) s(idx)
CROSS JOIN (
    SELECT
        ARRAY['Via','Piazza','Corso'] AS tipi_descr,
        ARRAY[
            'Roma','Milano','Torino','Genova','Venezia','Firenze','Napoli',
            'Bari','Palermo','Bologna','Verona','Messina','Padova','Trieste',
            'Brescia','Perugia','Ravenna','Livorno','Taranto','Reggio Calabria',
            'Ancona','Parma','L''Aquila','Alessandria','Monza','Asti','Como',
            'Lecce','Foggia','Pisa'
        ] AS nomi_strade,
        -- Mappa s.idx -> uno dei tipi di tipo_localita
        ARRAY['Via','Borgata','Regione','Altro'] AS tipi_fk
) arr
JOIN catasto.tipo_localita tl ON tl.nome = arr.tipi_fk[1 + ((s.idx - 1) % 4)]
ON CONFLICT (comune_id, nome) DO NOTHING;

SELECT COUNT(*) AS num_localita FROM catasto.localita;

-- ========================================================================
-- STEP 4: Inserimento ~100.000 partite (1000 per comune)
-- ========================================================================
INSERT INTO catasto.partita (comune_id, numero_partita, data_impianto, stato, tipo)
SELECT
    c.id AS comune_id,
    g.n AS numero_partita,
    (CURRENT_DATE - (RANDOM() * 18250)::INT * INTERVAL '1 day')::DATE AS data_impianto,
    CASE WHEN RANDOM() < 0.95 THEN 'attiva' ELSE 'inattiva' END AS stato,
    CASE WHEN RANDOM() < 0.85 THEN 'principale' ELSE 'secondaria' END AS tipo
FROM catasto.comune c
CROSS JOIN generate_series(1, 1000) g(n);

SELECT COUNT(*) AS num_partite FROM catasto.partita;

-- ========================================================================
-- STEP 5: Legami PARTITA <-> POSSESSORE (~1.2 per partita)
-- Un possessore casuale nello stesso comune della partita
-- ========================================================================
INSERT INTO catasto.partita_possessore (partita_id, possessore_id, tipo_partita, titolo, quota)
SELECT DISTINCT ON (partita_id, possessore_id)
    partita_id, possessore_id, tipo_partita, titolo, quota
FROM (
    SELECT
        p.id AS partita_id,
        (
            SELECT pos.id FROM catasto.possessore pos
            WHERE pos.comune_id = p.comune_id
            ORDER BY RANDOM()
            LIMIT 1
        ) AS possessore_id,
        CASE WHEN RANDOM() < 0.9 THEN 'principale' ELSE 'secondaria' END AS tipo_partita,
        CASE
            WHEN RANDOM() < 0.70 THEN 'proprietà esclusiva'
            WHEN RANDOM() < 0.85 THEN 'usufruttuario'
            WHEN RANDOM() < 0.95 THEN 'conduttore'
            ELSE 'altro diritto'
        END AS titolo,
        CASE
            WHEN RANDOM() < 0.3 THEN
                LPAD(((RANDOM() * 99 + 1)::INT)::TEXT, 2, '0') || '/'
                || LPAD(((RANDOM() * 99 + 1)::INT)::TEXT, 2, '0')
            ELSE NULL
        END AS quota
    FROM catasto.partita p
) t
WHERE possessore_id IS NOT NULL;

SELECT COUNT(*) AS num_legami FROM catasto.partita_possessore;

-- ========================================================================
-- STEP 6: Inserimento immobili (1 per partita, ~100.000)
-- Una localita casuale nello stesso comune della partita
-- ========================================================================
INSERT INTO catasto.immobile (partita_id, localita_id, natura, numero_piani, numero_vani, classificazione)
SELECT
    p.id AS partita_id,
    (
        SELECT l.id FROM catasto.localita l
        WHERE l.comune_id = p.comune_id
        ORDER BY RANDOM()
        LIMIT 1
    ) AS localita_id,
    CASE
        WHEN r < 0.40 THEN 'abitazione'
        WHEN r < 0.60 THEN 'negozio'
        WHEN r < 0.75 THEN 'terreno'
        WHEN r < 0.85 THEN 'cantina'
        WHEN r < 0.92 THEN 'garage'
        ELSE 'magazzino'
    END AS natura,
    CASE WHEN RANDOM() < 0.7 THEN (RANDOM() * 5 + 1)::INT ELSE NULL END AS numero_piani,
    CASE WHEN RANDOM() < 0.7 THEN (RANDOM() * 15 + 1)::INT ELSE NULL END AS numero_vani,
    CASE
        WHEN r < 0.3 THEN 'Prima categoria (A1-A8)'
        WHEN r < 0.6 THEN 'Seconda categoria (B1-B8)'
        WHEN r < 0.8 THEN 'Terza categoria (C1-C7)'
        WHEN r < 0.9 THEN 'Quarta categoria (D1-D10)'
        ELSE 'Quinta categoria (E)'
    END AS classificazione
FROM (SELECT id, comune_id, RANDOM() AS r FROM catasto.partita) p
WHERE EXISTS (SELECT 1 FROM catasto.localita l WHERE l.comune_id = p.comune_id);

SELECT COUNT(*) AS num_immobili FROM catasto.immobile;

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

    RAISE WARNING '========================================================================';
    RAISE WARNING 'DATI DI PERFORMANCE TESTING INSERITI CON SUCCESSO';
    RAISE WARNING '========================================================================';
    RAISE WARNING 'Comuni:             %', num_comuni;
    RAISE WARNING 'Possessori:         %', num_possessori;
    RAISE WARNING 'Localita:           %', num_localita;
    RAISE WARNING 'Partite:            %', num_partite;
    RAISE WARNING 'Legami P-P:         %', num_legami;
    RAISE WARNING 'Immobili:           %', num_immobili;
    RAISE WARNING '------------------------------------------------------------------------';
    RAISE WARNING 'Possessori/Comune:  %', (num_possessori / NULLIF(num_comuni, 0))::INT;
    RAISE WARNING 'Partite/Comune:     %', (num_partite / NULLIF(num_comuni, 0))::INT;
    RAISE WARNING 'Immobili/Comune:    %', (num_immobili / NULLIF(num_comuni, 0))::INT;
    RAISE WARNING 'Localita/Comune:    %', (num_localita / NULLIF(num_comuni, 0))::INT;
    RAISE WARNING '========================================================================';
    RAISE WARNING 'READY FOR PERFORMANCE TESTING';
    RAISE WARNING '========================================================================';
END $$;

-- ========================================================================
-- STEP 8: VACUUM + ANALYZE
-- ========================================================================
VACUUM ANALYZE catasto.comune;
VACUUM ANALYZE catasto.possessore;
VACUUM ANALYZE catasto.localita;
VACUUM ANALYZE catasto.partita;
VACUUM ANALYZE catasto.partita_possessore;
VACUUM ANALYZE catasto.immobile;

-- ========================================================================
-- STEP 9: Query di benchmark (EXPLAIN ANALYZE)
-- ========================================================================
EXPLAIN ANALYZE SELECT COUNT(*) FROM catasto.partita WHERE stato = 'attiva';
EXPLAIN ANALYZE SELECT COUNT(*) FROM catasto.possessore WHERE attivo = TRUE;
EXPLAIN ANALYZE
    SELECT COUNT(*) FROM catasto.immobile i
    JOIN catasto.partita p ON i.partita_id = p.id
    WHERE p.comune_id = 1;
EXPLAIN ANALYZE
    SELECT DISTINCT p.id FROM catasto.partita_possessore pp
    JOIN catasto.partita p ON pp.partita_id = p.id
    JOIN catasto.possessore pos ON pp.possessore_id = pos.id
    WHERE pos.nome_completo ILIKE '%Rossi%' LIMIT 100;

DO $$ BEGIN RAISE WARNING 'Script completato. Dati pronti per performance testing.'; END $$;
