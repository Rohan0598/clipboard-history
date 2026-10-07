; Stage 8: Windows installer for Clipboard History (built with Inno Setup).
; build.py compiles this automatically. You can also open it in Inno Setup and press Compile.
;
; What the installer does:
;   - installs into C:\Users\<you>\AppData\Local\Programs\ClipboardHistory (no admin needed)
;   - adds "Clipboard History" to Settings > Apps > Installed apps, with Uninstall
;   - adds a Start menu shortcut
;   - (ticked by default) starts the app automatically when you sign in
; Your history (AppData\Roaming\ClipboardHistory) is NOT deleted on uninstall.

#define MyAppName "Clipboard History"
#define MyAppVersion "1.3.0"
#define MyAppExe "ClipboardHistory.exe"
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"

[Setup]
; AppId identifies this app to Windows. Never change it, or upgrades install as a separate app.
AppId={{8F2C6B1E-4D7A-4E3B-9C51-2A6F0D3E7B94}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Personal project
DefaultDirName={autopf}\ClipboardHistory
DisableProgramGroupPage=yes
; "lowest" = install just for you, no admin prompt. {autopf} then means AppData\Local\Programs.
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ClipboardHistory-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "startup"; Description: "Start Clipboard History automatically when I sign in"; GroupDescription: "Options:"

[Files]
; Everything PyInstaller produced: the .exe plus the _internal folder.
Source: "dist\ClipboardHistory\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"

[Registry]
; Same entry the tray's "Start with Windows" tick uses, so the two always agree.
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "ClipboardHistory"; \
    ValueData: """{app}\{#MyAppExe}"""; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Start Clipboard History now"; Flags: nowait postinstall skipifsilent

[Code]
// Files can't be replaced or removed while the app is running, so close it first.
procedure CloseRunningApp;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#MyAppExe}', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseRunningApp;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CloseRunningApp;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Remove the auto-start entry even if it was switched on later from the tray menu.
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, '{#RunKey}', 'ClipboardHistory');
end;
