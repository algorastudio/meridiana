import os
import sys
import pytest

# Aggiungi la directory principale al sys.path per poter importare i moduli dell'app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_utils import GenericTextReportPDF, FPDF_AVAILABLE

# Salta l'intera suite di test se FPDF2 non è installato nell'ambiente di test
pytestmark = pytest.mark.skipif(
    not FPDF_AVAILABLE, 
    reason="Libreria fpdf2 non trovata. I test sui PDF vengono ignorati."
)

class TestGenericTextReportPDF:
    """Suite di test unitari per la classe GenericTextReportPDF in app_utils.py"""

    def test_initialization(self):
        """Verifica l'inizializzazione corretta del report PDF."""
        titolo_test = "Report Storico Test"
        pdf = GenericTextReportPDF(report_title=titolo_test)
        
        assert pdf.report_title == titolo_test
        # Verifica che i margini siano stati impostati a 15 come definito in init
        assert pdf.l_margin == 15
        assert pdf.r_margin == 15

    def test_add_report_text(self, tmp_path):
        """Verifica l'aggiunta di testo al report e la generazione del file."""
        pdf = GenericTextReportPDF(report_title="Test Testo Semplice")
        pdf.add_page()
        
        testo = "Questo è un testo di prova.\nContiene diverse righe.\n\tE anche tabulazioni."
        pdf.add_report_text(testo)
        
        output_file = tmp_path / "test_generic_report.pdf"
        pdf.output(str(output_file))
        
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert pdf.page_no() >= 1

    def test_multipage_text_report(self, tmp_path):
        """Verifica che un testo molto lungo generi correttamente più pagine."""
        pdf = GenericTextReportPDF(report_title="Test Paginazione Multipla")
        pdf.add_page()
        
        # Genera un testo lungo per forzare un salto pagina (es. report genealogico lungo)
        testo_lungo = "Riga di test per forzare il salto pagina.\n" * 150
        pdf.add_report_text(testo_lungo)
        
        assert pdf.page_no() > 1