"""Télécharge des voix françaises Piper (open source, licences libres) dans donnees/voix.

  python scripts/telecharger_voix.py            voix par défaut (1 féminine, 1 masculine)
  python scripts/telecharger_voix.py --toutes   toutes les voix françaises listées
Source : https://huggingface.co/rhasspy/piper-voices (une seule fois ; ensuite tout fonctionne hors ligne).
"""
import argparse
import sys
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR"
VOICES = {
    "fr_FR-siwis-medium": "siwis/medium",      # féminine
    "fr_FR-tom-medium": "tom/medium",          # masculine
    "fr_FR-upmc-medium": "upmc/medium",        # 2 locuteurs
    "fr_FR-gilles-low": "gilles/low",          # masculine
}
DEFAULT = ["fr_FR-siwis-medium", "fr_FR-tom-medium"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toutes", action="store_true")
    ap.add_argument("--dossier", default=str(Path(__file__).resolve().parent.parent / "donnees" / "voix"))
    a = ap.parse_args()
    out = Path(a.dossier)
    out.mkdir(parents=True, exist_ok=True)
    for name in (VOICES if a.toutes else DEFAULT):
        for ext in (".onnx", ".onnx.json"):
            dest = out / (name + ext)
            if dest.exists() and dest.stat().st_size > 1000:
                print("déjà présent :", dest.name)
                continue
            url = f"{BASE}/{VOICES[name]}/{name}{ext}?download=true"
            print("téléchargement :", dest.name, flush=True)
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as ex:  # noqa: BLE001
                dest.unlink(missing_ok=True)
                sys.exit(f"Échec ({ex}). Vérifiez la connexion Internet.")
    print("Voix installées dans", out)


if __name__ == "__main__":
    main()
