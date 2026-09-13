; Installeur de Plume, pour Inno Setup 6.
;
; Construit avec :  ISCC.exe outils\plume.iss
; Le script de construction s'en charge : python outils\construire.py
;
; Pourquoi un installeur plutot qu'un zip. Le zip obligeait a expliquer
; « Proprietes, Debloquer, puis decompresser », etape que tout le monde
; oubliait et qui laissait Windows bloquer une partie des fichiers. Un
; installeur pose les fichiers lui-meme, cree le raccourci, et se desinstalle
; proprement depuis Parametres. Il ne supprime PAS le dossier profil : les
; onglets, l'historique et les positions de lecture survivent a une mise a
; jour, et la desinstallation propose de les garder.
;
; Ce que l'installeur ne fait pas : il n'est pas signe. SmartScreen
; l'annoncera donc comme un editeur inconnu, exactement comme le zip. Seule
; une signature Authenticode y changerait quelque chose.

#define MonNom "Plume"
; La version vient du script de construction, qui la lit dans core.py :
; ISCC /DMaVersion=1.2.3. Une seule source, sinon les deux divergent.
#ifndef MaVersion
  #define MaVersion "1.0.0"
#endif
#define MonEditeur "Plume"
#define MonExe "Plume.exe"

[Setup]
AppId={{8C4D1E2A-6B3F-4A7C-9E15-2D8F0A5B7C31}
AppName={#MonNom}
AppVersion={#MaVersion}
AppVerName={#MonNom} {#MaVersion}
AppPublisher={#MonEditeur}
DefaultDirName={autopf}\{#MonNom}
DefaultGroupName={#MonNom}
DisableProgramGroupPage=yes
; Installation par utilisateur : pas de demande d'elevation, donc une
; alerte de moins. Le dossier part alors dans %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
OutputDir=..\..\Plume-paquet
OutputBaseFilename=Plume-{#MaVersion}-installeur
SetupIconFile=..\icone\plume.ico
UninstallDisplayIcon={app}\{#MonExe}
; Compression forte : le paquet pese 166 Mo en zip, l'essentiel etant mpv,
; Deno et yt-dlp. LZMA2 fait nettement mieux que le deflate du zip.
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Windows 10 1809 au minimum : WebView2 n'existe pas avant.
MinVersion=10.0.17763

[Languages]
Name: "francais"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Creer un raccourci sur le Bureau"; \
    GroupDescription: "Raccourcis :"

[Files]
; Tout le dossier construit par outils\construire.py, sauf le profil, qui
; n'y est de toute facon jamais copie.
Source: "..\..\Plume-paquet\Plume\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MonNom}"; Filename: "{app}\{#MonExe}"
Name: "{group}\Desinstaller {#MonNom}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MonNom}"; Filename: "{app}\{#MonExe}"; Tasks: bureau

[Run]
Filename: "{app}\{#MonExe}"; Description: "Lancer {#MonNom}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Les fichiers ecrits par Plume apres l'installation : sans cela le dossier
; reste derriere, a moitie vide.
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\erreur-demarrage.txt"

[Code]
// Le dossier profil contient les onglets, l'historique, les cookies de
// session et les positions de lecture. Le supprimer sans demander ferait
// perdre tout cela a la premiere desinstallation, y compris celle que
// certains font pour reinstaller proprement.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Profil: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Profil := ExpandConstant('{app}\profil');
    if DirExists(Profil) then
    begin
      if MsgBox('Supprimer aussi vos donnees Plume ?' + #13#10#13#10 +
                'Cela efface vos onglets, votre historique, vos favoris et ' +
                'les positions de lecture de vos videos.' + #13#10 +
                'Repondez Non si vous comptez reinstaller Plume.',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Profil, True, True, True);
    end;
  end;
end;
