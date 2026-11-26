Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

standaloneExe = scriptDir & "\dist\ViDow\ViDow.exe"
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
depsMarker = scriptDir & "\.venv\.vidow_deps_v2_ok"
appScript = scriptDir & "\app.py"

WshShell.CurrentDirectory = scriptDir

' 1. Falls kompilierte Standalone-EXE vorhanden ist und keine Dev-.venv genutzt wird
If fso.FileExists(standaloneExe) And Not fso.FileExists(venvPythonw) Then
    WshShell.Run """" & standaloneExe & """", 1, False
    WScript.Quit 0
End If

' 2. Falls .venv oder Abhaengigkeiten noch fehlen, einmalig ViDow.bat --setup-only ausfuehren
If (Not fso.FileExists(venvPythonw)) Or (Not fso.FileExists(depsMarker)) Then
    exitCode = WshShell.Run("""" & scriptDir & "\ViDow.bat"" --setup-only", 1, True)
    If exitCode <> 0 Then
        WScript.Quit exitCode
    End If
End If

' 3. Starte ViDow komplett ohne Konsolenfenster (pythonw + isolierte Umgebung)
Set procEnv = WshShell.Environment("PROCESS")
procEnv("PYTHONNOUSERSITE") = "1"
procEnv("PYTHONUTF8") = "1"
WshShell.Run """" & venvPythonw & """ """ & appScript & """", 0, False
