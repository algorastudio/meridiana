import os
import sys
import pytest

# Aggiungi la directory principale al sys.path per poter importare i moduli dell'app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_utils import BulkReportPDF, FPDF_AVAILABLE

# Salta l'intera suite di test se FPDF2 non è installato nell'ambiente di test
pytestmark = pytest.mark.skipif(
    not FPDF_AVAILABLE, 
    reason="Libreria fpdf2 non trovata. I test sui PDF vengono ignorati."
)

class TestBulkReportPDF:
    """Suite di test unitari per la classe BulkReportPDF in app_utils.py"""

    def test_initialization(self):
        """Verifica che il PDF venga inizializzato con i parametri corretti."""
        titolo_test = "Report di Prova Catasto"
        pdf = BulkReportPDF(report_title=titolo_test)
        
        assert pdf.report_title == titolo_test
        assert pdf.headers == []
        assert pdf.col_widths == []

    def test_print_table_empty_data(self):
        """Verifica che la fornitura di dati vuoti non provochi errori."""
        pdf = BulkReportPDF()
        headers = ["Colonna 1", "Colonna 2"]
        
        # Chiamata con dati vuoti
        pdf.print_table(headers, [])
        
        # Non dovrebbe aver aggiunto alcuna pagina
        assert pdf.page_no() == 0

    def test_print_table_with_list_of_lists(self, tmp_path):
        """Verifica l'esportazione di una tabella fornendo i dati come lista di liste."""
        pdf = BulkReportPDF(report_title="Report Lista Semplice")
        headers = ["ID", "Nome", "Valore"]
        data = [
            [1, "Oggetto A", 100.50],
            [2, "Oggetto B", 200.75],
            [3, "Oggetto C", 300.00]
        ]
        
        pdf.print_table(headers, data)
        
        # Verifica che sia stata creata una pagina e salva il file temporaneo
        assert pdf.page_no() >= 1
        output_file = tmp_path / "test_list_output.pdf"
        pdf.output(str(output_file))
        
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_print_table_with_list_of_dicts(self, tmp_path):
        """Verifica l'esportazione di una tabella fornendo i dati come lista di dizionari (comune con DB)."""
        pdf = BulkReportPDF(report_title="Report da Dizionari")
        headers = ["nome", "cognome", "eta"]
        data = [
            {"nome": "Mario", "cognome": "Rossi", "eta": 45, "ignorato": "xyz"},
            {"nome": "Luigi", "cognome": "Verdi", "eta": 32}
        ]
        
        pdf.print_table(headers, data)
        
        output_file = tmp_path / "test_dict_output.pdf"
        pdf.output(str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_pagination_and_page_breaks(self, tmp_path):
        """Verifica che un dataset molto grande inneschi correttamente la paginazione automatica."""
        pdf = BulkReportPDF(report_title="Report Paginazione")
        headers = ["ID", "Dato di Test"]
        
        # Genera 150 righe, che dovrebbero forzare almeno un salto di pagina
        data = [[i, f"Valore di test numero {i}"] for i in range(150)]
        
        pdf.print_table(headers, data)
        
        # Verifica che ci siano più pagine (normalmente ~40-50 righe per pagina A4 orizzontale)
        assert pdf.page_no() > 1