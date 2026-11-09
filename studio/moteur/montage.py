"""Montage, contrôle qualité, rendu final et exports (FFmpeg)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .spec import FORMATS


def ffprobe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    return json.loads(out)


def duration_of(path: Path) -> float:
    return float(ffprobe(path)["format"]["duration"])


def run_ffmpeg(args: list[str], total: float, progress=None, cancel=None, cwd=None) -> None:
    """Lance ffmpeg et remonte la progression réelle (temps encodé / durée totale)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-progress", "pipe:1", "-nostats"] + args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    for line in p.stdout:
        if cancel and cancel():
            p.kill()
            raise InterruptedError("annulé")
        m = re.match(r"out_time_us=(\d+)", line) or re.match(r"out_time_ms=(\d+)", line)
        if m and progress and total > 0:
            progress(min(1.0, int(m.group(1)) / 1e6 / total))
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError("FFmpeg : " + err[-1200:])
    if progress:
        progress(1.0)


def _ts(t: float, sep=".") -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    if sep == ",":
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_subtitles(cues: list[dict], names: dict, w: int, h: int, ass_path: Path, srt_path: Path) -> None:
    fs = max(14, int(min(w, h) * .055))
    margin = int(h * (.16 if h > w else .07))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fs},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,{max(2, fs // 9)},0,2,{int(w * .07)},{int(w * .07)},{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev, srt = [], []
    for i, c in enumerate(cues, 1):
        txt = c["text"].replace("\n", " ").replace("{", "(").replace("}", ")")
        who = names.get(c["who"], "")
        ev.append(f"Dialogue: 0,{_ts(c['start'])},{_ts(c['end'] + .25)},Default,,0,0,0,,{{\\c&H7FD8FF&}}{who} : {{\\c&HFFFFFF&}}{txt}")
        srt.append(f"{i}\n{_ts(c['start'], ',')} --> {_ts(c['end'] + .25, ',')}\n{who} : {txt}\n")
    ass_path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt), encoding="utf-8")


def montage(clips: list[Path], out: Path, w: int, h: int, subs_ass: Path | None, music: Path | None, total: float,
            progress=None, cancel=None) -> None:
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips), encoding="utf-8")
    vf = f"scale={w}:{h}:flags=lanczos,setsar=1"
    if subs_ass:
        vf += f",ass={subs_ass.name}"
    args = ["-f", "concat", "-safe", "0", "-i", str(lst.resolve())]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music.resolve())]
        af = ("[1:a]volume=0.22,aformat=channel_layouts=stereo[m];[0:a]asplit=2[v][sc];"
              "[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];[v][duck]amix=inputs=2:duration=first:normalize=0[a]")
        args += ["-filter_complex", af, "-map", "0:v", "-map", "[a]"]
    args += ["-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", str(out.resolve())]
    run_ffmpeg(args, total, progress, cancel, cwd=str(subs_ass.parent) if subs_ass else None)


def quality_control(path: Path, expected: dict, voices_expected: bool) -> dict:
    """Contrôles objectifs. Retourne {"ok", "checks": [{name, ok, detail, level}]}"""
    checks = []

    def add(name, ok, detail, level="erreur"):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "level": level})

    if not path.exists() or path.stat().st_size < 1000:
        add("Fichier vidéo", False, "fichier absent ou vide")
        return {"ok": False, "checks": checks}
    info = ffprobe(path)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    add("Piste vidéo", bool(v), v[0]["codec_name"] if v else "absente")
    add("Piste audio", bool(a), a[0]["codec_name"] if a else "absente")
    if v:
        add("Résolution", (int(v[0]["width"]), int(v[0]["height"])) == (expected["width"], expected["height"]),
            f"{v[0]['width']}×{v[0]['height']} (attendu {expected['width']}×{expected['height']})")
    dur = float(info["format"]["duration"])
    add("Durée", abs(dur - expected["duration"]) < .6, f"{dur:.2f} s (attendu {expected['duration']:.2f} s)")
    # passages noirs
    res = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "blackdetect=d=1.0:pix_th=0.06", "-an", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", res.stderr)
    add("Écrans noirs", not blacks, "aucun" if not blacks else f"{len(blacks)} passage(s) noir(s) > 1 s", "avertissement")
    # niveau audio
    res = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"max_volume: (-?[\d.]+) dB", res.stderr)
    mx = float(m.group(1)) if m else -91.0
    if voices_expected:
        add("Voix audibles", mx > -40, f"crête {mx:.1f} dB", "avertissement")
        add("Saturation audio", mx < -.05, f"crête {mx:.1f} dB", "avertissement")
    ok = all(c["ok"] for c in checks if c["level"] == "erreur")
    return {"ok": ok, "checks": checks, "duration": dur}


def final_encode(master: Path, out: Path, total: float, progress=None, cancel=None) -> None:
    run_ffmpeg(["-i", str(master), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(out)],
               total, progress, cancel)


def thumbnail(video: Path, out: Path, at: float) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)],
                   check=True, capture_output=True)


def export_format(src: Path, out: Path, fmt: str, method: str, short: int, progress=None, cancel=None) -> None:
    """Recadrage rapide vers un autre format. method = "flou" (fond flouté) ou "recadrage" (remplit l'image)."""
    a, b = FORMATS[fmt]
    if a == b:
        w = h = short
    elif a < b:
        w, h = short, round(short * b / a)
    else:
        w, h = round(short * a / b), short
    w, h = w - w % 2, h - h % 2
    if method == "recadrage":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
        args = ["-i", str(src), "-vf", vf]
    else:
        fc = (f"[0:v]split=2[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,eq=brightness=-0.08[bg];"
              f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
        args = ["-i", str(src), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             "-c:a", "aac", "-b:a", "160k", str(out)]
    run_ffmpeg(args, duration_of(src), progress, cancel)
