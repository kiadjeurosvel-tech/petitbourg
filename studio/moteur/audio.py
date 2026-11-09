"""Voix (TTS open source) et piste audio des scènes.

Moteurs interchangeables, par ordre de préférence en mode « auto » :
  1. Piper  (neural, hors ligne)   — modèles .onnx dans <données>/voix/
  2. espeak-ng (synthèse formantique, très léger)
  3. silence (aucune voix ; durée estimée, la bouche bouge quand même)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000
ENV_HZ = 100  # résolution de l'enveloppe pour la synchro labiale
GAP = .3
HEAD = .5
TAIL = .6


# --------------------------------------------------------------------------- détection

def piper_models(voice_dir: Path) -> list[Path]:
    return sorted(voice_dir.glob("*.onnx")) if voice_dir.exists() else []


def piper_available(voice_dir: Path) -> bool:
    if not piper_models(voice_dir):
        return False
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return shutil.which("piper") is not None


def engines_status(voice_dir: Path) -> dict:
    return {"piper": piper_available(voice_dir), "piper_models": [p.name for p in piper_models(voice_dir)],
            "espeak-ng": shutil.which("espeak-ng") is not None, "silence": True}


def pick_engine(pref: str, voice_dir: Path) -> str:
    st = engines_status(voice_dir)
    if pref in ("piper", "espeak-ng", "silence") and st.get(pref):
        return pref
    if st["piper"]:
        return "piper"
    if st["espeak-ng"]:
        return "espeak-ng"
    return "silence"


def tts_signature(engine: str, voice_dir: Path) -> str:
    if engine == "piper":
        return "piper:" + ",".join(p.name for p in piper_models(voice_dir))
    return engine


# --------------------------------------------------------------------------- synthèse

def _female_model(p: Path) -> bool:
    n = p.name.lower()
    return any(k in n for k in ("siwis", "jessica", "female", "_f", "-f-"))


def _piper(text: str, out: Path, voice: dict, gender: str, voice_dir: Path, slot: int):
    models = piper_models(voice_dir)
    same = [m for m in models if _female_model(m) == (gender == "f")] or models
    model = same[slot % len(same)]
    if voice.get("voice_id"):
        for m in models:
            if m.stem == voice["voice_id"]:
                model = m
    try:
        from piper import PiperVoice  # type: ignore
        pv = PiperVoice.load(str(model))
        with wave.open(str(out), "wb") as wf:
            if hasattr(pv, "synthesize_wav"):
                pv.synthesize_wav(text, wf)
            else:
                pv.synthesize(text, wf)
    except ImportError:
        subprocess.run(["piper", "-m", str(model), "-f", str(out)], input=text.encode(), check=True, capture_output=True)
    # légère variation de hauteur pour distinguer deux personnages sur la même voix
    shift = 1 + ((voice.get("pitch", 45) - 45) / 300)
    if abs(shift - 1) > .01:
        tmp = out.with_suffix(".p.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-af",
                        f"asetrate=22050*{shift:.3f},aresample=22050,atempo={1 / shift:.3f}", str(tmp)], check=True)
        tmp.replace(out)


def _espeak(text: str, out: Path, voice: dict, gender: str, slot: int):
    variant = (["f1", "f2", "f3", "f4", "f5"] if gender == "f" else ["m1", "m3", "m2", "m4", "m6"])[slot % 5]
    speed = int(160 * float(voice.get("speed", 1.0)))
    subprocess.run(["espeak-ng", "-v", f"fr+{variant}", "-p", str(int(voice.get("pitch", 50))), "-s", str(speed),
                    "-w", str(out), text], check=True, capture_output=True)


def _read_mono(path: Path) -> np.ndarray:
    """Décode n'importe quel fichier audio en float32 mono 48 kHz via ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _syllable_envelope(text: str, dur: float) -> np.ndarray:
    """Enveloppe synthétique quand il n'y a pas de voix (moteur « silence »)."""
    n = max(1, int(dur * ENV_HZ))
    t = np.arange(n) / ENV_HZ
    syl = max(1, sum(1 for ch in text.lower() if ch in "aeiouyéèêàâîôû"))
    f = syl / max(dur, .1)
    env = .5 + .5 * np.sin(2 * np.pi * f * t) ** 2
    env[: int(.05 * ENV_HZ)] *= .3
    return env.astype(np.float32)


def synth_line(text: str, voice: dict, gender: str, engine: str, voice_dir: Path, slot: int, tmpdir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Retourne (échantillons 48 kHz, enveloppe 100 Hz normalisée 0..1)."""
    tmpdir.mkdir(parents=True, exist_ok=True)
    wav = tmpdir / f"l{abs(hash((text, slot))) % 10**8}.wav"
    if engine == "piper":
        _piper(text, wav, voice, gender, voice_dir, slot)
    elif engine == "espeak-ng":
        _espeak(text, wav, voice, gender, slot)
    else:
        dur = max(.8, len(text) / 14.0 / float(voice.get("speed", 1.0)))
        return np.zeros(int(dur * SR), dtype=np.float32), _syllable_envelope(text, dur)
    s = _read_mono(wav)
    # coupe les silences de début/fin
    nz = np.where(np.abs(s) > .01)[0]
    if len(nz):
        s = s[max(0, nz[0] - int(.03 * SR)): nz[-1] + int(.08 * SR)]
    peak = float(np.max(np.abs(s))) if len(s) else 0
    if peak > 0:
        s = s * (.89 / peak)
    hop = SR // ENV_HZ
    n = max(1, len(s) // hop)
    env = np.sqrt(np.mean(s[: n * hop].reshape(n, hop) ** 2, axis=1)) if len(s) >= hop else np.zeros(1)
    if env.max() > 0:
        env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    return s.astype(np.float32), env.astype(np.float32)


def build_scene_audio(scene: dict, chars_by_id: dict, engine: str, voice_dir: Path, out_dir: Path) -> dict:
    """Crée out_dir/audio.wav et out_dir/timing.json. Retourne le timing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    order = {cid: i for i, cid in enumerate(chars_by_id)}
    pieces, t = [], HEAD
    lines = []
    for ln in scene["lines"]:
        c = chars_by_id.get(ln["who"], {"voice": {}, "gender": "f"})
        s, env = synth_line(ln["text"], c["voice"], c["gender"], engine, voice_dir, order.get(ln["who"], 0), out_dir / "tmp")
        d = len(s) / SR
        pieces.append((t, s))
        lines.append({"who": ln["who"], "text": ln["text"], "emotion": ln["emotion"], "start": round(t, 3), "end": round(t + d, 3),
                      "env": [round(float(v), 3) for v in env]})
        t += d + GAP
    total = max(t - GAP + TAIL, float(scene.get("min_duration", 3.0)))
    buf = np.zeros(int(total * SR) + 1, dtype=np.float32)
    for start, s in pieces:
        i = int(start * SR)
        buf[i:i + len(s)] += s[: max(0, len(buf) - i)]
    pcm = (np.clip(buf, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out_dir / "audio.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    shutil.rmtree(out_dir / "tmp", ignore_errors=True)
    timing = {"duration": round(len(buf) / SR, 3), "lines": lines, "engine": engine}
    (out_dir / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    return timing


def mouth_tracks(timing: dict, fps: int, char_ids: list[str]) -> dict:
    """Ouverture de bouche par personnage et par image (0..1)."""
    n = int(round(timing["duration"] * fps)) + 1
    tracks = {cid: [0.0] * n for cid in char_ids}
    for ln in timing["lines"]:
        tr = tracks.get(ln["who"])
        if tr is None:
            continue
        env = ln["env"]
        for f in range(int(ln["start"] * fps), min(n, int(ln["end"] * fps) + 1)):
            k = int((f / fps - ln["start"]) * ENV_HZ)
            if 0 <= k < len(env):
                tr[f] = round(max(tr[f], env[k]), 3)
    return tracks


def speaker_at(timing: dict, t: float):
    for ln in timing["lines"]:
        if ln["start"] - .15 <= t <= ln["end"] + .2:
            return ln
    return None


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

