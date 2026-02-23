"""Test base per verificare il setup"""
import pytest

def test_import_modules():
    """Test che i moduli principali siano importabili"""
    try:
        import catasto_db_manager
        assert True
    except ImportError:
        pytest.skip("catasto_db_manager non trovato")
    
    try:
        import gui_widgets
        assert True
    except ImportError:
        pytest.skip("gui_widgets non trovato")

def test_basic_math():
    """Test semplice per verificare che pytest funzioni"""
    assert 2 + 2 == 4
    assert 3 * 3 == 9

class TestBasicSetup:
    """Test classe base"""
    
    def test_pytest_is_working(self):
        """Verifica che pytest stia funzionando"""
        assert True
    
    def test_fixture_access(self, db_manager):
        """Verifica accesso alle fixture del database reale"""
        assert db_manager is not None
        # Verifica che il vero manager abbia il pool di connessioni
        assert hasattr(db_manager, 'pool')
