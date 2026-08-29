; ==========================================================
; VAANITYPE OPEN-SOURCE INSTALLER (NSIS) - v0.0.1
; ==========================================================
!include "MUI2.nsh"

Name "VaaniType"
OutFile "Output_Installer\VaaniType_Setup_v0.0.1.exe"
InstallDir "$PROGRAMFILES\VaaniType"
RequestExecutionLevel admin

; Custom Icons
!define MUI_ABORTWARNING
!define MUI_ICON "vaani.ico"
!define MUI_UNICON "vaani.ico"

; Wizard Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Finish Page with Launch Option
!define MUI_FINISHPAGE_RUN "$INSTDIR\VaaniType.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch VaaniType v0.0.1 now"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ==========================================
; INSTALLATION
; ==========================================
Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy executable & your exact logo/icon assets
    File "dist\VaaniType.exe"
    File "vaani.ico"
    File "vaanilogo.png"
    
    ; Create Uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Shortcuts
    CreateShortcut "$DESKTOP\VaaniType.lnk" "$INSTDIR\VaaniType.exe" "" "$INSTDIR\vaani.ico" 0
    CreateDirectory "$SMPROGRAMS\VaaniType"
    CreateShortcut "$SMPROGRAMS\VaaniType\VaaniType.lnk" "$INSTDIR\VaaniType.exe" "" "$INSTDIR\vaani.ico" 0
    CreateShortcut "$SMPROGRAMS\VaaniType\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\vaani.ico" 0
    
    ; Windows Registry Entry for Control Panel / Installed Apps
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType" "DisplayName" "VaaniType - AI Voice Dictation"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType" "DisplayIcon" "$INSTDIR\vaani.ico"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType" "Publisher" "VaaniType AI"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType" "DisplayVersion" "0.0.1"
SectionEnd

; ==========================================
; UNINSTALLATION
; ==========================================
Section "Uninstall"
    Delete "$INSTDIR\VaaniType.exe"
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$INSTDIR\vaani.ico"
    Delete "$INSTDIR\vaanilogo.png"
    Delete "$INSTDIR\config.json"
    RMDir "$INSTDIR"
    
    Delete "$DESKTOP\VaaniType.lnk"
    Delete "$SMPROGRAMS\VaaniType\VaaniType.lnk"
    Delete "$SMPROGRAMS\VaaniType\Uninstall.lnk"
    RMDir "$SMPROGRAMS\VaaniType"
    
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VaaniType"
SectionEnd