"""Point d'entrée.

  python -m serveur                      démarre le studio (http://127.0.0.1:8765)
  python -m serveur --hote 0.0.0.0       accessible depuis le réseau local (téléphone sur le même Wi-Fi)
  python -m serveur mot-de-passe         définit / change le mot de passe
  python -m serveur produire "texte" [--duree 30] [--format 9:16] [--qualite standard] [--sortie video.mp4]
                                         production en ligne de commande (sans serveur, utilisé par GitHub Actions)
  python -m serveur diagnostic           vérifie Blender, FFmpeg, voix, modèle local
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from serveur import auth  # noqa: E402
from serveur.config import Config  # noqa: E402


def ensure_password(cfg: Config) -> None:
    if cfg.data.get("password_hash"):
        return
    pw = os.environ.get("STUDIO_PASSWORD")
    if not pw:
        pw = "-".join(secrets.token_urlsafe(4) for _ in range(3))
        f = cfg.data_dir / "MOT_DE_PASSE_INITIAL.txt"
        f.write_text(pw + "\n")
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
        print(f"\n  Mot de passe initial : {pw}\n  (aussi enregistré dans {f} — changez-le dans Réglages)\n")
    cfg.data["password_hash"] = auth.hash_password(pw)
    cfg.save()


def cmd_password(cfg: Config):
    pw = getpass.getpass("Nouveau mot de passe (10 caractères min.) : ")
    if len(pw) < 10 or pw != getpass.getpass("Confirmez : "):
        sys.exit("Mot de passe trop court ou différent.")
    cfg.data["password_hash"] = auth.hash_password(pw)
    cfg.data["token_gen"] = cfg.data.get("token_gen", 0) + 1
    cfg.save()
    (cfg.data_dir / "MOT_DE_PASSE_INITIAL.txt").unlink(missing_ok=True)
    print("Mot de passe enregistré. Les autres appareils devront se reconnecter.")


def cmd_diag(cfg: Config):
    from moteur import audio, llm, render
    s = cfg.settings
    b = render.find_blender(s.get("blender_path"))
    print("Données     :", cfg.data_dir)
    print("FFmpeg      :", shutil.which("ffmpeg") or "ABSENT (obligatoire)")
    print("Blender     :", f"{b} — {render.blender_version(b)}" if b else "absent → aperçu 2D")
    if b and render.needs_virtual_display():
        print("Affichage   :", "xvfb-run disponible" if shutil.which("xvfb-run") else "aucun écran ni xvfb → Cycles (lent)")
    st = audio.engines_status(cfg.data_dir / "voix")
    print("Voix        :", json.dumps(st, ensure_ascii=False), "→", audio.pick_engine(s.get("tts_engine", "auto"), cfg.data_dir / "voix"))
    print("Modèle local:", s["llm_provider"], s["llm_model"], json.dumps(llm.list_models(s), ensure_ascii=False))


def cmd_produce(cfg: Config, a):
    from serveur.production import Studio
    studio = Studio(cfg)
    r = studio.request({"text": a.texte, "command": a.commande, "duration": a.duree, "format": a.format,
                        "quality": a.qualite, "style": a.style})
    jid = r["job"]["id"]
    print("Interprétation :", json.dumps({k: r["resolved"][k] for k in ("command", "duration", "format", "style", "quality")}, ensure_ascii=False))
    job = studio.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    import threading
    t = threading.Thread(target=studio.run_job, args=(job,))
    t.start()
    last = ""
    while t.is_alive():
        j = studio.db.one("SELECT stages FROM jobs WHERE id=?", (jid,))
        line = " | ".join(f"{s['label']}: {s['done']}/{s['total']}" if s["status"] == "running" else "" for s in j["stages"]).strip(" |")
        if line and line != last:
            print(line, flush=True)
            last = line
        time.sleep(2)
    j = studio.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
    if j["status"] != "done":
        print(j.get("log", "")[-3000:])
        sys.exit(f"Échec : {j.get('error')}")
    res = j["result"]
    src = studio.version_dir(res["episode_id"], res["version"])
    if a.sortie:
        Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src / "video.mp4", a.sortie)
        for extra in ("miniature.jpg", "sous-titres.srt", "spec.json"):
            if (src / extra).exists():
                shutil.copy(src / extra, Path(a.sortie).with_name(Path(a.sortie).stem + "_" + extra))
    print(json.dumps(res, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(prog="python -m serveur", description="Studio d'animation IA indépendant")
    ap.add_argument("action", nargs="?", default="demarrer", choices=["demarrer", "mot-de-passe", "produire", "diagnostic"])
    ap.add_argument("texte", nargs="?", default="")
    ap.add_argument("--hote", default=os.environ.get("STUDIO_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "8765")))
    ap.add_argument("--donnees", default=None, help="dossier de données (défaut : studio/donnees)")
    ap.add_argument("--commande", default="auto")
    ap.add_argument("--duree", type=int, default=None)
    ap.add_argument("--format", default=None)
    ap.add_argument("--qualite", default=None)
    ap.add_argument("--style", default=None)
    ap.add_argument("--sortie", default=None)
    a = ap.parse_args()
    cfg = Config(Path(a.donnees) if a.donnees else None)
    if a.action == "mot-de-passe":
        return cmd_password(cfg)
    if a.action == "diagnostic":
        return cmd_diag(cfg)
    if a.action == "produire":
        return cmd_produce(cfg, a)
    ensure_password(cfg)
    import uvicorn
    from serveur.app import create_app
    print(f"Studio : http://{'127.0.0.1' if a.hote in ('0.0.0.0', '::') else a.hote}:{a.port}")
    uvicorn.run(create_app(cfg), host=a.hote, port=a.port, log_level="warning", proxy_headers=True, forwarded_allow_ips="127.0.0.1")


if __name__ == "__main__":
    main()
