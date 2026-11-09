"""Vue aérienne de Petitbourg (style cartoon 3D comme les vidéos de référence) : grande ville, minuscules habitants."""
import math, random
from PIL import Image, ImageDraw
from base import font, sprite, OUTL

CELL, ROAD, COLS, ROWS = 420, 100, 8, 12
WW, WH = COLS * CELL, ROWS * CELL
OUT = (30, 28, 36)
def dk(c, f): return tuple(max(0, min(255, int(v * f))) for v in c[:3])

# ------------------------------------------------------------- la ville : id, genre, bloc(c,r), emplacement, couleurs, pseudo
H = lambda i, c, r, s, wall, roof, lab=None, **o: dict(id=i, k="house", c=c, r=r, s=s, wall=wall, roof=roof, lab=lab, **o)
CITY = [
 dict(id="mairie", k="mairie", c=3, r=5, s="full", lab="MAIRIE"),
 dict(id="eglise", k="church", c=2, r=5, s="full", lab="ÉGLISE"),
 dict(id="police", k="police", c=4, r=5, s="full", lab="COMMISSARIAT"),
 dict(id="mosquee", k="mosque", c=3, r=4, s="full", lab="MOSQUÉE"),
 dict(id="stade", k="stade", c=3, r=6, s="full", lab="STADE FC PETITBOURG"),
 H("ilyes", 2, 4, 0, (240, 210, 170), (190, 70, 50), "@h22rr1"), H("kvn", 2, 4, 1, (236, 236, 240), (60, 120, 200), "@kvnmlt30"),
 H("villa23", 2, 4, 2, (250, 250, 252), (70, 76, 92), "@23_fg_29", flat=True, pool=True), H("lara", 2, 4, 3, (196, 160, 232), (140, 100, 190), "@lara.fardeau"),
 H("pain", 4, 4, 0, (180, 110, 60), (240, 240, 240), "@usr.ysl1"), H("napo", 4, 4, 1, (250, 170, 190), (110, 64, 40), "@123e7890", tall=True),
 H("sauc", 4, 4, 2, (200, 90, 56), (150, 60, 40), "@cristal_bnt7", wide=True), H("pop", 4, 4, 3, (36, 36, 44), (250, 205, 60), "@la_fan_de_mj"),
 H("lac", 2, 6, 0, (250, 250, 252), (70, 76, 92), "@the_t0710", flat=True, pool=True, lake=True), H("licorne", 2, 6, 1, (255, 200, 230), (170, 120, 240), "@ax.ou0"),
 H("banane", 2, 6, 2, (255, 226, 60), (230, 190, 30), "@inconus_conunus", wide=True), H("cabane", 2, 6, 3, (170, 120, 70), (60, 140, 60), "@dan.caa", tall=True),
 H("chalet", 4, 6, 0, (150, 100, 58), (245, 248, 255), "@anonyme_ft5"), H("choco", 4, 6, 1, (110, 66, 40), (250, 240, 226), "@matheo01_02"),
 H("capy", 4, 6, 2, (196, 146, 100), (84, 150, 60), "@hassegyznfw"), H("poulet", 4, 6, 3, (206, 62, 52), (120, 36, 34), "@emilerzernofficial"),
 # --- Jour 4
 dict(id="ecole", k="school", c=1, r=5, s="full", lab="ÉCOLE"),
 H("omar", 1, 4, 0, (255, 236, 200), (210, 110, 70), "@mar_64kk", swing=True), H("rose", 1, 4, 1, (255, 190, 220), (240, 120, 180), "@nd.k601", flat=True, pool=True),
 H("elina", 1, 4, 2, (250, 250, 252), (255, 140, 190), "@elina.2286", flat=True, pool=True, jacuzzi=True), H("igloo", 1, 4, 3, (240, 248, 255), (200, 225, 245), "@keitonakamuraaaalp", dome=True),
 H("husky", 1, 6, 0, (220, 224, 232), (60, 70, 90), "@raph_ikih", flat=True, dog=True),
 dict(id="hopital", k="site", c=5, r=4, s="full", lab="HÔPITAL · @i.abdhi"), dict(id="parc", k="site", c=5, r=6, s="full", lab="PARC · @lacsorbx"),
 dict(id="caserne", k="site", c=5, r=5, s="full", lab="CASERNE · @cindydoudie"), dict(id="cinema", k="site", c=6, r=5, s="full", lab="CINÉ CLAP · @nathan.2402"),
 dict(id="vet", k="site", c=0, r=5, s="full", lab="CLINIQUE VÉTO · @raph_ikih"),
]
BY = {b["id"]: b for b in CITY}
def origin(b):
    x0, y0 = b["c"] * CELL + ROAD // 2, b["r"] * CELL + ROAD // 2
    if b["s"] == "full": return x0, y0, CELL - ROAD
    return x0 + (b["s"] % 2) * 160 + 6, y0 + (b["s"] // 2) * 160 + 6, 148
def top_center(b):
    x, y, sz = origin(b); return x + sz / 2, y + sz - (150 if b["s"] == "full" else 70)

# ------------------------------------------------------------- dessin
def box(d, x, y, w, dp, h, wall, roof, peak=0, win=True, flat=False):
    dx, dy = int(dp * .38), int(dp * .5)
    d.polygon([(x + w, y), (x + w, y - h), (x + w + dx, y - h - dy), (x + w + dx, y - dy)], fill=dk(wall, .74), outline=OUT)
    d.rectangle([x, y - h, x + w, y], fill=wall, outline=OUT, width=3)
    if peak:
        d.polygon([(x, y - h), (x + w, y - h), (x + w / 2, y - h - peak)], fill=wall, outline=OUT)
        d.polygon([(x + w, y - h), (x + w / 2, y - h - peak), (x + w / 2 + dx, y - h - peak - dy), (x + w + dx, y - h - dy)], fill=roof, outline=OUT)
        d.polygon([(x - 6, y - h + 3), (x + w / 2, y - h - peak - 4), (x + w / 2 + dx, y - h - peak - dy - 4), (x + dx - 6, y - h - dy + 3)], fill=dk(roof, 1.12), outline=OUT) if False else None
    else:
        d.polygon([(x, y - h), (x + w, y - h), (x + w + dx, y - h - dy), (x + dx, y - h - dy)], fill=roof, outline=OUT)
    if win:
        n = max(2, int(w // 34))
        for i in range(n):
            wx = x + 10 + i * (w - 20) / n
            d.rectangle([wx, y - h * .75, wx + (w - 20) / n - 8, y - h * .45], fill=(255, 232, 140), outline=OUT, width=2)
        d.rectangle([x + w / 2 - 9, y - h * .38, x + w / 2 + 9, y], fill=(110, 70, 42), outline=OUT, width=2)

def tree(d, x, y, s=1.0):
    d.rectangle([x - 4 * s, y - 14 * s, x + 4 * s, y], fill=(110, 72, 44))
    d.ellipse([x - 20 * s, y - 52 * s, x + 20 * s, y - 8 * s], fill=(58, 150, 70), outline=OUT, width=2)
    d.ellipse([x - 12 * s, y - 50 * s, x + 4 * s, y - 32 * s], fill=(96, 190, 100))

def draw_item(d, b):
    x, y, sz = origin(b); k = b["k"]; base = y + sz - 6
    d.ellipse([x + 6, base - 14, x + sz - 6, base + 6], fill=(0, 0, 0, 60))
    if k == "house":
        w = 104 if not b.get("wide") else 130; h = 62 if not b.get("tall") else 92; px = x + (sz - w) / 2 - 8
        if b.get("dome"):
            d.pieslice([px, base - 120, px + w + 10, base + 10], 180, 360, fill=b["wall"], outline=OUT, width=3)
            d.rectangle([px + w / 2 - 10, base - 34, px + w / 2 + 24, base], fill=(90, 120, 150), outline=OUT, width=2)
        else:
            box(d, px, base, w, 62, h, b["wall"], b["roof"], peak=0 if b.get("flat") else 40)
        if b.get("pool"):
            d.rounded_rectangle([x + 2, base - 4, x + 56, base + 2], 4, fill=(90, 200, 240), outline=OUT, width=2) if False else None
            d.rounded_rectangle([px + w + 14, base - 30, px + w + 54, base - 4], 6, fill=(80, 200, 240), outline=(240, 240, 240), width=3)
        if b.get("lake"): d.ellipse([x - 12, base - 26, x + 44, base + 4], fill=(60, 160, 220), outline=OUT, width=2)
        if b.get("jacuzzi"): d.ellipse([px + w + 20, base - 70, px + w + 46, base - 52], fill=(120, 220, 240), outline=OUT, width=2)
        if b.get("swing"): d.line([(px + w + 16, base - 4), (px + w + 24, base - 46), (px + w + 44, base - 46), (px + w + 50, base - 4)], fill=(120, 80, 50), width=3)
        if b.get("dog"): d.ellipse([px + w + 10, base - 18, px + w + 34, base - 4], fill=(230, 230, 236), outline=OUT, width=2)
        tree(d, x + 18, base - 4, .8)
    elif k == "mairie":
        box(d, x + 20, base, 240, 110, 118, (244, 232, 200), (150, 56, 46), peak=60)
        d.rectangle([x + 100, base - 150, x + 180, base - 118], fill=(24, 110, 56), outline=OUT, width=2)
        d.ellipse([x + 126, base - 196, x + 154, base - 168], fill=(255, 255, 255), outline=OUT, width=2)
    elif k == "church":
        box(d, x + 30, base, 150, 90, 90, (240, 236, 226), (120, 80, 70), peak=46)
        box(d, x + 190, base, 50, 50, 170, (236, 230, 218), (120, 80, 70), peak=40, win=False)
        d.line([(x + 215, base - 250), (x + 215, base - 292)], fill=(250, 220, 90), width=6); d.line([(x + 202, base - 276), (x + 228, base - 276)], fill=(250, 220, 90), width=6)
    elif k == "police":
        box(d, x + 20, base, 240, 100, 100, (222, 228, 242), (40, 60, 130), peak=0)
        d.rectangle([x + 90, base - 150, x + 190, base - 112], fill=(30, 50, 110), outline=OUT, width=2)
        d.ellipse([x + 130, base - 128, x + 150, base - 108], fill=(60, 120, 255), outline=OUT, width=2)
    elif k == "mosque":
        box(d, x + 40, base, 200, 100, 90, (250, 244, 228), (230, 220, 196), peak=0)
        d.pieslice([x + 90, base - 190, x + 190, base - 90], 180, 360, fill=(40, 150, 150), outline=OUT, width=3)
        for mx in (x + 28, x + 252):
            d.rectangle([mx - 12, base - 230, mx + 12, base], fill=(250, 244, 228), outline=OUT, width=3)
            d.polygon([(mx - 14, base - 230), (mx + 14, base - 230), (mx, base - 270)], fill=(40, 150, 150), outline=OUT)
    elif k == "stade":
        d.ellipse([x + 10, y + 30, x + sz - 10, y + sz - 20], fill=(190, 50, 50), outline=OUT, width=4)
        d.ellipse([x + 40, y + 56, x + sz - 40, y + sz - 46], fill=(64, 168, 70), outline=(255, 255, 255), width=4)
        d.line([(x + sz / 2, y + 56), (x + sz / 2, y + sz - 46)], fill=(255, 255, 255), width=3)
        d.ellipse([x + sz / 2 - 24, y + sz / 2 - 20, x + sz / 2 + 24, y + sz / 2 + 14], outline=(255, 255, 255), width=3)
        for fx in (x + 16, x + sz - 16): d.line([(fx, y + 40), (fx, y - 40)], fill=(150, 150, 160), width=5); d.rectangle([fx - 14, y - 56, fx + 14, y - 38], fill=(255, 244, 170), outline=OUT, width=2)
    elif k == "school":
        box(d, x + 20, base, 250, 100, 110, (255, 214, 90), (200, 70, 60), peak=50)
        d.rectangle([x + 110, base - 160, x + 170, base - 120], fill=(255, 255, 255), outline=OUT, width=2)
        d.line([(x + 140, base - 190), (x + 140, base - 250)], fill=(130, 130, 140), width=4); d.polygon([(x + 140, base - 250), (x + 180, base - 238), (x + 140, base - 226)], fill=(230, 50, 50))
        d.rounded_rectangle([x + 40, base + 6, x + 260, base + 40], 8, fill=(220, 120, 90), outline=OUT, width=2) if False else None
    elif k == "site":
        d.rounded_rectangle([x + 10, y + 40, x + sz - 10, y + sz - 20], 14, fill=(222, 190, 130), outline=OUT, width=3)
        for i in range(5): d.polygon([(x + 36 + i * 54, y + sz - 46), (x + 52 + i * 54, y + sz - 46), (x + 44 + i * 54, y + sz - 84)], fill=(255, 140, 40), outline=OUT)
        d.rectangle([x + 100, y + 60, x + 200, y + 100], fill=(250, 250, 250), outline=OUT, width=3)
        d.polygon([(x + 70, y + 160), (x + 230, y + 160), (x + 220, y + 130), (x + 80, y + 130)], fill=(255, 200, 40), outline=OUT)
    if b["k"] not in ("stade", "site"): tree(d, x + sz - 14, base - 2, .9)


F = 2.5   # super-échantillonnage : les bâtiments restent nets en gros plan

class _Sc:
    """enveloppe ImageDraw : échelle F + décalage (ox,oy) en coordonnées monde."""
    def __init__(s, d, ox=0, oy=0, f=F): s.d, s.ox, s.oy, s.f = d, ox, oy, f
    def _xy(s, v):
        if v and isinstance(v[0], (list, tuple)): return [((a - s.ox) * s.f, (b - s.oy) * s.f) for a, b in v]
        return [(v[i] - (s.ox if i % 2 == 0 else s.oy)) * s.f for i in range(len(v))]
    def __getattr__(s, n):
        fn = getattr(s.d, n)
        def w(xy, *a, **k):
            if n == "rounded_rectangle" and a: a = (a[0] * s.f,) + a[1:]
            if "width" in k: k["width"] = max(1, int(k["width"] * s.f))
            return fn(s._xy(xy), *a, **k)
        return w

_WORLD = {}
def world(built, reg):
    key = (tuple(sorted(built)), reg)
    if key in _WORLD: return _WORLD[key]
    if len(_WORLD) > 2: _WORLD.clear()
    rx0, ry0, rx1, ry1 = reg
    im = Image.new("RGB", (int((rx1 - rx0) * F) + 2, int((ry1 - ry0) * F) + 2), (120, 190, 90))
    d = _Sc(ImageDraw.Draw(im, "RGBA"), rx0, ry0)
    for c in range(COLS):
        for r in range(ROWS):
            x0, y0 = c * CELL + ROAD // 2, r * CELL + ROAD // 2
            if x0 > rx1 or y0 > ry1 or x0 + CELL < rx0 or y0 + CELL < ry0: continue
            d.rounded_rectangle([x0, y0, x0 + CELL - ROAD, y0 + CELL - ROAD], 26, fill=(138, 206, 100), outline=(232, 228, 214), width=8)
    for c in range(COLS + 1):
        d.rectangle([c * CELL - ROAD // 2 + 10, 0, c * CELL + ROAD // 2 - 10, WH], fill=(62, 64, 72))
        for y in range(0, WH, 90): d.rectangle([c * CELL - 3, y, c * CELL + 3, y + 46], fill=(245, 245, 245))
    for r in range(ROWS + 1):
        d.rectangle([0, r * CELL - ROAD // 2 + 10, WW, r * CELL + ROAD // 2 - 10], fill=(62, 64, 72))
        for x in range(0, WW, 90): d.rectangle([x, r * CELL - 3, x + 46, r * CELL + 3], fill=(245, 245, 245))
    rnd = random.Random(5)
    for c in range(COLS):
        for r in range(ROWS):
            if not any(b["c"] == c and b["r"] == r for b in CITY):
                for _ in range(rnd.randint(2, 5)): tree(d, c * CELL + rnd.randint(70, 350), r * CELL + rnd.randint(110, 360), rnd.uniform(.8, 1.3))
    items = sorted([BY[i] for i in built if i in BY], key=lambda b: (b["r"], b["s"] if b["s"] != "full" else 0))
    for b in items: draw_item(d, b)
    _WORLD[key] = im; return im

_SPR = {}
def item_sprite(i):
    if i in _SPR: return _SPR[i]
    b = BY[i]; PAD = 300
    im = Image.new("RGBA", (int(CELL * F), int((CELL + PAD) * F)), (0, 0, 0, 0))
    bb = dict(b); bb["c"] = 0; bb["r"] = 0
    draw_item(_Sc(ImageDraw.Draw(im, "RGBA"), 0, -PAD), bb)
    _SPR[i] = (im, b["c"] * CELL, b["r"] * CELL - PAD); return _SPR[i]

def ease(x): x = max(0, min(1, x)); return x * x * (3 - 2 * x)
def cam_at(cam, t):
    if t <= cam[0][0]: return cam[0][1:]
    for a, b in zip(cam, cam[1:]):
        if t <= b[0]:
            k = ease((t - a[0]) / max(.01, b[0] - a[0])); return [a[i] + (b[i] - a[i]) * k for i in (1, 2, 3)]
    return cam[-1][1:]

def tagimg(text, big=False):
    f = font(34 if big else 28); tw = f.getbbox(text)[2] + 34; im = Image.new("RGBA", (tw, 58), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, tw - 1, 44], 14, fill=(255, 255, 255, 240), outline=OUT, width=3); d.polygon([(tw / 2 - 9, 44), (tw / 2 + 9, 44), (tw / 2, 57)], fill=(255, 255, 255, 240))
    d.text((tw / 2, 22), text, font=f, fill=(30, 40, 90), anchor="mm"); return im

def _region(A, W, H):
    xs0, ys0, xs1, ys1 = 1e9, 1e9, -1e9, -1e9
    for kf in A["cam"]:
        z = kf[3]; vw, vh = W / z, H / z
        xs0 = min(xs0, kf[1] - vw / 2); xs1 = max(xs1, kf[1] + vw / 2); ys0 = min(ys0, kf[2] - vh / 2); ys1 = max(ys1, kf[2] + vh / 2)
    m = 120
    return (int(max(0, xs0 - m)), int(max(0, ys0 - m)), int(min(WW, xs1 + m)), int(min(WH, ys1 + m)))

def render(sc, t, a, at, W, H):
    """sc['aerial'] = {built:[ids], new:[{id,line}], cam:[[sec|'L2',cx,cy,zoom]], tags:[ids]}"""
    A = sc["aerial"]; new = {n["id"]: at(sc, n.get("line", 0)) if n.get("line", 0) >= 0 else -1e9 for n in A.get("new", [])}
    built = [i for i in A["built"] if i not in new]
    cam = [[(at(sc, int(kf[0][1:])) - a) if isinstance(kf[0], str) else kf[0], kf[1], kf[2], kf[3]] for kf in A["cam"]]
    cx, cy, z = cam_at(cam, t - a); z += .01 * math.sin(t * .8)
    vw, vh = W / z, H / z
    reg = _region(A, W, H)
    x0 = max(reg[0], min(reg[2] - vw, cx - vw / 2)); y0 = max(reg[1], min(reg[3] - vh, cy - vh / 2))
    sc["_view"] = (x0, y0, z)
    wim = world(built, reg)
    px0, py0 = (x0 - reg[0]) * F, (y0 - reg[1]) * F
    fr = wim.crop((int(px0), int(py0), int(px0 + vw * F), int(py0 + vh * F))).resize((W, H), Image.BILINEAR).convert("RGBA")
    S = lambda wx, wy: ((wx - x0) * z, (wy - y0) * z)
    for i, ta in new.items():
        dt = t - ta
        if dt < 0: continue
        k = ease(dt / .7); k = k * (1 + .1 * math.sin(min(1, dt / .9) * math.pi)) if dt < .9 else 1.0
        spr, wx, wy = item_sprite(i); sw0, sh0 = spr.width / F * z, spr.height / F * z
        sw, sh = max(1, int(sw0 * k)), max(1, int(sh0 * k))
        s2 = spr.resize((sw, sh), Image.BILINEAR); px, py = S(wx, wy + spr.height / F)
        fr.alpha_composite(s2, (int(px + (sw0 - sw) / 2), int(py - sh)))
    d = ImageDraw.Draw(fr, "RGBA")
    for n in range(7):
        col = [(230, 60, 60), (60, 120, 230), (250, 200, 50), (240, 240, 240)][n % 4]
        if n % 2:
            wx = (n * 3 % COLS) * CELL + (-18 if n % 3 else 18); wy = (n * 733 + t * 70 * (1 if n % 4 else -1)) % WH
            px, py = S(wx, wy); d.rounded_rectangle([px - 13 * z, py - 24 * z, px + 13 * z, py + 24 * z], 6 * z, fill=col, outline=OUT, width=2)
        else:
            wy = (n * 2 % ROWS) * CELL + (-18 if n % 3 else 18); wx = (n * 611 + t * 70 * (1 if n % 4 else -1)) % WW
            px, py = S(wx, wy); d.rounded_rectangle([px - 24 * z, py - 13 * z, px + 24 * z, py + 13 * z], 6 * z, fill=col, outline=OUT, width=2)
    kinds = ["v1", "v2", "v3", "v4"]; sprs = {}
    for n in range(16):
        kd = kinds[n % 4]; sc_ = round(max(.04, .05 * z), 2)
        sprs.setdefault((kd, sc_), sprite(kd, 0, sc_)); sp = sprs[(kd, sc_)]
        if n % 2: wx = (n * 5 % COLS) * CELL + 50 + (n % 3) * 4; wy = (n * 457 + t * 38 * (1 if n % 4 else -1)) % WH
        else: wy = (n * 3 % ROWS) * CELL + 50 + (n % 3) * 4; wx = (n * 389 + t * 38 * (1 if n % 4 else -1)) % WW
        px, py = S(wx, wy)
        if -80 < px < W + 80 and -80 < py < H + 160: fr.alpha_composite(sp, (int(px - sp.width / 2), int(py - sp.height + math.sin(t * 9 + n) * 2)))
    ids = A.get("tags", [])
    for i in ids:
        if i in new and t < new[i] + .5: continue
        b = BY[i]; wx, wy = top_center(b); px, py = S(wx, wy - 40)
        tg = tagimg(b["lab"], b["s"] == "full")
        if -tg.width < px < W + tg.width and 0 < py < H: fr.alpha_composite(tg, (int(px - tg.width / 2), int(py - tg.height - 6 * math.sin(t * 3 + hash(i) % 7))))
    return fr

def MP(c, r, dx=0):
    """position monde (pieds) pour un personnage debout devant le bloc (c,r)."""
    return c * CELL + 210 + dx, (r + 1) * CELL - 14
def CAM(c, r, z, dy=-120): return [c * CELL + 210, r * CELL + 210 + dy, z]
