import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Aggiungi la directory principale al path per l'importazione
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QDateTime
from gui_widgets import AuditLogViewerWidget

# Fixture per creare una singola istanza di QApplication per la sessione di test
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

class TestAuditLogViewerPagination:
    """Test per la logica di paginazione in AuditLogViewerWidget."""

    @pytest.fixture
    def mock_db_manager(self):
        """Crea un mock del DB manager che simula risultati paginati."""
        db_mock = MagicMock()
        
        # Simula un database con 250 log. Con una page_size di 100, avremo 3 pagine.
        total_records = 250
        
        def get_logs_side_effect(filters=None, page=1, page_size=100):
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            page_logs = [{'id': i, 'tabella': 'test', 'operazione': 'I'} for i in range(start_index, min(end_index, total_records))]
            return page_logs, total_records

        db_mock.get_audit_logs.side_effect = get_logs_side_effect
        return db_mock

    @pytest.fixture
    def widget(self, qapp, mock_db_manager):
        """Crea un'istanza di AuditLogViewerWidget con il DB mockato e carica i dati iniziali."""
        viewer_widget = AuditLogViewerWidget(db_manager=mock_db_manager)
        viewer_widget.load_initial_data()  # Attiva manualmente il lazy loading per il test
        return viewer_widget

    def test_initial_load_and_ui_state(self, widget):
        """Verifica lo stato della UI e dei dati dopo il caricamento iniziale."""
        assert widget.current_page == 1
        assert widget.total_records == 250
        assert widget.total_pages == 3  # 250 record / 100 page_size = 2.5 -> 3 pagine
        
        # Controlla gli elementi della UI
        assert widget.page_info_label.text() == "Pagina 1 / 3 (250 risultati)"
        assert widget.btn_first_page.isEnabled() is False
        assert widget.btn_prev_page.isEnabled() is False
        assert widget.btn_next_page.isEnabled() is True
        assert widget.btn_last_page.isEnabled() is True
        
        # Controlla che il mock sia stato chiamato correttamente
        widget.db_manager.get_audit_logs.assert_called_with(
            filters=widget.current_filters, page=1, page_size=100
        )
        assert widget.log_table.rowCount() == 100

    def test_go_to_next_page(self, widget):
        """Testa il click sul pulsante 'pagina successiva'."""
        widget._go_to_next_page()
        
        assert widget.current_page == 2
        widget.db_manager.get_audit_logs.assert_called_with(
            filters=widget.current_filters, page=2, page_size=100
        )
        assert widget.log_table.rowCount() == 100
        assert widget.page_info_label.text() == "Pagina 2 / 3 (250 risultati)"
        assert widget.btn_first_page.isEnabled() is True
        assert widget.btn_prev_page.isEnabled() is True

    def test_go_to_last_page(self, widget):
        """Testa il click sul pulsante 'ultima pagina'."""
        widget._go_to_last_page()
        
        assert widget.current_page == 3
        widget.db_manager.get_audit_logs.assert_called_with(
            filters=widget.current_filters, page=3, page_size=100
        )
        # L'ultima pagina ha solo 50 record
        assert widget.log_table.rowCount() == 50
        
        # Controlla la UI all'ultima pagina
        assert widget.page_info_label.text() == "Pagina 3 / 3 (250 risultati)"
        assert widget.btn_next_page.isEnabled() is False
        assert widget.btn_last_page.isEnabled() is False

    def test_go_to_previous_page(self, widget):
        """Testa il click su 'pagina precedente' dopo essere avanzati."""
        widget._go_to_next_page()  # Vai a pagina 2
        assert widget.current_page == 2
        
        widget._go_to_previous_page()  # Torna a pagina 1
        
        assert widget.current_page == 1
        widget.db_manager.get_audit_logs.assert_called_with(
            filters=widget.current_filters, page=1, page_size=100
        )
        assert widget.btn_prev_page.isEnabled() is False

    def test_go_to_first_page(self, widget):
        """Testa il click su 'prima pagina' dopo essere andati alla fine."""
        widget._go_to_last_page()  # Vai a pagina 3
        assert widget.current_page == 3
        
        widget._go_to_first_page()  # Torna a pagina 1
        
        assert widget.current_page == 1
        assert widget.btn_first_page.isEnabled() is False

class TestAuditLogViewerFilters:
    """Test per la logica di filtraggio in AuditLogViewerWidget."""

    @pytest.fixture
    def mock_db_manager(self):
        """Crea un mock del DB manager che non fa nulla, serve solo a spiare le chiamate."""
        db_mock = MagicMock()
        # La chiamata a get_audit_logs restituirà una tupla vuota per evitare errori
        db_mock.get_audit_logs.return_value = ([], 0)
        return db_mock

    @pytest.fixture
    def widget(self, qapp, mock_db_manager):
        """Crea un'istanza di AuditLogViewerWidget con il DB mockato."""
        # Non carichiamo i dati iniziali, lo faremo nei test
        viewer_widget = AuditLogViewerWidget(db_manager=mock_db_manager)
        return viewer_widget

    def test_apply_filters_all_fields(self, widget, mock_db_manager):
        """Verifica che l'applicazione di tutti i filtri chiami il DB con i parametri corretti."""
        # 1. Simula l'input dell'utente nei campi di filtro
        start_dt = QDateTime(2023, 1, 1, 10, 0, 0)
        end_dt = QDateTime(2023, 1, 31, 23, 59, 0)

        widget.filter_table_name_edit.setText("partita")
        widget.filter_app_user_id_edit.setText("admin_test") # Test con username
        widget.filter_operation_combo.setCurrentText("UPDATE")
        widget.filter_start_datetime_edit.setDateTime(start_dt)
        widget.filter_end_datetime_edit.setDateTime(end_dt)

        # 2. Simula il click sul pulsante "Applica"
        widget._apply_filters_and_search()

        # 3. Verifica che il metodo del DB manager sia stato chiamato con i filtri corretti
        expected_filters = {
            "table_name": "partita",
            "username": "admin_test",
            "operation_char": "U",
            "app_user_id": None, # Non è un numero, quindi app_user_id è None
            "start_datetime": start_dt.toPyDateTime(),
            "end_datetime": end_dt.toPyDateTime(),
        }

        mock_db_manager.get_audit_logs.assert_called_once()
        # Accediamo agli argomenti della chiamata
        _call_args, call_kwargs = mock_db_manager.get_audit_logs.call_args
        
        # Il dizionario dei filtri è passato come keyword argument 'filters'
        assert call_kwargs.get('filters') == expected_filters
        # La paginazione deve essere resettata a 1
        assert call_kwargs.get('page') == 1

    def test_apply_filters_with_user_id(self, widget, mock_db_manager):
        """Verifica che un ID utente numerico venga passato correttamente."""
        widget.filter_app_user_id_edit.setText("123")
        widget._apply_filters_and_search()
        _call_args, call_kwargs = mock_db_manager.get_audit_logs.call_args
        filters = call_kwargs.get('filters')
        assert filters['username'] == "123"
        assert filters['app_user_id'] == 123

    def test_reset_filters(self, widget, mock_db_manager):
        """Verifica che il reset dei filtri pulisca i campi e riesegua la ricerca con filtri vuoti."""
        widget.filter_table_name_edit.setText("some_table")
        widget.filter_operation_combo.setCurrentIndex(1) # INSERT
        widget._reset_filters()
        assert widget.filter_table_name_edit.text() == ""
        assert widget.filter_operation_combo.currentIndex() == 0 # "Tutte"
        mock_db_manager.get_audit_logs.assert_called_once()
        _call_args, call_kwargs = mock_db_manager.get_audit_logs.call_args
        filters = call_kwargs.get('filters')
        assert filters['table_name'] is None
        assert filters['username'] is None
        assert filters['operation_char'] is None
        assert filters['app_user_id'] is None


class TestAuditLogViewerExports:
    """Test per la logica di esportazione CSV ed Excel in AuditLogViewerWidget."""

    @pytest.fixture
    def mock_db_manager(self):
        """Crea un mock del DB manager con dati fittizi pronti per l'export."""
        db_mock = MagicMock()
        self.fake_logs = [
            {'id': 1, 'timestamp': datetime(2023, 1, 1, 10, 0), 'username': 'admin', 'tabella': 'partita', 'operazione': 'I', 'record_id': 10, 'ip_address': '127.0.0.1'},
            {'id': 2, 'timestamp': datetime(2023, 1, 2, 11, 30), 'username': 'user1', 'tabella': 'possessore', 'operazione': 'U', 'record_id': 20, 'ip_address': '192.168.1.5'}
        ]
        db_mock.get_audit_logs.return_value = (self.fake_logs, 2)
        return db_mock

    @pytest.fixture
    def widget(self, qapp, mock_db_manager):
        return AuditLogViewerWidget(db_manager=mock_db_manager)

    @patch('gui_widgets.QFileDialog.getSaveFileName')
    @patch('gui_widgets.QMessageBox.information')
    def test_export_csv_success(self, mock_msg_info, mock_file_dialog, widget, mock_db_manager, tmp_path):
        """Verifica che l'esportazione CSV generi il file corretto se ci sono dati."""
        export_file = tmp_path / "export_audit.csv"
        mock_file_dialog.return_value = (str(export_file), "CSV Files (*.csv)")

        widget._handle_export_csv()

        # Verifica che il file esista
        assert export_file.exists()
        
        # Verifica che il messaggio di successo sia stato mostrato
        mock_msg_info.assert_called_once()
        
        # Verifica che i dati siano stati scritti correttamente
        with open(export_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "username;tabella;operazione" in content
            assert "admin;partita;I" in content

    @patch('gui_widgets.QMessageBox.warning')
    def test_export_csv_no_data(self, mock_msg_warn, widget, mock_db_manager):
        """Verifica che venga mostrato un avviso se non ci sono dati da esportare in CSV."""
        mock_db_manager.get_audit_logs.return_value = ([], 0)
        
        with patch('gui_widgets.QFileDialog.getSaveFileName') as mock_file_dialog:
            widget._handle_export_csv()
            # Il file dialog non deve nemmeno aprirsi
            mock_file_dialog.assert_not_called()
            
        mock_msg_warn.assert_called_once()

    @patch('gui_widgets.QFileDialog.getSaveFileName')
    @patch('gui_widgets.QMessageBox.information')
    def test_export_xls_success(self, mock_msg_info, mock_file_dialog, widget, mock_db_manager, tmp_path):
        """Verifica che l'esportazione Excel generi il file se la libreria pandas è disponibile."""
        export_file = tmp_path / "export_audit.xlsx"
        mock_file_dialog.return_value = (str(export_file), "Excel Files (*.xlsx)")

        widget._handle_export_xls()

        assert export_file.exists()
        mock_msg_info.assert_called_once()

    @patch('gui_widgets.QMessageBox.warning')
    def test_export_xls_no_data(self, mock_msg_warn, widget, mock_db_manager):
        """Verifica che venga mostrato un avviso se non ci sono dati da esportare in Excel."""
        mock_db_manager.get_audit_logs.return_value = ([], 0)
        widget._handle_export_xls()
        mock_msg_warn.assert_called_once()