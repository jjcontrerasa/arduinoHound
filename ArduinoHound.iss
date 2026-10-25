; Inno Setup: compilar con ISCC.exe ArduinoHound.iss (requiere dist\ArduinoHound de PyInstaller)
#define AppName "Arduino Hound V3"
#define AppVersion "3.0.0"
#define AppPublisher "Instituto Politécnico Nacional"
#define AppExe "ArduinoHound.exe"

[Setup]
AppId={{7B1C2E54-3A0F-4C8D-9E61-5D2A8F4B1C90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Proyecto de tesis - Instituto Politécnico Nacional
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador de {#AppName}
VersionInfoProductName={#AppName}
DefaultDirName={autopf}\ArduinoHound
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=ArduinoHound_Setup_{#AppVersion}
SetupIconFile=assets\IconoAHound.ico
WizardImageFile=assets\wizard_grande.bmp
WizardSmallImageFile=assets\wizard_pequena.bmp
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\ArduinoHound\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
