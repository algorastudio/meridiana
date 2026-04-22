import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Aggiungi la directory principale al path per l'importazione
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import QApplication
from gui_widgets import EsportazioniWidget

# Fixture per creare una singola istanza di QApplication per la sessione di test
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

class TestEsportazioniWidget:
    """Test unitari per il widget di esportazioni massive (EsportazioniWidget)."""

    @pytest.fixture
    def mock_db_manager(self):
        """Fornisce un DBManager mockato con dati di esempio per tutti i tipi di esportazione."""
        manager = MagicMock()
        manager.get_elenco_comuni_semplice.return_value = [(1, "Savona"), (2, "Genova")]
        manager.get_possessori_by_comune.return_value = [{
            'id': 1, 'nome_completo': 'Mario Rossi', 'comune_nome': 'Savona', 'attivo': True, 'num_partite': 1
        }]
        manager.get_partite_by_comune.return_value = [{
            'id': 100, 'numero_partita': 123, 'suffisso_partita': 'A',
            'stato': 'attiva', 'data_impianto': '1900-01-01', 'num_possessori': 1, 'num_immobili': 1
        }]
        manager.get_elenco_immobili_per_esportazione.return_value = [{
            'id_immobile': 1, 'natura': 'Casa', 'classificazione': 'A/2',
            'localita_nome': 'Via Roma', 'numero_partita': 123, 'comune_nome': 'Savona'
        }]
        manager.get_elenco_localita_per_esportazione.return_value = [{'id': 1, 'nome': 'Via Roma', 'tipo': 'Via', 'comune_nome': 'Savona'}]
        manager.get_elenco_variazioni_per_esportazione.return_value = [{
            'variazione_id': 1, 'tipo_variazione': 'Vendita', 'data_variazione': '1950-01-01',
            'partita_origine_numero': 1, 'partita_origine_comune': 'Savona',
            'partita_dest_numero': 2, 'partita_dest_comune': 'Savona',
            'tipo_contratto': 'Vendita', 'notaio': 'Rossi'
        }]
        manager.get_report_consistenza_patrimoniale.return_value = {'Mario Rossi': [{'numero_partita': 123, 'suffisso_partita': '', 'titolo': 'proprietà', 'quota': '1/1', 'stato': 'attiva'}]}
        return manager

    @pytest.fixture
    def widget(self, qapp, mock_db_manager):
        """Crea un'istanza di EsportazioniWidget con un DB manager mockato e dati caricati."""
        widget = EsportazioniWidget(db_manager=mock_db_manager)
        widget._load_data_on_first_show()  # Attiva manualmente il lazy loading per il test
        return widget

    @patch('gui_widgets.QFileDialog.getSaveFileName')
    @patch('gui_widgets.QMessageBox.information')
    def test_export_csv_success(self, mock_msg_info, mock_save_dialog, widget, mock_db_manager, tmp_path):
        """Verifica il successo dell'esportazione CSV per 'Elenco Possessori'."""
        export_file = tmp_path / "possessori.csv"
        mock_save_dialog.return_value = (str(export_file), "CSV Files (*.csv)")

        # Simula la selezione dell'utente
        widget.export_type_combo.setCurrentText("Elenco Possessori")
        widget.comune_filter_combo.setCurrentIndex(1)  # Seleziona "Savona"

        # Avvia l'esportazione
        widget._handle_export_csv()

        # Verifiche
        mock_db_manager.get_possessori_by_comune.assert_called_once_with(1)
        mock_save_dialog.assert_called_once()
        mock_msg_info.assert_called_once()
        assert export_file.exists()
        assert "ID Possessore;Comune di Riferimento;Nome Completo" in export_file.read_text(encoding='utf-8')

    @patch('pandas.DataFrame.to_excel')
    @patch('gui_widgets.QFileDialog.getSaveFileName')
    @patch('gui_widgets.QMessageBox.information')
    def test_export_xls_success(self, mock_msg_info, mock_save_dialog, mock_to_excel, widget, mock_db_manager, tmp_path):
        """Verifica il successo dell'esportazione XLS per 'Elenco Partite'."""
        export_file = tmp_path / "partite.xlsx"
        mock_save_dialog.return_value = (str(export_file), "Excel Files (*.xlsx)")

        widget.export_type_combo.setCurrentText("Elenco Partite")
        widget.comune_filter_combo.setCurrentIndex(1)

        widget._handle_export_xls()

        mock_db_manager.get_partite_by_comune.assert_called_once_with(1)
        mock_save_dialog.assert_called_once()
        mock_to_excel.assert_called_once()
        mock_msg_info.assert_called_once()

    @patch('app_utils.BulkReportPDF.output')
    @patch('gui_widgets.QFileDialog.getSaveFileName')
    @patch('gui_widgets.QMessageBox.information')
    def test_export_pdf_success(self, mock_msg_info, mock_save_dialog, mock_pdf_output, widget, mock_db_manager, tmp_path):
        """Verifica il successo dell'esportazione PDF per 'Elenco Immobili'."""
        export_file = tmp_path / "immobili.pdf"
        mock_save_dialog.return_value = (str(export_file), "PDF Files (*.pdf)")

        widget.export_type_combo.setCurrentText("Elenco Immobili")
        widget.comune_filter_combo.setCurrentIndex(1)

        widget._handle_export_pdf()

        mock_db_manager.get_elenco_immobili_per_esportazione.assert_called_once_with(1)
        mock_save_dialog.assert_called_once()
        mock_pdf_output.assert_called_once()
        mock_msg_info.assert_called_once()

    @patch('gui_widgets.QMessageBox.warning')
    def test_export_with_no_data(self, mock_msg_warn, widget, mock_db_manager):
        """Verifica che l'esportazione con dati vuoti mostri un avviso e si interrompa."""
        mock_db_manager.get_possessori_by_comune.return_value = []

        widget.export_type_combo.setCurrentText("Elenco Possessori")
        widget.comune_filter_combo.setCurrentIndex(1)

        with patch('gui_widgets.QFileDialog.getSaveFileName') as mock_save_dialog:
            widget._handle_export_csv()
            mock_save_dialog.assert_not_called()

        mock_msg_warn.assert_called_once()
        assert "Nessun Dato" in mock_msg_warn.call_args[0][1]

    @patch('gui_widgets.QMessageBox.warning')
    def test_export_without_selecting_comune(self, mock_msg_warn, widget):
        """Verifica che l'esportazione senza aver selezionato un comune mostri un avviso."""
        widget.export_type_combo.setCurrentText("Elenco Possessori")
        widget.comune_filter_combo.setCurrentIndex(0)  # "--- Seleziona un Comune ---"

        with patch('gui_widgets.QFileDialog.getSaveFileName') as mock_save_dialog:
            widget._handle_export_csv()
            mock_save_dialog.assert_not_called()

        mock_msg_warn.assert_called_once()
        assert "Selezione Mancante" in mock_msg_warn.call_args[0][1]

    @patch('pandas.ExcelWriter')
    @patch('gui_widgets.QFileDialog.getSaveFileName')
    def test_export_consistenza_patrimoniale_xls(self, mock_save_dialog, mock_excel_writer, widget, mock_db_manager, tmp_path):
        """Verifica il caso speciale di esportazione del 'Report Consistenza Patrimoniale' in Excel."""
        export_file = tmp_path / "consistenza.xlsx"
        mock_save_dialog.return_value = (str(export_file), "Excel Files (*.xlsx)")

        widget.export_type_combo.setCurrentText("Report Consistenza Patrimoniale")
        widget.comune_filter_combo.setCurrentIndex(1)

        widget._handle_export_xls()

        mock_db_manager.get_report_consistenza_patrimoniale.assert_called_once_with(1)
        mock_save_dialog.assert_called_once()
        mock_excel_writer.assert_called()