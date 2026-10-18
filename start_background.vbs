Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = ScriptDir

' Launch main.py with pythonw in hidden window style
WshShell.Run "pythonw.exe """ & ScriptDir & "\main.py""", 0, False
