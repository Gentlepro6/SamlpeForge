Unicode true
Name "SampleForge"
OutFile "dist\SampleForge-Setup-1.0.0.exe"
InstallDir "$PROGRAMFILES64\SampleForge"
InstallDirRegKey HKLM "Software\SampleForge" "InstallDir"
RequestExecutionLevel admin

!include "MUI2.nsh"
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "dist\SampleForge\*.*"
  WriteRegStr HKLM "Software\SampleForge" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "DisplayName" "SampleForge"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "DisplayIcon" "$INSTDIR\SampleForge.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "Publisher" "SampleForge"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "DisplayVersion" "1.0.0"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge" "NoRepair" 1
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\SampleForge.lnk" "$INSTDIR\SampleForge.exe" "" "$INSTDIR\SampleForge.exe" 0
  CreateDirectory "$SMPROGRAMS\SampleForge"
  CreateShortCut "$SMPROGRAMS\SampleForge\SampleForge.lnk" "$INSTDIR\SampleForge.exe" "" "$INSTDIR\SampleForge.exe" 0
  CreateShortCut "$SMPROGRAMS\SampleForge\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  Delete "$DESKTOP\SampleForge.lnk"
  RMDir /r "$SMPROGRAMS\SampleForge"
  DeleteRegKey HKLM "Software\SampleForge"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\SampleForge"
SectionEnd
