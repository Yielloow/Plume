' Lance l'interface de recherche video (tkinter, ~35 Mo), sans console.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dossier = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dossier
sh.Run """pythonw.exe"" ""plume.py""", 0, False
