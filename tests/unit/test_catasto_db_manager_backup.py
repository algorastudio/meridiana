import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Aggiungi la directory principale al path per l'importazione
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from catasto_db_manager import CatastoDBManager

class TestEmergencyRestore:
    """Test unitari per la funzionalità di ripristino di emergenza in CatastoDBManager"""

    @pytest.fixture
    def mock_db_manager(self):
        """Fornisce un'istanza di CatastoDBManager con i path degli eseguibili mockati."""
        manager = CatastoDBManager(
            dbname="test_db",
            user="test_user",
            password="test_password",
            host="localhost",
            port=5432
        )
        # Evitiamo di cercare file veri nel sistema durante il test
        manager._resolve_executable_path = MagicMock(return_value="/fake/path/exe")
        # Evitiamo di manipolare l'ambiente di sistema reale
        manager.create_clean_environment = MagicMock()
        return manager

    @patch('catasto_db_manager.QProcess')
    def test_emergency_restore_success(self, mock_qprocess_class, mock_db_manager):
        """Verifica che il ripristino abbia successo se tutti e 3 i processi terminano correttamente."""
        mock_process_instance = MagicMock()
        mock_qprocess_class.return_value = mock_process_instance
        
        # Simuliamo il successo del processo
        mock_process_instance.waitForFinished.return_value = True
        mock_process_instance.exitCode.return_value = 0
        
        success, msg = mock_db_manager.execute_restore_from_file_emergency("/fake/backup.dump")
        
        assert success is True
        assert "completato con successo" in msg
        # Verifica che il processo sia stato avviato esattamente 3 volte (drop, create, restore)
        assert mock_process_instance.start.call_count == 3

    def test_emergency_restore_missing_executables(self, mock_db_manager):
        """Verifica che il ripristino si interrompa se mancano gli eseguibili di PostgreSQL."""
        # Simuliamo che _resolve_executable_path non trovi uno degli eseguibili
        mock_db_manager._resolve_executable_path.return_value = None
        
        success, msg = mock_db_manager.execute_restore_from_file_emergency("/fake/backup.dump")
        
        assert success is False
        assert "Impossibile trovare gli eseguibili" in msg

    @patch('catasto_db_manager.QProcess')
    def test_emergency_restore_process_timeout(self, mock_qprocess_class, mock_db_manager):
        """Verifica la gestione di un timeout o crash durante l'esecuzione del processo."""
        mock_process_instance = MagicMock()
        mock_qprocess_class.return_value = mock_process_instance
        
        # Simuliamo che il processo non finisca in tempo
        mock_process_instance.waitForFinished.return_value = False
        mock_process_instance.errorString.return_value = "Process timed out unexpectedly"
        
        success, msg = mock_db_manager.execute_restore_from_file_emergency("/fake/backup.dump")
        
        assert success is False
        assert "Timeout o errore" in msg
        assert "Process timed out unexpectedly" in msg
        # Si deve interrompere al primo comando (dropdb) senza eseguire gli altri
        assert mock_process_instance.start.call_count == 1

    @patch('catasto_db_manager.QProcess')
    def test_emergency_restore_process_exit_error(self, mock_qprocess_class, mock_db_manager):
        """Verifica la gestione di un errore restituito dal tool da riga di comando (exit code != 0)."""
        mock_process_instance = MagicMock()
        mock_qprocess_class.return_value = mock_process_instance
        
        mock_process_instance.waitForFinished.return_value = True
        # Simuliamo un errore nel comando (es. password errata)
        mock_process_instance.exitCode.return_value = 1
        
        # Simuliamo il messaggio di errore su stderr. .data() deve restituire bytes per via del .decode()
        mock_stderr = MagicMock()
        mock_stderr.data.return_value = b"FATAL: authentication failed for user test_user"
        mock_process_instance.readAllStandardError.return_value = mock_stderr
        
        success, msg = mock_db_manager.execute_restore_from_file_emergency("/fake/backup.dump")
        
        assert success is False
        assert "Fallimento durante" in msg
        assert "FATAL: authentication failed" in msg
        assert mock_process_instance.start.call_count == 1