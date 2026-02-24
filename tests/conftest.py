# tests/conftest.py

import pytest
import os
import sys
import psycopg2

# Aggiungi la directory principale al path per trovare catasto_db_manager.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catasto_db_manager import CatastoDBManager

# 1. Configurazione della connessione (legge da GitHub Actions o usa parametri locali)
@pytest.fixture(scope="session")
def test_db_setup():
    """Fornisce i parametri di connessione al database di test."""
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'dbname': os.environ.get('DB_NAME', 'catasto_storico'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASS', 'testpassword'), # Password che abbiamo messo nel .yml
        'port': os.environ.get('DB_PORT', '5432')
    }

# 2. Creazione del Manager reale
@pytest.fixture
def db_manager(test_db_setup):
    """Inizializza il CatastoDBManager con i parametri di test."""
    manager = CatastoDBManager(**test_db_setup)
    manager.initialize_main_pool()  # <--- CORRETTO QUI
    yield manager
    
    # Al termine del test, chiude le connessioni
    # ATTENZIONE: se nel suo codice la chiusura si chiama 'close_main_pool',
    # lo modifichi anche qui sotto. Altrimenti lasci 'close_pool()'.
    try:
        manager.close_main_pool()
    except AttributeError:
        manager.close_pool()
# 3. Pulizia del Database (Fondamentale per test isolati)
@pytest.fixture
def clean_db(db_manager):
    """Fornisce un database pulito prima di ogni singolo test."""
    conn = db_manager._get_connection()
    try:
        with conn.cursor() as cur:
            # Svuota le tabelle principali a cascata per partire da zero
            cur.execute("TRUNCATE TABLE comune CASCADE;")
        conn.commit()
    finally:
        db_manager._release_connection(conn)
    return db_manager

# 4. Dati di Esempio Precaricati
@pytest.fixture
def sample_data(clean_db):
    """Fornisce un set di dati di base (un Comune, un Possessore, una Partita) pronti all'uso."""
    # Creiamo i dati base necessari per i test avanzati
    comune_id = clean_db.aggiungi_comune("Genova Test", "GE", "Liguria")
    possessore1_id = clean_db.create_possessore(
        nome_completo="TEST MARIO", 
        comune_riferimento_id=comune_id, 
        cognome_nome="TEST"
    )
    partita_id = clean_db.create_partita(
        comune_id=comune_id, 
        numero_partita=100, 
        tipo='principale'
    )
    
    # Restituiamo un dizionario con gli ID in modo che i test possano usarli
    return {
        'db': clean_db,
        'comune_id': comune_id,
        'possessore1_id': possessore1_id,
        'partita_id': partita_id,
        'localita_id': None # Eventualmente da popolare se implementato nel DB
    }

# 5. File CSV Temporaneo per i test di importazione
@pytest.fixture
def temp_csv_file(tmp_path):
    """Crea un file CSV temporaneo per testare l'importazione possessori."""
    file_path = tmp_path / "test_import.csv"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("nome_completo;cognome_nome\n")
        f.write("VERDI GIUSEPPE fu Antonio;VERDI GIUSEPPE\n")
        f.write("NERI LUCIA fu Marco;NERI LUCIA\n")
    return str(file_path)