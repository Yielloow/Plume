# Plume

A light browser for Windows. Français : [README.fr.md](README.fr.md)

Plume is a desktop browser built around the WebView2 engine that Windows
already ships. It keeps the window, the tabs and the drawing to itself, and
asks the engine only for the pages. The result is a browser that sits at a
few hundred megabytes instead of a few gigabytes, and that never sends
anything anywhere.

[Download the latest version](https://github.com/Yielloow/Plume/releases/latest)
 ·  [Site](https://yielloow.github.io/Plume/)  ·
[Changelog](CHANGELOG.md)

![Plume showing a Wikipedia article, with three tabs open](docs/capture-onglets.png)

| The home page | The settings |
|---|---|
| ![Plume's home page, with its search field and two work groups](docs/capture-accueil.png) | ![Plume's settings page](docs/capture-parametres.png) |

## What it looks like on the meter

A Task Manager capture, taken by a Plume user while a Twitch live was playing
in it:

| | CPU | Memory |
|---|---|---|
| Plume.exe | 0.5 % | 118.9 MB |
| Brave Browser | 30.7 % | 708.6 MB |

Plume's rendering engine, WebView2, runs as its own process and is counted
separately by Windows: on another capture it sat at 0 % and 275.5 MB. So the
honest figure for Plume with a page open is the sum of the two, and it is
still well under what a full browser costs. Both captures are on the
[site](https://yielloow.github.io/Plume/).

## What it does

- **Tabs, bookmarks bar, work groups.** Right-click a tab to file it in a
  group; one click on the home page reopens the whole group.
- **Sleeping tabs.** Tabs you are not looking at are frozen and give their
  memory back. Coming back finds them intact, and a tab playing audio is
  never put to sleep.
- **YouTube without ads.** Ads are removed from the page before the player
  even sees them, and known ad requests are refused. YouTube keeps its own
  player, fullscreen included.
- **Twitch, your choice.** Twitch's own player by default, light on the
  graphics card. Or Plume's player, mpv fed by streamlink, which skips ad
  breaks but asks more of the GPU. A button in the address bar switches
  between them.
- **A colour you choose.** The whole palette follows from one colour: the
  bars, the tabs, the drawn opening, the window icon, the video player's
  controls and Plume's own pages.
- **Private window.** No history, no cookies, no tabs kept.
- **One-click updates.** Plume checks once a day, tells you, and installs on
  your word.

The first three are modules you can switch off in the settings page, without
uninstalling anything.

## Nothing leaves your machine

There is no server, no account, no synchronisation, no telemetry. Bookmarks,
history, cookies and the home page are files in a profile folder on your
disk; deleting that folder is all it takes to forget everything. The only
request Plume makes on its own is the daily update check, and it can be
switched off.

## Install

Windows 10 (1809) or 11, 64-bit. Download the installer from the
[releases](https://github.com/Yielloow/Plume/releases/latest) and run it.
Nothing else to install: the WebView2 runtime is already on Windows, and mpv
travels with Plume.

**Windows will complain, and that is expected.** Plume is not signed by a
certificate: one costs several hundred euros a year, and this is a free
project. So Windows does not know the publisher and shows a blue
"Windows protected your PC" window. Click *More info*, then *Run anyway*. The
SHA-256 of every release is published next to the download, so you can check
that the file you have is the file that was published:

```powershell
Get-FileHash .\Plume-1.0.20-installeur.exe -Algorithm SHA256
```

## Build it yourself

You need Python 3.10 (64-bit), the dependencies, and a copy of `mpv.exe` in
`outils-externes/`.

```powershell
pip install -r requirements.txt
python outils\construire.py
```

The build writes `..\Plume-paquet\Plume-<version>-installeur.exe`, a portable
folder next to it, and updates `docs/version.json`, the manifest Plume reads
to know whether a newer version exists. `python outils\publier.py` checks that
everything agrees before a release.

## What Plume is not

It helps to say this plainly.

- **Windows only.** It is built on WebView2 and on the Windows window
  manager. There is no Linux or macOS version, and none is planned.
- **No third-party extensions.** The modules are written into Plume.
- **One maintainer.** Issues are welcome, answers may take a while.
- **Not a privacy tool.** Nothing leaves your machine, but your internet
  provider still sees your traffic, and the sites you visit still see you.

## Contributing

Bug reports with the steps to reproduce are the most useful thing you can
send. For code, open an issue before a large change: Plume has opinions about
how it is written, and they are worth agreeing on first. The code and its
comments are in French; you are welcome to write in English.

## Licence

[GPL-3.0](LICENSE). Third-party components and their licences are listed in
[TIERS.md](TIERS.md).
