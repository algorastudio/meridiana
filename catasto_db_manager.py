import psycopg2
import psycopg2.errors # Importa specificamente gli errori
from psycopg2.extras import DictCursor
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE,ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql, extras, pool
import sys, csv
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple, Union
import json
import uuid
import os
import shutil # Per trovare i percorsi degli eseguibili
from contextlib import contextmanager
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QApplication, 
                             QCheckBox, QComboBox, QDateEdit, QDateTimeEdit,
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QFrame, QGridLayout,
                             QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMenu, QMessageBox, QProgressBar,
                             QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
                             QSpinBox, QStyle, QStyleFactory, QTabWidget,
                             QTableWidget, QTableWidgetItem, QTextEdit,
                             QVBoxLayout,QProgressDialog)
from PyQt5.QtCore import (QDate, QDateTime, QPoint, QProcess, QSettings, 
                          QSize, QStandardPaths, Qt, QTimer, QUrl, 
                          pyqtSignal,QProcessEnvironment,QObject)

COLONNE_POSSESSORI_DETTAGLI_NUM = 6 # Esempio: ID, Nome Compl, Cognome/Nome, Paternità, Quota, Titolo
COLONNE_POSSESSORI_DETTAGLI_LABELS = ["ID Poss.", "Nome Completo", "Cognome Nome", "Paternità", "Quota", "Titolo"]
logger = logging.getLogger(__name__)
class DBMError(Exception):
    """Classe base per errori specifici del DBManager."""
    pass
class DBUniqueConstraintError(DBMError):
    """Sollevata quando un vincolo di unicità viene violato."""
    def __init__(self, message, constraint_name=None, details=None):
        super().__init__(message)
        self.constraint_name = constraint_name
        self.details = details
class DBNotFoundError(DBMError):
    """Sollevata quando un record atteso non viene trovato per un'operazione."""
    pass
class DBDataError(DBMError):
    """Sollevata per errori relativi a dati o parametri forniti non validi."""
    pass

from db_modules.base_manager import BaseDBManager
from db_modules.comuni_mixin import ComuniMixin
from db_modules.partite_mixin import PartiteMixin
from db_modules.possessori_mixin import PossessoriMixin
from db_modules.immobili_mixin import ImmobiliMixin
from db_modules.localita_mixin import LocalitaMixin
from db_modules.tipologiche_mixin import TipologicheMixin
from db_modules.variazioni_mixin import VariazioniMixin
from db_modules.documenti_mixin import DocumentiMixin
from db_modules.relazioni_mixin import RelazioniMixin
from db_modules.utenti_mixin import UtentiMixin
from db_modules.sistema_mixin import SistemaMixin
from db_modules.report_mixin import ReportMixin
from db_modules.ricerca_mixin import RicercaMixin

class CatastoDBManager(BaseDBManager, ComuniMixin, PartiteMixin, PossessoriMixin, ImmobiliMixin, LocalitaMixin, TipologicheMixin, VariazioniMixin, DocumentiMixin, RelazioniMixin, UtentiMixin, SistemaMixin, ReportMixin, RicercaMixin):
    pass
