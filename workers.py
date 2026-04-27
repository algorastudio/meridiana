# -*- coding: utf-8 -*-
"""
Thread workers per l'interfaccia grafica.
"""
from PyQt5.QtCore import QThread, pyqtSignal

class CSVImportThread(QThread):
    """
    Thread dedicato per l'importazione massiva di CSV in background.
    Previene il blocco dell'interfaccia grafica durante le operazioni DB lunghe.
    """
    # Segnali emessi verso il thread principale della GUI
    finished_signal = pyqtSignal(dict)  # Restituisce il dizionario con successi/errori
    error_signal = pyqtSignal(str)      # Restituisce il messaggio d'errore

    def __init__(self, db_manager, import_type, file_path, comune_id, comune_nome, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.import_type = import_type  # Può essere 'possessori' o 'partite'
        self.file_path = file_path
        self.comune_id = comune_id
        self.comune_nome = comune_nome

    def run(self):
        try:
            # Esegue la funzione corretta in base al tipo richiesto
            if self.import_type == 'possessori':
                results = self.db_manager.import_possessori_from_csv(
                    self.file_path, self.comune_id, self.comune_nome
                )
            elif self.import_type == 'partite':
                results = self.db_manager.import_partite_from_csv(
                    self.file_path, self.comune_id, self.comune_nome
                )
            else:
                raise ValueError(f"Tipo di importazione '{self.import_type}' non supportato.")
            
            # Emette il risultato verso la GUI
            self.finished_signal.emit(results)
            
        except Exception as e:
            # Cattura qualsiasi errore DB o di file e lo passa alla GUI
            self.error_signal.emit(str(e))
