"""Petitbourg episode renderer — data driven.

usage: python engine/render.py episodes/jour_N.json out_dir [--dry] [--preview t1,t2,...]
"""
import sys, os, json, math, re, base64, subprocess, random
sys.path.insert(0, os.path.dirname(__file__))
import base as B
from base import *  # noqa
from PIL import Image, ImageDraw, ImageChops
import buildings as BL

ROOT = os.path.join(os.path.dirname(__file__), "..")
AV_DIR = os.path.join(ROOT, "assets", "avatars")
DEFAULT_VOICE = "TX3LPaxmHKxFdv7VOQHJ"   # "Liam" — voice of Jour 1 & 2

COLORS = {"green": (60, 170, 50), "blue": (40, 90, 160), "red": RED, "white": WHITE, "olive": (80, 100, 50),
          "navy": (30, 40, 90), "brown": (150, 90, 50), "black": BLACK, "orange": (230, 120, 30)}
def col(c, default=(60, 170, 50)):
    if c is None: return default
    if isinstance(c, (list, tuple)): return tuple(c)
    return COLORS.get(c, default)

# ------------------------------------------------------------------ TTS
def tts(text, voice, out_mp3, dry=False):
    """returns (duration, char_start_times)"""
    if dry:
        dur = len(text) / 15.0 + 1.0
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono", "-t", str(dur), out_mp3], check=True)
        return dur, [0.3 + i / 15.0 for i in range(len(text))]
    import urllib.request
    key = os.environ["ELEVENLABS_API_KEY"]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                         "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.loads(r.read())
    open(out_mp3, "wb").write(base64.b64decode(j["audio_base64"]))
    al = j["alignment"]
    starts = al["character_start_times_seconds"]
    if len(starts) != len(text):  # be robust: map by proportion
        starts = [starts[min(len(starts) - 1, int(i * len(starts) / len(text)))] for i in range(len(text))]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out_mp3],
                               capture_output=True, text=True).stdout.strip())
    return dur, starts

# ------------------------------------------------------------------ captions
def norm(w): return re.sub(r"[^\wÀ-ÿ'’]", "", w.lower())

def build_captions(text, starts, dur, highlight):
    hl = {norm(h) for h in highlight}
    words = [(m.start(), m.group()) for m in re.finditer(r"\S+", text)]
    chunks, cur = [], []
    for i, (pos, w) in enumerate(words):
        cur.append((pos, w))
        clen = sum(len(x[1]) + 1 for x in cur)
        end_punct = re.search(r"[.!?:…,]$", w)
        if len(cur) >= 4 or clen > 20 or end_punct:
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    caps = []
    for k, ch in enumerate(chunks):
        a = starts[ch[0][0]]
        b = starts[chunks[k + 1][0][0]] if k + 1 < len(chunks) else dur
        txt = " ".join((f"[{w.upper()}]" if norm(w) in hl else w.upper()) for _, w in ch)
        caps.append((a, b, txt))
    return caps

# ------------------------------------------------------------------ assets
def av_img(user, size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    p = os.path.join(AV_DIR, f"{user}.png")
    if os.path.exists(p):
        a = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS); im.paste(a, (0, 0), m)
    else:
        cols = [(90, 120, 200), (200, 120, 80), (120, 170, 90), (170, 90, 160), (80, 160, 170)]
        d.ellipse([0, 0, size - 1, size - 1], fill=cols[sum(map(ord, user)) % len(cols)])
        d.text((size / 2, size / 2), user[0].upper(), font=font(int(size * .5)), fill=WHITE, anchor="mm")
    return im

def ccard(user, text, likes, top=False, w=860):
    text = "".join(ch for ch in text if ord(ch) < 0x2000 or ch in "’…").strip()
    f = font(40); lines = []; cur = ""
    for wd in text.split():
        t = (cur + " " + wd).strip()
        if f.getbbox(t)[2] > w - 200 and cur: lines.append(cur); cur = wd
        else: cur = t
    lines.append(cur)
    h = 150 + 52 * len(lines)
    im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([12, 14, w + 12, h + 14], 30, fill=(0, 0, 0, 80))
    d.rounded_rectangle([0, 0, w, h], 30, fill=WHITE, outline=(210, 210, 220), width=3)
    im.alpha_composite(av_img(user, 96), (30, 30))
    d.text((145, 58), user, font=font(32), fill=(120, 120, 130), anchor="lm")
    if top:
        x0 = 160 + font(32).getbbox(user)[2]
        d.rounded_rectangle([x0, 38, x0 + 250, 80], 12, fill=(254, 44, 85))
        d.text((x0 + 125, 59), "Top commentaire", font=font(24), fill=WHITE, anchor="mm")
    for i, l in enumerate(lines):
        d.text((145, 112 + i * 52), l, font=f, fill=BLACK, anchor="lm")
    hx, hy = w - 60, 70
    d.ellipse([hx - 22, hy - 16, hx, hy + 6], fill=(254, 44, 85)); d.ellipse([hx - 2, hy - 16, hx + 20, hy + 6], fill=(254, 44, 85))
    d.polygon([(hx - 21, hy), (hx + 19, hy), (hx - 1, hy + 24)], fill=(254, 44, 85))
    d.text((hx - 1, hy + 50), str(likes), font=font(28), fill=(120, 120, 130), anchor="mm")
    return im

def chapel(d, x, y, s=1.0):
    w, h = 180 * s, 170 * s
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=(240, 236, 226), outline=OUTL, width=6)
    d.polygon([(x - w / 2 - 20 * s, y - h), (x + w / 2 + 20 * s, y - h), (x, y - h - 120 * s)], fill=(110, 60, 50), outline=OUTL, width=6)
    d.rectangle([x - 6 * s, y - h - 210 * s, x + 6 * s, y - h - 110 * s], fill=(240, 200, 60), outline=OUTL, width=3)
    d.rectangle([x - 34 * s, y - h - 180 * s, x + 34 * s, y - h - 168 * s], fill=(240, 200, 60), outline=OUTL, width=3)
    d.rounded_rectangle([x - 28 * s, y - 90 * s, x + 28 * s, y], 20, fill=(110, 66, 40), outline=OUTL, width=5)
    d.ellipse([x - 26 * s, y - h + 20 * s, x + 26 * s, y - h + 72 * s], fill=(120, 170, 230), outline=OUTL, width=5)

def shop(d, x, y, s, label, wall=(225, 205, 170), roof=(120, 60, 50), sign=(250, 240, 220), signtext=(40, 30, 30)):
    w, h = 360 * s, 260 * s
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=wall, outline=OUTL, width=8)
    d.polygon([(x - w / 2 - 30 * s, y - h), (x + w / 2 + 30 * s, y - h), (x + w / 2, y - h - 90 * s), (x - w / 2, y - h - 90 * s)], fill=roof, outline=OUTL, width=8)
    d.rounded_rectangle([x - w / 2 + 20 * s, y - h - 70 * s, x + w / 2 - 20 * s, y - h - 10 * s], 10, fill=sign, outline=OUTL, width=5)
    fs = int(46 * s)
    while font(fs).getbbox(label)[2] > w - 60 * s and fs > 12: fs -= 2
    d.text((x, y - h - 40 * s), label, font=font(fs), fill=signtext, anchor="mm")
    d.rectangle([x - 40 * s, y - 130 * s, x + 40 * s, y], fill=(110, 66, 40), outline=OUTL, width=6)
    for wx in (-w / 3, w / 3):
        d.rectangle([x + wx - 45 * s, y - 200 * s, x + wx + 45 * s, y - 120 * s], fill=(255, 214, 110), outline=OUTL, width=6)

def lot_sign(d, x, y, l1, l2):
    d.rectangle([x - 8, y - 260, x + 8, y], fill=(110, 70, 40))
    d.rounded_rectangle([x - 200, y - 330, x + 200, y - 220], 14, fill=WHITE, outline=OUTL, width=6)
    d.text((x, y - 295), l1, font=font(36), fill=OUTL, anchor="mm")
    fs = 36
    while font(fs).getbbox(l2)[2] > 380: fs -= 2
    d.text((x, y - 252), l2, font=font(fs), fill=(30, 40, 120), anchor="mm")

def coin(d, x, y, r=26):
    d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 200, 40), outline=(150, 100, 20), width=4)
    d.text((x, y), "€", font=font(int(r * 1.1)), fill=(150, 100, 20), anchor="mm")


def daysky(d, w, h, top=(105, 175, 240), bot=(205, 232, 250), hz=900):
    for y in range(hz):
        k = y / hz
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    d.ellipse([w - 520, 160, w - 240, 440], fill=(255, 236, 140))

CLOUDS = [(random.Random(i).uniform(0, 1400), random.Random(i + 9).uniform(80, 520), random.Random(i + 3).uniform(.7, 1.3)) for i in range(5)]
def clouds(fr, t):
    d = ImageDraw.Draw(fr)
    for x0, y, s in CLOUDS:
        x = (x0 + t * 25 * s) % 1500 - 200
        for dx, dy, r in ((0, 0, 60), (55, -25, 70), (115, 0, 58), (60, 15, 60)):
            d.ellipse([x + dx * s - r * s, y + dy * s - r * s, x + dx * s + r * s, y + dy * s + r * s], fill=(255, 255, 255))

def envelope(d, x, y, a=0):
    d.rectangle([x - 50, y - 32, x + 50, y + 32], fill=WHITE, outline=OUTL, width=4)
    d.line([(x - 50, y - 32), (x, y + 5), (x + 50, y - 32)], fill=OUTL, width=4)

def confetti(fr, t, t0):
    if t < t0 or t > t0 + 2.2: return
    d = ImageDraw.Draw(fr); r = random.Random(7); cols = [(250, 80, 80), (80, 200, 90), (250, 210, 60), (80, 150, 250), (230, 120, 220)]
    for i in range(70):
        x0 = r.uniform(0, W); v = r.uniform(500, 900); y = -40 + (t - t0) * v + r.uniform(-200, 0)
        x = x0 + math.sin((t - t0) * 6 + i) * 30
        d.rectangle([x, y, x + 16, y + 26], fill=cols[i % 5])

NEWT = ("custom", "mosque", "house")
LCACHE = {}
def layers(sc):
    b = sc["build"]; key = json.dumps(b, sort_keys=True)
    if key in LCACHE: return LCACHE[key]
    w, h = W * 2, H * 2
    base = BL.scenery(w, h); BL.road_strip(base, 3300, h)
    full = base.copy()
    if b["type"] == "house":
        styles = ["maison"]; opts = [{"roof": col(b.get("roof"), (170, 60, 46))}]
    else:
        styles = b.get("styles") or [b.get("style", "mosquee" if b["type"] == "mosque" else "maison")]
        opts = b.get("opts") or [{} for _ in styles]
    n = len(styles)
    xs = [1080] if n == 1 else [int(w * (i + .5) / n) for i in range(n)]
    tgt = 1700 if n == 1 else int(w / n * 1.12)
    for st, x, o in zip(styles, xs, opts): BL.draw_style(full, st, x, 2700, tgt, **o)
    base = base.resize((W, H), Image.LANCZOS).convert("RGBA"); full = full.resize((W, H), Image.LANCZOS).convert("RGBA")
    bb = ImageChops.difference(base.convert("RGB"), full.convert("RGB")).getbbox() or (0, 0, W, H)
    LCACHE[key] = (base, full, bb); return LCACHE[key]

def scene_bg(sc, t, a):
    b = sc.get("build") or {}
    if b.get("type") not in NEWT: return background(sc).copy()
    base, full, bb = layers(sc)
    p = ease((t - a - .3) / b.get("dur", 2.6)) if b.get("anim", True) else 1
    if p >= 1:
        fr = full.copy()
        dt = t - a - .3 - b.get("dur", 2.6)
        if 0 < dt < .5:  # petit rebond final
            k = 1 + .02 * math.sin(dt / .5 * math.pi); cx = (bb[0] + bb[2]) // 2
            sub = full.crop(bb); sub = sub.resize((int(sub.width * k), int(sub.height * k)))
            fr = base.copy(); fr.alpha_composite(sub, (cx - sub.width // 2, bb[3] - sub.height))
        return fr
    fr = base.copy(); cut = int(bb[3] - (bb[3] - bb[1]) * p)
    if cut < bb[3]: fr.alpha_composite(full.crop((0, cut, W, bb[3])), (0, cut))
    d = ImageDraw.Draw(fr, "RGBA")
    for x in range(bb[0], bb[2] + 1, 70):   # échafaudage
        d.line([(x, cut - 40), (x, bb[3])], fill=(150, 110, 60, 230), width=7)
    for y in range(bb[3], cut - 40, -90):
        d.line([(bb[0], y), (bb[2], y)], fill=(150, 110, 60, 230), width=7)
    r = random.Random(int(t * 12))
    for _ in range(14):  # poussière
        x = r.uniform(bb[0], bb[2]); y = bb[3] - r.uniform(0, 60); rr = r.uniform(18, 46)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(235, 225, 205, 150))
    return fr

BGCACHE = {}
CLEAR = True
def background(sc):
    """sc['bg'] = base kind or dict {kind, build}"""
    kind = sc.get("bg", "road"); build = sc.get("build")
    key = json.dumps([kind, build], sort_keys=True)
    if key in BGCACHE: return BGCACHE[key]
    if build is None and kind in ("wide", "road", "schild", "well", "grid", "rathaus", "kasse", "night"):
        im = bg(kind)
    else:
        w, h = W * 2, H * 2
        im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
        sky(d, w, h, hz=1900); church(d, 1700, 1500, 1.2)
        trees(d, 1600, 1.6, seed=2, w=w); trees(d, 1700, 2.0, col=(26, 52, 34), seed=5, w=w)
        grass(d, 1650, w, h); road(d, 2700, 3300, w)
        b = build or {}
        t = b.get("type")
        if kind == "houses" and not t:
            for i, x in enumerate([260, 1080, 1900]):
                house(d, x, 2560, 2.7, roof=[(150, 52, 40), (60, 110, 160), (140, 80, 40)][i], lit=True)
        if t == "chapel": chapel(d, b.get("x", 1080), 2700, 4.6)
        elif t == "house": house(d, b.get("x", 1080), 2700, 4.2, roof=col(b.get("roof"), (60, 110, 160)), lit=True)
        elif t == "shop": shop(d, b.get("x", 1080), 2700, 3.8, b.get("label", ""), roof=col(b.get("roof"), (120, 60, 50)))
        elif t == "desk":
            d.rectangle([0, 0, w, h], fill=(236, 220, 190))
            d.rectangle([0, 2600, w, h], fill=(170, 120, 80))
            d.rectangle([300, 500, 1000, 1300], fill=(150, 210, 250), outline=OUTL, width=14)
            d.line([(650, 500), (650, 1300)], fill=OUTL, width=12); d.line([(300, 900), (1000, 900)], fill=OUTL, width=12)
            d.rounded_rectangle([1250, 600, 1900, 1100], 20, fill=(60, 120, 60), outline=OUTL, width=12)
            d.text((1575, 850), "MAIRIE", font=font(110), fill=WHITE, anchor="mm")
            d.rectangle([200, 2350, 1960, 2520], fill=(140, 90, 50), outline=OUTL, width=12)
            d.rectangle([260, 2520, 340, 3000], fill=(120, 75, 40), outline=OUTL, width=10); d.rectangle([1820, 2520, 1900, 3000], fill=(120, 75, 40), outline=OUTL, width=10)
            for i in range(6): d.rectangle([1300 + i * 12, 2200 - i * 30, 1700 + i * 12, 2350 - i * 30], fill=WHITE, outline=OUTL, width=5)
        elif t == "lot":
            d.rectangle([1250, 2250, 2000, 2650], fill=(120, 90, 60))
            for i in range(10): d.line([(1250 + i * 75, 2250), (1250 + i * 75, 2650)], fill=(150, 120, 80), width=6)
        im = im.resize((W, H), Image.LANCZOS)
        if b.get("type") == "lot":
            lot_sign(ImageDraw.Draw(im), 810, 1300, b.get("l1", "FUTUR"), b.get("l2", "?"))
    BGCACHE[key] = im.convert("RGBA")
    return BGCACHE[key]

def mkbadge(spec):
    if isinstance(spec, str): spec = {"text": spec}
    lines = spec["text"] if isinstance(spec["text"], list) else [spec["text"]]
    c = spec.get("color", "green")
    fill = col(c); tc = BLACK if c == "white" else WHITE
    border = OUTL if c == "white" else WHITE
    return badge_img(lines, fill=fill, tc=tc, size=spec.get("size", 56), pad=22, border=border,
                     sub=spec.get("sub"), subfill=(RED if c == "white" else (230, 240, 230)), rot=spec.get("rot", -3))

ICONS = {"beer": icon_beer, "church": icon_church, "?": "?"}

# ------------------------------------------------------------------ main
def main():
    ep_path, out_dir = sys.argv[1], sys.argv[2]
    dry = "--dry" in sys.argv
    preview = None
    if "--preview" in sys.argv: preview = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")]
    ep = json.load(open(ep_path))
    global CLEAR
    CLEAR = ep.get("weather", "clear") != "rain"
    if CLEAR:
        B.sky = daysky; globals()["sky"] = daysky
    os.makedirs(out_dir, exist_ok=True)
    for k, v in ep.get("characters", {}).items():
        CH[k] = {kk: (tuple(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()}
    out_name = ep.get("out_name") or f"petitbourg_jour{ep['day']}"

    # script text + line offsets
    scenes = ep["scenes"]; parts = []; offs = []; pos = 0
    for si, sc in enumerate(scenes):
        sc["_lines"] = []
        for ln in sc["lines"]:
            offs.append(pos); sc["_lines"].append(len(offs) - 1)
            parts.append(ln); pos += len(ln) + 1
    text = " ".join(parts)
    mp3 = os.path.join(out_dir, "voice.mp3")
    cache = os.path.join(ROOT, "episodes", "voice_cache", out_name)
    if not dry and os.path.exists(cache + ".json") and json.load(open(cache + ".json"))["text"] == text:
        import shutil; shutil.copy(cache + ".mp3", mp3); dur, starts = json.load(open(cache + ".json"))["timing"]
    else:
        dur, starts = tts(text, ep.get("voice_id", DEFAULT_VOICE), mp3, dry=dry)
        if not dry:
            os.makedirs(os.path.dirname(cache), exist_ok=True); import shutil; shutil.copy(mp3, cache + ".mp3")
            json.dump({"text": text, "timing": [dur, starts]}, open(cache + ".json", "w"))
    line_t = [starts[o] for o in offs]
    DUR = dur + 0.7
    for si, sc in enumerate(scenes):
        sc["_t"] = 0.0 if si == 0 else max(0.0, line_t[sc["_lines"][0]] - 0.15)
        sc["_lt"] = [line_t[i] for i in sc["_lines"]]
    for si, sc in enumerate(scenes):
        sc["_end"] = scenes[si + 1]["_t"] if si + 1 < len(scenes) else DUR
    caps = build_captions(text, starts, DUR, ep.get("highlight", []))

    def at(sc, idx):  # time of line idx within scene
        idx = max(0, min(idx, len(sc["_lt"]) - 1)); return sc["_lt"][idx]

    def place_char(fr, c, i, t, sc):
        x, y, s = c.get("x", 540), c.get("y", 1520), c.get("scale", .9)
        ang = 0
        if c.get("enter"):
            t_in = at(sc, c.get("enter_line", 0)); x0 = -260 if c["enter"] == "left" else W + 260
            k = ease((t - t_in) / .9)
            if k < 1:
                x = x0 + (x - x0) * k; y -= abs(math.sin(t * 11)) * 14 * s; ang = math.sin(t * 11) * 5
        if c.get("jump_line") is not None:
            dt = t - at(sc, c["jump_line"])
            if 0 < dt < .55: y -= math.sin(dt / .55 * math.pi) * 90 * s
        talk = c.get("talk", False)
        mouth = 1 if talk and int(t * 9 + i) % 2 == 0 else 0
        sp = sprite(c["kind"], mouth, round(s, 2))
        bob = math.sin(t * 3 + i) * 4 * s
        if talk and not ang: ang = math.sin(t * 2.3 + i) * 2.5
        if ang: sp = sp.rotate(ang, resample=Image.BICUBIC, expand=True)
        fr.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height + bob)))

    def draw_scene(sc, t):
        a = sc["_t"]; typ = sc.get("type", "place"); L = max(.5, sc["_end"] - a)
        fr = scene_bg(sc, t, a)
        if CLEAR and sc.get("build", {}).get("type") != "desk": clouds(fr, t); BL.birds(fr, t)
        if sc.get("letters"):
            d = ImageDraw.Draw(fr); r = random.Random(3)
            for k in range(14):
                yy = ((t - a) * r.uniform(250, 420) + r.uniform(-900, 0)) % 1500 - 100
                envelope(d, r.uniform(80, 1000) + math.sin(t * 2 + k) * 40, yy)
        for i, c in enumerate(sc.get("chars", [])): place_char(fr, c, i, t, sc)
        if sc.get("kasse"):
            k = kasse_img(); k = k.resize((k.width // 2, k.height // 2)); fr.alpha_composite(k, (640, 1180))
        if not CLEAR: rain(fr, t, 60 if sc.get("bg") == "night" else 110)
        # camera: slow pan + zoom + punch on badge2
        pan = sc.get("pan", [.45, .55] if CLEAR else [.5, .5]); pk = ease((t - a) / L)
        z = 1 + sc.get("zoom", 0.025) * pk
        if sc.get("badge2"):
            dt = t - at(sc, sc["badge2"].get("at_line", 1))
            if 0 < dt < .4: z += .05 * (1 - dt / .4)
        fr = zoom(fr, z, pan[0] + (pan[1] - pan[0]) * pk, .55)
        fr.alpha_composite(BL.vignette(W, H))
        d = ImageDraw.Draw(fr)
        if typ == "title":
            pop(fr, badge_img([sc.get("badge", f"JOUR {ep.get('day', '')}")], size=sc.get("badge_size", 150)), 540, 300, a + .05, t)
        elif sc.get("badge"):
            pop(fr, mkbadge(sc["badge"]), 540, sc.get("badge_y", 300), at(sc, sc.get("badge_at_line", 0)) + .1, t)
        if sc.get("counter"):
            cn = sc["counter"]; ta = at(sc, cn.get("at_line", 0))
            if t > ta:
                p = ease((t - ta) / 1.8); v = cn["from"] + (cn["to"] - cn["from"]) * p
                sz = int(230 * (1 + (.15 * math.sin(min(1, (t - ta - 1.8) / .3) * math.pi) if t - ta > 1.8 else 0)))
                text_stroke(d, (540, cn.get("y", 560)), f"{int(round(v))}", sz, col(cn.get("color"), GREEN), 14)
                text_stroke(d, (540, cn.get("y", 560) + 170), cn.get("suffix", ""), 70, WHITE, 8)
        if sc.get("comment"):
            c = sc["comment"]
            if "comment_until_line" not in sc or t < at(sc, sc["comment_until_line"]):
                pop(fr, ccard(c["user"], c["text"], c.get("likes", 0), c.get("top", False)), 540, sc.get("comment_y", 600 if typ == "title" else 330), at(sc, c.get("at_line", 0)) + .05, t)
        if sc.get("badge2"):
            b2 = sc["badge2"]
            pop(fr, mkbadge(b2), 540, b2.get("y", 620), at(sc, b2.get("at_line", 1)), t)
            if b2.get("confetti"): confetti(fr, t, at(sc, b2.get("at_line", 1)))
        if typ == "cards":
            cs = sc["cards"]; n = len(cs); t0 = at(sc, sc.get("cards_line", 0))
            step = min(270, 1050 // max(1, n))
            for i, c in enumerate(cs):
                im = ccard(c["user"], c["text"], c.get("likes", 0), w=760)
                if n > 4: im = im.resize((int(im.width * .85), int(im.height * .85)))
                pop(fr, im, 540, 270 + i * step, t0 + .1 + i * sc.get("card_gap", .7), t)
            if sc.get("end_badge"):
                pop(fr, mkbadge(sc["end_badge"]), 540, 1300, at(sc, sc.get("end_badge_line", len(sc["_lt"]) - 1)), t)
        if typ == "panel":
            d.rounded_rectangle([140, 300, 940, 1180], 30, fill=(250, 245, 230), outline=OUTL, width=8)
            names = [(f"• {n}" if sc.get("raw") else f"• @{n}") for n in sc.get("names", [])] + ([sc["extra"]] if sc.get("extra") else [])
            off = max(0, (t - a - .6) * sc.get("scroll", 75))
            lay = Image.new("RGBA", (800, 740), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
            for i, n in enumerate(names):
                yy = 40 + i * 64 - off
                if -60 < yy < 760: ld.text((60, yy), n, font=font(40), fill=OUTL)
            fr.alpha_composite(lay, (140, 425))
            d.rounded_rectangle([140, 300, 940, 420], 30, fill=(60, 170, 50), outline=OUTL, width=8)
            d.text((540, 360), sc.get("title", ""), font=font(56), fill=WHITE, anchor="mm")
        if sc.get("bars"):
            br = sc["bars"]; tb = at(sc, br.get("at_line", 0))
            if t > tb:
                kk = ease((t - tb) / 1.4)
                d.rounded_rectangle([90, 280, 990, 330 + 140 * len(br["items"])], 30, fill=(250, 245, 230), outline=OUTL, width=8)
                d.text((540, 330), br.get("title", "VOTE EN COURS"), font=font(50), fill=OUTL, anchor="mm")
                for i, (lab, v) in enumerate(br["items"]):
                    y0 = 400 + i * 140
                    d.text((130, y0), lab, font=font(40), fill=OUTL, anchor="lm")
                    d.rounded_rectangle([130, y0 + 30, 950, y0 + 80], 20, fill=(220, 215, 200))
                    d.rounded_rectangle([130, y0 + 30, 130 + max(40, 820 * v * kk), y0 + 80], 20, fill=[(40, 60, 140), (60, 170, 50), (230, 150, 40)][i % 3])
        if sc.get("amount"):
            am = sc["amount"]; ta = at(sc, am.get("at_line", 0))
            if t > ta:
                p = min(1, (t - ta) / 1.6); v = am.get("from", 0) + (am["to"] - am.get("from", 0)) * p
                text_stroke(d, (540, am.get("y", 560)), f"{int(round(v))} €", 160, col(am.get("color"), GREEN), 12)
                if am["to"] > am.get("from", 0):
                    for i in range(8): coin(d, 380 + i * 50, 680 + ((t * 600 + i * 120) % 300))
        if sc.get("stamp"):
            st = sc["stamp"]; ts_ = at(sc, st.get("at_line", 1))
            if t > ts_:
                k = min(1, (t - ts_) / .22); sc_ = 2.6 - 1.6 * k
                im = Image.new("RGBA", (620, 200), (0, 0, 0, 0)); sd = ImageDraw.Draw(im)
                c_ = col(st.get("color", "red"))
                sd.rounded_rectangle([10, 10, 610, 190], 24, outline=c_, width=16)
                sd.text((310, 100), st["text"], font=font(110), fill=c_, anchor="mm")
                im = im.resize((int(620 * sc_), int(200 * sc_))).rotate(-12, resample=Image.BICUBIC, expand=True)
                fr.alpha_composite(im, (int(540 - im.width / 2), int(st.get("y", 900) - im.height / 2)))
                if t - ts_ < .3:
                    fr = fr.transform(fr.size, Image.AFFINE, (1, 0, math.sin(t * 90) * 10, 0, 1, 0))
        if typ == "vote":
            opts = sc["options"]; tv = at(sc, sc.get("options_line", 1)); n = len(opts)
            xs = [230, 540, 850] if n == 3 else ([330, 750] if n == 2 else [540])
            for i, o in enumerate(opts):
                pop(fr, card(o["label"], fill=col(o.get("color", "white"), WHITE), tc=(BLACK if o.get("color", "white") == "white" else WHITE),
                             icon=ICONS.get(o.get("icon", "?"), "?"), rot=[4, -3, 5][i % 3]), xs[i], 410 + (i % 2) * -10, tv + i * .9, t)
            if sc.get("end_badge"):
                pop(fr, mkbadge(sc["end_badge"]), 540, 760, at(sc, len(sc["_lt"]) - 1), t)
        return fr

    def frame(t):
        cur = scenes[0]
        for sc in scenes:
            if t >= sc["_t"]: cur = sc
        fr = draw_scene(cur, t)
        for a, b, txt in caps: caption(fr, txt, t, a, b)
        for sc in scenes[1:]:
            if 0 <= t - sc["_t"] < .08:
                fr = Image.blend(fr, Image.new("RGBA", fr.size, (255, 255, 255, 255)), .25)
        return fr.convert("RGB")

    if preview:
        ims = [frame(t).resize((270, 480)) for t in preview]
        sh = Image.new("RGB", (270 * min(7, len(ims)), 480 * ((len(ims) + 6) // 7)))
        for i, im in enumerate(ims): sh.paste(im, ((i % 7) * 270, (i // 7) * 480))
        sh.save(os.path.join(out_dir, "preview.jpg"), quality=85); return

    vid = os.path.join(out_dir, "video_only.mp4")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    out = os.path.join(out_dir, f"{out_name}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", mp3, "-f", "lavfi", "-i",
                    (f"anoisesrc=color=pink:amplitude=0.25:d={DUR},lowpass=f=3500,highpass=f=300,volume=0.25" if not CLEAR else f"anullsrc=r=44100:cl=mono,atrim=0:{DUR}"),
                    "-filter_complex", f"[1:a]apad=whole_dur={DUR},volume=1.6[v];[v][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(DUR), out], check=True)
    open(os.path.join(out_dir, "description.txt"), "w").write(ep.get("description", "") + "\n\nCommentaire à épingler :\n" + ep.get("pinned_comment", "") + "\n")
    print("OK", out, round(DUR, 1), "s")

if __name__ == "__main__":
    main()
