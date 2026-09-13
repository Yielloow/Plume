' Lance Plume en consignant ce qu'il fait dans diagnostic.txt.
' A utiliser quand quelque chose ne marche pas : reproduire le probleme,
' fermer Plume, puis regarder le fichier.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dossier = fso.GetParentFolderName(WScript.ScriptFullName)
journal = dossier & "\diagnostic.txt"
If fso.FileExists(journal) Then fso.DeleteFile journal
sh.CurrentDirectory = dossier
Set env = sh.Environment("Process")
env("PLUME_DEBUG") = journal
sh.Run """pythonw.exe"" ""navigateur.py""", 0, False
