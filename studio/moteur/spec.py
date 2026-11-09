"""Format du scénario (« spec ») et normalisation.

Un épisode est décrit par un dictionnaire JSON :

{
  "title": str, "logline": str, "genre": str,
  "style": "cartoon3d" | "cinematique" | "mystere" | "pastel",
  "format": "9:16" | "16:9" | "1:1",
  "quality": "brouillon" | "standard" | "final",
  "subtitles": bool,
  "characters": [ {id, name, gender, role, look{...}, voice{...}} ],
  "scenes": [ {id, n, set, variant, time, lighting, mood, summary, characters[ids],
               action, lines[{who, text, emotion}], camera{move, shot, speed},
               expressiveness, anim_speed, min_duration, seed} ],
  "memory_out": {summary, ending, facts[]}
}

Tout ce qui arrive d'un modèle de langage passe par `normalize_spec`, qui
borne les valeurs et remplace les inconnues : le moteur de rendu ne reçoit
jamais de données invalides.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re

FORMATS = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1)}
QUALITIES = {
    # hauteur de référence (petit côté), images/s, moteur Blender
    "brouillon": {"short": 360, "fps": 12, "engine": "workbench", "samples": 1},
    "standard": {"short": 540, "fps": 24, "engine": "eevee", "samples": 16},
    "final": {"short": 1080, "fps": 24, "engine": "eevee", "samples": 48},
}
STYLES = {
    "cartoon3d": "3D cartoon",
    "cinematique": "Cinématographique",
    "mystere": "Mystère / nuit",
    "pastel": "Pastel doux",
}
SETS = {
    "restaurant": "Restaurant",
    "rue": "Rue / ville",
    "foret": "Forêt",
    "salon": "Salon",
    "bureau": "Bureau",
    "manoir": "Manoir (nuit)",
    "plage": "Plage",
    "espace": "Espace",
    "classe": "Salle de classe",
}
TIMES = ["jour", "soir", "nuit"]
LIGHTINGS = ["normal", "lumineux", "sombre", "dramatique"]
CAMERA_MOVES = ["static", "dolly_in", "dolly_out", "pan_left", "pan_right", "orbit", "crane_up", "handheld"]
SHOTS = ["large", "moyen", "gros_plan"]
EMOTIONS = ["neutre", "joie", "colere", "triste", "surprise", "peur", "reflexion"]
ACTIONS = ["parler", "dispute", "marcher", "entree", "surprise", "rire", "triste", "reflexion", "peur"]
GENRES = ["dispute", "mystere", "comedie", "aventure", "romance", "drame"]

SKIN = ["#f1c7a5", "#e0ac83", "#c68a5e", "#9c6644", "#6f4630", "#4a2f22"]
HAIR = ["#1c1410", "#3b2416", "#6b3e1f", "#b5833d", "#d9b36c", "#8c8c8c", "#a8322a"]
OUTFIT = ["#d64545", "#2f6fd6", "#2fa36b", "#e0a43a", "#8a4fd6", "#e06a9a", "#2a2f3a", "#f2f2f2", "#16a3a3"]
HAIR_STYLES = ["court", "long", "chignon", "boucles", "chauve"]


def rnd(seed) -> random.Random:
    return random.Random(str(seed))


def stable_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def frame_size(fmt: str, quality: str) -> tuple[int, int]:
    a, b = FORMATS.get(fmt, (9, 16))
    short = QUALITIES.get(quality, QUALITIES["standard"])["short"]
    if a == b:
        return short, short
    if a < b:  # vertical
        w, h = short, round(short * b / a)
    else:
        w, h = round(short * a / b), short
    return w - w % 2, h - h % 2


def _clamp(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _pick(v, allowed, default):
    if isinstance(v, str):
        v2 = v.strip().lower()
        for a in allowed:
            if v2 == a.lower():
                return a
    return default


def _color(v, default):
    if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v.strip()):
        return v.strip().lower()
    return default


def make_look(seed, gender="f") -> dict:
    r = rnd(seed)
    styles = ["long", "chignon", "boucles", "court"] if gender == "f" else ["court", "court", "boucles", "chauve"]
    return {
        "skin": r.choice(SKIN), "hair": r.choice(HAIR), "hair_style": r.choice(styles),
        "outfit": r.choice(OUTFIT), "pants": r.choice(["#2a2f3a", "#3a3326", "#1f3150", "#4a4a4a"]),
        "height": round(r.uniform(.92, 1.08), 2), "build": round(r.uniform(.9, 1.15), 2),
        "eyes": r.choice(["#3b2416", "#2f6fd6", "#2fa36b", "#1c1410"]),
    }


def normalize_character(c: dict, idx: int) -> dict:
    gender = "m" if str(c.get("gender", "f")).lower().startswith(("m", "h")) else "f"
    cid = str(c.get("id") or f"c{idx + 1}")
    name = str(c.get("name") or f"Personnage {idx + 1}")[:40]
    base = make_look(f"{name}-{cid}", gender)
    look = c.get("look") if isinstance(c.get("look"), dict) else {}
    out_look = {
        "skin": _color(look.get("skin"), base["skin"]),
        "hair": _color(look.get("hair"), base["hair"]),
        "hair_style": _pick(look.get("hair_style"), HAIR_STYLES, base["hair_style"]),
        "outfit": _color(look.get("outfit"), base["outfit"]),
        "pants": _color(look.get("pants"), base["pants"]),
        "height": _clamp(look.get("height"), .8, 1.2, base["height"]),
        "build": _clamp(look.get("build"), .8, 1.3, base["build"]),
        "eyes": _color(look.get("eyes"), base["eyes"]),
    }
    voice = c.get("voice") if isinstance(c.get("voice"), dict) else {}
    vr = rnd(cid + name)
    out_voice = {
        "pitch": int(round(_clamp(voice.get("pitch"), 20, 80, vr.randint(35, 60) if gender == "f" else vr.randint(25, 45)))),
        "speed": _clamp(voice.get("speed"), .7, 1.4, 1.0),
        "voice_id": str(voice.get("voice_id") or ""),
    }
    return {"id": cid, "name": name, "gender": gender, "role": str(c.get("role") or "")[:120],
            "look": out_look, "voice": out_voice}


def normalize_scene(s: dict, idx: int, char_ids: list[str], defaults: dict) -> dict:
    chars = [c for c in (s.get("characters") or []) if c in char_ids][:4] or char_ids[:2]
    lines = []
    for ln in s.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        who = ln.get("who") if ln.get("who") in char_ids else (chars[0] if chars else None)
        text = re.sub(r"\s+", " ", str(ln.get("text") or "")).strip()[:300]
        if who and text:
            lines.append({"who": who, "text": text, "emotion": _pick(ln.get("emotion"), EMOTIONS, "neutre")})
            if who not in chars:
                chars.append(who)
    cam = s.get("camera") if isinstance(s.get("camera"), dict) else {}
    return {
        "id": str(s.get("id") or f"s{idx + 1}"),
        "n": idx + 1,
        "set": _pick(s.get("set"), list(SETS), defaults.get("set", "salon")),
        "variant": int(_clamp(s.get("variant"), 0, 99, 0)),
        "time": _pick(s.get("time"), TIMES, defaults.get("time", "jour")),
        "lighting": _pick(s.get("lighting"), LIGHTINGS, "normal"),
        "mood": str(s.get("mood") or "")[:40],
        "summary": str(s.get("summary") or "")[:300],
        "characters": chars,
        "action": _pick(s.get("action"), ACTIONS, "parler"),
        "lines": lines,
        "camera": {
            "move": _pick(cam.get("move"), CAMERA_MOVES, "static"),
            "shot": _pick(cam.get("shot"), SHOTS, "moyen"),
            "speed": _clamp(cam.get("speed"), .2, 3, 1.0),
        },
        "expressiveness": _clamp(s.get("expressiveness"), .2, 3, 1.0),
        "anim_speed": _clamp(s.get("anim_speed"), .25, 3, 1.0),
        "min_duration": _clamp(s.get("min_duration"), 1.5, 30, 3.0),
        "seed": int(_clamp(s.get("seed"), 0, 10**9, idx * 7919 + 17)),
    }


def normalize_spec(spec: dict, *, fmt=None, quality=None, style=None) -> dict:
    spec = copy.deepcopy(spec or {})
    chars = [normalize_character(c, i) for i, c in enumerate((spec.get("characters") or [])[:8]) if isinstance(c, dict)]
    seen = set()
    for c in chars:  # identifiants uniques
        while c["id"] in seen:
            c["id"] += "x"
        seen.add(c["id"])
    if not chars:
        chars = [normalize_character({"name": "Léa", "gender": "f"}, 0), normalize_character({"name": "Hugo", "gender": "m"}, 1)]
    ids = [c["id"] for c in chars]
    defaults = {"set": _pick(spec.get("set"), list(SETS), "salon"), "time": "jour"}
    scenes = [normalize_scene(s, i, ids, defaults) for i, s in enumerate((spec.get("scenes") or [])[:40]) if isinstance(s, dict)]
    if not scenes:
        scenes = [normalize_scene({"lines": []}, 0, ids, defaults)]
    mem = spec.get("memory_out") if isinstance(spec.get("memory_out"), dict) else {}
    return {
        "title": str(spec.get("title") or "Sans titre")[:120],
        "logline": str(spec.get("logline") or "")[:400],
        "genre": _pick(spec.get("genre"), GENRES, "comedie"),
        "style": _pick(style or spec.get("style"), list(STYLES), "cartoon3d"),
        "format": fmt if fmt in FORMATS else (spec.get("format") if spec.get("format") in FORMATS else "9:16"),
        "quality": quality if quality in QUALITIES else (spec.get("quality") if spec.get("quality") in QUALITIES else "standard"),
        "subtitles": bool(spec.get("subtitles", True)),
        "target_duration": _clamp(spec.get("target_duration"), 5, 600, 30),
        "characters": chars,
        "scenes": scenes,
        "memory_out": {
            "summary": str(mem.get("summary") or spec.get("logline") or "")[:800],
            "ending": str(mem.get("ending") or "")[:400],
            "facts": [str(f)[:200] for f in (mem.get("facts") or [])][:20],
        },
    }


# --------------------------------------------------------------------------- empreintes

def audio_key(scene: dict, chars_by_id: dict, tts_sig: str) -> str:
    """Empreinte de tout ce qui influence l'audio d'une scène."""
    voices = {cid: chars_by_id[cid]["voice"] | {"gender": chars_by_id[cid]["gender"]} for cid in scene["characters"] if cid in chars_by_id}
    return stable_hash({"lines": scene["lines"], "voices": voices, "tts": tts_sig, "v": 2})


def visual_key(scene: dict, spec: dict, chars_by_id: dict, akey: str, renderer_sig: str) -> str:
    """Empreinte de tout ce qui influence l'image d'une scène (l'audio compte pour la synchro labiale)."""
    looks = {cid: chars_by_id[cid]["look"] for cid in scene["characters"] if cid in chars_by_id}
    vis = {k: v for k, v in scene.items() if k not in ("summary", "n", "id")}
    vis["lines"] = [{"who": ln["who"], "emotion": ln["emotion"]} for ln in scene["lines"]]
    return stable_hash({"scene": vis, "looks": looks, "audio": akey, "fmt": spec["format"],
                        "quality": spec["quality"], "style": spec["style"], "r": renderer_sig, "v": 3})
