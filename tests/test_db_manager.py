#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite completa per CatastoDBManager — v1.2.1
Copertura massima: CRUD, soft delete, validazione, import CSV, ricerca avanzata
"""
import pytest
import psycopg2
from datetime import date

from catasto_db_manager import (
    CatastoDBManager, DBMError, DBUniqueConstraintError,
    DBNotFoundError, DBDataError
)


# ===========================================================================
# Test eccezioni personalizzate
# ===========================================================================

class TestEccezioniDB:
    def test_dbmerror_is_exception(self):
        e = DBMError("test")
        assert isinstance(e, Exception)

    def test_unique_constraint_error_hierarchy(self):
        e = DBUniqueConstraintError("msg", constraint_name="uq_nome", details="det")
        assert isinstance(e, DBMError)
        assert e.constraint_name == "uq_nome"
        assert e.details == "det"

    def test_not_found_error_hierarchy(self):
        e = DBNotFoundError("non trovato")
        assert isinstance(e, DBMError)

    def test_data_error_hierarchy(self):
        e = DBDataError("dato non valido")
        assert isinstance(e, DBMError)


# ===========================================================================
# Test _valida_intervallo_date (business logic centralizzata)
# ===========================================================================

class TestValidazioneDate:
    def test_date_valide_passano(self):
        """Nessuna eccezione se data_fine >= data_inizio"""
        CatastoDBManager._valida_intervallo_date(
            date(1900, 1, 1), date(1950, 6, 15), "Inizio", "Fine"
        )

    def test_stessa_data_passa(self):
        CatastoDBManager._valida_intervallo_date(
            date(1900, 1, 1), date(1900, 1, 1), "Inizio", "Fine"
        )

    def test_date_invertite_sollevano_data_error(self):
        with pytest.raises(DBDataError) as exc:
            CatastoDBManager._valida_intervallo_date(
                date(1950, 1, 1), date(1900, 1, 1), "Inizio", "Fine"
            )
        assert "Fine" in str(exc.value)
        assert "Inizio" in str(exc.value)

    def test_data_inizio_none_passa(self):
        CatastoDBManager._valida_intervallo_date(
            None, date(1950, 1, 1), "Inizio", "Fine"
        )

    def test_data_fine_none_passa(self):
        CatastoDBManager._valida_intervallo_date(
            date(1900, 1, 1), None, "Inizio", "Fine"
        )

    def test_entrambe_none_passano(self):
        CatastoDBManager._valida_intervallo_date(None, None, "Inizio", "Fine")


# ===========================================================================
# Test pool e connessione
# ===========================================================================

class TestPoolConnessione:
    def test_pool_inizialmente_none(self, test_db_setup):
        manager = CatastoDBManager(**test_db_setup)
        assert manager.pool is None

    def test_initialize_main_pool(self, test_db_setup):
        manager = CatastoDBManager(**test_db_setup)
        result = manager.initialize_main_pool()
        if not result:
            pytest.skip("Database di test non disponibile. Salto il test.")
        assert result is True
        assert manager.pool is not None
        manager.close_pool()

    def test_close_pool(self, test_db_setup):
        manager = CatastoDBManager(**test_db_setup)
        if not manager.initialize_main_pool():
            pytest.skip("Database di test non disponibile. Salto il test.")
        manager.close_pool()
        assert manager.pool is None

    def test_initialize_pool_idempotente(self, test_db_setup):
        manager = CatastoDBManager(**test_db_setup)
        if not manager.initialize_main_pool():
            pytest.skip("Database di test non disponibile. Salto il test.")
        manager.initialize_main_pool()  # seconda chiamata non deve fallire
        assert manager.pool is not None
        manager.close_pool()

    def test_query_base_pool(self, db_manager):
        """Verifica che la connessione funzioni."""
        with db_manager._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1


# ===========================================================================
# Test CRUD Comune
# ===========================================================================

class TestComuneCRUD:
    def test_create_comune_successo(self, clean_db):
        cid = clean_db.create_comune("Savona", "SV", "Liguria")
        assert isinstance(cid, int) and cid > 0

    def test_create_comune_campi_obbligatori(self, clean_db):
        with pytest.raises(DBDataError):
            clean_db.create_comune("", "SV", "Liguria")
        with pytest.raises(DBDataError):
            clean_db.create_comune("Savona", "", "Liguria")
        with pytest.raises(DBDataError):
            clean_db.create_comune("Savona", "SV", "")

    def test_create_comune_duplicato(self, clean_db):
        clean_db.create_comune("Duplicato", "SV", "Liguria")
        with pytest.raises(DBUniqueConstraintError):
            clean_db.create_comune("Duplicato", "SV", "Liguria")

    def test_create_comune_con_date_valide(self, clean_db):
        cid = clean_db.create_comune(
            "Comune Storico", "SV", "Liguria",
            data_istituzione=date(1860, 1, 1),
            data_soppressione=date(1946, 12, 31)
        )
        assert cid > 0

    def test_create_comune_date_invertite(self, clean_db):
        with pytest.raises(DBDataError):
            clean_db.create_comune(
                "Errore Date", "SV", "Liguria",
                data_istituzione=date(1950, 1, 1),
                data_soppressione=date(1900, 1, 1)
            )

    def test_get_all_comuni_details(self, clean_db):
        clean_db.create_comune("Alpha", "SV", "Liguria")
        clean_db.create_comune("Beta", "SV", "Liguria")
        comuni = clean_db.get_all_comuni_details()
        assert len(comuni) == 2
        nomi = [c['nome_comune'] for c in comuni]
        assert "Alpha" in nomi and "Beta" in nomi

    def test_get_all_comuni_details_vuoto(self, clean_db):
        comuni = clean_db.get_all_comuni_details()
        assert comuni == []

    def test_get_elenco_comuni_semplice(self, clean_db):
        cid = clean_db.create_comune("Varazze", "SV", "Liguria")
        elenco = clean_db.get_elenco_comuni_semplice()
        assert len(elenco) == 1
        assert elenco[0][0] == cid
        assert elenco[0][1] == "Varazze"

    def test_get_comune_by_id(self, sample_data):
        db = sample_data['db']
        c = db.get_comune_by_id(sample_data['comune_id'])
        assert c is not None
        assert c['nome_comune'] == "Genova Test"
        assert c['provincia'] == "GE"

    def test_get_comune_by_id_non_trovato(self, db_manager):
        assert db_manager.get_comune_by_id(99999999) is None

    def test_get_comune_by_id_invalido(self, db_manager):
        assert db_manager.get_comune_by_id(0) is None
        assert db_manager.get_comune_by_id(-1) is None

    def test_update_comune(self, sample_data):
        db = sample_data['db']
        cid = sample_data['comune_id']
        result = db.update_comune(cid, {'provincia': 'SV', 'note': 'Aggiornato'})
        assert result is True
        c = db.get_comune_by_id(cid)
        assert c['provincia'] == 'SV'

    def test_update_comune_date_invalide(self, sample_data):
        db = sample_data['db']
        with pytest.raises(DBDataError):
            db.update_comune(sample_data['comune_id'], {
                'data_istituzione': date(1950, 1, 1),
                'data_soppressione': date(1900, 1, 1),
            })

    def test_update_comune_non_trovato(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.update_comune(99999999, {'note': 'x'})

    def test_update_comune_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.update_comune(0, {'note': 'x'})

    def test_get_comuni_search(self, clean_db):
        clean_db.create_comune("Genova", "GE", "Liguria")
        clean_db.create_comune("Savona", "SV", "Liguria")
        results = clean_db.get_comuni(search_term="Genova")
        assert len(results) == 1
        assert results[0]['nome'] == "Genova"


# ===========================================================================
# Test soft delete Comune
# ===========================================================================

class TestComuneSoftDelete:
    def test_archivia_comune_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.archivia_comune(0)
        with pytest.raises(DBDataError):
            db_manager.archivia_comune(-5)

    def test_archivia_comune_non_trovato(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.archivia_comune(99999999)

    def test_archivia_comune_esclude_da_ricerca(self, clean_db):
        cid = clean_db.create_comune("Da Archiviare", "SV", "Liguria")
        assert len(clean_db.get_all_comuni_details()) == 1
        clean_db.archivia_comune(cid)
        comuni = clean_db.get_all_comuni_details()
        assert all(c['nome_comune'] != "Da Archiviare" for c in comuni)

    def test_archivia_comune_escluso_da_elenco_semplice(self, clean_db):
        cid = clean_db.create_comune("Archiviato SV", "SV", "Liguria")
        clean_db.archivia_comune(cid)
        elenco = clean_db.get_elenco_comuni_semplice()
        assert all(row[1] != "Archiviato SV" for row in elenco)


# ===========================================================================
# Test CRUD Possessore
# ===========================================================================

class TestPossessoreCRUD:
    def test_create_possessore_successo(self, sample_data):
        db = sample_data['db']
        pid = db.create_possessore(
            nome_completo="BIANCHI LUIGI fu Marco",
            comune_riferimento_id=sample_data['comune_id'],
            cognome_nome="BIANCHI LUIGI"
        )
        assert isinstance(pid, int) and pid > 0

    def test_create_possessore_duplicato(self, sample_data):
        db = sample_data['db']
        db.create_possessore(
            nome_completo="DUPLICATO TEST",
            comune_riferimento_id=sample_data['comune_id']
        )
        with pytest.raises(DBUniqueConstraintError):
            db.create_possessore(
                nome_completo="DUPLICATO TEST",
                comune_riferimento_id=sample_data['comune_id']
            )

    def test_get_possessore_full_details(self, sample_data):
        db = sample_data['db']
        p = db.get_possessore_full_details(sample_data['possessore1_id'])
        assert p is not None
        assert p['nome_completo'] == "ROSSI MARIO fu Giovanni"
        assert 'attivo' in p

    def test_get_possessore_full_details_non_trovato(self, db_manager):
        assert db_manager.get_possessore_full_details(99999999) is None

    def test_get_possessore_full_details_id_invalido(self, db_manager):
        assert db_manager.get_possessore_full_details(0) is None

    def test_get_possessori_by_comune(self, sample_data):
        db = sample_data['db']
        possessori = db.get_possessori_by_comune(sample_data['comune_id'])
        assert len(possessori) >= 1
        assert any(p['nome_completo'] == "ROSSI MARIO fu Giovanni" for p in possessori)

    def test_get_possessori_by_comune_con_filtro(self, sample_data):
        db = sample_data['db']
        db.create_possessore("VERDI GIUSEPPE", sample_data['comune_id'])
        results = db.get_possessori_by_comune(sample_data['comune_id'], filter_text="VERDI")
        assert len(results) >= 1
        assert all("VERDI" in p['nome_completo'] for p in results)

    def test_get_possessori_by_comune_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.get_possessori_by_comune(0)

    def test_update_possessore(self, sample_data):
        db = sample_data['db']
        pid = sample_data['possessore1_id']
        result = db.update_possessore(pid, {'paternita': 'fu Antonio'})
        assert result is True
        p = db.get_possessore_full_details(pid)
        assert p['paternita'] == 'fu Antonio'

    def test_update_possessore_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.update_possessore(0, {'paternita': 'x'})

    def test_update_possessore_non_trovato(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.update_possessore(99999999, {'paternita': 'x'})

    def test_search_possessori_globally(self, sample_data):
        db = sample_data['db']
        results = db.search_possessori_by_term_globally("ROSSI")
        assert len(results) >= 1
        assert any("ROSSI" in r['nome_completo'] for r in results)

    def test_search_possessori_globally_nessun_risultato(self, sample_data):
        db = sample_data['db']
        results = db.search_possessori_by_term_globally("ZZZNOMETROVATO999")
        assert isinstance(results, list)
        assert len(results) == 0


# ===========================================================================
# Test soft delete Possessore
# ===========================================================================

class TestPossessoreSoftDelete:
    def test_archivia_possessore_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.archivia_possessore(0)
        with pytest.raises(DBDataError):
            db_manager.archivia_possessore(-1)

    def test_archivia_possessore_non_trovato(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.archivia_possessore(99999999)

    def test_archivia_possessore_escluso_da_ricerca(self, sample_data):
        db = sample_data['db']
        pid = sample_data['possessore1_id']
        cid = sample_data['comune_id']
        assert len(db.get_possessori_by_comune(cid)) >= 1
        db.archivia_possessore(pid)
        possessori = db.get_possessori_by_comune(cid)
        assert all(p['id'] != pid for p in possessori)

    def test_archivia_possessore_escluso_da_ricerca_globale(self, sample_data):
        db = sample_data['db']
        pid = sample_data['possessore1_id']
        db.archivia_possessore(pid)
        results = db.search_possessori_by_term_globally("ROSSI")
        assert all(r['id'] != pid for r in results)


# ===========================================================================
# Test CRUD Partita
# ===========================================================================

class TestPartitaCRUD:
    def test_create_partita_successo(self, sample_data):
        db = sample_data['db']
        pid = db.create_partita(
            comune_id=sample_data['comune_id'],
            numero_partita=200,
            tipo='principale',
            stato='attiva',
            data_impianto=date(1920, 3, 15)
        )
        assert isinstance(pid, int) and pid > 0

    def test_create_partita_numero_duplicato(self, sample_data):
        db = sample_data['db']
        with pytest.raises((DBUniqueConstraintError, DBMError)):
            db.create_partita(
                comune_id=sample_data['comune_id'],
                numero_partita=100,  # già esiste in sample_data
                tipo='secondaria',
                stato='attiva',
                data_impianto=date(1920, 1, 1)
            )

    def test_create_partita_date_invertite(self, sample_data):
        with pytest.raises(DBDataError):
            sample_data['db'].create_partita(
                comune_id=sample_data['comune_id'],
                numero_partita=300,
                tipo='principale',
                stato='attiva',
                data_impianto=date(1950, 1, 1),
                data_chiusura=date(1900, 1, 1)
            )

    def test_get_partita_details(self, sample_data):
        db = sample_data['db']
        p = db.get_partita_details(sample_data['partita_id'])
        assert p is not None
        assert p['numero_partita'] == 100
        assert 'possessori' in p
        assert 'immobili' in p
        assert 'variazioni' in p

    def test_get_partita_details_non_trovata(self, db_manager):
        assert db_manager.get_partita_details(99999999) is None

    def test_get_partita_details_id_invalido(self, db_manager):
        assert db_manager.get_partita_details(0) is None

    def test_get_partite_by_comune(self, sample_data):
        db = sample_data['db']
        partite = db.get_partite_by_comune(sample_data['comune_id'])
        assert len(partite) >= 1
        assert any(p['numero_partita'] == 100 for p in partite)

    def test_get_partite_by_comune_con_filtro(self, sample_data):
        db = sample_data['db']
        db.create_partita(sample_data['comune_id'], 201, 'secondaria', 'attiva', date(1920, 1, 1))
        partite = db.get_partite_by_comune(sample_data['comune_id'], filter_text="secondaria")
        assert all('secondaria' in p.get('tipo', '') for p in partite)

    def test_update_partita(self, sample_data):
        db = sample_data['db']
        pid = sample_data['partita_id']
        result = db.update_partita(pid, {'stato': 'inattiva', 'data_chiusura': date(1950, 12, 31)})
        assert result is True
        p = db.get_partita_details(pid)
        assert p['stato'] == 'inattiva'

    def test_update_partita_date_invertite(self, sample_data):
        db = sample_data['db']
        with pytest.raises(DBDataError):
            db.update_partita(sample_data['partita_id'], {
                'data_impianto': date(1950, 1, 1),
                'data_chiusura': date(1900, 1, 1),
            })

    def test_update_partita_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.update_partita(0, {'stato': 'chiusa'})

    def test_update_partita_non_trovata(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.update_partita(99999999, {'stato': 'chiusa'})

    def test_search_partite_per_comune(self, sample_data):
        db = sample_data['db']
        results = db.search_partite(comune_id=sample_data['comune_id'])
        assert len(results) >= 1
        assert all(r['comune_nome'] == "Genova Test" for r in results)

    def test_search_partite_per_numero(self, sample_data):
        db = sample_data['db']
        results = db.search_partite(numero_partita=100)
        assert len(results) >= 1
        assert all(r['numero_partita'] == 100 for r in results)

    def test_search_partite_nessun_risultato(self, sample_data):
        db = sample_data['db']
        results = db.search_partite(numero_partita=999999)
        assert results == []


# ===========================================================================
# Test soft delete Partita
# ===========================================================================

class TestPartitaSoftDelete:
    def test_archivia_partita_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.archivia_partita(0)
        with pytest.raises(DBDataError):
            db_manager.archivia_partita(-1)

    def test_archivia_partita_non_trovata(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.archivia_partita(99999999)

    def test_archivia_partita_esclusa_da_search(self, sample_data):
        db = sample_data['db']
        pid = sample_data['partita_id']
        cid = sample_data['comune_id']
        db.archivia_partita(pid)
        results = db.search_partite(comune_id=cid)
        assert all(r['id'] != pid for r in results)


# ===========================================================================
# Test TipoLocalita
# ===========================================================================

class TestTipoLocalita:
    def test_get_tipi_localita_restituisce_lista(self, db_manager):
        tipi = db_manager.get_tipi_localita()
        assert isinstance(tipi, list)

    def test_crea_tipo_localita(self, db_manager):
        import uuid
        nome_unico = f"TipoTest_{uuid.uuid4().hex[:8]}"
        tid = db_manager.gestisci_tipo_localita(None, nome_unico)
        assert isinstance(tid, int) and tid > 0
        # Cleanup
        db_manager.elimina_tipo_localita(tid)

    def test_crea_tipo_localita_nome_vuoto(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.gestisci_tipo_localita(None, "")

    def test_aggiorna_tipo_localita(self, db_manager):
        import uuid
        nome = f"TipoUpdate_{uuid.uuid4().hex[:8]}"
        tid = db_manager.gestisci_tipo_localita(None, nome)
        nuovo_nome = f"TipoUpdateNuovo_{uuid.uuid4().hex[:8]}"
        tid2 = db_manager.gestisci_tipo_localita(tid, nuovo_nome, "descrizione aggiornata")
        assert tid2 == tid
        # Cleanup
        db_manager.elimina_tipo_localita(tid)

    def test_elimina_tipo_localita_non_usato(self, db_manager):
        import uuid
        tid = db_manager.gestisci_tipo_localita(None, f"TipoDaEliminare_{uuid.uuid4().hex[:8]}")
        result = db_manager.elimina_tipo_localita(tid)
        assert result is True

    def test_elimina_tipo_localita_in_uso(self, sample_data):
        db = sample_data['db']
        tid = sample_data['tipo_localita_id']
        # Il tipo è usato da localita_id, quindi non può essere eliminato
        with pytest.raises(DBMError):
            db.elimina_tipo_localita(tid)


# ===========================================================================
# Test CRUD Localita
# ===========================================================================

class TestLocalitaCRUD:
    def test_create_localita_successo(self, sample_data):
        db = sample_data['db']
        lid = db.create_localita(
            comune_id=sample_data['comune_id'],
            nome="Contrada Vecchia",
            tipo_id=sample_data['tipo_localita_id']
        )
        assert isinstance(lid, int) and lid > 0

    def test_create_localita_parametri_invalidi(self, sample_data):
        db = sample_data['db']
        with pytest.raises(DBDataError):
            db.create_localita(0, "Test", sample_data['tipo_localita_id'])
        with pytest.raises(DBDataError):
            db.create_localita(sample_data['comune_id'], "", sample_data['tipo_localita_id'])
        with pytest.raises(DBDataError):
            db.create_localita(sample_data['comune_id'], "Test", 0)

    def test_create_localita_upsert(self, sample_data):
        """create_localita deve restituire l'ID esistente in caso di conflitto."""
        db = sample_data['db']
        cid = sample_data['comune_id']
        tid = sample_data['tipo_localita_id']
        lid1 = db.create_localita(cid, "Via Upsert", tid)
        lid2 = db.create_localita(cid, "Via Upsert", tid)
        assert lid1 == lid2

    def test_get_localita_by_comune(self, sample_data):
        db = sample_data['db']
        localita = db.get_localita_by_comune(sample_data['comune_id'])
        assert len(localita) >= 1
        assert any(l['nome'] == "Via Roma" for l in localita)

    def test_get_localita_by_comune_con_filtro(self, sample_data):
        db = sample_data['db']
        db.create_localita(sample_data['comune_id'], "Via Garibaldi", sample_data['tipo_localita_id'])
        results = db.get_localita_by_comune(sample_data['comune_id'], filter_text="Garibaldi")
        assert len(results) == 1
        assert results[0]['nome'] == "Via Garibaldi"

    def test_get_localita_by_comune_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.get_localita_by_comune(0)

    def test_get_localita_details(self, sample_data):
        db = sample_data['db']
        l = db.get_localita_details(sample_data['localita_id'])
        assert l is not None
        assert l['id'] == sample_data['localita_id']

    def test_update_localita(self, sample_data):
        db = sample_data['db']
        lid = sample_data['localita_id']
        result = db.update_localita(lid, {'nome': 'Via Roma Aggiornata'})
        assert result is True

    def test_update_localita_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.update_localita(0, {'nome': 'x'})

    def test_update_localita_non_trovata(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.update_localita(99999999, {'nome': 'x'})


# ===========================================================================
# Test soft delete Localita
# ===========================================================================

class TestLocalitaSoftDelete:
    def test_archivia_localita_id_invalido(self, db_manager):
        with pytest.raises(DBDataError):
            db_manager.archivia_localita(0)
        with pytest.raises(DBDataError):
            db_manager.archivia_localita(-1)

    def test_archivia_localita_non_trovata(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.archivia_localita(99999999)

    def test_archivia_localita_esclusa_da_ricerca(self, sample_data):
        db = sample_data['db']
        lid = sample_data['localita_id']
        cid = sample_data['comune_id']
        assert len(db.get_localita_by_comune(cid)) >= 1
        db.archivia_localita(lid)
        localita = db.get_localita_by_comune(cid)
        assert all(l['id'] != lid for l in localita)


# ===========================================================================
# Test legami Partita-Possessore
# ===========================================================================

class TestLegamiPartitaPossessore:
    def test_aggiungi_possessore_a_partita(self, sample_data):
        db = sample_data['db']
        result = db.aggiungi_possessore_a_partita(
            partita_id=sample_data['partita_id'],
            possessore_id=sample_data['possessore1_id'],
            tipo_partita_rel='principale',
            titolo='proprietà esclusiva',
            quota='1/1'
        )
        assert result is True

    def test_get_possessori_per_partita(self, sample_data):
        db = sample_data['db']
        db.aggiungi_possessore_a_partita(
            sample_data['partita_id'], sample_data['possessore1_id'],
            'principale', 'proprietà', '1/1'
        )
        possessori = db.get_possessori_per_partita(sample_data['partita_id'])
        assert len(possessori) == 1
        assert possessori[0]['possessore_id'] == sample_data['possessore1_id']
        assert possessori[0]['titolo_possesso'] == 'proprietà'

    def test_get_partite_per_possessore(self, sample_data):
        db = sample_data['db']
        db.aggiungi_possessore_a_partita(
            sample_data['partita_id'], sample_data['possessore1_id'],
            'principale', 'proprietà', None
        )
        partite = db.get_partite_per_possessore(sample_data['possessore1_id'])
        assert len(partite) >= 1
        assert any(p['numero_partita'] == 100 for p in partite)

    def test_aggiorna_legame_partita_possessore(self, sample_data):
        db = sample_data['db']
        db.aggiungi_possessore_a_partita(
            sample_data['partita_id'], sample_data['possessore1_id'],
            'principale', 'proprietà', '1/2'
        )
        possessori = db.get_possessori_per_partita(sample_data['partita_id'])
        link_id = possessori[0]['id_relazione_partita_possessore']
        result = db.aggiorna_legame_partita_possessore(link_id, 'comproprietà', '1/3')
        assert result is True

    def test_rimuovi_possessore_da_partita(self, sample_data):
        db = sample_data['db']
        db.aggiungi_possessore_a_partita(
            sample_data['partita_id'], sample_data['possessore1_id'],
            'principale', 'proprietà', None
        )
        possessori = db.get_possessori_per_partita(sample_data['partita_id'])
        link_id = possessori[0]['id_relazione_partita_possessore']
        result = db.rimuovi_possessore_da_partita(link_id)
        assert result is True
        assert db.get_possessori_per_partita(sample_data['partita_id']) == []

    def test_rimuovi_legame_non_trovato(self, clean_db):
        with pytest.raises((DBNotFoundError, DBMError)):
            clean_db.rimuovi_possessore_da_partita(99999999)


# ===========================================================================
# Test import CSV Possessori
# ===========================================================================

class TestImportCSVPossessori:
    def test_import_successo(self, sample_data, temp_csv_possessori):
        db = sample_data['db']
        cid = sample_data['comune_id']
        risultato = db.import_possessori_from_csv(temp_csv_possessori, cid, "Genova Test")
        assert len(risultato['success']) == 2
        assert len(risultato['errors']) == 0

    def test_import_righe_duplicate_vanno_in_errors(self, sample_data, temp_csv_possessori):
        db = sample_data['db']
        cid = sample_data['comune_id']
        # Prima importazione OK
        db.import_possessori_from_csv(temp_csv_possessori, cid, "Genova Test")
        # Seconda: i duplicati vanno negli errori, non solleva eccezione
        risultato = db.import_possessori_from_csv(temp_csv_possessori, cid, "Genova Test")
        assert len(risultato['errors']) == 2
        assert len(risultato['success']) == 0

    def test_import_file_non_trovato(self, sample_data):
        with pytest.raises((FileNotFoundError, IOError)):
            sample_data['db'].import_possessori_from_csv(
                "/percorso/inesistente.csv", sample_data['comune_id'], "Test"
            )

    def test_import_csv_intestazioni_mancanti(self, sample_data, tmp_path):
        db = sample_data['db']
        f = tmp_path / "bad.csv"
        f.write_text("nome;cognome\nMASSI;MARIO\n", encoding="utf-8")
        with pytest.raises((IOError, ValueError)):
            db.import_possessori_from_csv(str(f), sample_data['comune_id'], "Test")

    def test_import_csv_vuoto(self, sample_data, tmp_path):
        db = sample_data['db']
        f = tmp_path / "empty.csv"
        f.write_text("nome_completo;cognome_nome\n", encoding="utf-8")
        risultato = db.import_possessori_from_csv(str(f), sample_data['comune_id'], "Test")
        assert risultato == {"success": [], "errors": []}


# ===========================================================================
# Test ricerca avanzata
# ===========================================================================

class TestRicercaAvanzata:
    def test_search_partite_senza_filtri(self, sample_data):
        db = sample_data['db']
        results = db.search_partite()
        assert isinstance(results, list)

    def test_search_partite_non_include_archiviate(self, sample_data):
        db = sample_data['db']
        pid = sample_data['partita_id']
        cid = sample_data['comune_id']
        db.archivia_partita(pid)
        results = db.search_partite(comune_id=cid)
        assert all(r['id'] != pid for r in results)

    def test_search_partite_per_possessore(self, sample_data):
        db = sample_data['db']
        db.aggiungi_possessore_a_partita(
            sample_data['partita_id'], sample_data['possessore1_id'],
            'principale', 'proprietà', None
        )
        results = db.search_partite(possessore="ROSSI")
        assert len(results) >= 1

    def test_search_possessori_globally_attivi_solo(self, sample_data):
        db = sample_data['db']
        pid = sample_data['possessore1_id']
        db.archivia_possessore(pid)
        results = db.search_possessori_by_term_globally("ROSSI")
        assert all(r['id'] != pid for r in results)

    def test_ricerca_avanzata_immobili_restituisce_lista(self, sample_data):
        db = sample_data['db']
        results = db.ricerca_avanzata_immobili_gui(
            comune_id=sample_data['comune_id']
        )
        assert isinstance(results, list)

    def test_ricerca_avanzata_immobili_senza_filtri(self, sample_data):
        db = sample_data['db']
        results = db.ricerca_avanzata_immobili_gui()
        assert isinstance(results, list)

    def test_ricerca_avanzata_possessori(self, sample_data):
        db = sample_data['db']
        results = db.ricerca_avanzata_possessori("ROSSI")
        assert isinstance(results, list)


# ===========================================================================
# Test dashboard e statistiche
# ===========================================================================

class TestDashboard:
    def test_get_dashboard_stats(self, db_manager):
        stats = db_manager.get_dashboard_stats()
        assert isinstance(stats, dict)
        for key in ('total_comuni', 'total_possessori', 'total_partite', 'total_immobili'):
            assert key in stats
            assert isinstance(stats[key], int)

    def test_get_statistiche_comune(self, db_manager):
        stats = db_manager.get_statistiche_comune()
        assert isinstance(stats, list)


# ===========================================================================
# Test bug fixes v1.2.1 - tipo_localita migration
# ===========================================================================

class TestBugFixesTipoLocalita:
    """Test per i fix della migrazione tipo_localita (script 20)."""

    def test_get_localita_details_usa_join_tipo_localita(self, sample_data):
        """get_localita_details deve usare LEFT JOIN con tipo_localita, non l.tipo."""
        db = sample_data['db']
        l = db.get_localita_details(sample_data['localita_id'])
        assert l is not None
        assert 'tipo' in l  # Campo rinominato da l.tipo a tl.nome

    def test_get_immobile_details_usa_join_tipo_localita(self, sample_data, db_manager):
        """get_immobile_details deve usare LEFT JOIN con tipo_localita."""
        # Crea un immobile per il test (via SQL diretto)
        db = sample_data['db']
        cid = sample_data['comune_id']
        pid = sample_data['partita_id']
        lid = sample_data['localita_id']

        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO catasto.immobile (partita_id, localita_id, natura) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (pid, lid, 'Casa')
                )
                immobile_id = cur.fetchone()[0]

        i = db.get_immobile_details(immobile_id)
        assert i is not None
        assert 'localita_tipo' in i

    def test_ricerca_avanzata_immobili_gui_funziona_dopo_fix(self, sample_data):
        """ricerca_avanzata_immobili_gui deve funzionare dopo il fix di l.tipo."""
        db = sample_data['db']
        results = db.ricerca_avanzata_immobili_gui(
            comune_id=sample_data['comune_id']
        )
        # Non deve sollevare eccezione riguardo a colonna non esistente
        assert isinstance(results, list)
