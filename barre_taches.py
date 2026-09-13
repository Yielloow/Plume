# -*- coding: utf-8 -*-
"""
Plume / barre des taches : dire a Windows ce qu'il doit epingler.

Le probleme : Plume.exe n'est qu'un lanceur, le vrai processus est pythonw.exe.
Quand on epingle le bouton de la barre des taches, Windows epingle donc Python,
avec son icone et son nom. Appeler SetCurrentProcessExplicitAppUserModelID
suffit pour l'icone de la fenetre, mais pas pour l'epinglage.

La solution tient dans trois proprietes posees sur la fenetre elle-meme :
« relance par cette commande », « avec ce nom », « avec cette icone ». Windows
s'en sert au moment de creer le raccourci epingle.

Tout passe par COM en ctypes : ni pywin32 ni comtypes ne sont installes, et les
embarquer pour quatre appels serait disproportionne.
"""
import ctypes
from ctypes import wintypes

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
propsys = ctypes.WinDLL("propsys", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, texte):
        super(GUID, self).__init__()
        ole32.CLSIDFromString(wintypes.LPCWSTR(texte), ctypes.byref(self))


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class PROPVARIANT(ctypes.Structure):
    # vt, trois champs reserves, puis l'union de 16 octets en 64 bits
    _fields_ = [("vt", ctypes.c_ushort),
                ("wReserved1", ctypes.c_ushort),
                ("wReserved2", ctypes.c_ushort),
                ("wReserved3", ctypes.c_ushort),
                ("donnees", ctypes.c_byte * 16)]


IID_IPROPERTYSTORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
# Toutes les proprietes AppUserModel partagent ce groupe.
GROUPE_APPUSERMODEL = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"
CLE_ID = 5              # System.AppUserModel.ID
CLE_COMMANDE = 2        # System.AppUserModel.RelaunchCommand
CLE_ICONE = 3           # System.AppUserModel.RelaunchIconResource
CLE_NOM = 4             # System.AppUserModel.RelaunchDisplayNameResource

# IPropertyStore : QueryInterface, AddRef, Release, GetCount, GetAt, GetValue,
# SetValue, Commit
INDEX_RELEASE = 2
INDEX_SETVALUE = 6
INDEX_COMMIT = 7

VT_LPWSTR = 31
ole32.CoTaskMemAlloc.restype = ctypes.c_void_p
ole32.CoTaskMemAlloc.argtypes = [ctypes.c_size_t]


def _valeur_texte(texte):
    """Fabrique un PROPVARIANT de type chaine.

    InitPropVariantFromString, que l'on trouve dans la documentation, n'est pas
    exportee par propsys.dll : c'est une fonction en ligne de l'en-tete. Il faut
    donc poser le type et le pointeur soi-meme. La memoire est allouee par
    CoTaskMemAlloc, seule facon pour PropVariantClear de la liberer ensuite.
    """
    octets = (texte + "\0").encode("utf-16-le")
    memoire = ole32.CoTaskMemAlloc(len(octets))
    if not memoire:
        return None
    ctypes.memmove(memoire, octets, len(octets))
    valeur = PROPVARIANT()
    valeur.vt = VT_LPWSTR
    # l'union commence apres vt et les trois champs reserves, soit 8 octets
    ctypes.memmove(ctypes.byref(valeur, 8),
                   ctypes.byref(ctypes.c_void_p(memoire)),
                   ctypes.sizeof(ctypes.c_void_p))
    return valeur


def _methode(pointeur, index, *types_arguments):
    """Recupere la methode d'index donne dans la table virtuelle de l'objet."""
    table = ctypes.cast(pointeur,
                        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    prototype = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                   *types_arguments)
    return prototype(table[index])


def identifier_processus(identifiant):
    """Donne son identite a l'application, avant toute creation de fenetre.

    Sans cela, Windows regroupe les fenetres sous Python et en affiche l'icone.
    """
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID(
            wintypes.LPCWSTR(identifiant))
        return True
    except Exception:
        return False


def marquer_fenetre(hwnd, identifiant, commande, nom, icone):
    """Pose sur la fenetre de quoi l'epingler correctement.

    `commande` est ce que Windows relancera, `icone` le fichier .ico a
    afficher. Sans ces proprietes, epingler cree un raccourci vers pythonw.exe.
    """
    if not hwnd:
        return False
    magasin = ctypes.c_void_p()
    try:
        hr = shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd), ctypes.byref(GUID(IID_IPROPERTYSTORE)),
            ctypes.byref(magasin))
        if hr != 0 or not magasin:
            return False
    except Exception:
        return False

    poser = _methode(magasin, INDEX_SETVALUE,
                     ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))
    valider = _methode(magasin, INDEX_COMMIT)
    liberer = _methode(magasin, INDEX_RELEASE)

    groupe = GUID(GROUPE_APPUSERMODEL)
    valeurs = ((CLE_ID, identifiant), (CLE_COMMANDE, commande),
               (CLE_NOM, nom), (CLE_ICONE, icone))
    ok = True
    try:
        for numero, texte in valeurs:
            if not texte:
                continue
            cle = PROPERTYKEY(groupe, numero)
            valeur = _valeur_texte(texte)
            if valeur is None:
                ok = False
                continue
            try:
                poser(magasin, ctypes.byref(cle), ctypes.byref(valeur))
            except OSError:
                ok = False
            # PropVariantClear vit dans ole32, pas dans propsys
            ole32.PropVariantClear(ctypes.byref(valeur))
        valider(magasin)
    except OSError:
        ok = False
    finally:
        try:
            liberer(magasin)
        except Exception:
            pass
    return ok

# --------------------------------------------------------------------------
# Liste de raccourcis (le menu « Taches » du clic droit sur l'icone)
# --------------------------------------------------------------------------
CLSID_LISTE = "{77F10CF0-3DB5-4966-B520-B7C54FD35ED6}"
IID_LISTE = "{6332DEBF-87B5-4670-90C0-5E57B408A49E}"
CLSID_COLLECTION = "{2D3468C1-36A7-43B6-AC24-D3F02FD9607A}"
IID_COLLECTION = "{5632B1A4-E38A-400A-928A-D4CD63230295}"
IID_TABLEAU = "{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}"
CLSID_RACCOURCI = "{00021401-0000-0000-C000-000000000046}"
IID_RACCOURCI = "{000214F9-0000-0000-C000-000000000046}"
# System.Title, pour le libelle affiche dans le menu
GROUPE_TITRE = "{F29F85E0-4FF9-1068-AB91-08002B27B3D9}"
CLE_TITRE = 2

CLSCTX_INPROC_SERVER = 1

# ICustomDestinationList : ..., SetAppID(3), BeginList(4), AppendCategory(5),
# AppendKnownCategory(6), AddUserTasks(7), CommitList(8)
INDEX_SETAPPID = 3
INDEX_BEGINLIST = 4
INDEX_ADDUSERTASKS = 7
INDEX_COMMITLIST = 8
# IObjectCollection herite de IObjectArray : GetCount(3), GetAt(4),
# puis AddObject(5)
INDEX_ADDOBJECT = 5
# IShellLinkW : ..., SetArguments(11), SetIconLocation(17), SetPath(20)
INDEX_SETDESCRIPTION = 7
INDEX_SETARGUMENTS = 11
INDEX_SETICONLOCATION = 17
INDEX_SETPATH = 20

ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]


def _creer(clsid, iid):
    objet = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(GUID(clsid)), None,
                                CLSCTX_INPROC_SERVER,
                                ctypes.byref(GUID(iid)), ctypes.byref(objet))
    if hr != 0 or not objet:
        return None
    return objet


def _raccourci(chemin, arguments, titre, icone):
    """Un element du menu : un raccourci, plus son libelle en propriete."""
    lien = _creer(CLSID_RACCOURCI, IID_RACCOURCI)
    if lien is None:
        return None
    try:
        _methode(lien, INDEX_SETPATH, wintypes.LPCWSTR)(
            lien, wintypes.LPCWSTR(chemin))
        if arguments:
            _methode(lien, INDEX_SETARGUMENTS, wintypes.LPCWSTR)(
                lien, wintypes.LPCWSTR(arguments))
        _methode(lien, INDEX_SETDESCRIPTION, wintypes.LPCWSTR)(
            lien, wintypes.LPCWSTR(titre))
        if icone:
            _methode(lien, INDEX_SETICONLOCATION, wintypes.LPCWSTR,
                     ctypes.c_int)(lien, wintypes.LPCWSTR(icone), 0)

        # Le libelle affiche ne vient pas de la description mais de
        # System.Title : sans lui, Windows montre le nom du fichier vise.
        magasin = ctypes.c_void_p()
        interroger = _methode(lien, 0, ctypes.POINTER(GUID),
                              ctypes.POINTER(ctypes.c_void_p))
        interroger(lien, ctypes.byref(GUID(IID_IPROPERTYSTORE)),
                   ctypes.byref(magasin))
        if magasin:
            cle = PROPERTYKEY(GUID(GROUPE_TITRE), CLE_TITRE)
            valeur = _valeur_texte(titre)
            if valeur is not None:
                _methode(magasin, INDEX_SETVALUE,
                         ctypes.POINTER(PROPERTYKEY),
                         ctypes.POINTER(PROPVARIANT))(
                    magasin, ctypes.byref(cle), ctypes.byref(valeur))
                _methode(magasin, INDEX_COMMIT)(magasin)
                ole32.PropVariantClear(ctypes.byref(valeur))
            _methode(magasin, INDEX_RELEASE)(magasin)
        return lien
    except OSError:
        try:
            _methode(lien, INDEX_RELEASE)(lien)
        except Exception:
            pass
        return None


def definir_taches(identifiant, taches):
    """Pose le menu « Taches » du clic droit sur l'icone.

    `taches` est une suite de (titre, executable, arguments, icone). Windows
    rattache ce menu a l'identifiant d'application, le meme que celui des
    fenetres, sans quoi il n'apparaitrait nulle part.
    """
    liste = _creer(CLSID_LISTE, IID_LISTE)
    if liste is None:
        return False
    collection = _creer(CLSID_COLLECTION, IID_COLLECTION)
    if collection is None:
        _methode(liste, INDEX_RELEASE)(liste)
        return False

    ok = True
    try:
        _methode(liste, INDEX_SETAPPID, wintypes.LPCWSTR)(
            liste, wintypes.LPCWSTR(identifiant))
        nombre = ctypes.c_uint()
        retires = ctypes.c_void_p()
        _methode(liste, INDEX_BEGINLIST, ctypes.POINTER(ctypes.c_uint),
                 ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
            liste, ctypes.byref(nombre), ctypes.byref(GUID(IID_TABLEAU)),
            ctypes.byref(retires))
        if retires:
            _methode(retires, INDEX_RELEASE)(retires)

        ajoutes = 0
        for titre, chemin, arguments, icone in taches:
            lien = _raccourci(chemin, arguments, titre, icone)
            if lien is None:
                ok = False
                continue
            _methode(collection, INDEX_ADDOBJECT, ctypes.c_void_p)(
                collection, lien)
            _methode(lien, INDEX_RELEASE)(lien)
            ajoutes += 1

        if ajoutes:
            tableau = ctypes.c_void_p()
            interroger = _methode(collection, 0, ctypes.POINTER(GUID),
                                  ctypes.POINTER(ctypes.c_void_p))
            interroger(collection, ctypes.byref(GUID(IID_TABLEAU)),
                       ctypes.byref(tableau))
            if tableau:
                _methode(liste, INDEX_ADDUSERTASKS, ctypes.c_void_p)(
                    liste, tableau)
                _methode(tableau, INDEX_RELEASE)(tableau)
            _methode(liste, INDEX_COMMITLIST)(liste)
        else:
            ok = False
    except OSError:
        ok = False
    finally:
        for objet in (collection, liste):
            try:
                _methode(objet, INDEX_RELEASE)(objet)
            except Exception:
                pass
    return ok
