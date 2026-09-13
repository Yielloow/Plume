' Lance le navigateur Plume sans aucune fenetre de console.
' pythonw.exe est la version sans console de Python.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dossier = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dossier
sh.Run """pythonw.exe"" ""navigateur.py""", 0, False
