import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Aggiungi la directory principale al path per l'importazione
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_utils import (
    gui_esporta_partita_json,
    gui_esporta_partita_csv,
    gui_esporta_partita_pdf,
    gui_esporta_possessore_json,
    gui_esporta_possessore_csv,
    gui_esporta_possessore_pdf
)

from PyQt5.QtWidgets import QDialog

class TestGUIExports:
    """Test per le funzioni di esportazione collegate alla GUI in app_utils.py"""

    @pytest.fixture
    def mock_db_manager(self):
        """Fornisce un DBManager mockato con dati fittizi per l'esportazione."""
        manager = MagicMock()
        manager.get_partita_data_for_export.return_value = {
            "partita": {"id": 1, "numero_partita": 100, "comune_nome": "Savona", "tipo": "principale", "stato": "attiva", "data_impianto": "1900-01-01"},
            "possessori": [{"id": 1, "nome_completo": "Mario Rossi", "titolo": "proprietà", "quota": "1/1"}],
            "immobili": [{"id": 1, "natura": "Casa", "classificazione": "A/2", "consistenza": "5 vani"}],
            "variazioni": [{"id": 1, "tipo": "Vendita", "data_variazione": "1950-01-01"}]
        }
        manager.get_possessore_data_for_export.return_value = {
            "possessore": {"id": 1, "nome_completo": "Mario Rossi", "comune_nome": "Savona", "paternita": "fu Giuseppe", "attivo": True},
            "partite": [{"id": 1, "numero_partita": 100, "comune_nome": "Savona", "tipo": "principale", "quota": "1/1", "titolo": "proprietà"}],
            "immobili": [{"id": 1, "natura": "Casa", "localita_nome": "Via Roma", "numero_partita": 100, "comune_nome": "Savona"}]
        }
        return manager

    @pytest.fixture
    def parent_widget(self):
        return MagicMock()

    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_partita_json_success(self, mock_msg_info, mock_save_dialog, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione JSON corretta di una partita."""
        export_file = tmp_path / "test_partita.json"
        mock_save_dialog.return_value = (str(export_file), "JSON Files (*.json)")

        gui_esporta_partita_json(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()
        with open(export_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["partita"]["id"] == 1

    @patch('app_utils.CSVApreviewDialog')
    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_partita_csv_success(self, mock_msg_info, mock_save_dialog, mock_preview, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione CSV corretta di una partita dopo aver accettato l'anteprima."""
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec_.return_value = QDialog.Accepted
        mock_preview.return_value = mock_preview_instance
        
        export_file = tmp_path / "test_partita.csv"
        mock_save_dialog.return_value = (str(export_file), "CSV Files (*.csv)")

        gui_esporta_partita_csv(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()

    @patch('app_utils.FPDF_AVAILABLE', True)
    @patch('app_utils.PDFApreviewDialog')
    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_partita_pdf_success(self, mock_msg_info, mock_save_dialog, mock_preview, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione PDF corretta di una partita dopo aver accettato l'anteprima."""
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec_.return_value = QDialog.Accepted
        mock_preview.return_value = mock_preview_instance
        
        export_file = tmp_path / "test_partita.pdf"
        mock_save_dialog.return_value = (str(export_file), "PDF Files (*.pdf)")

        gui_esporta_partita_pdf(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()

    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_possessore_json_success(self, mock_msg_info, mock_save_dialog, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione JSON corretta di un possessore."""
        export_file = tmp_path / "test_possessore.json"
        mock_save_dialog.return_value = (str(export_file), "JSON Files (*.json)")

        gui_esporta_possessore_json(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()
        with open(export_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["possessore"]["id"] == 1

    @patch('app_utils.CSVApreviewDialog')
    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_possessore_csv_success(self, mock_msg_info, mock_save_dialog, mock_preview, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione CSV corretta di un possessore."""
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec_.return_value = QDialog.Accepted
        mock_preview.return_value = mock_preview_instance
        
        export_file = tmp_path / "test_possessore.csv"
        mock_save_dialog.return_value = (str(export_file), "CSV Files (*.csv)")

        gui_esporta_possessore_csv(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()

    @patch('app_utils.FPDF_AVAILABLE', True)
    @patch('app_utils.PDFApreviewDialog')
    @patch('app_utils.QFileDialog.getSaveFileName')
    @patch('app_utils.QMessageBox.information')
    def test_gui_esporta_possessore_pdf_success(self, mock_msg_info, mock_save_dialog, mock_preview, mock_db_manager, parent_widget, tmp_path):
        """Verifica l'esportazione PDF corretta di un possessore."""
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec_.return_value = QDialog.Accepted
        mock_preview.return_value = mock_preview_instance
        
        export_file = tmp_path / "test_possessore.pdf"
        mock_save_dialog.return_value = (str(export_file), "PDF Files (*.pdf)")

        gui_esporta_possessore_pdf(parent_widget, mock_db_manager, 1)

        assert export_file.exists()
        mock_msg_info.assert_called_once()

    @patch('app_utils.CSVApreviewDialog')
    def test_gui_esporta_partita_csv_preview_cancelled(self, mock_preview, mock_db_manager, parent_widget):
        """Verifica che premendo Annulla nell'anteprima l'esportazione CSV venga interrotta senza salvare."""
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec_.return_value = QDialog.Rejected
        mock_preview.return_value = mock_preview_instance

        with patch('app_utils.QFileDialog.getSaveFileName') as mock_save:
            gui_esporta_partita_csv(parent_widget, mock_db_manager, 1)
            mock_save.assert_not_called() # Il file dialog non deve mai aprirsi!