; Inno Setup script for STZ Downloader.
;
; Build with scripts\build_installer.ps1, which passes AppVersion from
; pyproject.toml so the installer version never drifts from the app's.
;
; Per-user install by default: the app writes only to %APPDATA% and registers
; launch-at-login under HKCU, so nothing here needs administrator rights and
; the user never sees a UAC prompt.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

; The folder to package: the Qt build (default) or the Tauri desktop build,
; see scripts\build_installer.ps1 -Desktop.
#ifndef SourceDir
  #define SourceDir "..\..\dist\stz-downloader"
#endif
#ifndef OutputName
  #define OutputName "stz-downloader-" + AppVersion + "-setup"
#endif

#define AppName "STZ Downloader"
#define AppPublisher "STZ Labs"
#define AppExeName "stz-downloader.exe"
#define AppUrl "https://stzlabs.com"

[Setup]
; Never change AppId -- it is what ties an upgrade to an existing install.
AppId={{7C4B2E9A-3F5D-4A81-9B6C-2E7D8F1A4C30}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/pt/support
AppUpdatesURL={#AppUrl}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename={#OutputName}
SetupIconFile=..\..\assets\stz-downloader.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; x64 only: the bundled aria2c.exe and the frozen app are both 64-bit.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Ask for no more rights than needed; the user can still choose a
; machine-wide location, which is when Windows will prompt.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; The app normally sits in the tray, so an upgrade will find it running.
; Restart Manager cannot close it: aria2c.exe is windowless and the native
; messaging host is owned by the browser for as long as the extension keeps
; its port open, so it reports "could not close all applications". Restart
; Manager also runs before PrepareToInstall, so it is switched off and
; [Code] below terminates all three processes before files are replaced.
CloseApplications=no
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; The runtime folder is rebuilt from scratch on every install, so switching
; between the Qt and desktop builds never leaves the other's libraries behind.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; The whole PyInstaller onedir tree, including third_party\aria2 with its
; GPL licence text and the pointer to the corresponding source.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Only ever deleted, never created: the app owns this value (see
; autostart.py) and toggles it from settings. This just stops an uninstall
; leaving an entry that points at a binary which no longer exists.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueName: "STZ Downloader"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\stz-downloader-native-host.exe"; Parameters: "--register"; \
    Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent
; In-app updates run this installer silently with /AUTOUPDATE=1; the app was
; stopped for the upgrade, so start it again (as the user, not elevated).
Filename: "{app}\{#AppExeName}"; Flags: nowait runasoriginaluser; Check: IsAutoUpdate

[UninstallRun]
Filename: "{app}\stz-downloader-native-host.exe"; Parameters: "--unregister"; \
    Flags: runhidden waituntilterminated skipifdoesntexist; \
    RunOnceId: "UnregisterNativeMessagingHost"

[UninstallDelete]
; PyInstaller writes nothing here at runtime, but aria2's session file and
; logs live in %APPDATA% and are deliberately left behind: an uninstall
; should not silently discard a user's download queue.
Type: dirifempty; Name: "{app}"

[Code]
function IsAutoUpdate: Boolean;
begin
  Result := ExpandConstant('{param:AUTOUPDATE|0}') = '1';
end;

// Stop every process that may hold files in {app}. Killing is safe: aria2
// saves its session periodically and the app restarts it on next launch,
// and the browser extension reconnects the native host on its next message.
procedure KillProcess(const ImageName: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "' + ImageName + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure StopRunningApp;
begin
  KillProcess('{#AppExeName}');
  KillProcess('stz-engine.exe');
  KillProcess('aria2c.exe');
  KillProcess('stz-downloader-native-host.exe');
  // Give Windows a moment to release the image file handles.
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningApp;
  Result := True;
end;
