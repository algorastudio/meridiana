import os
import sys
import zipfile
import logging
from datetime import datetime

from PyQt5.QtCore import Qt, QSettings, QStandardPaths, QUrl, QCoreApplication
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QProgressDialog, QDialog

from app_paths import get_resource_path, load_stylesheet
from dialogs import CSVImportResultDialog, DBConfigDialog, BackupReminderSettingsDialog, EulaDialog
from workers import CSVImportThread
from gui_widgets import InserimentoComuneWidget, ElencoComuniWidget

class MainWindowActionsMixin:
    def _check_backup_reminder(self):
        settings = QSettings()
        reminder_days = settings.value("Backup/ReminderDays", 0, type=int)

        # Se il promemoria è disattivato, esci subito
        if reminder_days == 0:
            return

        last_backup_str = settings.value("Backup/LastBackupTimestamp", "")
        reason = ""
        show_reminder = False

        if not last_backup_str:
            show_reminder = True
            reason = "Non risulta essere mai stato eseguito un backup tramite il programma."
        else:
            try:
                last_backup_date = datetime.fromisoformat(last_backup_str)
                days_since_backup = (datetime.now() - last_backup_date).days
                if days_since_backup >= reminder_days:
                    show_reminder = True
                    reason = f"Sono passati {days_since_backup} giorni dall'ultimo backup (limite impostato: {reminder_days})."
            except ValueError:
                self.logger.warning("Timestamp dell'ultimo backup non valido.")
                show_reminder = True # In dubbio, meglio mostrare l'avviso
                reason = "Impossibile determinare la data dell'ultimo backup."

        if show_reminder:
            reply = QMessageBox.question(self, "Promemoria Backup",
                                        f"{reason}\nÈ fortemente consigliato eseguire un backup dei dati.\n\nVuoi andare alla sezione di backup ora?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.activate_tab_and_sub_tab("Sistema", "Backup/Ripristino DB")

    def _change_stylesheet(self, filename: str):
        """Carica, applica e salva il nuovo stylesheet selezionato."""
        self.logger.info(f"Cambio tema grafico richiesto: {filename}")
        
        # 'load_stylesheet' è già definita in gui_main.py
        new_stylesheet = load_stylesheet(filename)
        
        if new_stylesheet:
            # Applica lo stile all'intera applicazione
            QApplication.instance().setStyleSheet(new_stylesheet)
            
            # Salva la scelta nelle impostazioni per caricarla al prossimo avvio
            settings = QSettings()
            settings.setValue("UI/CurrentStyle", filename)
            
            QMessageBox.information(self, "Cambio Tema", f"Tema '{filename.replace('.qss', '').title()}' applicato con successo.")
        else:
            QMessageBox.warning(self, "Errore Tema", f"Impossibile caricare il file di stile '{filename}'.")
            
    def _show_about_eula_dialog(self):
        """Apre la finestra di dialogo con le informazioni su versione e licenza (EULA)."""
        dialog = EulaDialog(self)
        dialog.exec_()

    def apri_dialog_inserimento_comune(self):  # Metodo integrato nella classe
        if not self.db_manager:
            QMessageBox.critical(
                self, "Errore", "Manager Database non inizializzato.")
            return
        if not self.logged_in_user_info:
            QMessageBox.warning(self, "Login Richiesto",
                                "Effettuare il login per procedere.")
            return

        ruolo_utente = self.logged_in_user_info.get('ruolo')
        if ruolo_utente not in ['admin', 'archivista']:
            QMessageBox.warning(self, "Accesso Negato",
                                "Non si dispone delle autorizzazioni necessarie per aggiungere un comune.")
            return

        utente_login_username = self.logged_in_user_info.get(
            'username', 'log_utente_sconosciuto')

        dialog = InserimentoComuneWidget(
            self.db_manager, utente_login_username, self)  # Passa 'self' come parent
        if dialog.exec_() == QDialog.Accepted:
            logging.getLogger("CatastoGUI").info(
                f"Dialogo inserimento comune chiuso con successo da utente '{utente_login_username}'.")
            QMessageBox.information(
                self, "Comune Aggiunto", "Il nuovo comune è stato registrato con successo.")
            # Aggiorna la vista dell'elenco comuni se presente nel tab consultazione
            # Questo ciclo cerca il widget ElencoComuniWidget tra i sotto-tab di consultazione
            if hasattr(self, 'consultazione_sub_tabs'):
                for i in range(self.consultazione_sub_tabs.count()):
                    widget = self.consultazione_sub_tabs.widget(i)
                    if isinstance(widget, ElencoComuniWidget):
                        widget.load_comuni_data()  # Assumendo che ElencoComuniWidget abbia questo metodo
                        logging.getLogger("CatastoGUI").info(
                            "Principale nel tab consultazione aggiornato.")
                        break
        else:
            logging.getLogger("CatastoGUI").info(
                f"Dialogo inserimento comune annullato da utente '{utente_login_username}'.")

    def _apri_dialogo_configurazione_db(self):
        """Apre il dialogo di configurazione DB, pre-compilandolo con i valori correnti."""
        self.logger.info("Apertura dialogo configurazione DB dal menu.")
        settings = QSettings()

        # Raccoglie la configurazione attuale da QSettings
        current_config = {
            "db_type": settings.value("Database/Type", "local", type=str),
            "host": settings.value("Database/Host", "localhost", type=str),
            "port": settings.value("Database/Port", 5432, type=int),
            "dbname": settings.value("Database/DBName", "catasto_storico", type=str),
            "user": settings.value("Database/User", "postgres", type=str)
        }

        # Passa il dizionario di configurazione usando il nome corretto del parametro
        config_dialog = DBConfigDialog(self, initial_config=current_config)

        if config_dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(
                self, "Riavvio Necessario",
                "Le nuove impostazioni del database sono state salvate.\n"
                "È necessario riavviare l'applicazione per applicarle."
            )
            # Potremmo anche chiudere l'applicazione qui per forzare il riavvio
            # self.close()
    def _import_possessori_csv(self):
        """Gestisce l'avvio dell'importazione dei possessori tramite thread."""
        try:
            # PASSO 1: Selezione del comune
            comuni = self.db_manager.get_elenco_comuni_semplice()
            if not comuni:
                QMessageBox.warning(self, "Nessun Comune", "Nessun comune trovato nel database.")
                return

            nomi_comuni = [c[1] for c in comuni]
            nome_comune_selezionato, ok = QInputDialog.getItem(
                self, "Selezione Comune", "A quale comune vuoi associare i nuovi possessori?", nomi_comuni, 0, False
            )
            if not ok or not nome_comune_selezionato: return

            comune_id_selezionato = next((cid for cid, cnome in comuni if cnome == nome_comune_selezionato), None)

            # PASSO 2: Selezione del file CSV
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleziona il file CSV con i possessori", "", "File CSV (*.csv);;Tutti i file (*)"
            )
            if not file_path: return

            # PASSO 3: Setup UI e Thread
            # Creiamo un popup di attesa modale. Disabilitiamo il tasto "Annulla" per evitare
            # di troncare bruscamente la connessione a PostgreSQL.
            self.progress_dialog = QProgressDialog("Importazione in corso, l'operazione potrebbe richiedere alcuni minuti...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Importazione CSV - Meridiana")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.show()

            # Inizializziamo il thread
            self.import_thread = CSVImportThread(self.db_manager, 'possessori', file_path, comune_id_selezionato, nome_comune_selezionato)
            
            # Colleghiamo i segnali ai nuovi slot
            self.import_thread.finished_signal.connect(self._on_import_possessori_finished)
            self.import_thread.error_signal.connect(self._on_import_error)
            
            # Avviamo il lavoro in background
            self.import_thread.start()

        except Exception as e:
            self.logger.error(f"Errore durante la preparazione CSV: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore", f"Impossibile avviare l'importazione: {e}")

    def _handle_stale_data_refresh_click(self):
        """Gestisce il click con feedback visivo."""
        self.stale_data_refresh_btn.setEnabled(False)
        self.stale_data_refresh_btn.setText("In corso...")
        QCoreApplication.processEvents() 
        
        try:
            if self.db_manager.refresh_materialized_views(show_success_message=True):
                self.stale_data_bar.hide()
        finally:
            self.stale_data_refresh_btn.setEnabled(True)
            self.stale_data_refresh_btn.setText("Aggiorna Ora")

    # --- NUOVI SLOT PER LA GESTIONE DELLA FINE DEL THREAD ---
    
    def _on_import_possessori_finished(self, import_results):
        """Callback eseguita quando il thread dei possessori termina con successo."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            
        result_dialog = CSVImportResultDialog(
            import_results.get('success', []),
            import_results.get('errors', []),
            self
        )
        result_dialog.exec_()
        
        if self.elenco_comuni_widget_ref:
            self.elenco_comuni_widget_ref.load_data()

    def _on_import_error(self, error_msg):
        """Callback universale per gli errori nei thread di importazione."""
        self.logger.error(f"Errore sollevato dal thread CSV: {error_msg}")
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            
        QMessageBox.critical(self, "Errore Database", f"Si è verificato un errore durante l'importazione:\n\n{error_msg}")
    
    def _import_partite_csv(self):
        """Gestisce l'avvio dell'importazione delle partite tramite thread in background."""
        try:
            # PASSO 1: Selezione del comune
            comuni = self.db_manager.get_elenco_comuni_semplice()
            if not comuni:
                QMessageBox.warning(self, "Nessun Comune", "Nessun comune trovato nel database. Impossibile importare.")
                return

            nomi_comuni = [c[1] for c in comuni]
            nome_comune_selezionato, ok = QInputDialog.getItem(
                self, "Selezione Comune", "A quale comune vuoi associare le nuove partite?", nomi_comuni, 0, False
            )
            if not ok or not nome_comune_selezionato:
                return

            comune_id_selezionato = next((cid for cid, cnome in comuni if cnome == nome_comune_selezionato), None)
            if comune_id_selezionato is None:
                QMessageBox.critical(self, "Errore", "Impossibile trovare l'ID del comune selezionato.")
                return

            # PASSO 2: Selezione del file CSV
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleziona il file CSV con le partite", "", "File CSV (*.csv);;Tutti i file (*)"
            )
            if not file_path:
                return

            # PASSO 3: Setup interfaccia di attesa
            self.progress_dialog = QProgressDialog("Importazione partite in corso, l'operazione potrebbe richiedere alcuni minuti...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Importazione CSV - Meridiana")
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setCancelButton(None) # Disabilita l'annullamento per evitare corruzione
            self.progress_dialog.show()

            # Inizializzazione del thread (notare 'partite' come parametro)
            self.import_thread = CSVImportThread(
                self.db_manager, 'partite', file_path, comune_id_selezionato, nome_comune_selezionato
            )
            
            # Collegamento dei segnali
            self.import_thread.finished_signal.connect(self._on_import_partite_finished)
            self.import_thread.error_signal.connect(self._on_import_error) # Riutilizziamo lo slot degli errori già creato
            
            # Avvio dell'operazione asincrona
            self.import_thread.start()

        except Exception as e:
            self.logger.error(f"Errore imprevisto durante la preparazione CSV delle partite: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore Importazione", f"Impossibile avviare l'importazione:\n{e}")

    # --- NUOVO SLOT PER IL COMPLETAMENTO DELLE PARTITE ---
    
    def _on_import_partite_finished(self, import_results):
        """Callback eseguita quando il thread delle partite termina con successo."""
        # Chiude il popup di attesa
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            
        # Formatta i dati di successo per adattarli al layout del CSVImportResultDialog
        success_display_data = []
        for row in import_results.get('success', []):
            suffisso = row.get('suffisso_partita') or ''
            nome_formattato = f"Partita N.{row.get('numero_partita')} {suffisso}".strip()
            
            success_display_data.append({
                'id': row.get('id'),
                'nome_completo': nome_formattato,
                'comune_nome': row.get('comune_nome')
            })

        # Mostra la finestra di riepilogo
        result_dialog = CSVImportResultDialog(
            success_display_data,
            import_results.get('errors', []),
            self
        )
        result_dialog.setWindowTitle("Riepilogo Importazione Partite")
        result_dialog.exec_()
        
        # Aggiorna la dashboard sottostante
        if self.elenco_comuni_widget_ref:
            self.elenco_comuni_widget_ref.load_data()
    def check_mv_refresh_status(self):
        """
        Controlla il timestamp dell'ultimo aggiornamento e mostra la barra di notifica se i dati sono obsoleti.
        """
        from datetime import timedelta, timezone
        if not self.db_manager or not self.db_manager.pool: return
        # --- MODIFICA QUI: Leggiamo il valore da QSettings ---
        settings = QSettings()
        threshold_hours = settings.value("General/StaleDataThresholdHours", 24, type=int)
        # ----------------------------------------------------

        last_refresh = self.db_manager.get_last_mv_refresh_timestamp()
        if last_refresh is None:
            # Se non c'è mai stato un refresh, consideriamo i dati obsoleti
            self.stale_data_label.setText("I dati delle statistiche non sono mai stati aggiornati.")
            self.stale_data_bar.show()
            return
        
        # Usiamo la soglia personalizzata
        staleness_threshold = timedelta(hours=threshold_hours)
        time_since_refresh = datetime.now(timezone.utc) - last_refresh

        if time_since_refresh > staleness_threshold:
            hours_ago = int(time_since_refresh.total_seconds() / 3600)
            # Mostriamo la soglia impostata nel messaggio
            self.stale_data_label.setText(f"I dati delle statistiche non sono aggiornati da circa {hours_ago} ore (soglia: {threshold_hours} ore).")
            self.stale_data_bar.show()
        else:
            self.stale_data_bar.hide()
    def _apri_dialogo_impostazioni_aggiornamento(self):
        """
        Apre un dialogo per permettere all'utente di impostare la soglia (in ore)
        per considerare i dati delle viste materializzate come obsoleti.
        """
        settings = QSettings()
        
        # Legge il valore corrente per mostrarlo come default (default a 24 se non esiste)
        current_threshold = settings.value("General/StaleDataThresholdHours", 24, type=int)
        
        # Apre un dialogo per l'inserimento di un numero intero
        new_threshold, ok = QInputDialog.getInt(
            self,
            "Soglia Aggiornamento Dati",
            "Dopo quante ore i dati delle statistiche devono essere considerati obsoleti?",
            value=current_threshold, # Valore di partenza
            min=1,                 # Minimo 1 ora
            max=720,               # Massimo 30 giorni (720 ore)
            step=1                 # Incremento di 1
        )
        
        # Se l'utente preme "OK" e il valore è valido
        if ok:
            # Salva il nuovo valore nelle impostazioni dell'applicazione
            settings.setValue("General/StaleDataThresholdHours", new_threshold)
            QMessageBox.information(self, "Impostazione Salvata",
                                    f"La nuova soglia di {new_threshold} ore è stata salvata.\n"
                                    "La modifica sarà effettiva al prossimo riavvio dell'applicazione.")


    
    def _apri_manuale_utente(self):
        """
        Apre il file PDF del manuale utente situato nella cartella 'resources'.
        """
        try:
            # Lista di percorsi possibili per il manuale
            possible_paths = []
            
            # Percorso 1: Usando get_resource_path (originale)
            try:
                manual_path_1 = get_resource_path(os.path.join("resources", "manuale_utente.pdf"))
                possible_paths.append(manual_path_1)
            except:
                pass
            
            # Percorso 2: Relativo all'eseguibile
            if getattr(sys, 'frozen', False):
                # Applicazione compilata
                exe_dir = os.path.dirname(sys.executable)
                manual_path_2 = os.path.join(exe_dir, "resources", "manuale_utente.pdf")
                possible_paths.append(manual_path_2)
                
                # Percorso 3: Nella cartella _internal (PyInstaller)
                manual_path_3 = os.path.join(exe_dir, "_internal", "resources", "manuale_utente.pdf")
                possible_paths.append(manual_path_3)
            
            # Percorso 4: Relativo allo script principale
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            manual_path_4 = os.path.join(base_dir, "resources", "manuale_utente.pdf")
            possible_paths.append(manual_path_4)
            
            # Percorso 5: Directory corrente
            manual_path_5 = os.path.join(os.getcwd(), "resources", "manuale_utente.pdf")
            possible_paths.append(manual_path_5)
            
            # Cerca il primo percorso valido
            found_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    found_path = path
                    break
            
            if found_path:
                self.logger.info(f"Manuale trovato al percorso: {found_path}")
                QDesktopServices.openUrl(QUrl.fromLocalFile(found_path))
            else:
                # Log di debug per vedere tutti i percorsi tentati
                self.logger.error(f"Manuale non trovato. Percorsi tentati:")
                for i, path in enumerate(possible_paths, 1):
                    self.logger.error(f"  {i}. {path}")
                
                QMessageBox.warning(self, "Manuale Non Trovato",
                                f"Il file del manuale utente non è stato trovato.\n\n"
                                f"Percorsi verificati:\n" + 
                                "\n".join([f"• {path}" for path in possible_paths[:3]]))
                                
        except Exception as e:
            self.logger.error(f"Errore imprevisto durante l'apertura del manuale: {e}", exc_info=True)
            QMessageBox.critical(self, "Errore", f"Impossibile aprire il manuale:\n{e}")
            
    def _esporta_log_sistema(self):
        """Comprime e salva i file di log per l'assistenza tecnica."""
        app_data_path = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        log_base_path = os.path.join(app_data_path, "meridiana_session.log")
        
        if not os.path.exists(log_base_path):
            QMessageBox.warning(self, "Attenzione", "Nessun file di log trovato nel sistema.")
            return

        # Chiede all'utente dove salvare il file ZIP
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Esporta Log per Assistenza", "Log_Meridiana_Assistenza.zip", "Archivio ZIP (*.zip)"
        )
        
        if save_path:
            try:
                # Assicurati che l'estensione sia .zip
                if not save_path.lower().endswith('.zip'):
                    save_path += '.zip'
                    
                with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Aggiunge il log corrente
                    zipf.write(log_base_path, os.path.basename(log_base_path))
                    
                    # Cerca e aggiunge eventuali log storici creati dalla rotazione (.1, .2, .3)
                    for i in range(1, 4):
                        old_log = f"{log_base_path}.{i}"
                        if os.path.exists(old_log):
                            zipf.write(old_log, os.path.basename(old_log))
                            
                QMessageBox.information(self, "Esportazione Completata", 
                                        "I file di log sono stati salvati con successo.\n"
                                        "Puoi inviare questo file ZIP al supporto tecnico.")
                self.logger.info(f"Log di sistema esportati dall'utente in: {save_path}")
            except Exception as e:
                self.logger.error(f"Errore durante l'esportazione dei log: {e}", exc_info=True)
                QMessageBox.critical(self, "Errore", f"Impossibile creare il file ZIP:\n{e}")
    def _show_backup_settings_dialog(self):
        dialog = BackupReminderSettingsDialog(self)
        dialog.exec_()

