; Inno Setup script for Quantify Viability.
;
; Wraps the PyInstaller one-folder build (dist\QuantifyViability) in a
; per-user Windows installer: Start Menu entry, optional desktop shortcut,
; and an uninstaller. No administrator rights required.
;
; Build (after build_exe.bat has produced dist\QuantifyViability):
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
; Produces:  installer\QuantifyViability-Setup.exe

#define AppName "Quantify Viability"
#define AppVersion "1.0.0"
#define AppExe "QuantifyViability.exe"
#define AppPublisher "Hao Research Group, University of Maryland"
#define AppUrl "https://github.com/shihj12/Quantify-Viability"

[Setup]
AppId={{A7E3F1C8-9B24-4D6E-8F35-2C1A7B0E9D44}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=QuantifyViability-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\QuantifyViability\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
