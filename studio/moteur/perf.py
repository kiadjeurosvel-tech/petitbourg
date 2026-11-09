"""Mise en scène calculée image par image (indépendante du moteur de rendu).

Entrée : une « scène de rendu » (voir pipeline.render_input).
Sortie : pour chaque image, l'état de chaque personnage (position, gestes, visage)
et de la caméra. Blender et l'aperçu 2D lisent exactement les mêmes données,
ce qui garantit la cohérence entre aperçu et rendu final.

Ce module n'utilise que la bibliothèque standard (il est importé dans Blender).
"""
from __future__ import annotations

import math
import random

EMO = {  # brow, tilt, smile, lean, head_pitch, gesture_gain
    "neutre": (0.0, 0.0, .15, 0.0, 0.0, 1.0),
    "joie": (.35, 0.0, 1.0, 0.0, -.05, 1.1),
    "colere": (-.7, -1.0, -.6, .14, .05, 1.6),
    "triste": (.3, 1.0, -.8, -.02, .28, .5),
    "surprise": (1.0, .2, 0.0, -.08, -.1, 1.2),
    "peur": (.8, .7, -.45, -.12, .05, .8),
    "reflexion": (.15, -.4, 0.0, 0.0, .1, .5),
}
SHOT_DIST = {"large": 7.0, "moyen": 4.2, "gros_plan": 2.2}


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def layout(n: int, set_name: str):
    """Positions (x, y) et orientation de base (yaw, rad ; 0 = face caméra)."""
    gap = 1.3 if set_name != "restaurant" else 1.6
    out = []
    for i in range(n):
        x = (i - (n - 1) / 2) * gap
        yaw = 0.0 if n == 1 else (-.55 if x < 0 else .55 if x > 0 else 0.0)
        y = .25 * abs(i - (n - 1) / 2) if n > 2 else 0.0
        out.append((x, y, yaw))
    return out


def smooth(prev, target, rate):
    return prev + (target - prev) * rate


def compute(ri: dict) -> dict:
    fps, n = ri["fps"], ri["frames"]
    chars = ri["characters"]
    lines = ri["lines"]
    expr = ri.get("expressiveness", 1.0)
    spd = ri.get("anim_speed", 1.0)
    action = ri.get("action", "parler")
    rnd = random.Random(ri.get("seed", 1))
    lay = layout(len(chars), ri.get("set", ""))
    xs = {c["id"]: lay[i][0] for i, c in enumerate(chars)}
    out_chars = {}
    rate = min(1.0, .18 * spd)
    for ci, c in enumerate(chars):
        cid = c["id"]
        x0, y0, yaw0 = lay[ci]
        h = c["look"].get("height", 1.0)
        mouth = ri["mouth"].get(cid, [])
        ph = rnd.uniform(0, 6.28)
        blinks = set()
        t = rnd.uniform(.5, 2.5)
        while t < n / fps:
            for k in range(int(.12 * fps) + 1):
                blinks.add(int(t * fps) + k)
            t += rnd.uniform(2.0, 4.5)
        st = dict(brow=0.0, tilt=0.0, smile=.15, lean=0.0, hp=0.0, hy=0.0, arm_l=0.0, arm_r=0.0)
        frames = []
        enter_from = -1 if x0 <= 0 else 1
        for f in range(n):
            tt = f / fps
            # émotion courante : dernière réplique de ce personnage ; sinon réaction à la réplique en cours
            cur = None
            speaking = None
            for ln in lines:
                if ln["start"] - .1 <= tt <= ln["end"] + .15:
                    speaking = ln
                if ln["who"] == cid and ln["start"] - .3 <= tt:
                    cur = ln["emotion"]
            if cur is None:
                cur = speaking["emotion"] if speaking and speaking["emotion"] in ("surprise", "peur", "joie") else ("colere" if action == "dispute" else "neutre")
            if action in ("triste", "peur", "reflexion", "surprise") and cur == "neutre":
                cur = action
            brow, tilt, smile, lean, hp, gain = EMO.get(cur, EMO["neutre"])
            talking = speaking is not None and speaking["who"] == cid
            amp = expr * gain
            # gestes : bras qui accompagnent la parole
            w = 2 * math.pi * .7 * spd
            if talking:
                arm_r_t = .35 * amp * (1 + math.sin(w * tt + ph)) + (.25 * amp if action == "dispute" else 0)
                arm_l_t = .25 * amp * (1 + math.sin(w * tt * .8 + ph + 1.7)) * (1 if amp > .9 else .4)
            else:
                arm_r_t = arm_l_t = .05 * math.sin(w * .3 * tt + ph)
            if cur == "reflexion":
                arm_r_t = 2.1
            if cur == "surprise":
                arm_l_t = arm_r_t = max(arm_r_t, 1.1 * min(1.5, expr))
            if cur == "peur":
                arm_l_t = arm_r_t = .9
            # tête : regarde celui qui parle
            if speaking and speaking["who"] != cid and speaking["who"] in xs:
                hy_t = max(-.7, min(.7, (xs[speaking["who"]] - x0) * .45)) - yaw0 * .5
            else:
                hy_t = .12 * math.sin(.6 * tt + ph) * expr
            nod = (.06 * amp * math.sin(2 * math.pi * 1.6 * spd * tt + ph)) if talking else .02 * math.sin(tt * 1.3 + ph)
            st["brow"] = smooth(st["brow"], brow * min(1.6, .55 + .45 * expr), rate)
            st["tilt"] = smooth(st["tilt"], tilt, rate)
            st["smile"] = smooth(st["smile"], smile, rate)
            st["lean"] = smooth(st["lean"], lean * expr, rate * .7)
            st["hp"] = smooth(st["hp"], hp, rate)
            st["hy"] = smooth(st["hy"], hy_t, rate * .8)
            st["arm_l"] = smooth(st["arm_l"], arm_l_t, rate * 1.4)
            st["arm_r"] = smooth(st["arm_r"], arm_r_t, rate * 1.4)
            bounce = 0.0
            if cur == "joie" or action == "rire":
                bounce = abs(math.sin(2 * math.pi * 1.8 * spd * tt)) * .05 * expr
            if talking:
                bounce += .012 * expr * abs(math.sin(w * 1.5 * tt))
            # déplacements
            x, y, walk = x0, y0, 0.0
            yaw = yaw0
            if action == "entree":
                dur_in = 2.2 / spd
                u = ease(tt / dur_in)
                x = x0 + enter_from * 4.5 * (1 - u)
                if u < 1:
                    walk = math.sin(2 * math.pi * 1.6 * spd * tt)
                    yaw = -enter_from * 1.3 * (1 - u) + yaw0 * u
            elif action == "marcher":
                x = x0 + (tt - n / fps / 2) * .35 * spd
                walk = math.sin(2 * math.pi * 1.4 * spd * tt)
            m = mouth[f] if f < len(mouth) else 0.0
            if cur == "surprise" and not talking:
                m = max(m, .35)
            frames.append([round(v, 4) for v in (
                x, y, yaw, walk, st["lean"], bounce, st["hp"] + nod, st["hy"], .03 * math.sin(tt * .9 + ph) * expr,
                st["arm_l"], st["arm_r"], st["brow"], st["tilt"], st["smile"], m, 0.0 if f in blinks else 1.0)])
        out_chars[cid] = {"h": h, "frames": frames}
    return {"keys": ["x", "y", "yaw", "walk", "lean", "bounce", "head_pitch", "head_yaw", "head_roll",
                     "arm_l", "arm_r", "brow", "tilt", "smile", "mouth", "eyes"],
            "chars": out_chars, "camera": camera(ri, xs)}


def camera(ri: dict, xs: dict) -> list:
    """[(px, py, pz, tx, ty, tz, lens)] par image. La caméra regarde vers +y (les personnages font face à -y)."""
    fps, n = ri["fps"], ri["frames"]
    cam = ri["camera"]
    move, shot, speed = cam["move"], cam["shot"], cam.get("speed", 1.0)
    w, h = ri["width"], ri["height"]
    lens = 35.0 if shot != "gros_plan" else 50.0
    # largeur horizontale du champ à distance 1 (capteur 36 mm, ajusté au format)
    sensor_w = 36.0 if w >= h else 36.0 * w / h
    half_tan = (sensor_w / 2) / lens
    spread = (max(xs.values()) - min(xs.values()) if xs else 0) + 1.1
    hs = [c["look"].get("height", 1) for c in ri["characters"]] or [1]
    head_z = 1.75 * sum(hs) / len(hs)
    base = SHOT_DIST[shot]
    if shot != "gros_plan":
        base = max(base, spread / 2 / half_tan * (1.0 if shot == "moyen" else 1.15))
    cx = (max(xs.values()) + min(xs.values())) / 2 if xs else 0
    rnd = random.Random(ri.get("seed", 1) * 7 + 3)
    nx = [rnd.uniform(0, 6.28) for _ in range(3)]
    out = []
    focus_x = cx
    for f in range(n):
        tt = f / fps
        u = ease(f / max(1, n - 1))
        d, ox, oz, ang = base, 0.0, 0.0, 0.0
        tz = head_z - (.25 if shot == "large" else .1)
        if move == "dolly_in":
            d = base * (1.35 - .45 * u * min(1.5, speed))
        elif move == "dolly_out":
            d = base * (.85 + .5 * u * min(1.5, speed))
        elif move == "pan_left":
            ox = (1 - 2 * u) * 1.3 * speed
        elif move == "pan_right":
            ox = (2 * u - 1) * 1.3 * speed
        elif move == "orbit":
            ang = (u - .5) * .9 * speed
        elif move == "crane_up":
            oz = u * 2.4 * speed
        elif move == "static":
            ox = .05 * math.sin(tt * .4)
        if shot == "gros_plan":
            sp = None
            for ln in ri["lines"]:
                if ln["start"] - .2 <= tt <= ln["end"] + .4:
                    sp = ln["who"]
            target_x = xs.get(sp, focus_x) if sp else focus_x
            focus_x = smooth(focus_x, target_x, .08)
            tx = focus_x
        else:
            tx = cx
        hx = hy = hz = 0.0
        if move == "handheld":
            k = .045 * speed
            hx = k * math.sin(1.7 * tt + nx[0]) + k * .5 * math.sin(4.1 * tt + nx[1])
            hz = k * math.sin(2.3 * tt + nx[2])
            hy = k * math.sin(1.1 * tt + nx[1])
            d = base * (1.1 - .15 * u)
        px = tx + ox + d * math.sin(ang) + hx
        py = -d * math.cos(ang) + hy
        pz = head_z - .25 + oz + hz + (.5 if shot == "large" else 0)
        out.append((round(px, 4), round(py, 4), round(pz, 4), round(tx + ox * .6, 4), 0.0, round(tz, 4), lens))
    return out
