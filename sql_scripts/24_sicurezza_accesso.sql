-- =============================================================================
-- Script 24: Sicurezza Accesso — Lockout e Password Policy
-- Versione 1.3.0 — Fase 1
-- =============================================================================
-- Aggiunge colonne di sicurezza alla tabella utente e crea le tabelle
-- password_history e config_sicurezza.
-- Sicuro da eseguire più volte grazie ad IF NOT EXISTS / ON CONFLICT DO NOTHING.
-- =============================================================================

-- 1. Colonne aggiuntive sulla tabella utente
ALTER TABLE catasto.utente
    ADD COLUMN IF NOT EXISTS failed_attempts      INT          NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS password_changed_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS password_must_change BOOLEAN      NOT NULL DEFAULT FALSE;

-- 2. Storico password (impedisce riuso degli ultimi N hash)
CREATE TABLE IF NOT EXISTS catasto.password_history (
    id            SERIAL PRIMARY KEY,
    utente_id     INT         NOT NULL REFERENCES catasto.utente(id) ON DELETE CASCADE,
    password_hash TEXT        NOT NULL,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_history_utente
    ON catasto.password_history (utente_id, changed_at DESC);

-- 3. Tabella configurazione sicurezza (chiave/valore, modificabile da admin)
CREATE TABLE IF NOT EXISTS catasto.config_sicurezza (
    chiave  TEXT PRIMARY KEY,
    valore  TEXT NOT NULL,
    note    TEXT
);

INSERT INTO catasto.config_sicurezza (chiave, valore, note) VALUES
    ('max_tentativi_falliti',  '5',  'Tentativi falliti consecutivi prima del blocco temporaneo'),
    ('durata_blocco_minuti',   '15', 'Durata del blocco in minuti dopo troppi tentativi falliti'),
    ('min_lunghezza_password', '12', 'Lunghezza minima della password'),
    ('storico_password',       '5',  'Numero di password precedenti che non possono essere riusate'),
    ('richiedi_maiuscole',     '1',  '1 = richiede almeno una lettera maiuscola'),
    ('richiedi_numeri',        '1',  '1 = richiede almeno un numero'),
    ('richiedi_speciali',      '1',  '1 = richiede almeno un carattere speciale (!@#$%^&*...)')
ON CONFLICT (chiave) DO NOTHING;

-- 4. Migra le password esistenti nello storico (prima esecuzione)
INSERT INTO catasto.password_history (utente_id, password_hash, changed_at)
SELECT id, password_hash, COALESCE(data_creazione, NOW())
FROM catasto.utente
WHERE password_hash IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM catasto.password_history ph WHERE ph.utente_id = catasto.utente.id
  );

-- 5. Imposta password_changed_at per utenti esistenti
UPDATE catasto.utente
SET password_changed_at = COALESCE(data_creazione, NOW())
WHERE password_changed_at IS NULL;
