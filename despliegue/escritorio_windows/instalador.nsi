Target amd64-unicode
!ifdef LP11_OPERATIVO
    !define LP11_MODALIDAD "operativo"
    !define LP11_NOMBRE "Lotería Predictor"
    !define LP11_CARPETA "LP11-Operativo"
    !define LP11_LANZADOR "Abrir Loteria Predictor.cmd"
    !define LP11_DESCRIPCION "Instalador por usuario de Lotería Predictor"
    !define LP11_BIENVENIDA "Instala Lotería Predictor con Mis apuestas para tu cuenta de Windows. El visor consulta los datos locales de Fase 6 con tu cuenta lectora."
    !define LP11_VERSION "2.0.0"
!else
    !define LP11_MODALIDAD "piloto"
    !define LP11_NOMBRE "Lotería Predictor (piloto)"
    !define LP11_CARPETA "LP11-Piloto"
    !define LP11_LANZADOR "Abrir piloto.cmd"
    !define LP11_DESCRIPCION "Instalador por usuario del piloto sintético"
    !define LP11_BIENVENIDA "Instala el piloto de consulta con datos sintéticos para tu cuenta de Windows."
    !define LP11_VERSION "1.0.0"
!endif

Name "${LP11_NOMBRE}"
OutFile "${LP11_SALIDA}"
InstallDir "$LOCALAPPDATA\Programs\${LP11_CARPETA}"
RequestExecutionLevel user
ManifestLongPathAware true
SetCompressor /SOLID lzma
ShowInstDetails nevershow
ShowUninstDetails nevershow
VIProductVersion "${LP11_VERSION}.0"

!include "MUI2.nsh"
!include "x64.nsh"

!define MUI_WELCOMEPAGE_TITLE "Lotería Predictor"
!define MUI_WELCOMEPAGE_TEXT "${LP11_BIENVENIDA}$\r$\n$\r$\nPodrás abrirlo desde el menú Inicio."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

VIAddVersionKey /LANG=${LANG_SPANISH} "ProductName" "${LP11_NOMBRE}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileDescription" "${LP11_DESCRIPCION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileVersion" "${LP11_VERSION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "ProductVersion" "${LP11_VERSION}"

!macro Detener mensaje
    MessageBox MB_OK|MB_ICONSTOP "${mensaje}" /SD IDOK
    SetErrorLevel 1
    Abort
!macroend

!macro PrepararUsuario
    SetShellVarContext current
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${LP11_CARPETA}"
    ${IfNot} ${IsNativeAMD64}
        !insertmacro Detener "El visor requiere Windows x64."
    ${EndIf}
    System::Call 'shell32::IsUserAnAdmin() i .r0'
    ${If} $0 != 0
        !insertmacro Detener "Abre el instalador o desinstalador con doble clic desde una sesión normal."
    ${EndIf}
!macroend

Function .onInit
    !insertmacro PrepararUsuario
FunctionEnd

Function un.onInit
    !insertmacro PrepararUsuario
FunctionEnd

!macro ExtraerGestor
    InitPluginsDir
    ClearErrors
    SetOutPath "$PLUGINSDIR\gestor"
    File /r "${LP11_BOOTSTRAP}/*"
    SetOutPath "$PLUGINSDIR"
    File "${__FILEDIR__}/gestionar.py"
    File "${LP11_CARGA}/manifiesto-kit.json"
    ${If} ${Errors}
        !insertmacro Detener "Windows no pudo preparar los archivos temporales del instalador."
    ${EndIf}
!macroend

!macro Ejecutar operacion
    SetOutPath "$PLUGINSDIR"
    ClearErrors
    ExecWait '"$PLUGINSDIR\gestor\python.exe" -I -B "$PLUGINSDIR\gestionar.py" ${operacion} "$SMPROGRAMS" "$PLUGINSDIR" "${LP11_MANIFIESTO_SHA256}" "${LP11_MODALIDAD}"' $0
    ${If} ${Errors}
        !insertmacro Detener "Windows no pudo abrir el verificador del visor."
    ${EndIf}
    ${If} $0 != 0
        StrCpy $2 "La operación del visor se detuvo."
        ClearErrors
        FileOpen $1 "$PLUGINSDIR\resultado.txt" r
        ${IfNot} ${Errors}
            FileReadUTF16LE $1 $2
            FileClose $1
        ${EndIf}
        !insertmacro Detener "$2"
    ${EndIf}
!macroend

Section "Instalar visor"
    !insertmacro ExtraerGestor
    ClearErrors
    SetOutPath "$PLUGINSDIR\carga"
    File /r "${LP11_CARGA}/*"
    ${If} ${Errors}
        !insertmacro Detener "Windows no pudo extraer los archivos del visor."
    ${EndIf}
    SetOutPath "$LOCALAPPDATA"
    ClearErrors
    CreateShortCut "$PLUGINSDIR\piloto.lnk" "$SYSDIR\cmd.exe" '/D /S /C ""$INSTDIR\app\${LP11_LANZADOR}""'
    WriteUninstaller "$PLUGINSDIR\Desinstalar.exe"
    ${If} ${Errors}
        !insertmacro Detener "Windows no pudo preparar el acceso directo o el desinstalador."
    ${EndIf}
    !insertmacro Ejecutar instalar
SectionEnd

Section "Uninstall"
    !insertmacro ExtraerGestor
    !insertmacro Ejecutar desinstalar
SectionEnd
