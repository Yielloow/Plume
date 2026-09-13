# -*- coding: utf-8 -*-
"""yt-dlp autonome, pour le paquet.

Le `yt-dlp.exe` installe par pip n'est qu'un amorceur : il a besoin du Python
de la machine. Dans le paquet, il faut un executable qui se suffise a lui-meme,
car mpv l'appelle directement par son chemin.
"""
import sys

from yt_dlp import main

if __name__ == "__main__":
    sys.exit(main())
