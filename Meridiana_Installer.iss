; Script per Inno Setup per l'applicazione Meridiana
; Creato da Supporto Definitivo per il Tirocinio per Marco Santoro

; --- DEFINIZIONE COSTANTI ---
; Usare le costanti rende lo script più pulito e facile da manutenere per versioni future.
#define MyAppName "Meridiana"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "Marco Santoro"
#define MyAppURL "https://github.com/saintgold74/catasto"
#define MyAppExeName "Meridiana.exe"
#define MyCopyright "Copyright © Marco Santoro. In gentile concessione gratuita all'Archivio di Stato di Savona."

[Setup]
; --- INFORMAZIONI PRINCIPALI SULL'APP E SULL'INSTALLER ---
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppId={{51E4F5FB-B2AB-4D5F-A1B2-C7D9E8F1A2B3}}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowConcurrentInstallation=no
; Specifica dove salvare l'installer finale e come chiamarlo.
OutputDir=Installer
OutputBaseFilename=Meridiana_{#MyAppVersion}_Setup
SetupIconFile=resources\icona_meridiana.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallLogMode=append

; --- INFORMAZIONI DI VERSIONE INCLUSE NELL'ESEGUIBILE DELL'INSTALLER ---
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Installazione di Meridiana - Archivio Catastale Storico
VersionInfoCopyright={#MyCopyright}

; --- LICENZA D'USO (EULA) ---
; Mostra il file di licenza prima dell'installazione.
; Assicurarsi che il file si trovi nel percorso specificato.
LicenseFile=resources\EULA.rtf

[Languages]
; Imposta la lingua dell'installer.
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
; Aggiunge una casella di controllo per creare un'icona sul desktop.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; --- COPIA DEI FILE DELL'APPLICAZIONE ---
; Questa è la sezione più importante. Copia TUTTO il contenuto della cartella
; generata da PyInstaller nella directory di installazione dell'utente.
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; --- CREAZIONE DEI COLLEGAMENTI (ICONE) ---
; Crea l'icona nel Menu Start.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Crea l'icona sul Desktop se l'utente ha spuntato la casella nel wizard.
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; --- ESECUZIONE POST-INSTALLAZIONE ---
; Offre all'utente la possibilità di avviare il programma subito dopo l'installazione.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallRegistryPath = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{51E4F5FB-B2AB-4D5F-A1B2-C7D9E8F1A2B3}_is1}';

function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{{51E4F5FB-B2AB-4D5F-A1B2-C7D9E8F1A2B3}_is1}');
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

function UnInstallOldVersion(): Integer;
var
  sUnInstallString: String;
  iResultCode: Integer;
begin
  Result := 0;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then begin
    sUnInstallString := RemoveQuotes(sUnInstallString);
    if Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
      Result := 0
    else
      Result := iResultCode;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) then
  begin
    if IsUpgrade() then
      UnInstallOldVersion();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DirExists(ExpandConstant('{app}')) then
      DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;