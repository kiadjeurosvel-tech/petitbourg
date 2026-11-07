import math, random, subprocess, sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
import os
FONT = os.path.join(os.path.dirname(__file__), "..", "assets", "Poppins-Bold.ttf")

def F(size): return ImageFont.truetype(FONT, size)
fcache = {}
def font(s):
    if s not in fcache: fcache[s] = F(s)
    return fcache[s]

GREEN = (88, 214, 58); DKGREEN = (34, 120, 30); WHITE = (255, 255, 255); BLACK = (20, 20, 24)
RED = (235, 50, 50); OUTL = (25, 22, 28)

def ease_back(t):
    t = max(0, min(1, t)); c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
def ease(t):
    t = max(0, min(1, t)); return t * t * (3 - 2 * t)

# ---------------------------------------------------------------- backgrounds (drawn 2x, downsampled)
def sky(d, w, h, top=(38, 40, 70), bot=(84, 86, 120), hz=900):
    for y in range(hz):
        k = y / hz
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))

def trees(d, y, s, col=(30, 62, 40), seed=1, w=2160):
    r = random.Random(seed)
    x = -40
    while x < w + 40:
        rr = r.randint(55, 95) * s
        d.ellipse([x - rr, y - rr * 1.6, x + rr, y + rr * 0.2], fill=col)
        x += rr * 1.3

def church(d, x, y, s=1.0, col=(70, 72, 100)):
    d.rectangle([x - 40 * s, y - 260 * s, x + 40 * s, y], fill=col)
    d.polygon([(x - 50 * s, y - 260 * s), (x + 50 * s, y - 260 * s), (x, y - 420 * s)], fill=col)
    d.ellipse([x - 16 * s, y - 220 * s, x + 16 * s, y - 188 * s], fill=(240, 220, 150))

def grass(d, y0, w, h, seed=3, base=(62, 108, 48)):
    d.rectangle([0, y0, w, h], fill=base)
    r = random.Random(seed)
    for _ in range(260):
        x = r.randint(0, w); y = r.randint(y0 + 10, h)
        sz = 10 + (y - y0) / (h - y0) * 34
        d.polygon([(x - sz * .5, y), (x + sz * .5, y), (x, y - sz * 1.6)], fill=(40, 82, 36))
    for _ in range(40):
        x = r.randint(0, w); y = r.randint(y0 + 30, h); rr = r.randint(60, 160)
        d.ellipse([x - rr, y - rr * .25, x + rr, y + rr * .25], fill=(54, 96, 42))

def road(d, y0, y1, w, col=(150, 92, 60)):
    d.rectangle([0, y0, w, y1], fill=col)
    r = random.Random(7)
    for _ in range(90):
        x = r.randint(0, w); y = r.randint(y0, y1); rr = r.randint(4, 14)
        d.ellipse([x - rr, y - rr * .5, x + rr, y + rr * .5], fill=(128, 76, 50))
    for _ in range(6):  # puddles
        x = r.randint(100, w - 100); y = r.randint(y0 + 30, y1 - 30); rr = r.randint(70, 150)
        d.ellipse([x - rr, y - rr * .22, x + rr, y + rr * .22], fill=(120, 124, 160))

def house(d, x, y, s=1.0, wall=(222, 206, 170), roof=(150, 52, 40), lit=False, q=False, beams=True):
    w, h = 300 * s, 230 * s
    lw = max(3, int(6 * s))
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=wall, outline=OUTL, width=lw)
    if beams:
        for bx in (-w / 2 + w / 3, -w / 2 + 2 * w / 3):
            d.line([(x + bx, y - h), (x + bx, y)], fill=(96, 62, 40), width=lw)
        d.line([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2)], fill=(96, 62, 40), width=lw)
    d.polygon([(x - w / 2 - 30 * s, y - h), (x + w / 2 + 30 * s, y - h), (x, y - h - 170 * s)], fill=roof, outline=OUTL, width=lw)
    wc = (255, 214, 110) if lit else (40, 44, 60)
    for wx in (-w / 4, w / 4):
        d.rectangle([x + wx - 36 * s, y - h + 40 * s, x + wx + 36 * s, y - h + 100 * s], fill=wc, outline=OUTL, width=lw)
    d.rectangle([x - 34 * s, y - 110 * s, x + 34 * s, y], fill=(110, 66, 40), outline=OUTL, width=lw)
    if q:
        d.ellipse([x - 44 * s, y - h - 120 * s, x + 44 * s, y - h - 32 * s], fill=(235, 235, 235), outline=OUTL, width=lw)
        f = font(int(70 * s)); d.text((x, y - h - 76 * s), "?", font=f, fill=(90, 90, 90), anchor="mm")

def ortsschild(d, x, y, s=1.0):
    d.rectangle([x - 70 * s, y - 520 * s, x - 52 * s, y], fill=(150, 150, 160))
    d.rectangle([x + 52 * s, y - 520 * s, x + 70 * s, y], fill=(150, 150, 160))
    d.rounded_rectangle([x - 300 * s, y - 760 * s, x + 300 * s, y - 470 * s], 26 * s, fill=WHITE, outline=BLACK, width=int(8 * s))
    d.rounded_rectangle([x - 280 * s, y - 740 * s, x + 280 * s, y - 490 * s], 18 * s, outline=(220, 30, 30), width=int(22 * s))
    d.text((x, y - 650 * s), "PETITBOURG", font=font(int(92 * s)), fill=BLACK, anchor="mm")
    d.text((x, y - 560 * s), "Commune · fondée en 2026", font=font(int(34 * s)), fill=BLACK, anchor="mm")

def well(d, x, y, s=1.0):
    d.ellipse([x - 150 * s, y - 50 * s, x + 150 * s, y + 50 * s], fill=(120, 120, 130), outline=OUTL, width=8)
    d.rectangle([x - 150 * s, y - 170 * s, x + 150 * s, y], fill=(140, 140, 150), outline=OUTL, width=8)
    for i in range(4):
        d.line([(x - 150 * s, y - 40 * s - i * 40 * s), (x + 150 * s, y - 40 * s - i * 40 * s)], fill=(110, 110, 120), width=6)
    d.ellipse([x - 150 * s, y - 220 * s, x + 150 * s, y - 120 * s], fill=(30, 40, 60), outline=OUTL, width=8)
    d.rectangle([x - 130 * s, y - 470 * s, x - 110 * s, y - 170 * s], fill=(110, 70, 40), outline=OUTL, width=5)
    d.rectangle([x + 110 * s, y - 470 * s, x + 130 * s, y - 170 * s], fill=(110, 70, 40), outline=OUTL, width=5)
    d.polygon([(x - 190 * s, y - 440 * s), (x + 190 * s, y - 440 * s), (x, y - 580 * s)], fill=(150, 52, 40), outline=OUTL, width=8)

def rathaus(d, x, y, s=1.0):
    w, h = 900 * s, 620 * s
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=(232, 218, 186), outline=OUTL, width=10)
    d.polygon([(x - w / 2 - 40, y - h), (x + w / 2 + 40, y - h), (x, y - h - 260 * s)], fill=(120, 48, 40), outline=OUTL, width=10)
    d.rectangle([x - 70 * s, y - 300 * s, x + 70 * s, y], fill=(100, 60, 36), outline=OUTL, width=10)
    for wx in (-300, 300):
        d.rectangle([x + wx * s - 80 * s, y - 470 * s, x + wx * s + 80 * s, y - 280 * s], fill=(255, 214, 110), outline=OUTL, width=10)
        d.line([(x + wx * s, y - 470 * s), (x + wx * s, y - 280 * s)], fill=OUTL, width=8)
    d.rounded_rectangle([x - 300 * s, y - h - 10 * s, x + 300 * s, y - h + 110 * s], 20, fill=WHITE, outline=OUTL, width=8)
    d.text((x, y - h + 50 * s), "MAIRIE", font=font(int(84 * s)), fill=(30, 90, 30), anchor="mm")

def make_bg(kind):
    w, h = W * 2, H * 2
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    sky(d, w, h, hz=1900)
    church(d, 1500, 1500, 1.4)
    trees(d, 1600, 1.6, seed=2, w=w); trees(d, 1700, 2.0, col=(26, 52, 34), seed=5, w=w)
    if kind == "wide":
        grass(d, 1650, w, h)
        road(d, 2300, 2900, w)
    elif kind == "road":
        grass(d, 1650, w, h); road(d, 2050, 3400, w)
    elif kind == "schild":
        grass(d, 1650, w, h); road(d, 2900, 3840, w)
        house(d, 300, 2100, 1.5); house(d, 1900, 2050, 1.3, roof=(110, 60, 50))
        ortsschild(d, 1160, 2700, 1.5)
    elif kind == "well":
        grass(d, 1650, w, h); road(d, 2200, 2700, w); well(d, 1450, 2550, 1.6)
    elif kind == "houses":
        grass(d, 1650, w, h)
        for i, x in enumerate([260, 820, 1380, 1940]):
            house(d, x, 2100, 1.35, roof=[(150, 52, 40), (110, 60, 50), (140, 80, 40), (120, 50, 60)][i])
        road(d, 2100, 2700, w)
    elif kind == "grid":
        grass(d, 1650, w, h)
        for row in range(3):
            for col in range(5):
                x = 220 + col * 430 + (row % 2) * 200; y = 1900 + row * 520
                house(d, x, y, 0.95 - row * 0.0, q=True, beams=False)
        road(d, 3400, 3840, w)
    elif kind == "rathaus":
        grass(d, 1650, w, h); rathaus(d, 1080, 2900, 2.0); road(d, 2900, 3840, w)
    elif kind == "kasse":
        grass(d, 1650, w, h); road(d, 2000, 2600, w)
    elif kind == "night":
        im = Image.new("RGB", (w, h), (20, 20, 40)); d = ImageDraw.Draw(im)
        sky(d, w, h, top=(10, 12, 30), bot=(40, 50, 90), hz=h)
        # spotlights
        for a in (-0.5, -0.2, 0.2, 0.5):
            d.polygon([(1080, 1700), (1080 + math.sin(a) * 2400 - 160, -200), (1080 + math.sin(a) * 2400 + 160, -200)], fill=(110, 130, 190))
        # skyline
        r = random.Random(11); x = 0
        while x < w:
            bw = r.randint(140, 260); bh = r.randint(500, 1300)
            d.rectangle([x, 2300 - bh, x + bw, 2300], fill=(30, 34, 64), outline=(60, 70, 120), width=6)
            for wy in range(2300 - bh + 40, 2280, 80):
                for wx in range(x + 25, x + bw - 30, 60):
                    if r.random() < .55: d.rectangle([wx, wy, wx + 28, wy + 40], fill=(255, 220, 120))
            x += bw + 20
        trees(d, 2500, 2.2, col=(20, 44, 30), seed=9, w=w)
        grass(d, 2500, w, h, base=(40, 80, 36))
        im = im.filter(ImageFilter.GaussianBlur(2))
    return im.resize((W, H), Image.LANCZOS)

# ---------------------------------------------------------------- characters (sprites, drawn 2x)
CH = {
 "mayor": dict(coat=(122, 74, 44), hat="top", moust=True, chain=True, hair=(70, 40, 25)),
 "heinz": dict(coat=(236, 236, 228), hat="baker", glasses=True, bald=True, apron=True),
 "dieter": dict(coat=(190, 40, 40), hat="helmet", moust=True, belly=True),
 "slipper": dict(coat=(70, 110, 170), hat="cap", sandals=True),
 "v1": dict(coat=(200, 150, 50), hair=(40, 30, 20)),
 "v2": dict(coat=(80, 140, 90), hair=(160, 100, 40)),
 "v3": dict(coat=(150, 70, 120), hat="cap", hair=(30, 30, 30)),
 "v4": dict(coat=(70, 90, 140), bald=True, moust=True),
}

@lru_cache(maxsize=None)
def sprite(kind, mouth=0, scale=1.0):
    p = CH[kind]; S = 2
    w, h = 420 * S, 760 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx = w // 2; lw = 7 * S
    skin = (244, 200, 160)
    # shadow
    d.ellipse([cx - 120 * S, h - 40 * S, cx + 120 * S, h - 6 * S], fill=(0, 0, 0, 70))
    # legs
    for lx in (-45, 45):
        d.rounded_rectangle([cx + (lx - 22) * S, 560 * S, cx + (lx + 22) * S, 715 * S], 10 * S, fill=(50, 50, 60), outline=OUTL, width=lw)
        if p.get("sandals"):
            d.rounded_rectangle([cx + (lx - 34) * S, 700 * S, cx + (lx + 34) * S, 730 * S], 12 * S, fill=(70, 160, 220), outline=OUTL, width=lw)
            for tx in (-16, 0, 16):
                d.ellipse([cx + (lx + tx - 7) * S, 692 * S, cx + (lx + tx + 7) * S, 706 * S], fill=skin, outline=OUTL, width=3 * S)
        else:
            d.rounded_rectangle([cx + (lx - 34) * S, 695 * S, cx + (lx + 30) * S, 732 * S], 16 * S, fill=(40, 30, 28), outline=OUTL, width=lw)
    # body
    bw = 150 if p.get("belly") else 120
    d.rounded_rectangle([cx - bw * S, 330 * S, cx + bw * S, 600 * S], 70 * S, fill=p["coat"], outline=OUTL, width=lw)
    if p.get("apron"):
        d.rounded_rectangle([cx - 80 * S, 380 * S, cx + 80 * S, 590 * S], 30 * S, fill=WHITE, outline=OUTL, width=4 * S)
    if p.get("chain"):
        d.arc([cx - 90 * S, 280 * S, cx + 90 * S, 470 * S], 20, 160, fill=(245, 200, 40), width=14 * S)
        d.ellipse([cx - 28 * S, 440 * S, cx + 28 * S, 496 * S], fill=(245, 200, 40), outline=OUTL, width=4 * S)
    if p.get("hat") == "helmet":
        d.rectangle([cx - bw * S + 10, 470 * S, cx + bw * S - 10, 495 * S], fill=(245, 220, 60))
    for bx in (0,):
        for by in (400, 470, 540):
            if not p.get("apron") and not p.get("chain"):
                d.ellipse([cx - 8 * S, by * S - 8 * S, cx + 8 * S, by * S + 8 * S], fill=(40, 40, 40))
    # arms
    for sgn in (-1, 1):
        ax = cx + sgn * (bw + 6) * S
        d.rounded_rectangle([ax - 22 * S, 360 * S, ax + 22 * S, 540 * S], 22 * S, fill=p["coat"], outline=OUTL, width=lw)
        d.ellipse([ax - 24 * S, 520 * S, ax + 24 * S, 568 * S], fill=skin, outline=OUTL, width=lw)
    if p.get("collar"):
        d.rectangle([cx - 40 * S, 330 * S, cx + 40 * S, 352 * S], fill=WHITE, outline=OUTL, width=4 * S)
    if p.get("long_hair"):
        d.rounded_rectangle([cx - 150 * S, 110 * S, cx + 150 * S, 420 * S], 90 * S, fill=p["long_hair"], outline=OUTL, width=lw)
    # head
    hx0, hy0, hx1, hy1 = cx - 125 * S, 70 * S, cx + 125 * S, 350 * S
    d.ellipse([hx0 - 18 * S, 190 * S, hx0 + 22 * S, 250 * S], fill=skin, outline=OUTL, width=lw)
    d.ellipse([hx1 - 22 * S, 190 * S, hx1 + 18 * S, 250 * S], fill=skin, outline=OUTL, width=lw)
    d.ellipse([hx0, hy0, hx1, hy1], fill=skin, outline=OUTL, width=lw)
    if not p.get("bald") and p.get("hair"):
        d.chord([hx0, hy0, hx1, hy1 - 60 * S], 180, 360, fill=p["hair"], outline=OUTL, width=lw)
    # eyes
    for ex in (-48, 48):
        d.ellipse([cx + (ex - 30) * S, 170 * S, cx + (ex + 30) * S, 236 * S], fill=WHITE, outline=OUTL, width=5 * S)
        d.ellipse([cx + (ex - 11) * S, 192 * S, cx + (ex + 11) * S, 216 * S], fill=BLACK)
    if p.get("glasses"):
        for ex in (-48, 48):
            d.ellipse([cx + (ex - 40) * S, 160 * S, cx + (ex + 40) * S, 246 * S], outline=OUTL, width=6 * S)
        d.line([(cx - 8 * S, 200 * S), (cx + 8 * S, 200 * S)], fill=OUTL, width=6 * S)
    # brows
    for ex in (-48, 48):
        d.line([(cx + (ex - 26) * S, 156 * S), (cx + (ex + 26) * S, 150 * S if ex < 0 else 156 * S)], fill=OUTL, width=8 * S)
    # nose & cheeks
    d.ellipse([cx - 22 * S, 222 * S, cx + 22 * S, 262 * S], fill=(232, 170, 130), outline=OUTL, width=4 * S)
    for ex in (-85, 85):
        d.ellipse([cx + (ex - 22) * S, 250 * S, cx + (ex + 22) * S, 274 * S], fill=(245, 160, 150))
    # mouth
    if mouth:
        d.ellipse([cx - 34 * S, 274 * S, cx + 34 * S, 320 * S], fill=(110, 30, 30), outline=OUTL, width=5 * S)
        d.chord([cx - 26 * S, 292 * S, cx + 26 * S, 324 * S], 180, 360, fill=(230, 100, 100))
    else:
        d.arc([cx - 36 * S, 262 * S, cx + 36 * S, 304 * S], 20, 160, fill=OUTL, width=6 * S)
    if p.get("moust"):
        d.chord([cx - 62 * S, 248 * S, cx + 62 * S, 300 * S], 180, 360, fill=(60, 36, 22), outline=OUTL, width=4 * S)
    # hats
    hat = p.get("hat")
    if hat == "top":
        d.rounded_rectangle([cx - 150 * S, 82 * S, cx + 150 * S, 112 * S], 12 * S, fill=(30, 30, 34), outline=OUTL, width=lw)
        d.rectangle([cx - 90 * S, -30 * S + 40 * S, cx + 90 * S, 96 * S], fill=(30, 30, 34), outline=OUTL, width=lw)
        d.rectangle([cx - 90 * S, 66 * S, cx + 90 * S, 86 * S], fill=(200, 160, 40))
    elif hat == "baker":
        d.ellipse([cx - 110 * S, 0, cx + 110 * S, 120 * S], fill=WHITE, outline=OUTL, width=lw)
        d.rectangle([cx - 90 * S, 80 * S, cx + 90 * S, 118 * S], fill=WHITE, outline=OUTL, width=lw)
    elif hat == "helmet":
        d.chord([cx - 135 * S, 40 * S, cx + 135 * S, 230 * S], 180, 360, fill=(230, 40, 40), outline=OUTL, width=lw)
        d.rectangle([cx - 150 * S, 128 * S, cx + 150 * S, 146 * S], fill=(230, 40, 40), outline=OUTL, width=5 * S)
    elif hat == "police":
        d.chord([cx - 120 * S, 60 * S, cx + 120 * S, 230 * S], 180, 360, fill=(30, 40, 90), outline=OUTL, width=lw)
        d.rounded_rectangle([cx - 150 * S, 128 * S, cx + 150 * S, 150 * S], 10 * S, fill=(20, 20, 30), outline=OUTL, width=5 * S)
        d.ellipse([cx - 18 * S, 82 * S, cx + 18 * S, 118 * S], fill=(245, 200, 40), outline=OUTL, width=3 * S)
    elif hat == "army":
        d.chord([cx - 135 * S, 40 * S, cx + 135 * S, 230 * S], 180, 360, fill=(80, 100, 50), outline=OUTL, width=lw)
        d.rectangle([cx - 150 * S, 128 * S, cx + 150 * S, 146 * S], fill=(80, 100, 50), outline=OUTL, width=5 * S)
    elif hat == "chef":
        d.ellipse([cx - 110 * S, 0, cx + 110 * S, 120 * S], fill=WHITE, outline=OUTL, width=lw)
        d.rectangle([cx - 90 * S, 80 * S, cx + 90 * S, 118 * S], fill=WHITE, outline=OUTL, width=lw)
    elif hat == "cap":
        d.chord([cx - 120 * S, 60 * S, cx + 120 * S, 230 * S], 180, 360, fill=(240, 240, 240), outline=OUTL, width=lw)
        d.rounded_rectangle([cx - 10 * S, 132 * S, cx + 170 * S, 152 * S], 10 * S, fill=(240, 240, 240), outline=OUTL, width=5 * S)
    out = im.resize((int(w / S * scale), int(h / S * scale)), Image.LANCZOS)
    return out

def put_char(fr, kind, x, y, scale, t, talk=False, phase=0):
    bob = math.sin(t * 3 + phase) * 4 * scale
    mouth = 1 if talk and int(t * 9 + phase) % 2 == 0 else 0
    sp = sprite(kind, mouth, round(scale, 2))
    fr.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height + bob)))

# ---------------------------------------------------------------- UI elements
def text_stroke(d, xy, txt, size, fill, stroke=8, anchor="mm", sc=BLACK):
    d.text(xy, txt, font=font(size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sc)

def badge_img(lines, fill=(60, 170, 50), tc=WHITE, size=110, pad=40, border=WHITE, sub=None, subfill=None, rot=0):
    f = font(size)
    tw = max(f.getbbox(l)[2] for l in lines); th = size * 1.15 * len(lines)
    sw = 0
    if sub: fs = font(int(size * .42)); sw = fs.getbbox(sub)[2]
    bw = max(tw, sw) + pad * 2; bh = th + pad * 1.2 + (size * .55 if sub else 0)
    im = Image.new("RGBA", (int(bw + 40), int(bh + 40)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([24, 26, bw + 24, bh + 26], 26, fill=(0, 0, 0, 90))
    d.rounded_rectangle([14, 14, bw + 14, bh + 14], 26, fill=fill, outline=border, width=8)
    for i, l in enumerate(lines):
        d.text((14 + bw / 2, 14 + pad * .6 + size * .6 + i * size * 1.15), l, font=f, fill=tc, anchor="mm")
    if sub:
        d.text((14 + bw / 2, 14 + bh - size * .42), sub, font=font(int(size * .42)), fill=subfill or tc, anchor="mm")
    if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    return im

def pop(fr, im, cx, cy, t0, t, dur=.35):
    if t < t0: return
    k = ease_back((t - t0) / dur)
    if k <= 0.02: return
    s = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    fr.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))

def caption(fr, words, t, start, end):
    """words: string with [green] markup"""
    if not (start <= t < end): return
    k = ease_back((t - start) / .18)
    parts = []
    for tok in words.split(" "):
        g = tok.startswith("[")
        parts.append((tok.strip("[]"), g))
    size = int(84 * (0.6 + 0.4 * k))
    f = font(size); sp = f.getbbox(" ")[2]
    widths = [f.getbbox(p)[2] for p, _ in parts]
    total = sum(widths) + sp * (len(parts) - 1)
    if total > W - 80:
        size = int(size * (W - 80) / total); f = font(size); sp = f.getbbox(" ")[2]
        widths = [f.getbbox(p)[2] for p, _ in parts]; total = sum(widths) + sp * (len(parts) - 1)
    d = ImageDraw.Draw(fr); x = (W - total) / 2; y = 1450
    for (p, g), wdt in zip(parts, widths):
        d.text((x, y), p, font=f, fill=GREEN if g else WHITE, anchor="lm", stroke_width=9, stroke_fill=BLACK)
        x += wdt + sp

# rain
RNG = random.Random(42)
DROPS = [(RNG.uniform(0, W + 300), RNG.uniform(0, H), RNG.uniform(900, 1500), RNG.uniform(30, 70)) for _ in range(260)]
def rain(fr, t, alpha=110):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for x0, y0, v, ln in DROPS:
        y = (y0 + v * t) % (H + 100) - 50; x = x0 - (y0 + v * t) * .18 % (W + 300)
        d.line([(x, y), (x - ln * .18, y + ln)], fill=(200, 210, 240, alpha), width=2)
    fr.alpha_composite(lay)

def zoom(fr, z, fx=.5, fy=.5):
    if abs(z - 1) < 1e-3: return fr
    cw, ch = W / z, H / z
    x0 = (W - cw) * fx; y0 = (H - ch) * fy
    return fr.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)

# ---------------------------------------------------------------- avatar / cards
def avatar(size=180, check=False):
    im = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([10, 10, size + 10, size + 10], fill=(220, 225, 235), outline=WHITE, width=8)
    sp = sprite("mayor", 0, 0.42)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).ellipse([16, 16, size + 4, size + 4], fill=255)
    tmp = Image.new("RGBA", im.size, (0, 0, 0, 0)); tmp.alpha_composite(sp, (int((im.width - sp.width) / 2), 22))
    im.paste(tmp, (0, 0), Image.composite(tmp.split()[3], Image.new("L", im.size, 0), m))
    d.ellipse([10, 10, size + 10, size + 10], outline=WHITE, width=8)
    if check:
        d.ellipse([size / 2 - 22 + 10, size - 26, size / 2 + 22 + 10, size + 18], fill=WHITE, outline=OUTL, width=3)
        d.line([(size / 2, size - 4), (size / 2 + 8, size + 6), (size / 2 + 24, size - 14)], fill=OUTL, width=6)
    return im

def profile_card(n_new=False):
    im = Image.new("RGBA", (760, 400), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 759, 399], 34, fill=(22, 22, 28, 245), outline=(90, 90, 100), width=3)
    d.text((40, 60), "Petitbourg", font=font(50), fill=WHITE, anchor="lm")
    d.text((40, 110), "@deinaccount", font=font(28), fill=(170, 170, 180), anchor="lm")
    av = avatar(130); im.alpha_composite(av, (590, 25))
    for i, (num, lab) in enumerate([("3", "Abonnements"), ("0", "Habitants"), ("0", "J'aime")]):
        x = 90 + i * 210
        d.text((x, 180), num, font=font(46), fill=WHITE, anchor="mm")
        d.text((x, 225), lab, font=font(24), fill=(170, 170, 180), anchor="mm")
    if n_new:
        d.ellipse([200, 140, 400, 250], outline=RED, width=6)
    d.rounded_rectangle([40, 270, 360, 340], 14, fill=(254, 44, 85))
    d.text((200, 305), "Suivre", font=font(32), fill=WHITE, anchor="mm")
    d.rounded_rectangle([380, 270, 690, 340], 14, fill=(60, 60, 70))
    d.text((535, 305), "Message", font=font(32), fill=WHITE, anchor="mm")
    d.text((40, 372), "1 abonné = 1 habitant", font=font(26), fill=(200, 200, 210), anchor="lm")
    return im

def comment_card():
    im = Image.new("RGBA", (820, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 819, 219], 30, fill=WHITE, outline=(200, 200, 210), width=3)
    d.ellipse([30, 40, 110, 120], fill=(200, 200, 215))
    d.text((135, 60), "dein_name", font=font(30), fill=(130, 130, 140), anchor="lm")
    d.rounded_rectangle([320, 40, 560, 80], 12, fill=(254, 44, 85))
    d.text((440, 60), "Top commentaire", font=font(24), fill=WHITE, anchor="mm")
    d.text((135, 130), "ton idée ?", font=font(46), fill=BLACK, anchor="lm")
    d.ellipse([748,52,772,76],fill=(254,44,85)); d.ellipse([768,52,792,76],fill=(254,44,85)); d.polygon([(749,68),(791,68),(770,96)],fill=(254,44,85))
    return im

def kasse_img(amount_txt=None):
    im = Image.new("RGBA", (760, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([40, 160, 720, 500], 30, fill=(46, 92, 64), outline=OUTL, width=10)
    d.rounded_rectangle([20, 90, 740, 210], 30, fill=(58, 110, 76), outline=OUTL, width=10)
    d.rounded_rectangle([280, 50, 480, 100], 16, outline=OUTL, width=10)
    d.rounded_rectangle([110, 260, 650, 380], 12, fill=(235, 235, 230), outline=OUTL, width=6)
    d.text((380, 305), "CAISSE COMMUNALE", font=font(50), fill=OUTL, anchor="mm")
    d.text((380, 356), "PETITBOURG", font=font(30), fill=(90, 90, 90), anchor="mm")
    d.rounded_rectangle([350, 400, 410, 460], 8, fill=(220, 180, 40), outline=OUTL, width=5)
    return im

def card(lines, fill=WHITE, tc=BLACK, icon=None, rot=0):
    im = Image.new("RGBA", (260, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, 252, 292], 24, fill=fill, outline=OUTL, width=6)
    if icon == "?":
        d.text((130, 100), "?", font=font(120), fill=WHITE, anchor="mm", stroke_width=4, stroke_fill=OUTL)
    elif icon:
        icon(d)
    for i, l in enumerate(lines):
        d.text((130, 200 + i * 40), l, font=font(28), fill=tc, anchor="mm")
    return im.rotate(rot, resample=Image.BICUBIC, expand=True)

def icon_beer(d):
    d.rounded_rectangle([90, 50, 160, 150], 10, fill=(250, 190, 40), outline=OUTL, width=5)
    d.ellipse([84, 32, 166, 70], fill=WHITE, outline=OUTL, width=5)
    d.arc([150, 70, 190, 130], 270, 90, fill=OUTL, width=8)
def icon_church(d):
    d.rectangle([105, 70, 155, 150], fill=(200, 200, 210), outline=OUTL, width=5)
    d.polygon([(95, 70), (165, 70), (130, 20)], fill=(150, 52, 40), outline=OUTL)
    d.line([(130, 4), (130, 28)], fill=OUTL, width=5); d.line([(120, 14), (140, 14)], fill=OUTL, width=5)

# ---------------------------------------------------------------- scenes
BG = {}
def bg(k):
    if k not in BG: BG[k] = make_bg(k).convert("RGBA")
    return BG[k]

SCENES = []
def scene(t0, t1):
    def deco(fn): SCENES.append((t0, t1, fn)); return fn
    return deco
