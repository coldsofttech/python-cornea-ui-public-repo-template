; NSIS installer for Example App: the command line (example-cli.exe) and the desktop app (example-ui.exe) in one
; setup, example-<version>-full-setup.exe. Windows only.
;
; Pages: components (command line, desktop app, or both) > folder > tasks (PATH, desktop
; shortcut). The uninstaller lets the user remove either program or both.
;
; lib\ holds the Python runtime and the dependencies. What both programs need (core) is installed
; once; what only one needs goes with that program. Which programs are installed is kept in the
; registry (Cli, Ui), so setup and the uninstaller always know what else uses lib\: it is removed
; only when neither program is left.
;
; installer/scripts/build.py passes these with /D:
;
;   GUID            stable id of the product, from installer/build.toml (never changes)
;
;   APP_NAME, APP_VERSION (APP_VERSION_NUMERIC "0.1.0.0" is derived if not given)
;   STAGE_DIR       folder with core\ and one folder per product, here cli\ and ui\ (each laid
;                   out as the install folder)
;   COMPONENTS_FILE the Remove_cli / Remove_ui macros (Remove_<product name>): the files each program installed
;   CLI_EXE, UI_EXE the two programs, e.g. "example-cli.exe"
;   CLI_VERSION, UI_VERSION  their versions (APP_VERSION is the setup's own)
;   OUT_FILE        the installer to write
;   PUBLISHER, URL, ICON_FILE (.ico), LICENSE_FILE   optional
;   SUPPORT_URL, UPDATE_URL   optional: the support page and the release notes (Apps & features)
;   INSTALL_DIR     folder under Program Files (or Programs for one user), e.g. "Vendor\Product";
;                   INSTALL_DIR_DEPTH is its number of parts, so the uninstaller can remove the
;                   empty parent folders too.
;   START_MENU_DIR  Start Menu folder, e.g. "Vendor\Product" (default APP_NAME);
;                   START_MENU_DIR_DEPTH is its number of parts, as for INSTALL_DIR.
;   HEADER_IMAGE (.bmp, 150x57), WELCOME_IMAGE (.bmp, 164x314)   optional, from brand/
;   USER_DATA_DIR   optional: folder with settings and data; the uninstaller asks before removing it
;
; Silent use: Setup.exe /S [/allusers | /currentuser] [/COMPONENTS=cli|ui|cli,ui] [/NOPATH]
;                          [/DESKTOP] [/D=C:\folder]
;             uninstall.exe /S [/COMPONENTS=cli|ui|cli,ui] [/PURGE]
;             (/PURGE also removes USER_DATA_DIR once nothing is left)
; The default choice is a per-user install of both programs; "all users" needs administrator
; rights (UAC). Running setup again keeps the programs that are installed and adds the chosen ones.

!ifndef GUID
  !error "Pass /DGUID=... (the guid in installer/build.toml; scripts/build.py does)."
!endif
!ifndef APP_NAME
  !error "Pass /DAPP_NAME=... (installer/scripts/build.py does)."
!endif
!ifndef APP_VERSION
  !error "Pass /DAPP_VERSION=..."
!endif
!ifndef STAGE_DIR
  !error "Pass /DSTAGE_DIR=... (the folder with core, cli and ui)."
!endif
!ifndef COMPONENTS_FILE
  !error "Pass /DCOMPONENTS_FILE=..."
!endif
!ifndef CLI_EXE
  !error "Pass /DCLI_EXE=..."
!endif
!ifndef UI_EXE
  !error "Pass /DUI_EXE=..."
!endif
!ifndef CLI_VERSION
  !error "Pass /DCLI_VERSION=..."
!endif
!ifndef UI_VERSION
  !error "Pass /DUI_VERSION=..."
!endif
!ifndef OUT_FILE
  !error "Pass /DOUT_FILE=..."
!endif
!ifndef APP_VERSION_NUMERIC
  !define APP_VERSION_NUMERIC "${APP_VERSION}.0"
!endif
!ifndef PUBLISHER
  !define PUBLISHER "${APP_NAME}"
!endif
!ifndef INSTALL_DIR
  !define INSTALL_DIR "${APP_NAME}"
!endif
!ifndef INSTALL_DIR_DEPTH
  !define INSTALL_DIR_DEPTH 1
!endif
!ifndef START_MENU_DIR
  !define START_MENU_DIR "${APP_NAME}"
!endif
!ifndef START_MENU_DIR_DEPTH
  !define START_MENU_DIR_DEPTH 1
!endif
; The window's Start Menu shortcut. Named differently from the folder, because Windows 11 Start
; showed a folder with an app of the same name as just that app, with no folder.
!define UI_LINK "${APP_NAME} Desktop"

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${GUID}"
!define UNINSTALLER "uninstall.exe"
!define APP_KEY "Software\${APP_NAME}"

Name "${APP_NAME}"
OutFile "${OUT_FILE}"
Unicode true
; The marker is still in $INSTDIR in .onInit unless the user gave /D=folder.
!define NO_INSTDIR "<default folder>"
InstallDir "${NO_INSTDIR}"
SetCompressor /SOLID lzma
BrandingText "${APP_NAME} ${APP_VERSION}"
ManifestDPIAware true
ManifestSupportedOS Win10

VIProductVersion "${APP_VERSION_NUMERIC}"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "${APP_NAME} setup"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${PUBLISHER}"

; ---- install mode: this user (default) or all users --------------------------------------------
; Highest: an administrator is asked once (UAC) at start; a standard user runs unelevated and is
; asked for an administrator only after choosing "all users".
!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_ALLOW_ELEVATION
!define MULTIUSER_INSTALLMODE_DEFAULT_CURRENTUSER
!define MULTIUSER_USE_PROGRAMFILES64
!define MULTIUSER_INSTALLMODE_INSTDIR "${INSTALL_DIR}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY "${APP_KEY}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME "InstallLocation"
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "${APP_KEY}"
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME "InstallLocation"

!include MUI2.nsh
!include MultiUser.nsh
!include FileFunc.nsh
!include LogicLib.nsh
!include Sections.nsh
!include nsDialogs.nsh
!include "${COMPONENTS_FILE}"

!insertmacro GetParameters
!insertmacro GetOptions
!insertmacro un.GetParameters
!insertmacro un.GetOptions

!ifdef ICON_FILE
  !define MUI_ICON "${ICON_FILE}"
  !define MUI_UNICON "${ICON_FILE}"
!endif
!ifdef HEADER_IMAGE
  !define MUI_HEADERIMAGE
  !define MUI_HEADERIMAGE_BITMAP "${HEADER_IMAGE}"
  !define MUI_HEADERIMAGE_UNBITMAP "${HEADER_IMAGE}"
!endif
!ifdef WELCOME_IMAGE
  !define MUI_WELCOMEFINISHPAGE_BITMAP "${WELCOME_IMAGE}"
  !define MUI_UNWELCOMEFINISHPAGE_BITMAP "${WELCOME_IMAGE}"
!endif
!define MUI_ABORTWARNING

Var WantPath
Var WantDesktop
Var CheckPath
Var CheckDesktop

; ---- pages ---------------------------------------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!ifdef LICENSE_FILE
  !insertmacro MUI_PAGE_LICENSE "${LICENSE_FILE}"
!endif
!insertmacro MULTIUSER_PAGE_INSTALLMODE
!define MUI_COMPONENTSPAGE_TEXT_TOP "Choose what to install. The command line and the desktop app share their libraries, so both together take little more room than one."
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ComponentsShow
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
Page custom TasksCreate TasksLeave
!insertmacro MUI_PAGE_INSTFILES
; Started through Explorer so the program runs as the user, not elevated like the installer.
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APP_NAME}"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
!define MUI_PAGE_CUSTOMFUNCTION_SHOW FinishShow
!insertmacro MUI_PAGE_FINISH

!define MUI_COMPONENTSPAGE_TEXT_TOP "Choose what to remove. Anything you leave unchecked stays installed and keeps working."
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ---- install -------------------------------------------------------------------------------------
; What both programs need, and what every install has: the shared lib\, the uninstaller, the
; Start Menu folder and the Apps & features entry.
Section "-Shared files" SecCore
  SetRegView 64

  ; An upgrade replaces the old files; stale ones from an earlier version must not stay behind.
  ; Setup keeps the programs that are installed (see .onInit), so they are all copied again below.
  RMDir /r "$INSTDIR\lib"

  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\core\*.*"
  !ifdef LICENSE_FILE
    File "/oname=LICENSE.txt" "${LICENSE_FILE}"
  !endif
  File "${__FILEDIR__}\path.ps1"

  WriteUninstaller "$INSTDIR\${UNINSTALLER}"

  CreateDirectory "$SMPROGRAMS\${START_MENU_DIR}"
  CreateShortcut "$SMPROGRAMS\${START_MENU_DIR}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\${UNINSTALLER}"

  ; Where it is installed (also tells a later setup, and the uninstaller, which mode this was).
  WriteRegStr SHCTX "${APP_KEY}" "InstallLocation" "$INSTDIR"

  ; Apps & features
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\${UNINSTALLER}"'
  WriteRegStr SHCTX "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\${UNINSTALLER}" /S'
  !ifdef URL
    WriteRegStr SHCTX "${UNINSTALL_KEY}" "URLInfoAbout" "${URL}"
  !endif
  !ifdef SUPPORT_URL
    WriteRegStr SHCTX "${UNINSTALL_KEY}" "HelpLink" "${SUPPORT_URL}"
  !endif
  !ifdef UPDATE_URL
    WriteRegStr SHCTX "${UNINSTALL_KEY}" "URLUpdateInfo" "${UPDATE_URL}"
  !endif
  WriteRegDWORD SHCTX "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD SHCTX "${UNINSTALL_KEY}" "NoRepair" 1
SectionEnd

Section "Command line (CLI)" SecCli
  SetRegView 64
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\cli\*.*"
  ; A prompt where the command already works, even if it was not added to PATH.
  CreateShortcut "$SMPROGRAMS\${START_MENU_DIR}\${APP_NAME} prompt.lnk" "$SYSDIR\cmd.exe" \
    '/K set "PATH=$INSTDIR;%PATH%"' "$INSTDIR\${CLI_EXE}" 0
  WriteRegDWORD SHCTX "${APP_KEY}" "Cli" 1
  WriteRegStr SHCTX "${APP_KEY}" "CliVersion" "${CLI_VERSION}"
SectionEnd

Section "Desktop app" SecUi
  SetRegView 64
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\ui\*.*"
  CreateShortcut "$SMPROGRAMS\${START_MENU_DIR}\${UI_LINK}.lnk" "$INSTDIR\${UI_EXE}"
  WriteRegDWORD SHCTX "${APP_KEY}" "Ui" 1
  WriteRegStr SHCTX "${APP_KEY}" "UiVersion" "${UI_VERSION}"
SectionEnd

; What the tasks page chose, once the programs are in place.
Section "-Tasks" SecTasks
  SetRegView 64
  ${If} ${SectionIsSelected} ${SecCli}
  ${AndIf} $WantPath == 1
    ${If} $MultiUser.InstallMode == "AllUsers"
      StrCpy $0 "Machine"
    ${Else}
      StrCpy $0 "User"
    ${EndIf}
    nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive \
      -ExecutionPolicy Bypass -File "$INSTDIR\path.ps1" -Action Add -Scope $0 -Dir "$INSTDIR"'
    Pop $1
    ${If} $1 != 0
      DetailPrint "Could not add $INSTDIR to PATH (code $1)."
    ${Else}
      WriteRegDWORD SHCTX "${APP_KEY}" "OnPath" 1
    ${EndIf}
  ${EndIf}
  ${If} ${SectionIsSelected} ${SecUi}
  ${AndIf} $WantDesktop == 1
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${UI_EXE}"
  ${EndIf}

  ; The icon of Apps & features: the window's when it is installed.
  ${If} ${SectionIsSelected} ${SecUi}
    WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${UI_EXE}"
  ${Else}
    WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${CLI_EXE}"
  ${EndIf}
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD SHCTX "${UNINSTALL_KEY}" "EstimatedSize" "$0"
SectionEnd

LangString DESC_Cli ${LANG_ENGLISH} "Use Example App from a terminal or a script."
LangString DESC_Ui ${LANG_ENGLISH} "Use Example App from its own window."
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCli} $(DESC_Cli)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUi} $(DESC_Ui)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ---- install: start up and pages (after the sections, whose constants they use) -----------------
Function .onInit
  ; MultiUser sets $INSTDIR for the chosen mode and would discard a folder given with /D=, so
  ; keep that folder (anything but the marker below) and put it back afterwards.
  StrCpy $R8 $INSTDIR
  !insertmacro MULTIUSER_INIT
  ${If} $R8 != "${NO_INSTDIR}"
    StrCpy $INSTDIR $R8
  ${EndIf}
  SetRegView 64

  StrCpy $WantPath 1
  StrCpy $WantDesktop 0
  ${GetParameters} $R0
  ${GetOptions} $R0 "/NOPATH" $R1
  ${IfNot} ${Errors}
    StrCpy $WantPath 0
  ${EndIf}
  ClearErrors
  ${GetOptions} $R0 "/DESKTOP" $R1
  ${IfNot} ${Errors}
    StrCpy $WantDesktop 1
  ${EndIf}
  ClearErrors
  ${GetOptions} $R0 "/COMPONENTS=" $R1
  ${IfNot} ${Errors}
    ${If} $R1 == "cli"
      !insertmacro UnselectSection ${SecUi}
    ${ElseIf} $R1 == "ui"
      !insertmacro UnselectSection ${SecCli}
    ${EndIf}
  ${EndIf}
  ClearErrors

  ; A program that is installed stays: lib\ is replaced as a whole, so it is copied again.
  ReadRegDWORD $R1 SHCTX "${APP_KEY}" "Cli"
  ${If} $R1 == 1
    !insertmacro SelectSection ${SecCli}
  ${EndIf}
  ReadRegDWORD $R1 SHCTX "${APP_KEY}" "Ui"
  ${If} $R1 == 1
    !insertmacro SelectSection ${SecUi}
  ${EndIf}
FunctionEnd

; At least one program must be chosen.
Function UpdateNext
  GetDlgItem $0 $HWNDPARENT 1
  ${If} ${SectionIsSelected} ${SecCli}
  ${OrIf} ${SectionIsSelected} ${SecUi}
    EnableWindow $0 1
  ${Else}
    EnableWindow $0 0
  ${EndIf}
FunctionEnd

Function ComponentsShow
  Call UpdateNext
FunctionEnd

Function .onSelChange
  Call UpdateNext
FunctionEnd

Function TasksCreate
  !insertmacro MUI_HEADER_TEXT "Additional tasks" "Choose what else setup should do."
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  ${NSD_CreateCheckbox} 0 10u 100% 12u "Add the command line (CLI) to PATH, so it runs from any terminal"
  Pop $CheckPath
  ${NSD_CreateCheckbox} 0 30u 100% 12u "Create a desktop shortcut for the desktop app"
  Pop $CheckDesktop
  ${If} ${SectionIsSelected} ${SecCli}
    ${If} $WantPath == 1
      ${NSD_Check} $CheckPath
    ${EndIf}
  ${Else}
    EnableWindow $CheckPath 0
  ${EndIf}
  ${If} ${SectionIsSelected} ${SecUi}
    ${If} $WantDesktop == 1
      ${NSD_Check} $CheckDesktop
    ${EndIf}
  ${Else}
    EnableWindow $CheckDesktop 0
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function TasksLeave
  ${NSD_GetState} $CheckPath $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $WantPath 1
  ${Else}
    StrCpy $WantPath 0
  ${EndIf}
  ${NSD_GetState} $CheckDesktop $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $WantDesktop 1
  ${Else}
    StrCpy $WantDesktop 0
  ${EndIf}
FunctionEnd

Function FinishShow
  ; There is no window to start when only the command line was installed.
  ${IfNot} ${SectionIsSelected} ${SecUi}
    ShowWindow $mui.FinishPage.Run ${SW_HIDE}
  ${EndIf}
FunctionEnd

Function LaunchApp
  ; Hiding the checkbox does not uncheck it, so without the window this would open Explorer on a
  ; file that is not there (and land in Documents).
  ${IfNot} ${SectionIsSelected} ${SecUi}
    Return
  ${EndIf}
  Exec '"$WINDIR\explorer.exe" "$INSTDIR\${UI_EXE}"'
FunctionEnd

; ---- uninstall -----------------------------------------------------------------------------------
; Only what setup installed is removed, so a folder chosen by hand keeps anything else in it.
Section "un.Command line (CLI)" UnSecCli
  SetRegView 64
  ReadRegDWORD $1 SHCTX "${APP_KEY}" "OnPath"
  ${If} $1 == 1
    ${If} $MultiUser.InstallMode == "AllUsers"
      StrCpy $0 "Machine"
    ${Else}
      StrCpy $0 "User"
    ${EndIf}
    nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive \
      -ExecutionPolicy Bypass -File "$INSTDIR\path.ps1" -Action Remove -Scope $0 -Dir "$INSTDIR"'
    Pop $1
    DeleteRegValue SHCTX "${APP_KEY}" "OnPath"
  ${EndIf}
  !insertmacro Remove_cli
  Delete "$SMPROGRAMS\${START_MENU_DIR}\${APP_NAME} prompt.lnk"
  DeleteRegValue SHCTX "${APP_KEY}" "Cli"
  DeleteRegValue SHCTX "${APP_KEY}" "CliVersion"
SectionEnd

Section "un.Desktop app" UnSecUi
  SetRegView 64
  !insertmacro Remove_ui
  Delete "$SMPROGRAMS\${START_MENU_DIR}\${UI_LINK}.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  DeleteRegValue SHCTX "${APP_KEY}" "Ui"
  DeleteRegValue SHCTX "${APP_KEY}" "UiVersion"
SectionEnd

; What is left decides what else goes: lib\ and the rest are shared, so they stay while either
; program does.
Section "-un.Shared files"
  SetRegView 64
  ReadRegDWORD $0 SHCTX "${APP_KEY}" "Cli"
  ReadRegDWORD $1 SHCTX "${APP_KEY}" "Ui"
  ${If} $0 == 1
  ${OrIf} $1 == 1
    ${If} $1 == 1
      WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${UI_EXE}"
    ${Else}
      WriteRegStr SHCTX "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${CLI_EXE}"
    ${EndIf}
  ${Else}
    RMDir /r "$INSTDIR\lib"
    Delete "$INSTDIR\LICENSE.txt"
    Delete "$INSTDIR\path.ps1"
    Delete "$INSTDIR\${UNINSTALLER}"
    RMDir "$INSTDIR"
    ; The vendor and product folders above it, only when empty.
    !if ${INSTALL_DIR_DEPTH} >= 2
      RMDir "$INSTDIR\.."
    !endif
    !if ${INSTALL_DIR_DEPTH} >= 3
      RMDir "$INSTDIR\..\.."
    !endif

    RMDir /r "$SMPROGRAMS\${START_MENU_DIR}"
    ; The publisher folder above it, only when empty.
    !if ${START_MENU_DIR_DEPTH} >= 2
      RMDir "$SMPROGRAMS\${START_MENU_DIR}\.."
    !endif
    !if ${START_MENU_DIR_DEPTH} >= 3
      RMDir "$SMPROGRAMS\${START_MENU_DIR}\..\.."
    !endif
    DeleteRegKey SHCTX "${UNINSTALL_KEY}"
    DeleteRegKey SHCTX "${APP_KEY}"

    ; Settings and data stay unless the user opts in (or passes /PURGE when silent).
    !ifdef USER_DATA_DIR
      ${un.GetParameters} $R0
      ${un.GetOptions} $R0 "/PURGE" $R1
      ${IfNot} ${Errors}
        RMDir /r "${USER_DATA_DIR}"
      ${ElseIfNot} ${Silent}
        MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 \
          "Also remove your ${APP_NAME} settings and data?$\r$\n${USER_DATA_DIR}" IDNO +2
        RMDir /r "${USER_DATA_DIR}"
      ${EndIf}
    !endif
  ${EndIf}
SectionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
  SetRegView 64
  ; Offer only what is installed. With neither recorded (a damaged install), both sections stay
  ; hidden and the shared files are cleaned up all the same.
  ReadRegDWORD $0 SHCTX "${APP_KEY}" "Cli"
  ${If} $0 != 1
    SectionSetText ${UnSecCli} ""
    SectionSetFlags ${UnSecCli} 0
  ${EndIf}
  ReadRegDWORD $0 SHCTX "${APP_KEY}" "Ui"
  ${If} $0 != 1
    SectionSetText ${UnSecUi} ""
    SectionSetFlags ${UnSecUi} 0
  ${EndIf}
  ${un.GetParameters} $R0
  ${un.GetOptions} $R0 "/COMPONENTS=" $R1
  ${IfNot} ${Errors}
    ${If} $R1 == "cli"
      !insertmacro UnselectSection ${UnSecUi}
    ${ElseIf} $R1 == "ui"
      !insertmacro UnselectSection ${UnSecCli}
    ${EndIf}
  ${EndIf}
  ClearErrors
FunctionEnd
