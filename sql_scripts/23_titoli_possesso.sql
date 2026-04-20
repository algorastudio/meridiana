-- File: 23_titoli_possesso.sql
-- Scopo: Tabella gestibile per i titoli di possesso (proprietà, usufrutto, ecc.)
-- Versione: 1.0
-- Data: 20/04/2026

SET search_path TO catasto, public;

DO $$
BEGIN

CREATE TABLE IF NOT EXISTS titolo_possesso (
    id   SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descrizione TEXT
);
RAISE NOTICE 'Tabella titolo_possesso verificata/creata.';

INSERT INTO titolo_possesso (nome) VALUES
    ('proprietà esclusiva'),
    ('comproprietà'),
    ('usufrutto'),
    ('nuda proprietà'),
    ('enfiteusi'),
    ('superficie'),
    ('uso'),
    ('abitazione'),
    ('servitù')
ON CONFLICT (nome) DO NOTHING;
RAISE NOTICE 'Valori di default per titolo_possesso inseriti/verificati.';

END $$;
