"""Script exécuté DANS Blender :  blender -b -noaudio -P blender_scene.py -- entree.json

Construit le décor, les personnages, anime tout image par image à partir des données
de perf.py, enregistre le fichier .blend source et rend les images PNG.
Compatible Blender 3.6 → 5.x (API de base uniquement).
"""
import json
import math
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
RI = json.load(open(ARGS[0]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perf  # noqa: E402

P = perf.compute(RI)
KEYS = {k: i for i, k in enumerate(P["keys"])}
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.frame_start, SC.frame_end = 1, RI["frames"]
SC.render.fps = RI["fps"]
SC.render.resolution_x, SC.render.resolution_y = RI["width"], RI["height"]
SC.render.resolution_percentage = 100
SC.render.image_settings.file_format = "PNG"
SC.render.image_settings.color_mode = "RGB"
SC.render.filepath = os.path.join(RI["out_dir"], "f_")
try:
    SC.view_settings.view_transform = "Standard"
except Exception:
    pass
COLL = SC.collection


def hexrgb(h, k=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [min(1, x * k) for x in c]
    return [x ** 2.2 for x in c]  # sRGB → linéaire


_MATS = {}


def mat(color, rough=.55, emit=0.0):
    key = (tuple(round(x, 3) for x in color), rough, emit)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new("m")
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
        if emit:
            for name in ("Emission Color", "Emission"):
                if name in b.inputs:
                    b.inputs[name].default_value = (*color, 1)
            if "Emission Strength" in b.inputs:
                b.inputs["Emission Strength"].default_value = emit
    _MATS[key] = m
    return m


def _abs(o):
    return list(o["abs"]) if o is not None and "abs" in o else [0.0, 0.0, 0.0]


def empty(name, parent=None, loc=(0, 0, 0)):
    """Pivot. `loc` est en coordonnées absolues (pose de repos) ; converti en local."""
    o = bpy.data.objects.new(name, None)
    COLL.objects.link(o)
    pa = _abs(parent)
    o.parent = parent
    o.location = [loc[i] - pa[i] for i in range(3)]
    o["abs"] = list(loc)
    return o


def _fin(o, parent, color, rough=.55, emit=0.0, smooth=False):
    o.data.materials.append(mat(color, rough, emit))
    if parent:
        pa = _abs(parent)
        o.parent = parent
        o.location = [o.location[i] - pa[i] for i in range(3)]
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return o


def box(parent, loc, size, color, rough=.6, emit=0.0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    return _fin(o, parent, color, rough, emit)


def sph(parent, loc, r, color, scale=(1, 1, 1), rough=.5, seg=20, emit=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=max(8, seg // 2))
    o = bpy.context.object
    o.scale = scale
    return _fin(o, parent, color, rough, emit, smooth=True)


def cyl(parent, loc, r, depth, color, rough=.55, verts=16, rot=(0, 0, 0), emit=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    return _fin(bpy.context.object, parent, color, rough, emit, smooth=True)


def cone(parent, loc, r, depth, color, verts=12):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, depth=depth, location=loc)
    return _fin(bpy.context.object, parent, color, .7)


# --------------------------------------------------------------------------- animation rapide

def animate(obj, path, index, values):
    """Pose une clé par image (interpolation linéaire). Compatible anciennes et nouvelles API d'actions."""
    if obj.animation_data is None:
        obj.animation_data_create()
    if obj.animation_data.action is None:
        obj.animation_data.action = bpy.data.actions.new(obj.name + "A")
    act = obj.animation_data.action
    fc = None
    try:
        fc = act.fcurve_ensure_for_datablock(obj, path, index=index)  # Blender 4.4+
    except Exception:
        try:
            fc = act.fcurves.find(path, index=index) or act.fcurves.new(path, index=index)
        except Exception:
            fc = None
    if fc is None:
        for f, v in enumerate(values):
            getattr(obj, path)[index] = v
            obj.keyframe_insert(path, index=index, frame=f + 1)
        return
    fc.keyframe_points.add(len(values))
    co = []
    for f, v in enumerate(values):
        co += [f + 1, v]
    fc.keyframe_points.foreach_set("co", co)
    try:
        fc.keyframe_points.foreach_set("interpolation", [1] * len(values))  # LINEAR
    except Exception:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    fc.update()


# --------------------------------------------------------------------------- décors

PAL = {
    "restaurant": [("#7a4a2b", "#e8d9c0", "#b33a3a"), ("#5b3a29", "#d6e2d3", "#2f6f5e"), ("#3e2a22", "#f0c9a0", "#8a3b5c")],
    "rue": [("#6d6d75", "#e6b88a", "#3a6ea5"), ("#5a5a60", "#c9d6e3", "#a5523a"), ("#4a4f55", "#f1e0b5", "#3b8a5a")],
    "foret": [("#3f6b2a", "#2f5a2a", "#7a5a3a"), ("#55702f", "#8a6a2a", "#5a3a22"), ("#2a4a3a", "#1f3a2a", "#4a3a2a")],
    "salon": [("#8a6a4a", "#efe2cf", "#3a5f8a"), ("#6a5040", "#d8e4ea", "#c06a3a"), ("#4a3a40", "#ead6e0", "#3a8a7a")],
    "bureau": [("#5a5f66", "#dfe3e8", "#2f6fd6"), ("#4a4a4a", "#e8e0d0", "#2fa36b"), ("#3a3f4a", "#cfd8e8", "#d64545")],
    "manoir": [("#2a2a33", "#3a3348", "#c9a23a"), ("#22262e", "#2e3a40", "#8a2a2a"), ("#2a2230", "#403050", "#5ab0c0")],
    "plage": [("#e8d29a", "#2f8fcf", "#2fa36b"), ("#f0dcae", "#1f7fb0", "#e0873a"), ("#e0c890", "#3aa0c0", "#a33a8a")],
    "espace": [("#3a3a48", "#101020", "#5ab0ff"), ("#40303a", "#140c1c", "#ff7a5a"), ("#2a3a3a", "#081418", "#7aff9a")],
    "classe": [("#9a7a5a", "#e6ebd8", "#2a4a3a"), ("#7a6a5a", "#dfe6f0", "#3a3a5a"), ("#8a6a4a", "#f0e6d0", "#4a2a2a")],
    "studio": [("#5a5a66", "#3a3a48", "#ffffff")],
}


def build_set(name, variant, seed):
    import random
    r = random.Random(seed * 13 + variant)
    pals = PAL.get(name, PAL["salon"])
    floor_c, wall_c, acc_c = pals[variant % len(pals)]
    shift = 1 + .08 * (variant // len(pals))
    F, W, A = hexrgb(floor_c, shift), hexrgb(wall_c, shift), hexrgb(acc_c)
    root = empty("decor")
    indoor = name in ("restaurant", "salon", "bureau", "classe", "studio")
    box(root, (0, 4, -.05), (60, 40, .1), F, .8)
    if indoor:
        box(root, (0, 4.5, 3), (24, .2, 6.2), W, .9)
        box(root, (-9, 2, 3), (.2, 10, 6.2), W, .9)
        box(root, (9, 2, 3), (.2, 10, 6.2), W, .9)
        box(root, (0, 4.38, .35), (24, .05, .7), hexrgb(acc_c, .6), .5)  # plinthe
    if name == "restaurant":
        for wx in (-5, 0, 5):  # fenêtres lumineuses
            box(root, (wx, 4.35, 2.6), (2.4, .05, 1.8), hexrgb("#ffe7b0"), .3, emit=1.5)
        cyl(root, (0, .7, .37), .08, .74, hexrgb("#3a2a22"), .6)  # pied de table
        cyl(root, (0, .7, .76), .55, .05, hexrgb(acc_c, .9), .6, verts=32)  # plateau + nappe
        for px in (-.25, .25):
            cyl(root, (px, .6, .8), .12, .015, hexrgb("#ffffff"), .2)
            cyl(root, (px, .8, .88), .03, .16, hexrgb("#cfe8ff"), .05)
        cyl(root, (0, .75, .86), .025, .16, hexrgb("#f7f3d0"), .3, emit=3)  # bougie
        for lx in (-3.5, 0, 3.5):
            sph(root, (lx, 2.5, 4.2), .3, hexrgb("#ffd890"), emit=4)
        for k in range(4):  # autres tables au fond
            tx = -6 + k * 4 + r.uniform(-.4, .4)
            cyl(root, (tx, 3.3, .38), .55, .76, hexrgb(acc_c), .6)
        for px in (-7.5, 7.5):
            cyl(root, (px, 3.8, .4), .35, .8, hexrgb("#6a4a3a"))
            sph(root, (px, 3.8, 1.3), .6, hexrgb("#3f7a3a"))
    elif name == "salon":
        box(root, (-.2, 3.6, .45), (3.2, 1.0, .5), A, .8)  # canapé
        box(root, (-.2, 4.05, .95), (3.2, .3, .9), A, .8)
        box(root, (0, 4.35, 2.7), (2.0, .05, 1.3), hexrgb("#9ad0ff"), .2, emit=.8)  # fenêtre
        cyl(root, (3.2, 3.6, 0), .04, 3.0, hexrgb("#333333"))
        cone(root, (3.2, 3.6, 3.0), .4, .5, hexrgb("#fff2c0"))
        cyl(root, (0, 1.5, .01), 2.2, .02, hexrgb(acc_c, .8), .9, verts=32)  # tapis
        for fx in (-4, 4.5):
            box(root, (fx, 4.35, 2.2), (1.2, .05, .9), hexrgb(r.choice(["#e0a43a", "#2fa36b", "#d64545"])))
    elif name == "bureau":
        box(root, (0, 2.4, .75), (2.8, 1.0, .06), hexrgb("#ddd6c8"))
        for lx in (-1.2, 1.2):
            box(root, (lx, 2.4, .37), (.06, .9, .74), hexrgb("#444444"))
        box(root, (0, 2.6, 1.15), (.9, .05, .55), hexrgb("#9ad0ff"), .2, emit=2)
        for sx in (-6, 6):
            box(root, (sx, 4.1, 1.5), (2.4, .5, 3.0), hexrgb("#6a5040"))
        for k in range(5):
            box(root, (-6 + r.uniform(-.8, .8), 3.85, .5 + k * .55), (.25, .3, .4), hexrgb(r.choice(["#d64545", "#2f6fd6", "#e0a43a"])))
    elif name == "classe":
        box(root, (0, 4.35, 2.2), (5, .05, 1.8), hexrgb("#1f3a2a"), .9)
        for k in range(6):
            dx, dy = -5 + (k % 3) * 5, 2.4 + (k // 3) * 1.4
            box(root, (dx, dy, .72), (1.4, .7, .06), hexrgb("#b08a5a"))
    elif name == "rue":
        for k in range(7):
            bx = -15 + k * 5 + r.uniform(-.3, .3)
            hgt = r.uniform(5, 11)
            col = hexrgb(r.choice(["#e6b88a", "#c9d6e3", "#f1e0b5", "#d9a3a3", "#a3c2d9"]))
            box(root, (bx, 9, hgt / 2), (4.6, 4, hgt), col, .9)
            for wy in range(int(hgt // 2)):
                for wx in (-1.2, 0, 1.2):
                    box(root, (bx + wx, 6.95, 1.5 + wy * 2), (.7, .1, .9), hexrgb("#ffe7b0") if r.random() < .3 else hexrgb("#4a5a6a"), .2,
                        emit=1.2 if r.random() < .3 else 0)
        box(root, (0, 5.5, .08), (60, 2.5, .16), hexrgb("#9a9a9a"), .9)  # trottoir
        for lx in (-6, 6):
            cyl(root, (lx, 4.5, 2), .06, 4, hexrgb("#2a2a2a"))
            sph(root, (lx, 4.5, 4.1), .25, hexrgb("#fff2c0"), emit=5)
    elif name == "foret":
        for k in range(26):
            tx, ty = r.uniform(-14, 14), r.uniform(3, 16)
            if abs(tx) < 2.5 and ty < 5:
                continue
            hgt = r.uniform(3, 7)
            cyl(root, (tx, ty, hgt / 2), .2, hgt, hexrgb("#5a3a22"), verts=8)
            cone(root, (tx, ty, hgt + .6), r.uniform(1.0, 1.8), r.uniform(2.5, 4), hexrgb(r.choice([wall_c, "#2f6a2f", "#3f7a3a"])))
        for k in range(10):
            sph(root, (r.uniform(-6, 6), r.uniform(.5, 3), .2), r.uniform(.2, .45), hexrgb("#4a8a3a"), (1.4, 1, .7))
    elif name == "manoir":
        box(root, (0, 14, 4.5), (12, 6, 9), hexrgb("#1c1c24"), .9)
        cone(root, (-4.5, 14, 11), 2.2, 4, hexrgb("#141418"), 4)
        cone(root, (4.5, 14, 11), 2.2, 4, hexrgb("#141418"), 4)
        for wx in (-3, 0, 3):
            box(root, (wx, 10.9, 5), (1, .1, 1.6), hexrgb("#ffcc66"), .3, emit=3 if r.random() < .7 else 0)
        sph(root, (6, 25, 13), 1.6, hexrgb("#f4f1d0"), emit=6)  # lune
        for k in range(8):
            tx = r.choice([-1, 1]) * r.uniform(3, 10)
            ty = r.uniform(3, 9)
            cyl(root, (tx, ty, 1.8), .12, 3.6, hexrgb("#2a2420"), verts=6)
            cyl(root, (tx + .5, ty, 3.2), .05, 1.6, hexrgb("#2a2420"), verts=6, rot=(0, .9, 0))
        for gx in range(-6, 7):
            cyl(root, (gx * .5, 6, .9), .03, 1.8, hexrgb("#111111"), verts=6)
    elif name == "plage":
        box(root, (0, 16, -.02), (80, 20, .06), hexrgb(wall_c), .1)  # mer
        sph(root, (-8, 30, 7), 2.5, hexrgb("#ffd36a"), emit=6)
        for px in (-6, 7):
            for k in range(6):
                cyl(root, (px + k * .08, 4 + k * .02, .5 + k * .9), .16, .95, hexrgb("#8a6a3a"), verts=8, rot=(0, .06 * k, 0))
            for a in range(6):
                box(root, (px + .5 + math.cos(a) * 1.0, 4 + math.sin(a) * 1.0, 5.6), (2.2, .4, .06), hexrgb("#2fa36b"), rot=(0, -.35, a))
    elif name == "espace":
        for k in range(120):
            sph(root, (r.uniform(-40, 40), r.uniform(20, 40), r.uniform(-5, 30)), r.uniform(.04, .12), (1, 1, 1), seg=6, emit=8)
        sph(root, (9, 30, 9), 5, hexrgb(acc_c), emit=.6)
        box(root, (0, 4, -.05), (30, 20, .1), hexrgb("#3a3a48"), .4)
    return root


def lights(time, lighting, name):
    w = bpy.data.worlds.new("w")
    SC.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    sky = {"jour": "#9ccaf0", "soir": "#f0a070", "nuit": "#1a2440"}[time]
    if name in ("manoir",):
        sky = "#121a30"
    if name == "espace":
        sky = "#05050c"
    col = hexrgb(sky)
    bg.inputs[0].default_value = (*col, 1)
    k = {"normal": 1.0, "lumineux": 1.5, "sombre": .45, "dramatique": .7}[lighting]
    if time == "nuit":
        k *= .45
    bg.inputs[1].default_value = .6 * k
    w.color = col
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = (2.2 if time == "jour" else 1.4) * k
    sun.color = (1, .95, .9) if time == "jour" else ((1, .7, .5) if time == "soir" else (.55, .65, 1))
    so = bpy.data.objects.new("sun", sun)
    COLL.objects.link(so)
    so.rotation_euler = (math.radians(50 if lighting != "dramatique" else 70), 0, math.radians(30 if lighting != "dramatique" else 75))
    key = bpy.data.lights.new("key", "AREA")
    key.energy = 220 * k * (1.4 if lighting == "dramatique" else 1)
    key.size = 4
    ko = bpy.data.objects.new("key", key)
    COLL.objects.link(ko)
    ko.location = (-3, -5, 4)
    ko.rotation_euler = (math.radians(55), 0, math.radians(-30))
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = (90 if lighting != "dramatique" else 20) * k
    fill.size = 6
    fo = bpy.data.objects.new("fill", fill)
    COLL.objects.link(fo)
    fo.location = (4, -4, 3)
    fo.rotation_euler = (math.radians(60), 0, math.radians(35))
    rim = bpy.data.lights.new("rim", "SPOT")
    rim.energy = 500 * k
    rim.color = (.6, .7, 1) if time == "nuit" else (1, .9, .8)
    ro = bpy.data.objects.new("rim", rim)
    COLL.objects.link(ro)
    ro.location = (0, 4, 4)
    ro.rotation_euler = (math.radians(-50), 0, 0)


# --------------------------------------------------------------------------- personnages

def build_character(c):
    L = c["look"]
    skin, hair, outfit, pants = hexrgb(L["skin"]), hexrgb(L["hair"]), hexrgb(L["outfit"]), hexrgb(L["pants"])
    b = L.get("build", 1.0)
    root = empty("P_" + c["id"])
    s = L.get("height", 1.0)
    root.scale = (s, s, s)
    parts = {"root": root}
    for side, x in (("l", .13), ("r", -.13)):
        hip = empty(f"hip{side}", root, (x * b, 0, .82))
        cyl(hip, (x * b, 0, .42), .085 * b, .8, pants)
        sph(hip, (x * b, -.06, .04), .1, hexrgb("#2a2a2a"), (1, 1.6, .6))
        parts["hip" + side] = hip
    body = empty("body", root, (0, 0, .82))
    parts["body"] = body
    sph(body, (0, 0, 1.17), .3, outfit, (1.0 * b, .72 * b, 1.25), .7)
    cyl(body, (0, 0, .88), .22 * b, .16, pants)
    cyl(body, (0, 0, 1.52), .07, .12, skin)
    for side, x in (("l", .33), ("r", -.33)):
        sh = empty(f"sh{side}", body, (x * b, 0, 1.4))
        cyl(sh, (x * b, 0, 1.12), .07, .56, outfit, .7)
        sph(sh, (x * b, 0, .8), .075, skin)
        parts["sh" + side] = sh
    head = empty("head", body, (0, 0, 1.56))
    parts["head"] = head
    sph(head, (0, 0, 1.8), .27, skin, (1, .95, 1.05), .45, seg=28)
    sph(head, (0, -.27, 1.77), .04, hexrgb(L["skin"], .9), (1, 1, 1.2))  # nez
    for x in (.27, -.27):
        sph(head, (x, 0, 1.78), .05, skin, (.6, 1, 1))
    hs = L.get("hair_style", "court")
    if hs != "chauve":
        sph(head, (0, .05, 1.9), .285, hair, (1.04, 1.0, .78), .8, seg=24)
        if hs == "long":
            sph(head, (0, .12, 1.62), .27, hair, (1.05, .55, 1.15), .8)
        elif hs == "chignon":
            sph(head, (0, .14, 2.08), .11, hair, rough=.8)
        elif hs == "boucles":
            for k in range(8):
                a = k / 8 * 6.283
                sph(head, (math.cos(a) * .25, .05 + math.sin(a) * .1, 1.98 + .04 * math.sin(3 * a)), .09, hair, rough=.9, seg=10)
    eyes = empty("eyes", head, (0, -.22, 1.84))
    parts["eyes"] = eyes
    for x in (.09, -.09):
        sph(eyes, (x, -.22, 1.84), .055, (.95, .95, .95), (1, .6, 1.15), .2)
        sph(eyes, (x, -.255, 1.84), .028, hexrgb(L.get("eyes", "#3b2416")), rough=.1)
        sph(eyes, (x + .008, -.275, 1.85), .009, (1, 1, 1), rough=.1, seg=8)
    for side, x in (("l", .09), ("r", -.09)):
        br = empty(f"brow{side}", head, (x, -.25, 1.94))
        box(br, (x, -.25, 1.94), (.1, .02, .022), hair, .8)
        parts["brow" + side] = br
    mo = empty("mouth", head, (0, -.25, 1.66))
    parts["mouth"] = mo
    sph(mo, (0, -.25, 1.66), .065, hexrgb("#3a1010"), (1.2, .5, .35), .4)
    parts["mouthdots"] = []
    for k in range(5):
        x = (k - 2) * .028
        d = sph(head, (x, -.262, 1.69), .015, hexrgb("#3a1010"), rough=.4, seg=8)
        parts["mouthdots"].append((d, x))
    return parts


def animate_character(parts, data, keys):
    fr = data["frames"]
    col = lambda k: [f[keys[k]] for f in fr]  # noqa: E731
    root, body, head = parts["root"], parts["body"], parts["head"]
    h = data["h"]
    animate(root, "location", 0, col("x"))
    animate(root, "location", 1, col("y"))
    animate(root, "location", 2, [v * h for v in col("bounce")])
    animate(root, "rotation_euler", 2, col("yaw"))
    animate(body, "rotation_euler", 0, [-v for v in col("lean")])
    animate(head, "rotation_euler", 0, [-v for v in col("head_pitch")])
    animate(head, "rotation_euler", 2, col("head_yaw"))
    animate(head, "rotation_euler", 1, col("head_roll"))
    walk = col("walk")
    animate(parts["hipl"], "rotation_euler", 0, [.5 * w for w in walk])
    animate(parts["hipr"], "rotation_euler", 0, [-.5 * w for w in walk])
    al, ar = col("arm_l"), col("arm_r")
    animate(parts["shl"], "rotation_euler", 0, [-a + .3 * w for a, w in zip(al, walk)])
    animate(parts["shr"], "rotation_euler", 0, [-a - .3 * w for a, w in zip(ar, walk)])
    animate(parts["shl"], "rotation_euler", 1, [-.12 - .25 * a for a in al])
    animate(parts["shr"], "rotation_euler", 1, [.12 + .25 * a for a in ar])
    brow, tilt = col("brow"), col("tilt")
    hz = _abs(head)[2]
    animate(parts["browl"], "location", 2, [1.94 - hz + .035 * b for b in brow])
    animate(parts["browr"], "location", 2, [1.94 - hz + .035 * b for b in brow])
    animate(parts["browl"], "rotation_euler", 1, [.35 * t for t in tilt])
    animate(parts["browr"], "rotation_euler", 1, [-.35 * t for t in tilt])
    mouth = col("mouth")
    animate(parts["mouth"], "scale", 2, [.15 + 1.9 * m for m in mouth])
    animate(parts["mouth"], "scale", 0, [.85 + .25 * m for m in mouth])
    smile = col("smile")
    for d, x in parts["mouthdots"]:
        animate(d, "location", 2, [1.69 - hz + s * (x * x * 22 - .012) * .9 for s in smile])
    animate(parts["eyes"], "scale", 2, col("eyes"))


# --------------------------------------------------------------------------- caméra / rendu

def setup_camera(track):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    COLL.objects.link(cam)
    SC.camera = cam
    cam.data.sensor_fit = "HORIZONTAL" if RI["width"] >= RI["height"] else "VERTICAL"
    cam.data.sensor_width = 36
    cam.data.sensor_height = 36
    cam.data.clip_end = 300
    tgt = empty("cam_target")
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    animate(cam, "location", 0, [c[0] for c in track])
    animate(cam, "location", 1, [c[1] for c in track])
    animate(cam, "location", 2, [c[2] for c in track])
    animate(tgt, "location", 0, [c[3] for c in track])
    animate(tgt, "location", 1, [c[4] for c in track])
    animate(tgt, "location", 2, [c[5] for c in track])
    cam.data.lens = track[0][6]
    if RI["width"] < RI["height"]:
        # en vertical, sensor_fit VERTICAL avec 36 mm : on garde la même largeur de champ que perf.py
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.sensor_width = 36 * RI["width"] / RI["height"]


def setup_engine():
    eng = RI.get("engine", "eevee")
    if eng == "workbench":
        SC.render.engine = "BLENDER_WORKBENCH"
        sh = SC.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_shadows = True
        sh.show_cavity = True
        return
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            SC.render.engine = e
            break
        except Exception:
            continue
    ee = SC.eevee
    for k, v in (("taa_render_samples", RI.get("samples", 16)), ("use_gtao", True), ("gtao_distance", 1.5),
                 ("use_soft_shadows", True), ("use_bloom", True), ("bloom_intensity", .03)):
        try:
            setattr(ee, k, v)
        except Exception:
            pass
    if RI.get("style") == "mystere" or RI.get("lighting") == "sombre":
        try:
            SC.view_settings.look = "Medium High Contrast"
        except Exception:
            pass


def main():
    setup_engine()
    set_name = RI.get("set", "salon")
    build_set(set_name, RI.get("variant", 0), RI.get("seed", 1))
    lights(RI.get("time", "jour"), RI.get("lighting", "normal"), set_name)
    for c in RI["characters"]:
        parts = build_character(c)
        animate_character(parts, P["chars"][c["id"]], KEYS)
    setup_camera(P["camera"])
    if RI.get("blend_out"):
        try:
            bpy.ops.wm.save_as_mainfile(filepath=RI["blend_out"], compress=True)
        except Exception as ex:  # noqa: BLE001
            print("BLEND_SAVE_FAIL", ex)
    print("STUDIO_BUILD_OK", flush=True)
    if RI["frames"] == 1:
        SC.frame_set(1)
        SC.render.filepath = os.path.join(RI["out_dir"], "f_0001.png")
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("STUDIO_RENDER_OK", flush=True)


main()
