"""Orchestration de la production : personnages → scènes → audio → animation → montage → contrôle → rendu final.

Régénération partielle : chaque scène a deux empreintes (audio / image). Un résultat déjà
présent dans le cache avec la même empreinte est réutilisé tel quel — après une retouche,
seules les scènes réellement modifiées sont recalculées.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import audio, montage, render
from .spec import QUALITIES, frame_size, stable_hash, audio_key, visual_key

STAGES = [
    ("attente", "Travail en attente"),
    ("scenario", "Génération du scénario"),
    ("personnages", "Création des personnages"),
    ("scenes", "Génération des scènes"),
    ("audio", "Génération audio"),
    ("animation", "Animation"),
    ("montage", "Montage"),
    ("controle", "Contrôle qualité"),
    ("final", "Rendu final"),
]


class Reporter:
    """Interface minimale ; le serveur fournit une implémentation qui écrit en base."""

    def stage(self, key, status, done=None, total=None, unit=None, detail=None, eta=None):  # noqa: D401
        pass

    def log(self, msg):
        print(msg, flush=True)

    def cancelled(self) -> bool:
        return False


class Cancelled(Exception):
    pass


def _check(rep):
    if rep.cancelled():
        raise Cancelled()


def engines(settings: dict, data_dir: Path) -> dict:
    kind, path = render.choose_renderer(settings)
    voice_dir = data_dir / "voix"
    return {"renderer": kind, "blender_path": path, "blender_version": render.blender_version(path) if path else None,
            "renderer_sig": render.renderer_signature(kind, path),
            "tts": audio.pick_engine(settings.get("tts_engine") or "auto", voice_dir), "voice_dir": voice_dir}


def render_input(spec, scene, chars_by_id, timing, w, h, q):
    fps = q["fps"]
    frames = max(1, int(round(timing["duration"] * fps)))
    cast = [chars_by_id[c] for c in scene["characters"] if c in chars_by_id]
    return {
        "width": w, "height": h, "fps": fps, "frames": frames, "engine": q["engine"], "samples": q["samples"],
        "style": spec["style"], "set": scene["set"], "variant": scene["variant"], "time": scene["time"],
        "lighting": "sombre" if spec["style"] == "mystere" and scene["lighting"] == "normal" else scene["lighting"],
        "seed": scene["seed"], "expressiveness": scene["expressiveness"], "anim_speed": scene["anim_speed"],
        "action": scene["action"], "camera": scene["camera"], "characters": cast,
        "lines": [{k: ln[k] for k in ("who", "start", "end", "emotion")} for ln in timing["lines"]],
        "mouth": audio.mouth_tracks(timing, fps, [c["id"] for c in cast]),
        "duration": timing["duration"],
    }


def portrait_input(char, w=400, h=500):
    return {"width": w, "height": h, "fps": 12, "frames": 1, "engine": "eevee", "samples": 16, "style": "cartoon3d",
            "set": "studio", "variant": 0, "time": "jour", "lighting": "lumineux", "seed": 1, "expressiveness": 1.0,
            "anim_speed": 1.0, "action": "parler", "camera": {"move": "static", "shot": "gros_plan", "speed": 1.0},
            "characters": [char], "lines": [{"who": char["id"], "start": 0, "end": .01, "emotion": "joie"}],
            "mouth": {char["id"]: [0.0]}, "duration": .1}


def plan(spec: dict, settings: dict, data_dir: Path, eng: dict | None = None) -> dict:
    """Calcule, sans rien produire, ce qui sera réutilisé ou recalculé."""
    eng = eng or engines(settings, data_dir)
    cache = data_dir / "cache"
    chars = {c["id"]: c for c in spec["characters"]}
    tsig = audio.tts_signature(eng["tts"], eng["voice_dir"])
    out = []
    for sc in spec["scenes"]:
        ak = audio_key(sc, chars, tsig)
        vk = visual_key(sc, spec, chars, ak, eng["renderer_sig"])
        out.append({"n": sc["n"], "id": sc["id"], "audio_key": ak, "visual_key": vk,
                    "audio_cached": (cache / "audio" / ak / "timing.json").exists(),
                    "visual_cached": (cache / "visual" / vk / "clip.mp4").exists()})
    return {"scenes": out, "renderer": eng["renderer"], "tts": eng["tts"]}


def produce(spec: dict, version_dir: Path, story_dir: Path, settings: dict, data_dir: Path, rep: Reporter) -> dict:
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    eng = engines(settings, data_dir)
    rep.log(f"Moteur de rendu : {eng['renderer']}" + (f" ({eng['blender_version']})" if eng["blender_version"] else "") + f" · voix : {eng['tts']}")
    q = QUALITIES[spec["quality"]]
    w, h = frame_size(spec["format"], spec["quality"])
    chars = {c["id"]: c for c in spec["characters"]}
    cache = data_dir / "cache"
    started = time.time()

    # ------------------------------------------------------------ personnages (références visuelles)
    _check(rep)
    refs = story_dir / "references"
    refs.mkdir(parents=True, exist_ok=True)
    todo = []
    for c in spec["characters"]:
        p = refs / f"{c['id']}_{stable_hash(c['look'])}.png"
        if not p.exists():
            todo.append((c, p))
    rep.stage("personnages", "running", 0, len(spec["characters"]), "personnages",
              f"{len(spec['characters']) - len(todo)} déjà connus, {len(todo)} à créer")
    for i, (c, p) in enumerate(todo):
        _check(rep)
        work = cache / "tmp" / f"portrait_{c['id']}_{int(time.time() * 1000)}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            render.render_frames(portrait_input(c), work, eng["renderer"], eng["blender_path"], lambda n: None, rep.cancelled, rep.log)
            shutil.copy(work / "frames" / "f_0001.png", p)
        except InterruptedError as ex:
            raise Cancelled() from ex
        finally:
            shutil.rmtree(work, ignore_errors=True)
        rep.stage("personnages", "running", len(spec["characters"]) - len(todo) + i + 1, len(spec["characters"]), "personnages")
    rep.stage("personnages", "done", len(spec["characters"]), len(spec["characters"]), "personnages")

    # ------------------------------------------------------------ scènes (plan + empreintes)
    pl = plan(spec, settings, data_dir, eng)
    n = len(pl["scenes"])
    rep.stage("scenes", "done", n, n, "scènes",
              f"{sum(not s['visual_cached'] for s in pl['scenes'])} à produire, {sum(s['visual_cached'] for s in pl['scenes'])} réutilisée(s)")
    (version_dir / "plan.json").write_text(json.dumps(pl, indent=1))

    # ------------------------------------------------------------ audio
    need_audio = [(sc, s) for sc, s in zip(spec["scenes"], pl["scenes"]) if not s["audio_cached"]]
    rep.stage("audio", "running", 0, len(need_audio), "scènes", f"voix : {eng['tts']} · {n - len(need_audio)} réutilisée(s)")
    timings = {}
    for i, (sc, s) in enumerate(need_audio):
        _check(rep)
        d = cache / "audio" / s["audio_key"]
        tmp = d.with_name(d.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        audio.build_scene_audio(sc, chars, eng["tts"], eng["voice_dir"], tmp)
        shutil.rmtree(d, ignore_errors=True)
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(d)
        rep.stage("audio", "running", i + 1, len(need_audio), "scènes")
    for s in pl["scenes"]:
        timings[s["id"]] = json.loads((cache / "audio" / s["audio_key"] / "timing.json").read_text()) \
            if (cache / "audio" / s["audio_key"] / "timing.json").exists() else None
    rep.stage("audio", "done", len(need_audio), len(need_audio), "scènes")

    # ------------------------------------------------------------ animation
    need_vis = [(sc, s) for sc, s in zip(spec["scenes"], pl["scenes"]) if not s["visual_cached"]]
    for sc, s in need_vis:
        if timings[s["id"]] is None:  # audio absent du cache alors que l'image l'est plus → recalcul
            d = cache / "audio" / s["audio_key"]
            audio.build_scene_audio(sc, chars, eng["tts"], eng["voice_dir"], d)
            timings[s["id"]] = json.loads((d / "timing.json").read_text())
    total_frames = sum(int(round(timings[s["id"]]["duration"] * q["fps"])) for _, s in need_vis)
    done_before = 0
    t0 = time.time()
    used_engine = None
    rep.stage("animation", "running", 0, total_frames, "images",
              f"{len(need_vis)} scène(s) à animer, {n - len(need_vis)} réutilisée(s)")
    for sc, s in need_vis:
        _check(rep)
        ri = render_input(spec, sc, chars, timings[s["id"]], w, h, q)
        d = cache / "visual" / s["visual_key"]
        work = cache / "tmp" / s["visual_key"]
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        if settings.get("keep_blend", True) and eng["renderer"] == "blender":
            ri["blend_out"] = str(work / "scene.blend")

        def prog(k, base=done_before):
            done = base + k
            el = time.time() - t0
            eta = (total_frames - done) * el / done if done > 0 else None
            rep.stage("animation", "running", done, total_frames, "images", f"scène {sc['n']}", eta)

        try:
            used_engine = render.render_frames(ri, work, eng["renderer"], eng["blender_path"], prog, rep.cancelled, rep.log)
        except InterruptedError as ex:
            raise Cancelled() from ex
        render.encode_clip(work / "frames", cache / "audio" / s["audio_key"] / "audio.wav", q["fps"], ri["frames"] / q["fps"], work / "clip.mp4")
        shutil.rmtree(work / "frames", ignore_errors=True)
        (work / "meta.json").write_text(json.dumps({"scene": sc["n"], "engine": used_engine, "frames": ri["frames"]}))
        shutil.rmtree(d, ignore_errors=True)
        d.parent.mkdir(parents=True, exist_ok=True)
        work.rename(d)
        done_before += ri["frames"]
    rep.stage("animation", "done", total_frames, total_frames, "images", f"moteur : {used_engine or 'cache'}")

    # ------------------------------------------------------------ montage
    _check(rep)
    clips = [cache / "visual" / s["visual_key"] / "clip.mp4" for s in pl["scenes"]]
    durs = [montage.duration_of(c) for c in clips]
    total = sum(durs)
    cues, t = [], 0.0
    for s, dd in zip(pl["scenes"], durs):
        tm = timings[s["id"]] or json.loads((cache / "audio" / s["audio_key"] / "timing.json").read_text())
        for ln in tm["lines"]:
            cues.append({"who": ln["who"], "text": ln["text"], "start": t + ln["start"], "end": t + ln["end"]})
        t += dd
    names = {c["id"]: c["name"] for c in spec["characters"]}
    montage.write_subtitles(cues, names, w, h, version_dir / "subs.ass", version_dir / "sous-titres.srt")
    music = _pick_music(data_dir, spec) if settings.get("music", True) else None
    rep.stage("montage", "running", 0, 100, "%", f"{n} scène(s), {total:.1f} s" + (f", musique : {music.name}" if music else ""))
    master = version_dir / "master.mp4"
    montage.montage(clips, master, w, h, version_dir / "subs.ass" if spec.get("subtitles", True) else None, music, total,
                    lambda p: rep.stage("montage", "running", int(p * 100), 100, "%"), rep.cancelled)
    rep.stage("montage", "done", 100, 100, "%")

    # ------------------------------------------------------------ contrôle qualité
    _check(rep)
    rep.stage("controle", "running", 0, 1, "contrôle")
    qc = montage.quality_control(master, {"width": w, "height": h, "duration": total}, eng["tts"] != "silence")
    (version_dir / "qc.json").write_text(json.dumps(qc, ensure_ascii=False, indent=1))
    warn = [c for c in qc["checks"] if not c["ok"]]
    rep.stage("controle", "done" if qc["ok"] else "error", 1, 1, "contrôle",
              "tous les contrôles sont passés" if not warn else "; ".join(f"{c['name']} : {c['detail']}" for c in warn))
    if not qc["ok"]:
        raise RuntimeError("Le contrôle qualité a échoué : " + "; ".join(f"{c['name']} ({c['detail']})" for c in warn if c["level"] == "erreur"))

    # ------------------------------------------------------------ rendu final
    _check(rep)
    final = version_dir / "video.mp4"
    rep.stage("final", "running", 0, 100, "%")
    montage.final_encode(master, final, total, lambda p: rep.stage("final", "running", int(p * 100), 100, "%"), rep.cancelled)
    montage.thumbnail(final, version_dir / "miniature.jpg", min(total / 2, durs[0] * .6 if durs else 1))
    master.unlink(missing_ok=True)
    rep.stage("final", "done", 100, 100, "%", f"{final.stat().st_size / 1e6:.1f} Mo")
    return {
        "video": "video.mp4", "thumbnail": "miniature.jpg", "srt": "sous-titres.srt", "duration": round(total, 2),
        "width": w, "height": h, "qc": qc, "renderer": used_engine or eng["renderer"], "tts": eng["tts"],
        "scenes_rendered": [sc["n"] for sc, _ in need_vis], "scenes_reused": [s["n"] for s in pl["scenes"] if s["visual_cached"]],
        "scene_keys": {s["id"]: s["visual_key"] for s in pl["scenes"]},
        "elapsed": round(time.time() - started, 1),
    }


def _pick_music(data_dir: Path, spec: dict):
    d = data_dir / "musique"
    if not d.exists():
        return None
    files = sorted(p for p in d.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".flac"))
    for p in files:
        if p.stem.lower() in (spec["genre"], spec["style"]):
            return p
    return files[0] if files else None
