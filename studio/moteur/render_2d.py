"""Rendu d'aperçu 2D (Pillow) — utilisé quand Blender n'est pas installé, ou pour les tests.

Il lit exactement la même mise en scène que Blender (perf.compute) et projette
les positions 3D avec la même caméra : cadrage, gestes, synchro labiale et
expressions sont identiques, seul le rendu est simplifié.
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw

from . import perf

SKY = {"jour": (156, 202, 240), "soir": (240, 160, 112), "nuit": (26, 36, 64)}
SET_COL = {  # sol, mur/fond, accent
    "restaurant": ((122, 74, 43), (232, 217, 192), (179, 58, 58)), "rue": ((109, 109, 117), (230, 184, 138), (58, 110, 165)),
    "foret": ((63, 107, 42), (47, 90, 42), (122, 90, 58)), "salon": ((138, 106, 74), (239, 226, 207), (58, 95, 138)),
    "bureau": ((90, 95, 102), (223, 227, 232), (47, 111, 214)), "manoir": ((42, 42, 51), (28, 28, 36), (201, 162, 58)),
    "plage": ((232, 210, 154), (47, 143, 207), (47, 163, 107)), "espace": ((58, 58, 72), (16, 16, 32), (90, 176, 255)),
    "classe": ((154, 122, 90), (230, 235, 216), (42, 74, 58)), "studio": ((90, 90, 102), (58, 58, 72), (255, 255, 255)),
}
INDOOR = {"restaurant", "salon", "bureau", "classe", "studio"}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


class Cam:
    def __init__(self, c, W, H):
        px, py, pz, tx, ty, tz, lens = c
        self.p = (px, py, pz)
        f = (tx - px, ty - py, tz - pz)
        n = math.sqrt(sum(v * v for v in f)) or 1
        self.f = tuple(v / n for v in f)
        r = (self.f[1], -self.f[0], 0.0)
        n = math.sqrt(r[0] ** 2 + r[1] ** 2) or 1
        self.r = (r[0] / n, r[1] / n, 0.0)
        self.u = (self.r[1] * self.f[2] - self.r[2] * self.f[1], self.r[2] * self.f[0] - self.r[0] * self.f[2], self.r[0] * self.f[1] - self.r[1] * self.f[0])
        sensor_w = 36.0 if W >= H else 36.0 * W / H
        self.k = lens / sensor_w * W
        self.W, self.H = W, H

    def proj(self, x, y, z):
        d = (x - self.p[0], y - self.p[1], z - self.p[2])
        zc = sum(a * b for a, b in zip(d, self.f))
        if zc < .05:
            return None
        xc = sum(a * b for a, b in zip(d, self.r))
        yc = sum(a * b for a, b in zip(d, self.u))
        s = self.k / zc
        return (self.W / 2 + xc * s, self.H / 2 - yc * s, s)


def _props(ri):
    """Éléments de décor simples : (type, x, y, z, w, h, couleur, émissif)."""
    r = random.Random(ri.get("seed", 1) * 13 + ri.get("variant", 0))
    name = ri.get("set", "salon")
    floor, wall, acc = SET_COL.get(name, SET_COL["salon"])
    v = ri.get("variant", 0)
    if v:
        acc = shade(acc, 1 + .15 * ((v % 3) - 1))
        wall = shade(wall, 1 - .07 * (v % 4))
    out = []
    if name == "restaurant":
        out += [("rect", wx, 4.3, 1.7, 2.4, 1.8, (255, 231, 176), True) for wx in (-5, 0, 5)]
        out += [("rect", -6 + k * 4, 3.3, 0, 1.1, .76, acc, False) for k in range(4)]
        out += [("rect", 0, .7, .72, 1.1, .06, acc, False), ("rect", 0, .7, 0, .16, .74, (58, 42, 34), False)]
    elif name == "salon":
        out += [("rect", -.2, 3.6, .2, 3.2, 1.1, acc, False), ("rect", 0, 4.3, 2.05, 2.0, 1.3, (154, 208, 255), True)]
    elif name == "bureau":
        out += [("rect", 0, 2.4, 0, 2.8, .78, (221, 214, 200), False), ("rect", 0, 2.6, .9, .9, .55, (154, 208, 255), True)]
        out += [("rect", sx, 4.1, 0, 2.4, 3.0, (106, 80, 64), False) for sx in (-6, 6)]
    elif name == "classe":
        out += [("rect", 0, 4.3, 1.3, 5, 1.8, (31, 58, 42), False)]
    elif name == "rue":
        for k in range(7):
            hgt = r.uniform(5, 11)
            out.append(("rect", -15 + k * 5, 9, 0, 4.6, hgt, r.choice([(230, 184, 138), (201, 214, 227), (241, 224, 181), (217, 163, 163)]), False))
    elif name == "foret":
        for k in range(18):
            tx, ty = r.uniform(-12, 12), r.uniform(4, 14)
            hgt = r.uniform(3, 7)
            out += [("rect", tx, ty, 0, .4, hgt, (90, 58, 34), False), ("tri", tx, ty, hgt * .55, 2.6, hgt * .8, shade(wall, r.uniform(.8, 1.2)), False)]
    elif name == "manoir":
        out += [("rect", 0, 14, 0, 12, 9, (28, 28, 36), False), ("disc", 6, 25, 13, 3.2, 3.2, (244, 241, 208), True)]
        out += [("rect", wx, 10.9, 4.2, 1, 1.6, (255, 204, 102), True) for wx in (-3, 0, 3)]
    elif name == "plage":
        out += [("disc", -8, 30, 7, 5, 5, (255, 211, 106), True)]
        out += [("rect", px, 4, 0, .3, 5.4, (138, 106, 58), False) for px in (-6, 7)]
    elif name == "espace":
        out += [("disc", r.uniform(-40, 40), 30, r.uniform(-5, 30), .25, .25, (255, 255, 255), True) for _ in range(80)]
        out += [("disc", 9, 30, 9, 10, 10, acc, False)]
    return floor, wall, out


def _ellipse(d, cx, cy, rx, ry, fill, outline=None):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline)


def _limb(d, a, b, w, fill):
    d.line([a, b], fill=fill, width=max(1, int(w)))
    _ellipse(d, b[0], b[1], w / 2, w / 2, fill)
    _ellipse(d, a[0], a[1], w / 2, w / 2, fill)


def draw_character(d, cam, c, st, keys, h, light):
    g = lambda k: st[keys[k]]  # noqa: E731
    L = c["look"]
    x, y = g("x"), g("y")
    base = cam.proj(x, y, g("bounce") * h)
    top = cam.proj(x, y, 1.8 * h + g("bounce") * h)
    if not base or not top:
        return
    s = base[2] * h  # pixels par mètre
    bx, by = base[0], base[1]
    lean = g("lean") * s * .8
    skin, hair, outfit, pants = (shade(hexrgb(L[k]), light) for k in ("skin", "hair", "outfit", "pants"))
    b = L.get("build", 1)
    walk = g("walk")
    # jambes
    for side, sx in ((-1, .13), (1, -.13)):
        hip = (bx + sx * b * s, by - .82 * s)
        foot = (hip[0] + side * walk * .2 * s, by - .03 * s)
        _limb(d, hip, foot, .17 * b * s, pants)
    # corps
    cx, cy = bx + lean * .5, by - 1.17 * s
    _ellipse(d, cx, cy, .3 * b * s, .37 * s, outfit)
    # bras
    for side, sx, key in ((-1, .33, "arm_l"), (1, -.33, "arm_r")):
        sh = (cx + sx * b * s, cy - .23 * s)
        a = g(key)
        ang = .12 + .25 * a
        ln = .6 * s
        hand = (sh[0] + math.sin(ang) * ln * (1 if sx > 0 else -1), sh[1] + math.cos(a * .9) * ln * (1 if a < 1.6 else -.2))
        _limb(d, sh, hand, .13 * s, outfit)
        _ellipse(d, hand[0], hand[1], .075 * s, .075 * s, skin)
    # tête
    hx = cx + lean + g("head_yaw") * .1 * s
    hy = by - 1.8 * s + g("head_pitch") * .12 * s
    r = .27 * s
    hs = L.get("hair_style", "court")
    if hs == "long":
        _ellipse(d, hx, hy + .15 * s, r * 1.05, r * 1.15, hair)
    _ellipse(d, hx, hy, r, r * 1.05, skin)
    if hs != "chauve":
        d.chord([hx - r * 1.04, hy - r * 1.1, hx + r * 1.04, hy + r * .5], 180, 360, fill=hair)
        if hs == "chignon":
            _ellipse(d, hx, hy - r * 1.15, r * .4, r * .4, hair)
        if hs == "boucles":
            for k in range(7):
                a = math.pi + k / 6 * math.pi
                _ellipse(d, hx + math.cos(a) * r, hy + math.sin(a) * r * .9, r * .3, r * .3, hair)
    ex = g("head_yaw") * .25 * r
    eo = g("eyes")
    for sx in (-.33, .33):
        _ellipse(d, hx + sx * r + ex, hy - .05 * r, .2 * r, .24 * r * max(.08, eo), (245, 245, 245))
        if eo > .3:
            _ellipse(d, hx + sx * r + ex * 1.3, hy - .03 * r, .1 * r, .12 * r, hexrgb(L.get("eyes", "#3b2416")))
    brow, tilt = g("brow"), g("tilt")
    for sx in (-1, 1):
        bxx = hx + sx * .33 * r + ex
        byy = hy - .38 * r - brow * .15 * r
        dy = tilt * .1 * r
        d.line([(bxx - .2 * r, byy + (dy if sx < 0 else -dy) * -1), (bxx + .2 * r, byy + (dy if sx > 0 else -dy) * -1)], fill=hair, width=max(1, int(.07 * r)))
    m, sm = g("mouth"), g("smile")
    my = hy + .45 * r
    if m > .08:
        _ellipse(d, hx + ex * .8, my, .2 * r, (.05 + .25 * m) * r, (60, 16, 16))
    else:
        bend = sm * .12 * r
        d.line([(hx - .2 * r + ex * .8, my - bend), (hx + ex * .8, my + bend), (hx + .2 * r + ex * .8, my - bend)], fill=(60, 16, 16), width=max(1, int(.06 * r)), joint="curve")


def render(ri: dict, progress=None, cancel=None):
    data = perf.compute(ri)
    W, H = ri["width"], ri["height"]
    keys = {k: i for i, k in enumerate(data["keys"])}
    floor, wall, props = _props(ri)
    tm = ri.get("time", "jour")
    sky = SKY.get(tm, SKY["jour"]) if ri.get("set") not in ("manoir", "espace") else (16, 20, 40)
    light = {"normal": 1.0, "lumineux": 1.15, "sombre": .6, "dramatique": .8}.get(ri.get("lighting", "normal"), 1.0) * (.6 if tm == "nuit" else 1.0)
    indoor = ri.get("set") in INDOOR
    os.makedirs(ri["out_dir"], exist_ok=True)
    order = sorted(ri["characters"], key=lambda c: -perf.layout(len(ri["characters"]), ri.get("set", ""))[ri["characters"].index(c)][1])
    for f in range(ri["frames"]):
        if cancel and cancel():
            raise InterruptedError("annulé")
        cam = Cam(data["camera"][f], W, H)
        im = Image.new("RGB", (W, H), shade(sky, light))
        d = ImageDraw.Draw(im)
        hz = cam.proj(cam.p[0], 60, 0)
        hy = hz[1] if hz else H * .5
        d.rectangle([0, hy, W, H], fill=shade(floor, light))
        if indoor:
            a, b = cam.proj(-12, 4.5, 6.2), cam.proj(12, 4.5, 0)
            if a and b:
                d.rectangle([a[0], a[1], b[0], b[1]], fill=shade(wall, light))
        for kind, x, y, z, w, h, col, emit in sorted(props, key=lambda p: -p[2]):
            a, b = cam.proj(x - w / 2, y, z + h), cam.proj(x + w / 2, y, z)
            if not a or not b:
                continue
            c = col if emit else shade(col, light)
            if kind == "rect":
                d.rectangle([a[0], a[1], b[0], b[1]], fill=c)
            elif kind == "tri":
                d.polygon([(a[0], b[1]), (b[0], b[1]), ((a[0] + b[0]) / 2, a[1])], fill=c)
            else:
                d.ellipse([a[0], a[1], b[0], b[1]], fill=c)
        for c in order:
            ch = data["chars"][c["id"]]
            draw_character(d, cam, c, ch["frames"][f], keys, ch["h"], light)
        im.save(os.path.join(ri["out_dir"], f"f_{f + 1:04d}.png"), compress_level=1)
        if progress:
            progress(f + 1)
