#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from PyQt5.QtCore import QCoreApplication, QSettings, Qt, QStandardPaths
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog

from catasto_db_manager import CatastoDBManager
from app_utils import get_local_ip_address, get_password_from_keyring
from app_paths import load_stylesheet, get_logo_path
from config import SETTINGS_DB_TYPE, SETTINGS_DB_HOST, SETTINGS_DB_PORT, SETTINGS_DB_NAME, SETTINGS_DB_USER, SETTINGS_DB_SCHEMA, SETTINGS_DB_PASSWORD
from dialogs import DBConfigDialog, EulaDialog
from gui_auth import LoginDialog
from gui_widgets import WelcomeScreen
from gui_main import CatastoMainWindow

  
def setup_global_logging():
    """
    Configura il logging in modo centralizzato e sicuro, scrivendo i file
    nella cartella AppData dell'utente, con rotazione automatica.
    """
    QCoreApplication.setOrganizationName("ArchivioDiStatoSavona")
    QCoreApplication.setApplicationName("Meridiana")
    
    app_data_path = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    os.makedirs(app_data_path, exist_ok=True)
    
    log_file_path = os.path.join(app_data_path, "meridiana_session.log")
    
    # Configurazione del RotatingFileHandler
    # maxBytes: 5 MB (5 * 1024 * 1024 byte)
    # backupCount: 3 (mantiene log.1, log.2, log.3 prima di sovrascriverli)
    file_handler = RotatingFileHandler(
        log_file_path, 
        mode='a', 
        maxBytes=5 * 1024 * 1024, 
        backupCount=3, 
        encoding='utf-8'
    )
    
    stream_handler = logging.StreamHandler(sys.stdout)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        handlers=[file_handler, stream_handler],
        force=True 
    )
    
    logging.info(f"Logging configurato con rotazione (Max 5MB, 3 file storici). I log verranno salvati in: {log_file_path}")
def run_gui_app():
    try:
        # --- AGGIUNTA QUI ---
        # Abilita il ridimensionamento per schermi ad alta risoluzione (4K/Retina)
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        # --------------------
        app = QApplication(sys.argv)
        # --- INIZIO MODIFICA ---
        # Imposta i metadati dell'applicazione.
        # Questo è FONDAMENTALE affinché QStandardPaths possa generare
        # percorsi di dati scrivibili e univoci per l'app.
        QCoreApplication.setOrganizationName("Marco Santoro")
        QCoreApplication.setApplicationName("Meridiana")
        # --- FINE MODIFICA ---

        # --- CHIAMATA ALLA NUOVA FUNZIONE QUI ---
        # Questo imposta il logging per l'intera applicazione prima che qualsiasi
        # altra cosa venga importata o eseguita.
        setup_global_logging()
        # --- FINE CHIAMATA ---

        # Ora puoi ottenere il logger già configurato
        gui_logger = logging.getLogger("CatastoGUI")

        # Il resto della funzione rimane identico...
        client_ip_address_gui = get_local_ip_address()
        gui_logger.info(f"Indirizzo IP locale identificato: {client_ip_address_gui}")

        settings = QSettings()
        current_style_file = settings.value("UI/CurrentStyle", "meridiana_style.qss", type=str)
        stylesheet = load_stylesheet(current_style_file)
        if stylesheet:
            app.setStyleSheet(stylesheet)
        # --- FINE MODIFICA ---
        # --- INIZIO BLOCCO CONTROLLO EULA ---
        settings = QSettings()
        eula_accepted = settings.value("EULA/accepted", False, type=bool)

        if not eula_accepted:
            eula_dialog = EulaDialog()
            if eula_dialog.exec_() == QDialog.Accepted:
                # L'utente ha accettato, salva l'impostazione e procedi
                settings.setValue("EULA/accepted", True)
                settings.sync()
            else:
                # L'utente ha rifiutato, esci dall'applicazione
                sys.exit(0)
        # --- FINE BLOCCO CONTROLLO EULA ---
        
        gui_logger.info("Avvio dell'applicazione GUI Catasto Storico...")
        db_manager_gui: Optional[CatastoDBManager] = None
        main_window_instance = CatastoMainWindow(client_ip_address_gui)

        # --- NUOVO FLUSSO DI AVVIO ---

         # 1. TENTATIVO DI CONNESSIONE AUTOMATICA
        gui_logger.info("Tentativo di connessione automatica con le impostazioni salvate...")
        
        # --- CORREZIONE: Gestisci la password in modo più robusto ---
        saved_password = settings.value(SETTINGS_DB_PASSWORD, "", type=str)
        
        # Se non c'è password salvata, prova a prenderla dal keyring
        if not saved_password:
            db_host = settings.value(SETTINGS_DB_HOST, "localhost", type=str)
            db_user = settings.value(SETTINGS_DB_USER, "postgres", type=str)
            saved_password = get_password_from_keyring(db_host, db_user)
        
        saved_config = {
            "host": settings.value(SETTINGS_DB_HOST, "localhost", type=str),
            "port": settings.value(SETTINGS_DB_PORT, 5432, type=int),
            "dbname": settings.value(SETTINGS_DB_NAME, "catasto_storico", type=str),
            "user": settings.value(SETTINGS_DB_USER, "postgres", type=str),
            "password": saved_password or ""  # Assicurati che ci sia sempre una password (anche vuota)
        }
        
        # Prova a connettere solo se sono presenti i dati essenziali E la password
        if saved_config["dbname"] and saved_config["user"] and saved_config["password"]:
            try:
                db_manager_gui = CatastoDBManager(**saved_config)
                if db_manager_gui.initialize_main_pool():
                    main_window_instance.db_manager = db_manager_gui
                    main_window_instance.pool_initialized_successful = True
                    gui_logger.info("Connessione automatica riuscita.")
                else:
                    db_manager_gui = None # Resetta se fallisce
            except Exception as e:
                gui_logger.warning(f"Errore durante la creazione di CatastoDBManager: {e}")
                db_manager_gui = None
        else:
            gui_logger.info("Dati di connessione incompleti (manca password o altri parametri essenziali). Skip connessione automatica.")
            db_manager_gui = None
        # --- FINE CORREZIONE ---
        
        # 2. FALLBACK A CONFIGURAZIONE MANUALE se la connessione automatica è fallita
        if not db_manager_gui or not db_manager_gui.pool:
            gui_logger.warning("Connessione automatica fallita. Apertura dialogo di configurazione manuale.")
            QMessageBox.information(None, "Configurazione Database", "Impossibile connettersi con le impostazioni salvate. Apriamo la configurazione.")

            while True: # Loop per riprovare la configurazione manuale
                config_dialog = DBConfigDialog(parent=None)
                # --- INIZIO MODIFICA: Leggiamo le impostazioni AD OGNI ciclo ---
                db_type = settings.value("Database/Type", "local", type=str)
                db_host = settings.value("Database/Host", "localhost", type=str)
                db_port = settings.value("Database/Port", 5432, type=int)
                db_name = settings.value("Database/DBName", "catasto_storico", type=str)
                db_user = settings.value("Database/User", "postgres", type=str)
                db_password = get_password_from_keyring(db_host, db_user)
                # --- FINE MODIFICA ---
                
                if config_dialog.exec_() != QDialog.Accepted:
                    gui_logger.info("Configurazione manuale annullata. Uscita.")
                    sys.exit(0)

                current_config = config_dialog.get_config_values(include_password=True)
                
                # --- CORREZIONE: Filtra solo i parametri supportati da CatastoDBManager ---
                db_manager_params = {
                    'host': current_config.get('host'),
                    'port': current_config.get('port'), 
                    'dbname': current_config.get('dbname'),
                    'user': current_config.get('user'),
                    'password': current_config.get('password', '')  # Assicurati che ci sia sempre una password
                }
                
                # Rimuovi eventuali chiavi con valore None (ma mantieni password vuota se necessario)
                db_manager_params = {k: v for k, v in db_manager_params.items() if v is not None}
                
                # Assicurati che password sia sempre presente
                if 'password' not in db_manager_params:
                    db_manager_params['password'] = ''
                
                try:
                    db_manager_gui = CatastoDBManager(**db_manager_params)
                except Exception as e:
                    gui_logger.error(f"Errore creazione CatastoDBManager: {e}")
                    QMessageBox.critical(None, "Errore Configurazione", f"Errore nella configurazione del database: {e}")
                    continue  # Riprova il loop di configurazione
                # --- FINE CORREZIONE ---
                
                if db_manager_gui.initialize_main_pool():
                    main_window_instance.db_manager = db_manager_gui
                    main_window_instance.pool_initialized_successful = True
                    gui_logger.info("Connessione manuale riuscita.")
                    break # Esce dal loop di configurazione
                else:
                    # Mostra l'errore specifico e il loop continuerà, riaprendo il dialogo
                    error_details = db_manager_gui.get_last_connect_error_details() or {}
                    pgcode = error_details.get('pgcode')
                    pgerror_msg = error_details.get('pgerror')
                    
                    if pgcode == '28P01': 
                        QMessageBox.critical(None, "Errore Autenticazione", "Password o utente errati.")
                    else: 
                        QMessageBox.critical(None, "Errore Connessione", f"Impossibile connettersi.\n{pgerror_msg}")

        # 3. SE LA CONNESSIONE (auto o manuale) è OK, PROCEDI CON IL LOGIN UTENTE
        # --- INIZIO MODIFICA ---
        # Passiamo la variabile 'client_ip_address_gui' al costruttore del LoginDialog
        login_dialog = LoginDialog(db_manager_gui, client_ip_address_gui, parent=main_window_instance)
        # --- FINE MODIFICA ---
        if login_dialog.exec_() != QDialog.Accepted:
            gui_logger.info("Login utente annullato. Uscita.")
            sys.exit(0)

        # 4. LOGIN UTENTE OK, MOSTRA WELCOME SCREEN E AVVIA L'APP
        base_dir_app = os.path.dirname(os.path.abspath(sys.argv[0]))
        logo_path = get_logo_path()
        manuale_path = None
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            possible_manual_paths = [
                os.path.join(exe_dir, "resources", "manuale_utente.pdf"),
                os.path.join(exe_dir, "_internal", "resources", "manuale_utente.pdf")
            ]
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            possible_manual_paths = [
                os.path.join(base_dir, "resources", "manuale_utente.pdf")
            ]
            
        for path in possible_manual_paths:
            if os.path.exists(path):
                manuale_path = path
                break

        welcome_screen = WelcomeScreen(parent=None, logo_path=logo_path, help_url=manuale_path)
        if welcome_screen.exec_() != QDialog.Accepted:
            gui_logger.info("Welcome screen chiusa. Uscita.")
            sys.exit(0)
            
        main_window_instance.perform_initial_setup(
            db_manager_gui,
            login_dialog.logged_in_user_id,
            login_dialog.logged_in_user_info,
            login_dialog.current_session_id_from_dialog
        )
        
        gui_logger.info("Setup completato. Avvio loop eventi.")
        sys.exit(app.exec_())

    except Exception as e:
        # Blocco di gestione crash (invariato)
        logging.basicConfig(filename='crash_report.log', level=logging.DEBUG)
        logging.exception("CRASH IMPREVISTO ALL'AVVIO:")
        QMessageBox.critical(None, "Errore Critico", f"Errore fatale: {e}\nControlla crash_report.log.")
        sys.exit(1)


if __name__ == "__main__":
    
    
    
    # Importa qui per evitare importazioni circolari (se necessario)
    import traceback
    
    try:
        run_gui_app()
    except Exception as e:
        # Log dell'errore critico
        logging.getLogger("CatastoGUI").critical(f"Errore critico all'avvio dell'applicazione: {e}", exc_info=True)
        traceback.print_exc()
        
        # Mostra messaggio di errore all'utente
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            if not QApplication.instance():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Errore Critico", 
                               f"Si è verificato un errore critico:\n\n{str(e)}\n\n"
                               "Controlla il file catasto_gui.log per maggiori dettagli.")
        except:
            print(f"ERRORE CRITICO: {e}")
            print("Controlla il file catasto_gui.log per maggiori dettagli.")
        
        sys.exit(1)