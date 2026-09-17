; =====================================================================
; ClassFellow - Inno Setup 6 Script (installer.iss)
; =====================================================================
; Packages standalone Windows 64-bit distribution into a professional setup wizard.
; Compiler: Inno Setup 6.x (ISCC.exe)
; Target Output: dist/ClassFellow_v1.0.0_Setup.exe
; =====================================================================

#define MyAppName "ClassFellow"
#define MyAppVersion "1.0.0-mvp"
#define MyAppPublisher "UCC Developer Platform"
#define MyAppURL "https://github.com/UCC-Developer-platform/ClassFellow"
#define MyAppExeName "ClassFellow.exe"
#define MyAppAssocName "ClassFellow Database"
#define MyAppAssocExt ".cfdb"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
; Unique Application ID (GUID generated specifically for ClassFellow)
AppId={{E7B6194E-8C83-4E6C-9A82-C895788484E9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output setup binary settings
OutputDir=dist
OutputBaseFilename=ClassFellow_v1.0.0_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Enforce 64-bit Windows targeting
ArchitecturesInstallIn64BitMode=x64compatible
; Allow user to choose install scope (All Users vs. Current User)
PrivilegesRequiredOverridesAllowed=commandline dialog
PrivilegesRequired=lowest
; Uninstallation metadata
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} School & Academy Management Software
DisableProgramGroupPage=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main Executable
Source: "dist\ClassFellow\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Bundled Python runtime, dynamic libraries, and packages
Source: "dist\ClassFellow\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; User-configurable theme and module licensing flags
Source: "config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs; Flags: skipifsourcedoesntexist

; Bundled Unicode TrueType and Urdu fonts
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Flags: skipifsourcedoesntexist

[Dirs]
; Safe local directories for institutional databases, backups, and error logs
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\backups"; Permissions: users-modify
Name: "{app}\data\backups\daily"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
; Start Menu and Desktop shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch ClassFellow immediately upon installation completion
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up runtime logs and temporary cache files
Type: files; Name: "{app}\logs\*.log"
Type: files; Name: "{app}\*.log"
Type: filesandordirs; Name: "{app}\__pycache__"
; Note: {app}\data and {app}\data\backups are intentionally PRESERVED during uninstall
; to safeguard institutional student records, fee receipts, and database snapshots.
