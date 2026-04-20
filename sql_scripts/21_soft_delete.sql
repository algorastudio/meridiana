-- ============================================================
-- MIGRAZIONE: Soft Delete per entità principali
-- Archivio di Stato di Savona - Meridiana v1.2
-- ============================================================
-- In un archivio storico i dati non si cancellano fisicamente.
-- Questo script aggiunge il supporto all'archiviazione logica
-- (soft delete) per: comune, partita, possessore, localita.
-- ============================================================

-- 1. COLONNE DI ARCHIVIAZIONE
-- ============================================================

ALTER TABLE catasto.comune
    ADD COLUMN IF NOT EXISTS archiviato BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_archiviazione TIMESTAMPTZ;

ALTER TABLE catasto.partita
    ADD COLUMN IF NOT EXISTS archiviato BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_archiviazione TIMESTAMPTZ;

-- possessore usa già 'attivo' come flag di archiviazione logica;
-- aggiungiamo solo data_archiviazione per coerenza.
ALTER TABLE catasto.possessore
    ADD COLUMN IF NOT EXISTS data_archiviazione TIMESTAMPTZ;

ALTER TABLE catasto.localita
    ADD COLUMN IF NOT EXISTS archiviato BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_archiviazione TIMESTAMPTZ;

COMMENT ON COLUMN catasto.comune.archiviato IS 'Se TRUE il comune è archiviato e non appare nelle ricerche standard.';
COMMENT ON COLUMN catasto.partita.archiviato IS 'Se TRUE la partita è archiviata e non appare nelle ricerche standard.';
COMMENT ON COLUMN catasto.possessore.data_archiviazione IS 'Data in cui attivo è stato impostato a FALSE (archiviazione logica).';
COMMENT ON COLUMN catasto.localita.archiviato IS 'Se TRUE la località è archiviata e non appare nelle ricerche standard.';


-- 2. INDICI PER PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_comune_archiviato    ON catasto.comune(archiviato);
CREATE INDEX IF NOT EXISTS idx_partita_archiviato   ON catasto.partita(archiviato);
CREATE INDEX IF NOT EXISTS idx_possessore_attivo    ON catasto.possessore(attivo);
CREATE INDEX IF NOT EXISTS idx_localita_archiviato  ON catasto.localita(archiviato);


-- 3. STORED PROCEDURES DI ARCHIVIAZIONE
-- ============================================================

CREATE OR REPLACE PROCEDURE catasto.archivia_comune(p_comune_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.comune
    SET archiviato = TRUE,
        data_archiviazione = CURRENT_TIMESTAMP,
        data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_comune_id AND archiviato = FALSE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Comune ID % non trovato oppure già archiviato.', p_comune_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE catasto.archivia_comune IS 'Archivia logicamente un comune (soft delete). Non cancella dati.';


CREATE OR REPLACE PROCEDURE catasto.archivia_partita(p_partita_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.partita
    SET archiviato = TRUE,
        data_archiviazione = CURRENT_TIMESTAMP,
        data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_partita_id AND archiviato = FALSE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partita ID % non trovata oppure già archiviata.', p_partita_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE catasto.archivia_partita IS 'Archivia logicamente una partita (soft delete). Non cancella dati.';


CREATE OR REPLACE PROCEDURE catasto.archivia_possessore(p_possessore_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.possessore
    SET attivo = FALSE,
        data_archiviazione = CURRENT_TIMESTAMP,
        data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_possessore_id AND attivo = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Possessore ID % non trovato oppure già archiviato.', p_possessore_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE catasto.archivia_possessore IS 'Archivia logicamente un possessore impostando attivo=FALSE. Non cancella dati.';


CREATE OR REPLACE PROCEDURE catasto.archivia_localita(p_localita_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.localita
    SET archiviato = TRUE,
        data_archiviazione = CURRENT_TIMESTAMP,
        data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_localita_id AND archiviato = FALSE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Località ID % non trovata oppure già archiviata.', p_localita_id;
    END IF;
END;
$$;

COMMENT ON PROCEDURE catasto.archivia_localita IS 'Archivia logicamente una località (soft delete). Non cancella dati.';


-- 4. PROCEDURE DI RIPRISTINO (per eventuali correzioni)
-- ============================================================

CREATE OR REPLACE PROCEDURE catasto.ripristina_comune(p_comune_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.comune
    SET archiviato = FALSE, data_archiviazione = NULL, data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_comune_id AND archiviato = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Comune ID % non trovato oppure non archiviato.', p_comune_id;
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE catasto.ripristina_partita(p_partita_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.partita
    SET archiviato = FALSE, data_archiviazione = NULL, data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_partita_id AND archiviato = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Partita ID % non trovata oppure non archiviata.', p_partita_id;
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE catasto.ripristina_possessore(p_possessore_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.possessore
    SET attivo = TRUE, data_archiviazione = NULL, data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_possessore_id AND attivo = FALSE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Possessore ID % non trovato oppure non archiviato.', p_possessore_id;
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE catasto.ripristina_localita(p_localita_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE catasto.localita
    SET archiviato = FALSE, data_archiviazione = NULL, data_modifica = CURRENT_TIMESTAMP
    WHERE id = p_localita_id AND archiviato = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Località ID % non trovata oppure non archiviata.', p_localita_id;
    END IF;
END;
$$;
