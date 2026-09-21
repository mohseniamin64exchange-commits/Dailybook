; DailyBook standard Windows x64 installer
#define AppName "DailyBook"
#define AppVersion "1.0.0-rc5.4"
#define AppPublisher "DailyBook"
#define ServiceName "DailyBook"
#define FirewallRule "DailyBook Server"

[Setup]
AppId={{8E2D8B57-3AA9-4A6B-9D0D-4A1B7C0D4000}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\DailyBook
DefaultGroupName=DailyBook
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
OutputDir=output
OutputBaseFilename=DailyBook-Setup-x64
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
SetupLogging=yes
Uninstallable=yes
UninstallDisplayIcon={app}\DailyBook.exe
CloseApplications=yes
RestartApplications=no

[Files]
Source: "dist\server\DailyBookServer\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\launcher\DailyBook.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "service\DailyBookService.exe"; DestDir: "{app}\service"; Flags: ignoreversion
Source: "service\DailyBookService.xml"; DestDir: "{app}\service"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\DailyBook"
Name: "{commonappdata}\DailyBook\backups"
Name: "{commonappdata}\DailyBook\logs"

[Tasks]
Name: "desktopicon"; Description: "ایجاد میانبر روی دسکتاپ"; GroupDescription: "میانبرها:"

[Icons]
Name: "{group}\DailyBook"; Filename: "{app}\DailyBook.exe"
Name: "{group}\حذف DailyBook"; Filename: "{uninstallexe}"
Name: "{commondesktop}\DailyBook"; Filename: "{app}\DailyBook.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\service\DailyBookService.exe"; Parameters: "install"; Flags: runhidden waituntilterminated; Check: not ServiceExists
Filename: "{app}\service\DailyBookService.exe"; Parameters: "start"; Flags: runhidden waituntilterminated
Filename: "{app}\DailyBook.exe"; Description: "اجرای DailyBook"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\service\DailyBookService.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopDailyBook"
Filename: "{app}\service\DailyBookService.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveDailyBook"

[Code]
function ExecHidden(const FileName, Params: String): Integer;
var
  ResultCode: Integer;
begin
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ResultCode := -1;
  Result := ResultCode;
end;

function ServiceExists(): Boolean;
begin
  Result := ExecHidden(ExpandConstant('{sys}\sc.exe'), 'query "{#ServiceName}"') = 0;
end;

function PrepareToInstall(var NeedsRestart: String): String;
var
  ExistingService: String;
begin
  Result := '';
  ExistingService := ExpandConstant('{app}\service\DailyBookService.exe');
  if FileExists(ExistingService) then
    ExecHidden(ExistingService, 'stop');
end;

procedure ConfigureFirewall;
begin
  ExecHidden(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="{#FirewallRule}"');
  if ExecHidden(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall add rule name="{#FirewallRule}" dir=in action=allow protocol=TCP localport=4000 profile=private,domain') <> 0 then
    MsgBox('قانون فایروال DailyBook ساخته نشد. گزارش نصب را بررسی کنید.', mbError, MB_OK);
end;

procedure RemoveFirewall;
begin
  ExecHidden(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="{#FirewallRule}"');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    ConfigureFirewall;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then begin
    RemoveFirewall;
    if MsgBox('آیا اطلاعات، تنظیمات و پشتیبان‌های DailyBook نیز حذف شوند؟' + #13#10 +
      'برای نگهداری اطلاعات گزینه «خیر» را انتخاب کنید.', mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{commonappdata}\DailyBook'), True, True, True);
  end;
end;
