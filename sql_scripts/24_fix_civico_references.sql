-- File: 24_fix_civico_references.sql
-- Oggetto: Correzione riferimenti alla colonna 'civico' rimossa in script 22
-- Data: 05/05/2026
-- Note: La colonna localita.civico è stata rimossa in 22_drop_civico_localita.sql.
--       Questo script aggiorna le funzioni che ancora la referenziavano.

SET search_path TO catasto, public;

-- ========================================================================
-- 1. Funzione search_all_entities_fuzzy (03_funzioni-procedure.sql)
--    Rimossa 'civico' dal jsonb_build_object della sezione Località
-- ========================================================================
DROP FUNCTION IF EXISTS search_all_entities_fuzzy(text,real,boolean,boolean,boolean,boolean,boolean,boolean,integer);

CREATE OR REPLACE FUNCTION search_all_entities_fuzzy(
    query_text TEXT,
    similarity_threshold REAL DEFAULT 0.3,
    search_possessori BOOLEAN DEFAULT TRUE,
    search_localita BOOLEAN DEFAULT TRUE,
    search_immobili BOOLEAN DEFAULT FALSE,
    search_variazioni BOOLEAN DEFAULT FALSE,
    search_contratti BOOLEAN DEFAULT FALSE,
    search_partite BOOLEAN DEFAULT FALSE,
    max_results_per_type INTEGER DEFAULT 30
)
RETURNS TABLE (
    entity_type TEXT,
    entity_id INTEGER,
    display_text TEXT,
    detail_text TEXT,
    similarity_score REAL,
    search_field TEXT,
    additional_info JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_limit(similarity_threshold);

    RETURN QUERY

    -- Possessori
    (SELECT
        'possessore'::TEXT,
        p.id,
        p.nome_completo::TEXT,
        CONCAT(p.cognome_nome, ' - ', c.nome)::TEXT,
        similarity(p.nome_completo, query_text),
        'nome_completo'::TEXT,
        jsonb_build_object(
            'paternita', p.paternita,
            'comune', c.nome,
            'attivo', p.attivo
        )
    FROM possessore p
    JOIN comune c ON p.comune_id = c.id
    WHERE search_possessori AND p.nome_completo % query_text
    ORDER BY similarity(p.nome_completo, query_text) DESC, p.id
    LIMIT max_results_per_type)

    UNION ALL

    -- Località
    (SELECT
        'localita'::TEXT,
        l.id,
        l.nome::TEXT,
        CONCAT(COALESCE(tl.nome, ''), ' ', l.nome, ' - ', c.nome)::TEXT,
        similarity(l.nome, query_text),
        'nome'::TEXT,
        jsonb_build_object(
            'tipo', tl.nome,
            'comune', c.nome
        )
    FROM localita l
    JOIN comune c ON l.comune_id = c.id
    LEFT JOIN tipo_localita tl ON l.tipo_id = tl.id
    WHERE search_localita AND l.nome % query_text
    ORDER BY similarity(l.nome, query_text) DESC, l.id
    LIMIT max_results_per_type)

    UNION ALL

    -- Immobili
    (SELECT
        'immobile'::TEXT,
        i.id,
        i.natura::TEXT,
        CONCAT('Partita ', p.numero_partita,
               CASE WHEN p.suffisso_partita IS NOT NULL AND p.suffisso_partita != ''
                    THEN CONCAT('/', p.suffisso_partita)
                    ELSE '' END,
               ' - ', l.nome, ' - ', c.nome)::TEXT,
        similarity(i.natura, query_text),
        'natura'::TEXT,
        jsonb_build_object(
            'partita', p.numero_partita,
            'suffisso_partita', COALESCE(p.suffisso_partita, ''),
            'localita', l.nome,
            'comune', c.nome,
            'classificazione', i.classificazione,
            'consistenza', i.consistenza
        )
    FROM immobile i
    JOIN partita p ON i.partita_id = p.id
    JOIN localita l ON i.localita_id = l.id
    JOIN comune c ON p.comune_id = c.id
    WHERE search_immobili AND i.natura % query_text
    ORDER BY similarity(i.natura, query_text) DESC, i.id
    LIMIT max_results_per_type * 2);

END;
$$;

-- ========================================================================
-- 2. Funzione esporta_partita_json (12_procedure_crud.sql)
--    Rimossa 'civico' dal SELECT degli immobili
-- ========================================================================
CREATE OR REPLACE FUNCTION catasto.esporta_partita_json(p_partita_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_partita_details jsonb;
    v_possessori jsonb;
    v_immobili jsonb;
    v_variazioni jsonb;
BEGIN
    -- Dettagli Partita
    SELECT to_jsonb(p.*) || jsonb_build_object('comune_nome', c.nome)
    INTO v_partita_details
    FROM catasto.partita p
    JOIN catasto.comune c ON p.comune_id = c.id
    WHERE p.id = p_partita_id;

    -- Possessori
    SELECT jsonb_agg(to_jsonb(poss_data))
    INTO v_possessori
    FROM (
        SELECT pos.id, pos.nome_completo, pp.titolo, pp.quota
        FROM catasto.possessore pos
        JOIN catasto.partita_possessore pp ON pos.id = pp.possessore_id
        WHERE pp.partita_id = p_partita_id
        ORDER BY pos.nome_completo
    ) AS poss_data;

    -- Immobili (senza civico, rimosso in script 22)
    SELECT jsonb_agg(to_jsonb(imm_data))
    INTO v_immobili
    FROM (
        SELECT i.id, i.natura, l.nome as localita_nome, i.classificazione, i.consistenza
        FROM catasto.immobile i
        JOIN catasto.localita l ON i.localita_id = l.id
        WHERE i.partita_id = p_partita_id
    ) AS imm_data;

    -- Variazioni
    SELECT jsonb_agg(to_jsonb(var_data))
    INTO v_variazioni
    FROM (
        SELECT v.*, con.tipo as contratto_tipo, con.data_contratto, con.notaio
        FROM catasto.variazione v
        LEFT JOIN catasto.contratto con ON v.id = con.variazione_id
        WHERE v.partita_origine_id = p_partita_id OR v.partita_destinazione_id = p_partita_id
        ORDER BY v.data_variazione
    ) AS var_data;

    RETURN jsonb_build_object(
        'partita', COALESCE(v_partita_details, '{}'::jsonb),
        'possessori', COALESCE(v_possessori, '[]'::jsonb),
        'immobili', COALESCE(v_immobili, '[]'::jsonb),
        'variazioni', COALESCE(v_variazioni, '[]'::jsonb)
    );
END;
$function$;

-- ========================================================================
-- 3. Funzione genera_report_proprieta (14_report_functions.sql)
--    Rimossa 'civico' dal SELECT e dalla logica di visualizzazione
-- ========================================================================
CREATE OR REPLACE FUNCTION genera_report_proprieta(p_partita_id INTEGER)
RETURNS TEXT AS $$
DECLARE
    v_partita partita%ROWTYPE;
    v_comune_nome comune.nome%TYPE;
    v_report TEXT := '';
    v_immobile RECORD;
    v_record RECORD;
BEGIN
    SELECT * INTO v_partita FROM partita WHERE id = p_partita_id;
    IF NOT FOUND THEN RETURN 'Partita con ID ' || p_partita_id || ' non trovata'; END IF;
    SELECT nome INTO v_comune_nome FROM comune WHERE id = v_partita.comune_id;

    v_report := '============================================================' || E'\n';
    v_report := v_report || '                REPORT PROPRIETA IMMOBILIARE' || E'\n';
    v_report := v_report || '                     CATASTO STORICO ANNI ''50' || E'\n';
    v_report := v_report || '============================================================' || E'\n\n';

    v_report := v_report || 'COMUNE: ' || v_comune_nome || E'\n';
    v_report := v_report || 'PARTITA N.: ' || v_partita.numero_partita || E'\n';
    v_report := v_report || 'TIPO: ' || v_partita.tipo || E'\n';
    v_report := v_report || 'DATA IMPIANTO: ' || COALESCE(v_partita.data_impianto::TEXT, 'N/D') || E'\n';
    v_report := v_report || 'STATO: ' || v_partita.stato || E'\n';
    IF v_partita.data_chiusura IS NOT NULL THEN v_report := v_report || 'DATA CHIUSURA: ' || v_partita.data_chiusura::TEXT || E'\n'; END IF;
    IF v_partita.numero_provenienza IS NOT NULL THEN v_report := v_report || 'PROVENIENZA: Partita n. ' || v_partita.numero_provenienza || E'\n'; END IF;
    v_report := v_report || E'\n';

    v_report := v_report || '-------------------- INTESTATARI --------------------' || E'\n';
    FOR v_record IN SELECT pos.nome_completo, pp.titolo, pp.quota FROM partita_possessore pp JOIN possessore pos ON pp.possessore_id = pos.id WHERE pp.partita_id = p_partita_id ORDER BY pos.nome_completo LOOP
        v_report := v_report || '- ' || v_record.nome_completo;
        IF v_record.titolo = 'comproprieta' AND v_record.quota IS NOT NULL THEN v_report := v_report || ' (quota: ' || v_record.quota || ')'; END IF;
        v_report := v_report || E'\n';
    END LOOP;
    v_report := v_report || E'\n';

    v_report := v_report || '-------------------- IMMOBILI --------------------' || E'\n';
    FOR v_immobile IN SELECT i.id, i.natura, i.numero_piani, i.numero_vani, i.consistenza, i.classificazione, l.tipologia_stradale AS tipo_localita, l.nome AS nome_localita FROM immobile i JOIN localita l ON i.localita_id = l.id WHERE i.partita_id = p_partita_id ORDER BY l.nome, i.natura LOOP
        v_report := v_report || 'Immobile ID: ' || v_immobile.id || E'\n';
        v_report := v_report || '  Natura: ' || COALESCE(v_immobile.natura, 'N/D') || E'\n';
        v_report := v_report || '  Localita: ' || COALESCE(v_immobile.nome_localita, 'N/D') || ' (' || COALESCE(v_immobile.tipo_localita, 'N/D') || ')' || E'\n';
        IF v_immobile.numero_piani IS NOT NULL THEN v_report := v_report || '  Piani: ' || v_immobile.numero_piani || E'\n'; END IF;
        IF v_immobile.numero_vani IS NOT NULL THEN v_report := v_report || '  Vani: ' || v_immobile.numero_vani || E'\n'; END IF;
        IF v_immobile.consistenza IS NOT NULL THEN v_report := v_report || '  Consistenza: ' || v_immobile.consistenza || E'\n'; END IF;
        IF v_immobile.classificazione IS NOT NULL THEN v_report := v_report || '  Classificazione: ' || v_immobile.classificazione || E'\n'; END IF;
        v_report := v_report || E'\n';
    END LOOP;

    v_report := v_report || '-------------------- VARIAZIONI --------------------' || E'\n';
    FOR v_record IN SELECT v.tipo, v.data_variazione, v.numero_riferimento, p2.numero_partita AS partita_destinazione_numero, c2.nome AS partita_destinazione_comune, con.tipo AS tipo_contratto, con.data_contratto, con.notaio, con.repertorio FROM variazione v LEFT JOIN partita p2 ON v.partita_destinazione_id = p2.id LEFT JOIN comune c2 ON p2.comune_id = c2.id LEFT JOIN contratto con ON v.id = con.variazione_id WHERE v.partita_origine_id = p_partita_id ORDER BY v.data_variazione DESC LOOP
        v_report := v_report || 'Variazione: ' || COALESCE(v_record.tipo, 'N/D') || ' del ' || COALESCE(v_record.data_variazione::TEXT, 'N/D') || E'\n';
        IF v_record.partita_destinazione_numero IS NOT NULL THEN
            v_report := v_report || '  Nuova partita: ' || v_record.partita_destinazione_numero;
            v_report := v_report || ' (Comune: ' || COALESCE(v_record.partita_destinazione_comune, 'N/D') || ')';
            v_report := v_report || E'\n'; END IF;
        IF v_record.tipo_contratto IS NOT NULL THEN
            v_report := v_report || '  Contratto: ' || v_record.tipo_contratto || ' del ' || COALESCE(v_record.data_contratto::TEXT, 'N/D') || E'\n';
            IF v_record.notaio IS NOT NULL THEN v_report := v_report || '  Notaio: ' || v_record.notaio || E'\n'; END IF;
            IF v_record.repertorio IS NOT NULL THEN v_report := v_report || '  Repertorio: ' || v_record.repertorio || E'\n'; END IF;
        END IF;
        v_report := v_report || E'\n';
    END LOOP;

    v_report := v_report || '============================================================' || E'\n';
    v_report := v_report || 'Report generato il: ' || CURRENT_DATE || E'\n';
    v_report := v_report || 'Il presente report ha valore puramente storico e documentale.' || E'\n';
    v_report := v_report || '============================================================' || E'\n';
    RETURN v_report;
END;
$$ LANGUAGE plpgsql;

SELECT 'Migrazione 24 applicata con successo: riferimenti a civico rimossi dalle funzioni.' AS status;
