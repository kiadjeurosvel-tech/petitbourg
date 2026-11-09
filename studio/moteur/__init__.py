"""Moteur de production du studio d'animation.

Aucune dépendance à Claude ni à une API payante : interprétation par règles
ou par un modèle de langage local (Ollama / serveur compatible OpenAI local),
rendu Blender (ou aperçu 2D Pillow), voix open source (Piper / espeak-ng),
montage FFmpeg.
"""

import os as _os

if _os.name == "nt":
    # Sous Windows, le studio tourne sans console (pythonw) : on empêche FFmpeg, Blender, etc.
    # d'ouvrir une fenêtre noire à chaque appel.
    import subprocess as _sp

    _orig_init = _sp.Popen.__init__

    def _no_window_init(self, *args, **kwargs):
        kwargs.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    _sp.Popen.__init__ = _no_window_init
