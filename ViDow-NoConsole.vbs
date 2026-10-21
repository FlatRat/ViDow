Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
appScript = scriptDir & "\app.py"

If Not fso.FileExists(venvPythonw) Then
    ' Falls die Umgebung noch nicht eingerichtet ist, starte zuerst ViDow.bat zur Installation
    WshShell.Run """" & scriptDir & "\ViDow.bat""", 1, True
Else
    ' Starte ViDow direkt ohne Konsolenfenster (pythonw)
    WshShell.CurrentDirectory = scriptDir
    WshShell.Run """" & venvPythonw & """ """ & appScript & """", 0, False
End If
