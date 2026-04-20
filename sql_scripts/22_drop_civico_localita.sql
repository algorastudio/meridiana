-- Script 22: Rimozione campo civico da localita
-- Il civico viene incorporato nel campo nome (es. "Via Roma 11A")
-- Data: 2026-04-20

BEGIN;

-- 1. Concatena il civico al nome per i record che ce l'hanno
UPDATE catasto.localita
SET nome = TRIM(nome || ' ' || civico::TEXT)
WHERE civico IS NOT NULL
  AND TRIM(civico::TEXT) != ''
  AND TRIM(civico::TEXT) != '0';

-- 2. Rimuovi il UNIQUE constraint che includeva civico
ALTER TABLE catasto.localita
    DROP CONSTRAINT IF EXISTS localita_comune_id_nome_civico_key;

-- 3. Aggiungi nuovo UNIQUE su (comune_id, nome)
ALTER TABLE catasto.localita
    ADD CONSTRAINT localita_comune_id_nome_key UNIQUE (comune_id, nome);

-- 4. Rimuovi la colonna civico
ALTER TABLE catasto.localita DROP COLUMN IF EXISTS civico;

COMMIT;
