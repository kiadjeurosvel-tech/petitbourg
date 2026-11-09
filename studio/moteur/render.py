"""Pilotage du rendu : Blender (sous-processus) ou aperçu 2D, puis encodage du plan en MP4.

La progression remontée est RÉELLE : nombre d'images PNG effectivement écrites sur le disque.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import render_2d

HERE = Path(__file__).resolve().parent
_BLENDER_CACHE: dict = {}


def find_blender(configured: str | None = None) -> str | None:
    cands = [configured] if configured else []
    cands += [shutil.which("blender")]
    if platform.system() == "Windows":
        cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    elif platform.system() == "Darwin":
        cands += ["/Applications/Blender.app/Contents/MacOS/Blender"]
    else:
        cands += sorted(glob.glob("/opt/blender*/blender"), reverse=True) + ["/snap/bin/blender"]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def blender_version(path: str | None) -> str | None:
    if not path:
        return None
    if path in _BLENDER_CACHE:
        return _BLENDER_CACHE[path]
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout
        v = out.splitlines()[0].strip() if out else None
    except Exception:  # noqa: BLE001
        v = None
    _BLENDER_CACHE[path] = v
    return v


def needs_virtual_display() -> bool:
    return platform.system() == "Linux" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


def choose_renderer(settings: dict) -> tuple[str, str | None]:
    """('blender', chemin) ou ('2d', None)"""
    pref = settings.get("renderer") or "auto"
    if pref == "2d":
        return "2d", None
    b = find_blender(settings.get("blender_path"))
    if b:
        return "blender", b
    if pref == "blender":
        raise RuntimeError("Blender est demandé mais introuvable. Installez-le ou indiquez son chemin dans Réglages.")
    return "2d", None


def renderer_signature(kind: str, path: str | None) -> str:
    return f"blender:{blender_version(path)}" if kind == "blender" else "2d:1"


def _count(out_dir: str) -> int:
    try:
        return sum(1 for n in os.listdir(out_dir) if n.endswith(".png"))
    except FileNotFoundError:
        return 0


def _run_blender(blender: str, ri_path: str, ri: dict, progress, cancel, log) -> None:
    cmd = [blender, "-b", "-noaudio", "--factory-startup", "-P", str(HERE / "blender_scene.py"), "--", ri_path]
    if needs_virtual_display() and ri.get("engine") != "cycles":
        if shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"] + cmd
        else:
            log("Pas d'affichage ni de xvfb-run : rendu en mode Cycles (plus lent).")
            ri["engine"] = "cycles"
    logf = open(Path(ri["out_dir"]).parent / "blender.log", "w")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    last = -1
    try:
        while proc.poll() is None:
            if cancel and cancel():
                proc.kill()
                raise InterruptedError("annulé")
            n = _count(ri["out_dir"])
            if n != last:
                progress(n)
                last = n
            time.sleep(.4)
    finally:
        logf.close()
    progress(_count(ri["out_dir"]))
    if proc.returncode != 0 or _count(ri["out_dir"]) < ri["frames"]:
        tail = (Path(ri["out_dir"]).parent / "blender.log").read_text(encoding="utf-8", errors="replace")[-1500:]
        raise RuntimeError(f"Blender a échoué (code {proc.returncode}). Fin du journal :\n{tail}")


def render_frames(ri: dict, work: Path, kind: str, blender: str | None, progress, cancel, log) -> str:
    """Rend les images de la scène dans work/frames. Retourne le moteur réellement utilisé."""
    frames = work / "frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    ri = dict(ri, out_dir=str(frames))
    if kind == "2d":
        render_2d.render(ri, progress=progress, cancel=cancel)
        return "2d"
    ri_path = work / "render_input.json"
    ri_path.write_text(json.dumps(ri), encoding="utf-8")
    try:
        _run_blender(blender, str(ri_path), ri, progress, cancel, log)
        return f"blender/{ri['engine']}"
    except InterruptedError:
        raise
    except Exception as ex:  # noqa: BLE001
        if ri.get("engine") == "eevee":
            log(f"EEVEE indisponible sur cette machine ({str(ex).splitlines()[0]}) → nouvel essai avec Workbench.")
            shutil.rmtree(frames, ignore_errors=True)
            frames.mkdir()
            ri["engine"] = "workbench"
            ri_path.write_text(json.dumps(ri), encoding="utf-8")
            _run_blender(blender, str(ri_path), ri, progress, cancel, log)
            return "blender/workbench"
        raise


def encode_clip(frames_dir: Path, audio_wav: Path, fps: int, duration: float, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", str(frames_dir / "f_%04d.png"), "-i", str(audio_wav),
           "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
