import os
import sys
import socket
import pytest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

# Aggiungi la directory principale al path per l'importazione
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_utils import (
    get_local_ip_address,
    check_network_environment,
    is_file_locked,
    get_alternative_filename,
    get_password_from_keyring
)

class TestNetworkUtils:
    """Test per le funzioni di rete in app_utils.py"""

    @patch('app_utils.socket.socket')
    def test_get_local_ip_address_success(self, mock_socket_class):
        """Verifica che l'IP venga recuperato correttamente tramite UDP."""
        # Configura il mock del socket
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance
        # getsockname() restituisce una tupla (ip, porta)
        mock_socket_instance.getsockname.return_value = ('192.168.1.55', 12345)

        ip = get_local_ip_address()
        
        assert ip == '192.168.1.55'
        mock_socket_instance.connect.assert_called_once_with(('8.8.8.8', 1))
        mock_socket_instance.close.assert_called_once()

    @patch('app_utils.socket.socket')
    @patch('app_utils.socket.gethostname')
    @patch('app_utils.socket.gethostbyname')
    def test_get_local_ip_address_fallback_hostname(self, mock_gethostbyname, mock_gethostname, mock_socket_class):
        """Verifica il fallback sull'hostname se la connessione UDP fallisce."""
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance
        # Facciamo fallire la connessione UDP
        mock_socket_instance.connect.side_effect = Exception("Network unreachable")
        
        mock_gethostname.return_value = 'my-computer'
        mock_gethostbyname.return_value = '10.0.0.5'

        ip = get_local_ip_address()
        
        assert ip == '10.0.0.5'
        mock_gethostbyname.assert_called_once_with('my-computer')

    @patch('app_utils.socket.socket')
    @patch('app_utils.socket.gethostname')
    @patch('app_utils.socket.gethostbyname')
    def test_get_local_ip_address_ultimate_fallback(self, mock_gethostbyname, mock_gethostname, mock_socket_class):
        """Verifica il fallback su localhost se tutto il resto fallisce."""
        mock_socket_class.return_value.connect.side_effect = Exception("Error")
        mock_gethostbyname.side_effect = socket.gaierror("Hostname not found")

        ip = get_local_ip_address()
        
        assert ip == '127.0.0.1'

    @patch('app_utils.DEVELOPMENT_MODE', True)
    def test_check_network_environment_dev_mode(self):
        """In DEV MODE la rete deve essere sempre approvata senza controlli."""
        assert check_network_environment() is True

    @patch('app_utils.DEVELOPMENT_MODE', False)
    @patch('app_utils.get_local_ip_address')
    def test_check_network_environment_valid_ip(self, mock_get_ip):
        """Se non in DEV MODE e l'IP è corretto, approva la rete."""
        mock_get_ip.return_value = '192.168.1.100'
        assert check_network_environment("192.168.1.") is True
        
        mock_get_ip.return_value = '127.0.0.1'
        assert check_network_environment("192.168.1.") is True

    @patch('app_utils.DEVELOPMENT_MODE', False)
    @patch('app_utils.get_local_ip_address')
    @patch('app_utils.QMessageBox') # Mockiamo PyQt per evitare crash nei test senza GUI
    def test_check_network_environment_invalid_ip(self, mock_qmessagebox, mock_get_ip):
        """Se l'IP non è nella subnet, blocca l'accesso e mostra un messaggio."""
        mock_get_ip.return_value = '10.0.0.50'
        
        mock_msg_instance = MagicMock()
        mock_qmessagebox.return_value = mock_msg_instance
        
        assert check_network_environment("192.168.1.") is False
        mock_msg_instance.exec_.assert_called_once()


class TestFileSystemUtils:
    """Test per le utility del file system in app_utils.py"""

    @patch('app_utils.os.path.exists')
    def test_is_file_locked_not_exists(self, mock_exists):
        """Se il file non esiste, non può essere bloccato."""
        mock_exists.return_value = False
        assert is_file_locked("fake_path.txt") is False

    @patch('app_utils.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_is_file_locked_free(self, mock_file, mock_exists):
        """Se il file si apre in scrittura senza errori, non è bloccato."""
        mock_exists.return_value = True
        assert is_file_locked("test_file.txt") is False
        mock_file.assert_called_once_with("test_file.txt", 'a')

    @patch('app_utils.os.path.exists')
    @patch('builtins.open')
    def test_is_file_locked_is_locked(self, mock_file, mock_exists):
        """Se l'apertura solleva PermissionError, il file è bloccato."""
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("File in uso")
        assert is_file_locked("test_file.txt") is True

    @patch('app_utils.datetime')
    def test_get_alternative_filename(self, mock_datetime):
        """Verifica la corretta generazione di un nome file con timestamp."""
        # Mockiamo il now() per avere un timestamp predicibile
        mock_now = datetime(2025, 12, 31, 23, 59, 59)
        mock_datetime.now.return_value = mock_now
        
        original = "C:/documenti/report.pdf"
        expected = "C:/documenti/report_20251231_235959.pdf"
        
        assert get_alternative_filename(original) == expected

    @patch('app_utils.keyring')
    def test_get_password_from_keyring(self, mock_keyring):
        """Verifica il recupero della password dal portachiavi di sistema."""
        mock_keyring.get_password.return_value = "secret123"
        
        assert get_password_from_keyring("meridiana_test", "admin") == "secret123"
        mock_keyring.get_password.assert_called_once_with("meridiana_test", "admin")