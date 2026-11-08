"""Bâtiments sur mesure de Petitbourg (ombrés, détaillés) + décor amélioré.

Tout est dessiné en coordonnées « unités » : x=0 centre, y=0 sol, y<0 vers le haut.
Les personnages / marques déposées ne sont PAS copiés : versions génériques (ours à miel, éponge de mer, chat rose...).
"""
import math, random
from PIL import Image, ImageDraw

OUTL = (25, 22, 28); WHITE = (255, 255, 255)

def dk(c, f): return tuple(max(0, min(255, int(v * f))) for v in c[:3])
def mix(a, b, k): return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))

class P:
    def __init__(s, im, x, y, k):
        s.im = im; s.d = ImageDraw.Draw(im, "RGBA"); s.x = x; s.y = y; s.k = k; s.ow = max(3, int(k * 1.7)); s.anchors = []
    def X(s, v): return s.x + v * s.k
    def Y(s, v): return s.y + v * s.k
    def rect(s, a, b, c, e, fill, ol=True):
        s.d.rectangle([s.X(a), s.Y(b), s.X(c), s.Y(e)], fill=fill, outline=OUTL if ol else None, width=s.ow)
    def rr(s, a, b, c, e, r, fill, ol=True):
        s.d.rounded_rectangle([s.X(a), s.Y(b), s.X(c), s.Y(e)], r * s.k, fill=fill, outline=OUTL if ol else None, width=s.ow)
    def ell(s, a, b, c, e, fill, ol=True):
        s.d.ellipse([s.X(a), s.Y(b), s.X(c), s.Y(e)], fill=fill, outline=OUTL if ol else None, width=s.ow)
    def poly(s, pts, fill, ol=True):
        q = [(s.X(a), s.Y(b)) for a, b in pts]
        s.d.polygon(q, fill=fill)
        if ol: s.d.line(q + [q[0]], fill=OUTL, width=s.ow, joint="curve")
    def line(s, pts, fill=OUTL, w=2):
        s.d.line([(s.X(a), s.Y(b)) for a, b in pts], fill=fill, width=max(2, int(w * s.k)), joint="curve")
    def grad(s, a, b, c, e, c1, c2, ol=True, r=0):
        x0, y0, x1, y1 = int(s.X(a)), int(s.Y(b)), int(s.X(c)), int(s.Y(e))
        n = max(1, y1 - y0)
        for i in range(n):
            s.d.line([(x0, y0 + i), (x1, y0 + i)], fill=mix(c1, c2, i / n))
        if ol: s.d.rectangle([x0, y0, x1, y1], outline=OUTL, width=s.ow)
    def pie(s, a, b, c, e, st, en, fill):
        s.d.pieslice([s.X(a), s.Y(b), s.X(c), s.Y(e)], st, en, fill=fill, outline=OUTL, width=s.ow)
    def anchor(s, kind, u, v, *extra): s.anchors.append((kind, s.X(u), s.Y(v), s.k) + extra)
    def shadow(s, w):
        s.d.ellipse([s.X(-w), s.Y(-14), s.X(w), s.Y(26)], fill=(0, 0, 0, 80))

# ------------------------------------------------------------------ éléments communs
def win(p, cx, cy, w, h, lit=True, rnd=False, frame=(250, 250, 245)):
    if lit: p.anchor("glow", cx, cy, w, h)
    glass = [(255, 226, 130), (255, 190, 90)] if lit else [(150, 195, 235), (90, 140, 200)]
    if rnd:
        p.ell(cx - w / 2 - 4, cy - h / 2 - 4, cx + w / 2 + 4, cy + h / 2 + 4, frame)
        p.ell(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, glass[0])
    else:
        p.rect(cx - w / 2 - 4, cy - h / 2 - 4, cx + w / 2 + 4, cy + h / 2 + 4, frame)
        p.grad(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, glass[0], glass[1], ol=False)
        p.line([(cx, cy - h / 2), (cx, cy + h / 2)], OUTL, 1.4); p.line([(cx - w / 2, cy), (cx + w / 2, cy)], OUTL, 1.4)
        p.line([(cx - w / 2 + 5, cy - h / 2 + 12), (cx - w / 2 + 14, cy - h / 2 + 5)], (255, 255, 255, 200), 1.6)

def door(p, cx, w=44, h=84, c=(120, 72, 42), arch=True):
    p.rr(cx - w / 2, -h, cx + w / 2, 0, 16 if arch else 2, c)
    p.rr(cx - w / 2 + 8, -h + 10, cx + w / 2 - 8, -h / 2 - 4, 8, dk(c, .82), ol=False)
    p.ell(cx + w / 2 - 14, -h / 2 + 4, cx + w / 2 - 6, -h / 2 + 12, (250, 205, 70), ol=False)

def shingles(p, pts, c, rows=6):
    (x0, y0), (x1, y1), (xt, yt) = pts
    p.poly(pts, c)
    for i in range(1, rows):
        f = i / rows
        ya = y0 + (yt - y0) * f
        xa = x0 + (xt - x0) * f; xb = x1 + (xt - x1) * f
        p.line([(xa, ya), (xb, ya)], dk(c, .75), .9)
    p.poly([(xt, yt), (x1, y1), (xt + (x1 - xt) * .45, (y1 + yt) / 2 + 10)], dk(c, .86), ol=False)

def smoke(p, cx, cy, n=4):
    for i in range(n):
        r = 14 + i * 6
        p.ell(cx - r + i * 8, cy - 30 - i * 34 - r, cx + r + i * 8, cy - 30 - i * 34 + r, (235, 235, 240, 190 - i * 35), ol=False)

def heart(p, cx, cy, r, c):
    p.ell(cx - r, cy - r, cx, cy, c, ol=False); p.ell(cx, cy - r, cx + r, cy, c, ol=False)
    p.poly([(cx - r, cy - r * .35), (cx + r, cy - r * .35), (cx, cy + r * .9)], c, ol=False)

def star(p, cx, cy, r, c):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * .45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    p.poly(pts, c)

def crescent(p, cx, cy, r, c=(245, 205, 70)):
    out = [(cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a))) for a in range(60, 301, 8)]
    r2 = .872 * r; dx = .4 * r
    inn = [(cx + dx + r2 * math.cos(math.radians(a)), cy - r2 * math.sin(math.radians(a))) for a in range(277, 82, -8)]
    p.poly(out + inn, c)

def palm(p, cx, h=300):
    p.poly([(cx - 10, 0), (cx + 10, 0), (cx + 26, -h), (cx + 8, -h)], (150, 100, 60))
    for a, l in ((-160, 110), (-120, 120), (-70, 120), (-20, 110), (-200, 90), (10, 80)):
        ex = cx + 16 + l * math.cos(math.radians(a)); ey = -h + l * math.sin(math.radians(a)) * .6 + 24
        p.poly([(cx + 14, -h), (ex, ey - 16), (ex + 8, ey + 4)], (52, 150, 60))
    p.ell(cx + 8, -h - 6, cx + 30, -h + 14, (120, 80, 40), ol=False)

def pine(p, cx, h=240, snow=False):
    p.rect(cx - 9, -26, cx + 9, 0, (100, 66, 40))
    for i in range(4):
        w = 70 - i * 14; y = -26 - i * h / 4
        p.poly([(cx - w, y), (cx + w, y), (cx, y - h / 3)], (34, 110, 60))
        if snow: p.poly([(cx - w * .45, y - h / 6), (cx + w * .45, y - h / 6), (cx, y - h / 3)], (245, 248, 255), ol=False)

def dog(p, cx, col=(222, 170, 80), flip=1):
    f = flip
    p.ell(cx - 60 * f - 40, -92, cx - 60 * f + 40, -34, col)                      # body
    for lx in (-40, -16, 24, 46): p.rr(cx + lx * f - 8, -48, cx + lx * f + 8, 0, 6, dk(col, .9))
    p.ell(cx + 6 * f, -130, cx + 66 * f if f > 0 else cx - 66, -76, col)           # head
    p.ell(cx + 40 * f - 16, -124, cx + 40 * f + 16, -100, dk(col, .8), ol=False) if False else None
    sx = cx + 54 * f
    p.ell(sx - 18, -112, sx + 18, -88, mix(col, (255, 255, 255), .25))             # museau
    p.ell(sx + 6 * f - 7, -112, sx + 6 * f + 7, -102, OUTL, ol=False)
    p.ell(cx + 36 * f - 5, -118, cx + 36 * f + 5, -108, OUTL, ol=False)
    p.ell(cx + 14 * f - 12, -126, cx + 14 * f + 12, -80, dk(col, .78))             # oreille
    p.poly([(cx - 96 * f, -76), (cx - 126 * f, -112), (cx - 112 * f, -64)], col)   # queue

def pool(p, x0, y0, x1, y1):
    p.rr(x0 - 10, y0 - 8, x1 + 10, y1 + 8, 22, (240, 240, 240))
    p.grad(x0, y0, x1, y1, (110, 220, 245), (30, 140, 210), ol=False)
    p.rr(x0, y0, x1, y1, 18, None, ol=True) if False else None
    for i in range(5):
        xx = x0 + 20 + i * (x1 - x0 - 40) / 4
        p.line([(xx, y0 + 14 + (i % 2) * 8), (xx + 26, y0 + 14 + (i % 2) * 8)], (255, 255, 255, 190), 1.4)
    p.line([(x1 - 40, y0 - 16), (x1 - 40, y0 + 18)], (200, 205, 215), 2); p.line([(x1 - 22, y0 - 16), (x1 - 22, y0 + 18)], (200, 205, 215), 2)

# ------------------------------------------------------------------ styles
def villa(p, **o):
    p.shadow(300)
    p.grad(-200, -140, 200, 0, (250, 250, 252), (212, 216, 226)); p.grad(-135, -262, 160, -140, (246, 246, 250), (205, 210, 222))
    p.rect(-218, -154, 218, -138, (60, 66, 82)); p.rect(-152, -276, 178, -260, (60, 66, 82))
    p.rect(120, -140, 200, 0, (172, 124, 80))                                      # bardage bois
    for i in range(7): p.line([(120, -130 + i * 19), (200, -130 + i * 19)], (130, 90, 55), .9)
    for cx in (-120, -40): win(p, cx, -72, 70, 110, lit=True)
    win(p, 30, -72, 56, 110, lit=True)
    p.grad(-110, -240, 140, -160, (150, 200, 240), (80, 140, 205))
    for xx in (-60, 10, 80): p.line([(xx, -240), (xx, -160)], OUTL, 1.4)
    p.line([(-95, -168), (-70, -236)], (255, 255, 255, 190), 2); p.line([(30, -168), (55, -236)], (255, 255, 255, 190), 2)
    p.rect(-218, -154, -135, -148, (230, 230, 235), ol=False)
    for i in range(9): p.line([(-214 + i * 10, -150), (-214 + i * 10, -190)], (90, 96, 112), .8)
    door(p, 160, 38, 90, (60, 66, 82), arch=False)
    palm(p, 270); palm(p, -270, 250)
    if o.get("lake"):
        p.ell(-330, 20, 330, 150, (60, 160, 215)); p.ell(-300, 34, 300, 130, (110, 205, 240), ol=False)
        p.poly([(180, 18), (240, 18), (300, -120), (270, -120)], (250, 120, 60)); p.poly([(240, 18), (260, 18), (330, 30), (300, 40)], (250, 200, 60), ol=False)
        p.rect(268, -126, 306, -118, (200, 200, 210)); p.ell(-120, 64, -50, 100, (255, 90, 110)); p.ell(-98, 72, -72, 92, (110, 205, 240), ol=False)
        p.ell(-10, 70, 70, 106, (250, 220, 70)); p.ell(100, 60, 150, 92, (255, 255, 255))
        p.ell(-250, 50, -190, 90, (255, 160, 60)); p.ell(-240, 58, -200, 82, (110, 205, 240), ol=False)
        p.rr(-210, 112, -150, 140, 14, (170, 220, 240)); p.ell(-200, 100, -190, 112, (255, 255, 255), ol=False)
    elif o.get("pool", True):
        pool(p, -170, 34, 90, 100)
        p.rr(112, 40, 190, 58, 6, (250, 250, 250)); p.rr(112, 64, 190, 82, 6, (250, 250, 250))
        p.ell(-40, 42, -10, 60, (255, 120, 120), ol=False)

def pastel(p, wall=(196, 160, 232), dogcol=(222, 170, 80), with_dog=True, **o):
    p.shadow(250)
    roof = dk(wall, .72)
    p.grad(-130, -190, 130, 0, mix(wall, WHITE, .35), wall)
    shingles(p, [(-170, -190), (170, -190), (0, -340)], roof, 6)
    p.rect(70, -330, 108, -240, dk(wall, .8)); smoke(p, 90, -330); p.anchor('smoke', 90, -330)
    win(p, 0, -278, 56, 56, True, rnd=True)
    win(p, -70, -120, 56, 62); win(p, 70, -120, 56, 62)
    for cx in (-70, 70): p.rr(cx - 34, -92, cx + 34, -78, 4, (236, 120, 160)); [heart(p, cx - 18 + i * 18, -96, 8, (255, 150, 190)) for i in range(3)]
    door(p, 0, 46, 92, (250, 245, 250))
    for i in range(7):
        xx = -250 + i * 24
        p.rect(xx, -52, xx + 14, 0, WHITE); p.poly([(xx, -52), (xx + 14, -52), (xx + 7, -66)], WHITE)
    if with_dog: dog(p, 230, dogcol, 1)

def gingerbread(p, **o):
    p.shadow(260)
    p.grad(-140, -190, 140, 0, (196, 128, 72), (160, 98, 52))
    p.poly([(-180, -190), (180, -190), (0, -330)], (176, 108, 60))
    for i in range(10):
        xx = -170 + i * 36; p.ell(xx, -206, xx + 38, -168, WHITE, ol=False)
    for i, c in enumerate([(240, 70, 80), (80, 200, 100), (250, 210, 60), (90, 160, 250)] * 3):
        a = -.9 + i * .16; p.ell(-88 + i * 14 - 8, -222 - (i % 4) * 22 - 8, -88 + i * 14 + 8, -222 - (i % 4) * 22 + 8, c)
    p.line([(-176, -192), (0, -330), (176, -192)], WHITE, 3)
    win(p, -70, -120, 56, 60, frame=WHITE); win(p, 70, -120, 56, 60, frame=WHITE)
    door(p, 0, 50, 96, (92, 52, 34))
    for sx in (-170, 170):
        p.rect(sx - 8, -150, sx + 8, 0, WHITE)
        for i in range(5): p.poly([(sx - 8, -i * 30), (sx + 8, -i * 30 - 14), (sx + 8, -i * 30 - 24), (sx - 8, -i * 30 - 10)], (235, 50, 60), ol=False)
    for lx in (-250, 250):
        p.rect(lx - 4, -70, lx + 4, 0, (240, 240, 240)); p.ell(lx - 28, -118, lx + 28, -62, [(255, 120, 170), (120, 200, 255)][lx > 0])

def sausage(p, **o):
    p.shadow(280)
    p.rr(-220, -190, 220, 0, 95, (188, 82, 52))
    p.rr(-210, -182, 200, -90, 80, (210, 108, 70), ol=False)
    for i in range(-5, 6): p.line([(i * 38 - 14, -176), (i * 38 + 22, -20)], (110, 46, 30, 150), 2.2)
    pts = [(-190 + i * 20, -196 - (10 if i % 2 else -4)) for i in range(20)]
    p.line(pts, (245, 205, 50), 5)
    win(p, -120, -110, 54, 54, True, rnd=True); win(p, 120, -110, 54, 54, True, rnd=True)
    door(p, 0, 54, 96, (96, 56, 36))
    p.rect(150, -240, 186, -182, (120, 120, 130)); smoke(p, 168, -240); p.anchor('smoke', 168, -240)

def honey(p, **o):
    p.shadow(250)
    p.grad(-130, -170, 130, 0, (255, 218, 90), (238, 178, 40))
    p.pie(-175, -420, 175, -60, 180, 360, (176, 110, 50))
    p.ell(-170, -396, -100, -330, (176, 110, 50)); p.ell(100, -396, 170, -330, (176, 110, 50))
    p.ell(-150, -378, -120, -350, (240, 200, 160), ol=False); p.ell(120, -378, 150, -350, (240, 200, 160), ol=False)
    for i, (xx, hh) in enumerate([(-140, 40), (-80, 70), (-20, 30), (40, 60), (100, 44)]):
        p.rr(xx - 18, -170, xx + 18, -170 + hh, 14, (255, 200, 40), ol=False)
    p.rect(-130, -170, 130, -160, (255, 200, 40), ol=False)
    win(p, -70, -96, 52, 52, True, rnd=True); win(p, 70, -96, 52, 52, True, rnd=True)
    door(p, 0, 54, 90, (140, 80, 40))
    p.rr(160, -80, 232, 0, 20, (200, 130, 60)); p.rect(160, -86, 232, -70, (255, 200, 40)); p.rr(172, -72, 220, -50, 6, (255, 244, 220), ol=False)
    for i in range(3): p.ell(-210 + i * 30, -24 - (i % 2) * 8, -190 + i * 30, -4 - (i % 2) * 8, (250, 220, 70))

def unicorn(p, **o):
    p.shadow(260)
    for i, c in enumerate([(240, 70, 70), (250, 160, 50), (250, 225, 70), (90, 200, 100), (80, 150, 250), (170, 100, 230)]):
        r = 330 - i * 22; p.d.arc([p.X(-r), p.Y(-r - 40), p.X(r), p.Y(r - 40)], 180, 360, fill=c, width=int(22 * p.k))
    p.grad(-130, -190, 130, 0, (255, 220, 240), (250, 170, 214))
    shingles(p, [(-165, -190), (165, -190), (0, -320)], (190, 130, 240), 6)
    p.poly([(-12, -320), (12, -320), (0, -410)], (250, 215, 80)); p.line([(-9, -340), (8, -352)], WHITE, 2); p.line([(-6, -366), (6, -378)], WHITE, 2)
    p.poly([(-50, -300), (-24, -300), (-44, -350)], (250, 200, 230)); p.poly([(50, -300), (24, -300), (44, -350)], (250, 200, 230))
    star(p, -70, -120, 34, (255, 235, 120)); star(p, 70, -120, 34, (255, 235, 120))
    door(p, 0, 48, 92, (255, 255, 255))
    for cx, cy in ((-230, -300), (230, -260)):
        p.ell(cx - 50, cy - 20, cx + 50, cy + 20, (255, 255, 255), ol=False); p.ell(cx - 30, cy - 40, cx + 30, cy, (255, 255, 255), ol=False)

def treehouse(p, **o):
    p.shadow(220)
    p.poly([(-50, 0), (50, 0), (36, -330), (-36, -330)], (120, 80, 48))
    p.poly([(-30, -240), (-170, -300), (-170, -270), (-20, -200)], (120, 80, 48))
    for cx, cy, r in ((-120, -420, 130), (0, -500, 160), (130, -420, 130), (-30, -380, 120), (60, -360, 100)):
        p.ell(cx - r, cy - r * .8, cx + r, cy + r * .8, (62, 150, 60))
    p.rect(-120, -290, 120, -272, (160, 110, 60))
    p.grad(-100, -380, 100, -290, (210, 160, 100), (176, 124, 70))
    for i in range(1, 6): p.line([(-100, -290 - i * 15), (100, -290 - i * 15)], (140, 96, 52), .9)
    shingles(p, [(-125, -380), (125, -380), (0, -450)], (190, 70, 50), 3)
    win(p, -45, -340, 40, 40); door(p, 50, 38, 62, (96, 56, 36))
    p.line([(70, -272), (84, -20)], (200, 170, 110), 2); p.line([(100, -272), (110, -20)], (200, 170, 110), 2)
    for i in range(6): p.line([(78 + i * 5, -250 + i * 40), (104 + i * 2, -250 + i * 40)], (160, 110, 60), 3)
    p.line([(-100, -450), (-100, -520)], (110, 70, 40), 3); p.anchor('flag', -100, -520, (240, 70, 70))

def bunker(p, **o):
    p.shadow(300)
    p.pie(-250, -300, 250, 190, 180, 360, (140, 142, 150))
    p.pie(-210, -250, 210, 150, 180, 360, (166, 168, 176))
    p.pie(-250, -300, 250, -170, 180, 360, (70, 130, 60)); p.pie(-228, -278, 228, -190, 180, 360, (88, 150, 70))
    p.rect(-250, -50, 250, 0, (140, 142, 150))
    p.rr(-52, -150, 52, 0, 8, (80, 86, 96)); p.ell(-24, -112, 24, -64, (110, 116, 128)); p.line([(-24, -88), (24, -88)], OUTL, 2); p.line([(0, -112), (0, -64)], OUTL, 2)
    for xx in (-170, 170):
        p.rect(xx - 30, -150, xx + 30, -110, (50, 54, 62))
        for i in range(4): p.line([(xx - 30, -146 + i * 10), (xx + 30, -146 + i * 10)], (120, 126, 138), 1.2)
    p.rect(100, -330, 112, -250, (90, 90, 98)); p.ell(86, -352, 126, -326, (255, 230, 140))
    for i in range(6): p.rr(-250 + i * 38, -34, -218 + i * 38, 0, 12, (190, 170, 120))

def sponge(p, **o):
    p.shadow(230)
    p.grad(-150, -240, 150, 0, (255, 232, 70), (240, 196, 30), r=20)
    r = random.Random(4)
    for _ in range(26):
        cx, cy, rr = r.uniform(-130, 130), r.uniform(-220, -20), r.uniform(7, 14)
        p.ell(cx - rr, cy - rr * .8, cx + rr, cy + rr * .8, (214, 170, 20), ol=False)
    win(p, -55, -160, 62, 62, True, rnd=True); win(p, 55, -160, 62, 62, True, rnd=True)
    door(p, 0, 52, 84, (130, 90, 50))
    for xx, hh in ((-200, 120), (-170, 170), (-230, 90), (200, 130), (172, 90)):
        p.poly([(xx - 12, 0), (xx + 12, 0), (xx + 6, -hh), (xx - 10, -hh)], (60, 170, 90))
    for i in range(4): p.ell(-190 + i * 22, -260 - i * 40, -160 + i * 22, -230 - i * 40, (210, 235, 255, 180))

def chalet(p, **o):
    p.shadow(280)
    p.grad(-170, -190, 170, 0, (150, 100, 58), (124, 80, 44))
    for i in range(1, 9): p.line([(-170, -i * 21), (170, -i * 21)], (96, 62, 34), 1.3)
    p.poly([(-210, -190), (210, -190), (0, -350)], (70, 56, 52))
    p.poly([(-196, -200), (196, -200), (150, -240), (-150, -240)], (250, 252, 255), ol=False)
    p.poly([(-120, -270), (120, -270), (60, -310), (-60, -310)], (250, 252, 255), ol=False)
    p.rect(98, -330, 140, -200, (150, 150, 158))
    for i in range(5): p.line([(98, -330 + i * 26), (140, -330 + i * 26)], (110, 110, 118), 1)
    smoke(p, 118, -330); p.anchor('smoke', 118, -330)
    win(p, -80, -110, 70, 66, True)
    p.ell(-114, -146, -46, -74, (255, 150, 60, 120), ol=False)
    door(p, 60, 52, 94, (92, 56, 34))
    pine(p, -250, 200, True); pine(p, 250, 170, True)

def banana(p, **o):
    p.shadow(280)
    n = 30; top = []; bot = []
    for i in range(n + 1):
        x = -230 + i * 460 / n; c = -60 - 100 * (x / 230) ** 2
        top.append((x, c - 62)); bot.append((x, c + 60))
    p.poly(top + bot[::-1], (255, 226, 60))
    p.poly(top[:n // 3] + [(x, y + 24) for x, y in top[:n // 3]][::-1], (255, 244, 150), ol=False)
    for i in range(2, n - 1, 4): p.line([top[i], (top[i][0], top[i][1] + 14)], (200, 150, 30), 1)
    p.ell(-250, -190, -216, -150, (110, 70, 30)); p.ell(216, -190, 250, -150, (110, 70, 30))
    for cx in (-120, 120):
        c = -60 - 100 * (cx / 230) ** 2; win(p, cx, c - 4, 46, 50, True, rnd=True)
    door(p, 0, 50, 84, (130, 90, 40))

def egg(p, **o):
    p.shadow(220)
    p.ell(-150, -330, 150, 0, (120, 70, 44))
    p.ell(-120, -310, 60, -140, (150, 96, 64, 140), ol=False)
    pts = []
    for i in range(14): pts.append((-136 + i * 20.9, -170 + (14 if i % 2 else -14)))
    p.poly(pts + [(x, y + 36) for x, y in pts[::-1]], (255, 255, 255), ol=True)
    win(p, -50, -250, 52, 52, True, rnd=True); win(p, 50, -250, 52, 52, True, rnd=True)
    door(p, 0, 50, 90, (250, 230, 190))
    p.ell(160, -80, 230, 0, (250, 200, 50)); p.line([(165, -40), (225, -40)], OUTL, 1.4)

def speculoos(p, **o):
    p.shadow(250)
    p.grad(-150, -210, 150, 0, (190, 118, 60), (160, 94, 44))
    r = random.Random(8)
    for _ in range(40): p.ell(x := r.uniform(-140, 140), y := r.uniform(-200, -10), x + 5, y + 5, (130, 74, 34), ol=False)
    for i in range(10): p.ell(-150 + i * 30, -232, -120 + i * 30, -190, (176, 106, 52))
    p.rect(-150, -212, 150, -196, (176, 106, 52), ol=False)
    for cx in (-80, 80):
        p.rr(cx - 32, -150, cx + 32, -74, 22, (110, 62, 28)); p.rr(cx - 24, -142, cx + 24, -80, 18, (255, 214, 120))
    door(p, 0, 50, 88, (92, 52, 28))
    p.rr(-180, -34, -120, 0, 8, (255, 230, 170)); p.rr(120, -34, 180, 0, 8, (255, 230, 170))

def napolitain(p, **o):
    p.shadow(260)
    cols = [(110, 64, 40), (255, 244, 230), (250, 170, 190), (255, 244, 230), (110, 64, 40)]
    for i, c in enumerate(cols):
        p.grad(-160, -(i + 1) * 54, 160, -i * 54, mix(c, WHITE, .12), c)
    for i in range(1, 4): p.line([(-160, -i * 54), (160, -i * 54)], dk(cols[i], .7), 1.2)
    win(p, -90, -80, 46, 36); win(p, 90, -80, 46, 36); win(p, -90, -190, 46, 36); win(p, 90, -190, 46, 36)
    door(p, 0, 54, 100, (255, 244, 230))
    for i in range(6): p.ell(-130 + i * 52, -300, -90 + i * 52, -252, WHITE)
    p.ell(-18, -340, 18, -296, (230, 30, 60)); p.line([(0, -340), (14, -366)], (60, 140, 60), 2)

def tacos(p, **o):
    p.shadow(260)
    p.pie(-210, -420, 210, 0, 180, 360, (244, 196, 80)); p.rect(-210, -210, 210, 0, (244, 196, 80), ol=True)
    p.pie(-190, -400, 190, -20, 180, 360, (252, 214, 110)); p.rect(-190, -210, 190, -4, (252, 214, 110), ol=False)
    r = random.Random(3)
    for i in range(16):
        a = math.radians(188 + i * 10.2); cx = 200 * math.cos(a); cy = -210 + 205 * math.sin(a)
        p.ell(cx - 24, cy - 24, cx + 24, cy + 24, [(70, 170, 60), (60, 150, 50)][i % 2])
    for cx, cy, c in ((-110, -380, (230, 50, 40)), (-30, -420, (150, 90, 50)), (60, -415, (230, 50, 40)), (130, -370, (250, 190, 40)), (10, -400, (250, 190, 40))):
        p.ell(cx - 22, cy - 22, cx + 22, cy + 22, c)
    win(p, -100, -150, 54, 54, True, rnd=True); win(p, 100, -150, 54, 54, True, rnd=True)
    door(p, 0, 54, 96, (120, 70, 40))

def pizza(p, **o):
    p.shadow(260)
    p.ell(-190, -380, 190, 0, (224, 164, 82))
    p.ell(-166, -356, 166, -24, (252, 196, 70))
    p.ell(-166, -356, 166, -24, (255, 214, 100, 120), ol=False)
    for cx, cy in ((-90, -280), (40, -300), (100, -200), (-110, -170), (-20, -230), (60, -100), (-60, -90)):
        p.ell(cx - 26, cy - 22, cx + 26, cy + 22, (200, 50, 40)); p.ell(cx - 10, cy - 10, cx + 4, cy, (225, 90, 70), ol=False)
    for cx, cy in ((-40, -330), (110, -270), (-140, -230)):
        p.poly([(cx, cy), (cx + 20, cy - 24), (cx + 40, cy)], (60, 150, 60))
    for cx, cy in ((-120, -110), (90, -150), (20, -170)): p.ell(cx - 9, cy - 9, cx + 9, cy + 9, (40, 40, 44), ol=False)
    p.rr(-38, -110, 38, -24, 22, (110, 66, 40)); win(p, -90, -240, 44, 44, True, rnd=True)

def choco(p, **o):
    p.shadow(300)
    p.grad(-170, -210, 70, 0, (110, 66, 40), (82, 46, 28))
    for i in range(1, 4): p.line([(-170 + i * 60, -210), (-170 + i * 60, 0)], (60, 32, 20), 1.6)
    for i in range(1, 3): p.line([(-170, -i * 70), (70, -i * 70)], (60, 32, 20), 1.6)
    win(p, -110, -150, 44, 50); door(p, 10, 50, 94, (60, 34, 22))
    p.poly([(-180, -210), (80, -210), (-50, -300)], (250, 240, 226))
    fx = 190
    p.rr(fx - 90, -30, fx + 90, 0, 8, (200, 200, 208)); p.ell(fx - 80, -62, fx + 80, -16, (92, 50, 30))
    p.rect(fx - 12, -240, fx + 12, -50, (200, 200, 208)); p.ell(fx - 56, -150, fx + 56, -120, (92, 50, 30)); p.ell(fx - 36, -240, fx + 36, -212, (92, 50, 30)); p.ell(fx - 18, -300, fx + 18, -270, (120, 70, 40))
    for dx in (-44, 0, 44): p.rr(fx + dx - 6, -140, fx + dx + 6, -70, 6, (120, 70, 40), ol=False)
    for dx in (-26, 26): p.rr(fx + dx - 5, -230, fx + dx + 5, -170, 5, (120, 70, 40), ol=False)
    for cx, c in ((fx - 60, (230, 50, 60)), (fx + 40, (250, 190, 70))): p.ell(cx - 14, -20, cx + 14, 6, c)

def kitty(p, **o):
    p.shadow(250)
    p.grad(-140, -190, 140, 0, (255, 222, 236), (250, 180, 210))
    p.pie(-180, -330, 180, -50, 180, 360, (255, 150, 190))
    p.poly([(-150, -300), (-90, -300), (-140, -380)], (255, 150, 190)); p.poly([(150, -300), (90, -300), (140, -380)], (255, 150, 190))
    p.poly([(-135, -312), (-100, -312), (-132, -356)], (255, 220, 235), ol=False); p.poly([(135, -312), (100, -312), (132, -356)], (255, 220, 235), ol=False)
    p.ell(-70, -260, -10, -220, (230, 40, 90)); p.ell(10, -260, 70, -220, (230, 40, 90)); p.ell(-16, -250, 16, -226, (250, 90, 140))
    win(p, -80, -120, 56, 56, True, rnd=True); win(p, 80, -120, 56, 56, True, rnd=True)
    for sy in (-110, -90, -70):
        p.line([(-150, sy), (-118, sy + (sy + 90) * .15)], (120, 60, 90), 1.2); p.line([(150, sy), (118, sy + (sy + 90) * .15)], (120, 60, 90), 1.2)
    door(p, 0, 48, 90, (255, 255, 255)); heart(p, 0, -50, 14, (240, 60, 120))

def poupee(p, **o):
    p.shadow(320)
    p.grad(-230, -200, 230, 0, (255, 190, 222), (244, 140, 190)); p.grad(-170, -330, 170, -200, (255, 200, 228), (246, 156, 200))
    p.rect(-250, -214, 250, -198, (255, 255, 255)); p.rect(-190, -344, 190, -328, (255, 255, 255))
    for cx in (-120, 0, 120): p.rect(cx - 10, -200, cx + 10, 0, WHITE)
    for cx in (-170, -60, 60, 170): win(p, cx, -100, 50, 70, True, frame=WHITE)
    heart(p, 0, -250, 34, (255, 255, 255)); win(p, -110, -270, 44, 56, True, frame=WHITE); win(p, 110, -270, 44, 56, True, frame=WHITE)
    door(p, 0, 50, 100, (255, 255, 255)); p.line([(0, -344), (0, -410)], (110, 110, 118), 3); p.anchor('flag', 0, -410, (240, 60, 130))
    pool(p, 90, 34, 250, 90); star(p, -170, 56, 30, (255, 235, 120))

def musique(p, **o):
    p.shadow(280)
    p.grad(-160, -210, 160, 0, (44, 44, 54), (24, 24, 32))
    p.poly([(-190, -210), (190, -210), (160, -250), (-160, -250)], (250, 205, 60))
    p.ell(-70, -190, 70, -50, (14, 14, 18)); p.ell(-24, -140, 24, -100, (230, 60, 80), ol=False)
    for r in (62, 50): p.d.ellipse([p.X(-r), p.Y(-120 - r * .96), p.X(r), p.Y(-120 + r * .96)], outline=(70, 70, 80), width=2)
    for i, cx in enumerate((-130, 130, -128, 128)): star(p, cx, -170 + (i // 2) * 90, 22, (250, 205, 60))
    door(p, 0, 50, 70, (250, 205, 60)) if False else None
    p.rr(-24, -60, 24, 0, 8, (250, 205, 60))
    for xx, c in ((-200, (250, 205, 60, 70)), (200, (250, 205, 60, 70))):
        p.poly([(xx, 0), (xx + (-80 if xx < 0 else 80), -330), (xx + (-20 if xx < 0 else 20), -330)], c, ol=False)
    for cx, cy in ((-250, -150), (240, -110)): p.ell(cx - 14, cy - 10, cx + 4, cy + 6, (250, 205, 60)); p.line([(cx + 3, cy - 4), (cx + 3, cy - 50)], (250, 205, 60), 2)

def capybara(p, **o):
    p.shadow(300)
    p.pie(-170, -330, 170, 10, 180, 360, (176, 124, 84)); p.rect(-170, -160, 170, 0, (176, 124, 84)); p.pie(-150, -310, 150, -10, 180, 360, (196, 146, 100))
    p.rect(-170, -160, 170, 0, (176, 124, 84), ol=True)
    win(p, -80, -130, 50, 50, True, rnd=True); door(p, 40, 52, 92, (96, 60, 36))
    p.ell(60, -330, 140, -290, (84, 150, 60)); p.ell(-120, -300, -50, -270, (84, 150, 60))
    cx = 260; cb = (150, 104, 64)
    p.ell(cx - 90, -120, cx + 70, -30, cb)
    for lx in (-60, -20, 30, 54): p.rr(cx + lx - 10, -44, cx + lx + 10, 0, 6, dk(cb, .85))
    p.rr(cx + 40, -140, cx + 112, -84, 24, cb); p.ell(cx + 100, -126, cx + 120, -102, dk(cb, .7))
    p.ell(cx + 74, -134, cx + 84, -124, OUTL, ol=False); p.ell(cx + 46, -148, cx + 62, -130, dk(cb, .8)); p.ell(cx + 64, -146, cx + 76, -136, OUTL, ol=False) if False else None
    p.ell(-300, -20, -210, 16, (96, 170, 220)); p.ell(-286, -22, -262, -8, (84, 150, 60), ol=False)

def poulailler(p, **o):
    p.shadow(280)
    p.grad(-170, -170, 170, 0, (206, 62, 52), (170, 40, 40))
    p.poly([(-190, -170), (190, -170), (150, -250), (0, -310), (-150, -250)], (120, 36, 34))
    p.line([(-190, -170), (-150, -250), (0, -310), (150, -250), (190, -170)], OUTL, 2)
    p.rect(-62, -150, 62, 0, (250, 244, 240)); p.line([(-62, -150), (62, 0)], (206, 62, 52), 3); p.line([(62, -150), (-62, 0)], (206, 62, 52), 3)
    win(p, -118, -110, 44, 44); win(p, 118, -110, 44, 44)
    p.ell(-52, -432, 54, -330, (252, 252, 252)); p.ell(-98, -400, -40, -350, (240, 240, 244)); p.poly([(30, -410), (66, -400), (36, -390)], (250, 160, 40))
    p.ell(40, -418, 50, -408, OUTL, ol=False); p.ell(-6, -450, 40, -420, (230, 40, 50), ol=False)
    for xx in (-20, 14): p.line([(xx, -334), (xx, -312)], (250, 160, 40), 3)
    for i in range(5): p.line([(190 + i * 8, 0), (210 + i * 9, -50 - (i % 2) * 10)], (236, 196, 70), 3)
    p.ell(210, -60, 270, 0, (236, 196, 70))

def mosque(p, **o):
    p.shadow(360)
    cream = (246, 238, 220); teal = (40, 150, 150)
    for mx in (-250, 250):                                        # minarets
        p.grad(mx - 24, -470, mx + 24, 0, (255, 250, 238), (216, 206, 184))
        p.rect(mx - 38, -400, mx + 38, -380, (200, 190, 168)); p.rect(mx - 38, -300, mx + 38, -286, (200, 190, 168))
        p.poly([(mx - 30, -470), (mx + 30, -470), (mx, -580)], teal)
        p.line([(mx, -580), (mx, -616)], (245, 205, 70), 2); crescent(p, mx, -632, 18)
        p.rr(mx - 8, -360, mx + 8, -322, 8, (60, 90, 110), ol=False)
    p.pie(-130, -460, 130, -140, 180, 360, teal)                  # grand dôme
    p.pie(-100, -430, 100, -170, 180, 360, (70, 180, 176))
    p.line([(0, -460), (0, -500)], (245, 205, 70), 2); crescent(p, 0, -518, 20)
    p.grad(-180, -300, 180, 0, (252, 246, 232), (226, 214, 190))
    p.rect(-196, -316, 196, -296, (216, 204, 180))
    for sx in (-150, 150): p.pie(sx - 50, -400, sx + 50, -240, 180, 360, (70, 180, 176))
    p.rect(-100, -300, 100, -250, (240, 230, 208), ol=False)
    for cx in (-120, -60, 60, 120):
        p.rr(cx - 20, -250, cx + 20, -120, 20, (50, 90, 130)); p.rr(cx - 12, -238, cx + 12, -128, 14, (255, 214, 120, 220), ol=False)
    p.rr(-34, -200, 34, 0, 34, (250, 236, 200)); p.rr(-22, -186, 22, 0, 22, (110, 72, 44))
    p.d.arc([p.X(-48), p.Y(-216), p.X(48), p.Y(-110)], 180, 360, fill=teal, width=int(5 * p.k))
    for i in range(7): p.ell(-130 + i * 40, -20, -110 + i * 40, 6, (84, 150, 60), ol=False)

def commissariat(p, **o):
    from base import font
    p.shadow(340)
    p.grad(-200, -240, 200, 0, (226, 232, 244), (178, 188, 210))
    p.rect(-216, -262, 216, -236, (30, 50, 110)); p.rect(-216, -262, 216, -250, (60, 90, 170), ol=False)
    p.rr(-130, -214, 130, -150, 10, (30, 50, 110))
    p.d.text((p.X(0), p.Y(-182)), "POLICE", font=font(int(54 * p.k)), fill=(255, 255, 255), anchor="mm")
    for cx in (-135, 135):
        win(p, cx, -80, 64, 90, True)
        for i in (-1, 0, 1): p.line([(cx + i * 18, -125), (cx + i * 18, -35)], (60, 60, 70), 1.1)
    door(p, 0, 76, 110, (40, 60, 130), arch=False); p.ell(-12, -104, 12, -88, (255, 255, 255), ol=False)
    p.rect(-12, -300, 12, -262, (140, 140, 150)); p.anchor('siren', 0, -311); p.ell(-34, -330, 34, -292, (60, 120, 255)); p.ell(-18, -318, 18, -300, (160, 200, 255), ol=False)
    p.line([(-170, -262), (-170, -400)], (130, 130, 140), 2.4); p.anchor('flag', -170, -400, (40, 80, 200))
    p.rect(-30, -60, 30, -46, (250, 250, 250), ol=False)
    for i in range(8): p.rect(-216 + i * 54, -20, -176 + i * 54, 0, (250, 205, 60), ol=False)

def stade(p, **o):
    from base import font
    p.shadow(420)
    for sx in (-380, 380):
        p.rect(sx - 10, -470, sx + 10, 0, (150, 152, 160))
        p.rr(sx - 50, -540, sx + 50, -470, 8, (70, 74, 84)); p.anchor('flood', sx, -505)
        for i in range(3):
            for j in range(2): p.ell(sx - 40 + i * 30, -530 + j * 30, sx - 18 + i * 30, -510 + j * 30, (255, 244, 170), ol=False)
    p.grad(-340, -150, 340, 0, (190, 192, 200), (150, 152, 162))
    for i in range(9): p.rr(-310 + i * 74, -110, -262 + i * 74, 0, 22, (60, 64, 78))
    p.rect(-340, -150, 340, -130, (230, 60, 60), ol=False)
    p.grad(-320, -260, 320, -150, (210, 50, 50), (170, 36, 40))
    for i in range(1, 14): p.line([(-320 + i * 46, -260), (-320 + i * 46, -150)], (255, 255, 255, 190), 2)
    p.poly([(-350, -262), (350, -262), (300, -330), (-300, -330)], (245, 246, 250))
    p.rr(-210, -250, 210, -176, 12, (30, 40, 90))
    p.d.text((p.X(0), p.Y(-213)), "FC PETITBOURG", font=font(int(46 * p.k)), fill=(255, 255, 255), anchor="mm")
    p.ell(-36, -400, 36, -328, (255, 255, 255))
    for a in range(0, 360, 72):
        p.ell(-8 + 20 * math.cos(math.radians(a)) - 8, -364 + 20 * math.sin(math.radians(a)) - 8, -8 + 20 * math.cos(math.radians(a)) + 16, -364 + 20 * math.sin(math.radians(a)) + 8, (30, 30, 36), ol=False)
    p.ell(-10, -372, 10, -356, (30, 30, 36), ol=False)

def mairie(p, **o):
    from base import font
    p.shadow(400)
    cream = (240, 226, 192)
    p.grad(-330, -430, 330, 0, (246, 236, 208), (222, 204, 166))
    p.grad(-380, -300, -330, 0, (236, 222, 188), (210, 192, 154)); p.grad(330, -300, 380, 0, (236, 222, 188), (210, 192, 154))
    p.poly([(-350, -430), (350, -430), (0, -560)], (150, 56, 46)); p.poly([(0, -560), (350, -430), (120, -470)], (126, 44, 38), ol=False)
    p.ell(-46, -548, 46, -456, (255, 255, 255)); p.line([(0, -502), (0, -532)], OUTL, 1.4); p.line([(0, -502), (22, -494)], OUTL, 1.4)
    p.rr(-250, -400, 250, -330, 12, (24, 110, 56))
    p.d.text((p.X(0), p.Y(-365)), "MAIRIE DE PETITBOURG", font=font(int(40 * p.k)), fill=(255, 255, 255), anchor="mm")
    for cx in (-250, -125, 125, 250):
        win(p, cx, -260, 70, 110, True, frame=(60, 110, 190)); p.rect(cx - 52, -300, cx - 38, -206, (60, 110, 190), ol=False); p.rect(cx + 38, -300, cx + 52, -206, (60, 110, 190), ol=False)
    p.rect(-110, -300, 110, -250, (230, 214, 180), ol=False)
    for cx in (-250, -125, 125, 250): win(p, cx, -110, 70, 100, True, frame=(60, 110, 190))
    p.rr(-60, -220, 60, 0, 40, (110, 66, 40)); p.line([(0, -215), (0, 0)], OUTL, 1.4)
    for i in range(4): p.rect(-120 + i * 0, -18 + i * 0, 120, 0, (200, 196, 190)) if False else None
    p.rect(-140, -16, 140, 0, (206, 202, 196)); p.rect(-170, -8, 170, 0, (190, 186, 180))
    p.line([(-300, -430), (-300, -640)], (130, 130, 140), 2.4); p.anchor('flag', -300, -640, (40, 80, 200))
    p.line([(300, -430), (300, -640)], (130, 130, 140), 2.4); p.anchor('flag', 300, -640, (230, 50, 50))

def better_house(p, wall=(236, 220, 186), roof=(170, 60, 46), **o):
    p.shadow(230)
    p.grad(-140, -200, 140, 0, mix(wall, WHITE, .3), dk(wall, .92))
    shingles(p, [(-176, -200), (176, -200), (0, -340)], roof, 6)
    p.rect(80, -330, 118, -240, dk(wall, .78)); smoke(p, 99, -330); p.anchor('smoke', 99, -330)
    for cx in (-70, 70):
        win(p, cx, -120, 56, 66); p.rr(cx - 34, -88, cx + 34, -72, 4, (200, 70, 80))
        for i in range(3): p.ell(cx - 24 + i * 20, -100, cx - 12 + i * 20, -88, [(255, 120, 150), (250, 220, 70), (255, 140, 190)][i], ol=False)
    door(p, 0, 48, 94, (130, 78, 46)); win(p, 0, -262, 44, 44, True, rnd=True)
    for i in range(5):
        p.rect(-238 + i * 22, -48, -226 + i * 22, 0, (250, 248, 240)); p.rect(130 + i * 22, -48, 142 + i * 22, 0, (250, 248, 240))

STYLES = {"villa": villa, "pastel": pastel, "pain_depices": gingerbread, "saucisson": sausage, "miel": honey, "licorne": unicorn,
          "cabane": treehouse, "bunker": bunker, "eponge": sponge, "chalet": chalet, "banane": banana, "oeuf": egg,
          "speculoos": speculoos, "napolitain": napolitain, "tacos": tacos, "pizza": pizza, "chocolat": choco, "chat": kitty,
          "poupee": poupee, "musique": musique, "capybara": capybara, "poulailler": poulailler, "mosquee": mosque, "commissariat": commissariat, "stade": stade, "mairie": mairie, "maison": better_house}
WIDTH = {"villa": 640, "pastel": 560, "pain_depices": 540, "saucisson": 460, "miel": 500, "licorne": 700, "cabane": 460, "bunker": 520,
         "eponge": 500, "chalet": 580, "banane": 520, "oeuf": 420, "speculoos": 400, "napolitain": 380, "tacos": 440, "pizza": 420,
         "chocolat": 560, "chat": 400, "poupee": 540, "musique": 520, "capybara": 640, "poulailler": 520, "mosquee": 660, "commissariat": 520, "stade": 760, "mairie": 760, "maison": 520}

def draw_style(layer, name, x, ground, target_px, anchors=None, **opts):
    """dessine le style `name` centré en x, posé sur y=ground, large d'environ target_px (px 2x)."""
    k = target_px / WIDTH.get(name, 480)
    p = P(layer, x, ground, k)
    STYLES.get(name, better_house)(p, **opts)
    if anchors is not None: anchors.extend(p.anchors)

# ------------------------------------------------------------------ décor amélioré
def scenery(w, h, ground=2650):
    """décor de base : ciel dégradé + soleil + collines + arbres ombrés + pelouse fleurie + route. Retourne RGB (w,h)."""
    from PIL import ImageFilter
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    top, bot = (96, 170, 240), (214, 238, 252)
    for y in range(1900):
        d.line([(0, y), (w, y)], fill=mix(top, bot, y / 1900))
    glow = Image.new("RGBA", (w, 1900), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    for i in range(14):
        r = 520 - i * 34; g.ellipse([w - 380 - r, 300 - r, w - 380 + r, 300 + r], fill=(255, 240, 170, 16))
    g.ellipse([w - 520, 160, w - 240, 440], fill=(255, 244, 160, 255))
    im.paste(glow, (0, 0), glow)
    for k, (col, base, amp, ph) in enumerate([((150, 190, 200), 1560, 130, 0.0), ((110, 168, 130), 1660, 110, 1.7), ((78, 148, 84), 1760, 90, 3.1)]):
        pts = [(0, 1900)] + [(x, base - amp * (0.5 + 0.5 * math.sin(x / 380 + ph)) - amp * .25 * math.sin(x / 130 + ph)) for x in range(0, w + 40, 40)] + [(w, 1900)]
        d.polygon(pts, fill=col)
    r = random.Random(2)
    for row, (y, s, c1, c2) in enumerate([(1800, 1.5, (44, 110, 60), (64, 140, 76)), (1900, 2.0, (36, 96, 52), (56, 128, 66))]):
        x = -40
        while x < w + 40:
            rr = r.randint(55, 95) * s * .8
            d.rectangle([x - 8 * s, y - 40, x + 8 * s, y + 20], fill=(96, 62, 40))
            d.ellipse([x - rr, y - rr * 1.7, x + rr, y + rr * .2], fill=c1)
            d.ellipse([x - rr * .8, y - rr * 1.7, x + rr * .4, y - rr * .5], fill=c2)
            x += rr * 1.5
    for y in range(1900, h):
        d.line([(0, y), (w, y)], fill=mix((96, 170, 70), (62, 132, 52), (y - 1900) / (h - 1900)))
    for _ in range(420):
        x = r.randint(0, w); y = r.randint(1960, h - 20); sz = 10 + (y - 1900) / (h - 1900) * 40
        d.polygon([(x - sz * .4, y), (x + sz * .4, y), (x, y - sz * 1.5)], fill=(50, 118, 46))
    for _ in range(150):
        x = r.randint(0, w); y = r.randint(2000, h - 40); sz = 8 + (y - 1900) / (h - 1900) * 14
        c = r.choice([(255, 90, 120), (255, 220, 70), (255, 255, 255), (170, 110, 240)])
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=c); d.ellipse([x - sz * .4, y - sz * .4, x + sz * .4, y + sz * .4], fill=(255, 190, 60))
    return im

def road_strip(im, y0, y1):
    d = ImageDraw.Draw(im); w = im.width
    for y in range(y0, y1): d.line([(0, y), (w, y)], fill=mix((196, 160, 110), (170, 132, 88), (y - y0) / max(1, y1 - y0)))
    d.rectangle([0, y0 - 14, w, y0], fill=(220, 214, 200))
    r = random.Random(7)
    for _ in range(80):
        x = r.randint(0, w); y = r.randint(y0 + 10, y1 - 10); rr = r.randint(4, 14)
        d.ellipse([x - rr, y - rr * .5, x + rr, y + rr * .5], fill=(150, 116, 76))

_V = None
def vignette(W, H):
    global _V
    if _V is None:
        small = Image.new("L", (108, 192), 0); d = ImageDraw.Draw(small)
        for y in range(192):
            for x in range(108):
                dx = (x - 54) / 54; dy = (y - 96) / 96
                small.putpixel((x, y), int(max(0, (dx * dx * .55 + dy * dy * .75) - .35) * 120))
        a = small.resize((W, H), Image.BICUBIC)
        _V = Image.new("RGBA", (W, H), (20, 14, 40, 0)); _V.putalpha(a)
    return _V

def birds(fr, t):
    d = ImageDraw.Draw(fr)
    for i in range(3):
        x = (t * (70 + 15 * i) + i * 330) % 1300 - 120; y = 330 + i * 90 + math.sin(t * 2 + i) * 18
        wv = math.sin(t * 9 + i) * 8
        d.line([(x - 22, y - wv), (x, y), (x + 22, y - wv)], fill=(50, 50, 70), width=4)


def animate(fr, anchors, t, tf=lambda x, y: (x, y), kk=1.0):
    """anime fumée, drapeaux, gyrophare, projecteurs, fenêtres — anchors en px 1x."""
    d = ImageDraw.Draw(fr, "RGBA")
    for a in anchors:
        kind, x, y, k = a[:4]; x, y = tf(x, y); k = k * kk
        if kind == "smoke":
            for i in range(6):
                ph = (t * .45 + i / 6) % 1; r = (10 + 26 * ph) * k * 1.6
                cx = x + math.sin(t * 1.5 + i) * 10 * k + ph * 50 * k; cy = y - 20 * k - ph * 330 * k * .6
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(238, 238, 244, int(190 * (1 - ph))))
        elif kind == "flag":
            col = a[4]; L = 62 * k * 1.3; n = 9; top = []; bot = []
            for j in range(n + 1):
                f = j / n; off = math.sin(t * 6 - f * 4) * 9 * k * f * 1.4
                top.append((x + f * L, y + off)); bot.append((x + f * L, y + off + 34 * k * 1.3 * (1 - .15 * f)))
            d.polygon(top + bot[::-1], fill=col, outline=OUTL)
        elif kind == "siren":
            on = int(t * 4) % 2; c = (60, 120, 255) if on else (255, 60, 60); g = 15 * k
            d.ellipse([x - g, y - g, x + g, y + g], fill=c + (70,)); d.ellipse([x - g * .5, y - g * .5, x + g * .5, y + g * .5], fill=c + (130,))
        elif kind == "flood":
            g = (24 + 3 * math.sin(t * 3)) * k
            d.ellipse([x - g, y - g, x + g, y + g], fill=(255, 250, 190, 60)); d.ellipse([x - g * .5, y - g * .5, x + g * .5, y + g * .5], fill=(255, 255, 220, 90))
        elif kind == "glow":
            w, h = a[4] * k, a[5] * k; al = int(34 + 30 * math.sin(t * 2.2 + x * .013 + y * .007))
            if (t * 3 + x * .01) % 11 < .12: al = 5
            d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=(255, 238, 150, max(0, al)))
