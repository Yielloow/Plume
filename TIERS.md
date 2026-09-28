# Composants tiers / Third-party components

Plume est distribuée avec les composants ci-dessous. Chacun garde sa propre
licence ; les licences en question sont reproduites dans les paquets d'origine
et accessibles aux adresses indiquées.

Plume ships with the components listed below. Each keeps its own licence; the
licence texts are available at the addresses given.

## Programmes appelés par Plume / Programs Plume runs

| Composant | Version embarquée | Licence | Sources |
|---|---|---|---|
| [mpv](https://mpv.io/) | v0.41.0-244-gaf9c81fa1 | GPL-2.0-or-later | https://github.com/mpv-player/mpv |

mpv est redistribué tel quel, sans modification, dans
`outils-externes/mpv.exe`. Sa licence exige que les sources correspondantes
soient disponibles : elles le sont au dépôt ci-dessus, à la révision
`af9c81fa1`. Les binaires officiels pour Windows viennent de
https://sourceforge.net/projects/mpv-player-windows/files/ et
https://github.com/shinchiro/mpv-winbuild-cmake. mpv embarque lui-même FFmpeg,
libplacebo, libass et d'autres bibliothèques, dont les licences figurent dans
son paquet.

mpv is redistributed unmodified, as `outils-externes/mpv.exe`. Its licence
requires the corresponding sources to be available: they are, in the
repository above, at revision `af9c81fa1`.

## Bibliothèques Python embarquées / Bundled Python libraries

| Composant | Version | Licence |
|---|---|---|
| [Python](https://www.python.org/) | 3.10 | PSF-2.0 |
| [streamlink](https://streamlink.github.io/) | 8.5.0 | BSD-2-Clause |
| [pythonnet](https://pythonnet.github.io/) | 3.1.0 | MIT |
| [Pillow](https://python-pillow.org/) | 11.3.0 | MIT-CMU |
| [pycryptodome](https://www.pycryptodome.org/) | 3.23.0 | BSD-2-Clause et domaine public |
| [requests](https://requests.readthedocs.io/) | 2.32.5 | Apache-2.0 |
| [urllib3](https://urllib3.readthedocs.io/) | 2.5.0 | MIT |
| [certifi](https://github.com/certifi/python-certifi) | 2025.10.5 | MPL-2.0 |
| [psutil](https://github.com/giampaolo/psutil) | 7.1.1 | BSD-3-Clause |
| [websocket-client](https://github.com/websocket-client/websocket-client) | 1.9.0 | Apache-2.0 |
| [lxml](https://lxml.de/) | 6.1.0 | BSD-3-Clause |
| [trio](https://trio.readthedocs.io/) | 0.32.0 | MIT ou Apache-2.0 |
| [isodate](https://github.com/gweis/isodate) | 0.7.2 | BSD-3-Clause |
| [PySocks](https://github.com/Anorov/PySocks) | 1.7.1 | BSD-3-Clause |
| [PyInstaller](https://pyinstaller.org/) | runtime seulement | GPL-2.0 avec exception de liaison |

L'exception de liaison de PyInstaller autorise expressément à distribuer un
programme empaqueté sous la licence de son choix ; c'est ce que fait Plume.

## Composants Microsoft / Microsoft components

| Composant | Rôle | Conditions |
|---|---|---|
| [WebView2 SDK](https://developer.microsoft.com/microsoft-edge/webview2/) | moteur de rendu des pages | [Microsoft Software License Terms](https://aka.ms/webview2/license), redistribution autorisée |
| WebView2 Runtime | fourni par Windows, non redistribué | installé par Microsoft |

Plume n'embarque pas le moteur lui-même : il utilise le WebView2 Runtime
présent sur Windows, ou installé par Microsoft. Seules les bibliothèques
d'interface (`Microsoft.Web.WebView2.Core.dll`,
`Microsoft.Web.WebView2.WinForms.dll`) sont redistribuées, ce que leurs
conditions autorisent.

## Outils utilisés pour construire, non redistribués

| Outil | Rôle | Licence |
|---|---|---|
| [Inno Setup](https://jrsoftware.org/isinfo.php) | fabrique l'installeur | licence Inno Setup |
| [PyInstaller](https://pyinstaller.org/) | empaquette l'exécutable | GPL-2.0 avec exception |

## Polices et icônes

L'interface est dessinée avec Segoe UI, la police de Windows, qui n'est pas
redistribuée. Toutes les icônes de Plume, l'étincelle comprise, sont tracées
en code dans `interface.py` : aucune image n'est empruntée.
