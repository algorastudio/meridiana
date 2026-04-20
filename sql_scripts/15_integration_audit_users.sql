-- Script: 15_integration_audit_users.sql
-- Oggetto: Integrazione FK audit_log → utente
-- Versione: 1.2
-- Data: 20/04/2026

SET search_path TO catasto, public;

DO $$ BEGIN RAISE NOTICE '--- INIZIO 15_integration_audit_users.sql ---'; END $$;

-- ================================================
-- FK: audit_log.app_user_id → utente(id)
-- ================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_audit_log_app_user_id_utente'
        AND conrelid = 'catasto.audit_log'::regclass
    ) THEN
        ALTER TABLE catasto.audit_log
        ADD CONSTRAINT fk_audit_log_app_user_id_utente
        FOREIGN KEY (app_user_id) REFERENCES catasto.utente(id) ON DELETE SET NULL;
        RAISE NOTICE 'FK fk_audit_log_app_user_id_utente creata.';
    ELSE
        RAISE NOTICE 'FK fk_audit_log_app_user_id_utente già esistente.';
    END IF;
END $$;

DO $$ BEGIN RAISE NOTICE '--- FINE 15_integration_audit_users.sql ---'; END $$;
