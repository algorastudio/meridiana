# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Raccoglie dati aggiuntivi da pacchetti che li richiedono
pyqt5_datas = collect_data_files('PyQt5', includes=['Qt5/plugins/**/*'])
fpdf2_datas = collect_data_files('fpdf')
pandas_datas = collect_data_files('pandas')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),
        ('styles', 'styles'),
        ('docs', 'docs'),
        ('db_modules', 'db_modules'),
        ('models', 'models'),
        ('views', 'views'),
        *fpdf2_datas,
        *pandas_datas,
    ],
    hiddenimports=[
        # Pacchetti interni del progetto
        'db_modules',
        'db_modules.base_manager',
        'db_modules.comuni_mixin',
        'db_modules.partite_mixin',
        'db_modules.possessori_mixin',
        'db_modules.immobili_mixin',
        'db_modules.localita_mixin',
        'db_modules.tipologiche_mixin',
        'db_modules.variazioni_mixin',
        'db_modules.documenti_mixin',
        'db_modules.relazioni_mixin',
        'db_modules.utenti_mixin',
        'db_modules.sistema_mixin',
        'db_modules.report_mixin',
        'db_modules.ricerca_mixin',
        'models',
        'models.comune',
        'models.consultazione',
        'models.documento',
        'models.immobile',
        'models.localita',
        'models.partita',
        'models.possessore',
        'models.variazione',
        'views',
        'views.amministrazione',
        'views.comuni',
        'views.dashboard',
        'views.localita',
        'views.partite',
        'views.possessori_immobili',
        'views.ricerca',
        'views.strumenti',
        # psycopg2
        'psycopg2',
        'psycopg2._psycopg',
        'psycopg2.extensions',
        'psycopg2.extras',
        'psycopg2.errors',
        'psycopg2.pool',
        'psycopg2._json',
        'psycopg2._range',
        # PyQt5 plugin e moduli
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtNetwork',
        'PyQt5.sip',
        # PyQtWebEngine (se usato per visualizzazione HTML)
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebChannel',
        # pandas e numpy
        'pandas',
        'pandas.io.formats.style',
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        # openpyxl
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'et_xmlfile',
        # fpdf2
        'fpdf',
        'fpdf.image_datastructures',
        'fpdf.image_types',
        # Pillow
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # bcrypt
        'bcrypt',
        # keyring (Windows backends)
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.backends.fail',
        # Altri
        'dateutil',
        'dateutil.relativedelta',
        'six',
        'pytz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Esclude moduli inutili per ridurre dimensioni
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'pytest',
        'setuptools',
        'pkg_resources',
        'unittest',
        'xmlrpc',
        'http.server',
        'email',
        'html',
        'urllib3',
        'requests',
        'cryptography',
        'ssl',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Meridiana',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icona_meridiana.ico',
    version='version.txt',
    copyright='Copyright © Marco Santoro. In gentile concessione gratuita all\'Archivio di Stato di Savona.'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Meridiana'
)
