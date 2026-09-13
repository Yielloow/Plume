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
; L'ordre compte : Inno propose la langue du systeme si elle est dans la liste,
; et l'anglais sert de repli pour tout le reste du monde. C'est aussi cette
; langue-la que Plume parlera au premier lancement.
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Creer un raccourci sur le Bureau"; \
    GroupDescription: "Raccourcis :"

[Files]
; Tout le dossier construit par outils\construire.py, sauf le profil, qui
; n'y est de toute facon jamais copie.
Source: "..\..\Plume-paquet\Plume\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; Declaration de Plume comme navigateur possible, sous HKCU : l'installation
; est par utilisateur, elle n'a donc ni le droit ni le besoin d'ecrire dans
; HKLM. Windows lit les deux.
;
; Ce que ces cles font, et surtout ce qu'elles ne font pas : elles font
; APPARAITRE Plume dans Parametres > Applications par defaut. Elles ne le
; rendent pas navigateur par defaut, et aucune cle ne le peut : depuis
; Windows 10, seul un choix explicite de l'utilisateur y parvient.
Root: HKCU; Subkey: "Software\Classes\PlumeHTML"; \
    ValueType: string; ValueName: ""; ValueData: "Plume Document"; \
    Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PlumeHTML\DefaultIcon"; \
    ValueType: string; ValueName: ""; ValueData: "{app}\{#MonExe},0"
Root: HKCU; Subkey: "Software\Classes\PlumeHTML\shell\open\command"; \
    ValueType: string; ValueName: ""; \
    ValueData: """{app}\{#MonExe}"" ""%1"""
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities"; \
    ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MonNom}"; \
    Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities"; \
    ValueType: string; ValueName: "ApplicationDescription"; \
    ValueData: "Un navigateur qui joue les videos avec mpv"
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities\URLAssociations"; \
    ValueType: string; ValueName: "http"; ValueData: "PlumeHTML"
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities\URLAssociations"; \
    ValueType: string; ValueName: "https"; ValueData: "PlumeHTML"
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities\FileAssociations"; \
    ValueType: string; ValueName: ".html"; ValueData: "PlumeHTML"
Root: HKCU; Subkey: "Software\{#MonNom}\Capabilities\FileAssociations"; \
    ValueType: string; ValueName: ".htm"; ValueData: "PlumeHTML"
Root: HKCU; Subkey: "Software\RegisteredApplications"; \
    ValueType: string; ValueName: "{#MonNom}"; \
    ValueData: "Software\{#MonNom}\Capabilities"; \
    Flags: uninsdeletevalue

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
// La langue retenue par l'assistant devient celle de Plume, ecrite dans
// config.json juste apres la copie des fichiers. Sans cela, une personne qui
// installe en anglais verrait un navigateur en francais au premier
// lancement, et n'aurait aucune idee d'ou changer cela.
//
// Le fichier est charge et reecrit tel quel, octet pour octet : le seul
// morceau touche est de l'ASCII, les accents du reste du fichier traversent
// donc intacts.
procedure CurStepChanged(CurStep: TSetupStep);
var
  Chemin, Texte: String;
  Brut: AnsiString;
begin
  if CurStep = ssPostInstall then
  begin
    Chemin := ExpandConstant('{app}\config.json');
    // Trois types, et ce n'est pas du zele : LoadStringFromFile et
    // SaveStringToFile travaillent sur des octets (AnsiString), tandis que
    // StringChangeEx travaille sur du texte (String). Les melanger donne un
    // « Type mismatch » a la compilation, ce qui a deja coute une
    // construction.
    if LoadStringFromFile(Chemin, Brut) then
    begin
      Texte := Brut;
      StringChangeEx(Texte, '"langue": "auto"',
                     '"langue": "' + ActiveLanguage + '"', True);
      SaveStringToFile(Chemin, Texte, False);
    end;
  end;
end;

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
