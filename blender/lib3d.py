"""Petitbourg 3D library (Blender). 1 unit = 1 metre. Everything is parented to a root empty so it can pop in."""
import bpy, math, random
from mathutils import Vector

_M = {}
def mat(c, rough=.5, metal=0.0):
    k = (round(c[0], 3), round(c[1], 3), round(c[2], 3), rough, metal)
    if k not in _M:
        m = bpy.data.materials.new("m"); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
        b.inputs["Roughness"].default_value = rough
        try: b.inputs["Metallic"].default_value = metal
        except Exception: pass
        _M[k] = m
    return _M[k]

def rgb(h):  # '#rrggbb' or tuple
    if isinstance(h, (tuple, list)): return tuple(h)
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

def root(name):
    o = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(o); return o

import bmesh
_U = {}
def _unit(kind, n=24):
    k = (kind, n)
    if k not in _U:
        me = bpy.data.meshes.new("u"); bm = bmesh.new()
        if kind == 'cube': bmesh.ops.create_cube(bm, size=1.0)
        elif kind == 'cyl': bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=1.0, radius2=1.0, depth=1.0)
        elif kind == 'cone': bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=1.0, radius2=0.0, depth=1.0)
        elif kind == 'sph': bmesh.ops.create_uvsphere(bm, u_segments=n, v_segments=max(6, n // 2), radius=1.0)
        bm.to_mesh(me); bm.free()
        if kind in ('sph', 'cyl', 'cone'):
            for p_ in me.polygons: p_.use_smooth = (kind == 'sph')
        _U[k] = me
    return _U[k]
def _obj(kind, n, loc, scale, rot=(0, 0, 0)):
    o = bpy.data.objects.new("o", _unit(kind, n).copy()); bpy.context.scene.collection.objects.link(o)
    o.location = loc; o.scale = scale; o.rotation_euler = rot; return o

def _fin(o, par, c, rough, metal=0.0):
    o.data.materials.append(mat(rgb(c), rough, metal)); o.parent = par; return o

def box(par, x, y, z, w, d, h, c, rough=.55):
    """box with its BOTTOM at z, centred on x,y"""
    return _fin(_obj('cube', 0, (x, y, z + h / 2), (w, d, h)), par, c, rough)

def cyl(par, x, y, z, r, h, c, rough=.5, v=24, rx=0):
    return _fin(_obj('cyl', min(v, 16), (x, y, z + h / 2), (r, r, h), (rx, 0, 0)), par, c, rough)

def sph(par, x, y, z, r, c, s=(1, 1, 1), rough=.5, seg=24):
    return _fin(_obj('sph', min(seg, 16), (x, y, z), (r * s[0], r * s[1], r * s[2])), par, c, rough)

def cone4(par, x, y, z, w, d, h, c):
    return _fin(_obj('cone', 4, (x, y, z + h / 2), (w * .7071, d * .7071, h), (0, 0, math.pi / 4)), par, c, .6)

def gable(par, x, y, z, w, d, h, c, ov=.5):
    """gable roof, ridge along x"""
    w2, d2 = w / 2 + ov, d / 2 + ov
    v = [(-w2, -d2, 0), (w2, -d2, 0), (w2, d2, 0), (-w2, d2, 0), (-w2, 0, h), (w2, 0, h)]
    f = [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
    me = bpy.data.meshes.new("g"); me.from_pydata(v, [], f); me.update()
    o = bpy.data.objects.new("g", me); bpy.context.scene.collection.objects.link(o)
    o.location = (x, y, z); o.data.materials.append(mat(rgb(c), .7)); o.parent = par; return o

def text(par, s, x, y, z, size, c=(1, 1, 1), rot=(math.pi / 2, 0, 0), ext=.02):
    cu = bpy.data.curves.new("t", 'FONT'); cu.body = s; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.extrude = ext
    o = bpy.data.objects.new("t", cu); bpy.context.scene.collection.objects.link(o)
    o.location = (x, y, z); o.rotation_euler = rot; cu.materials.append(mat(rgb(c), .4)); o.parent = par; return o

def sign(par, s, x, y, z, w, h, bg, fg=(1, 1, 1), size=None):
    """sign facing -y"""
    box(par, x, y, z, w, .3, h, bg, .4)
    text(par, s, x, y - .2, z + h / 2, size or min(h * .62, w / max(4, len(s)) * 1.45), fg)

def window(par, x, y, z, w, h, side=-1, c=(.6, .85, 1.0)):
    box(par, x, y, z, w, .12, h, (1, 1, 1), .3); box(par, x, y + side * .04, z + .1, w - .25, .14, h - .2, c, .08)

def door(par, x, y, z=0, w=1.4, h=2.4, c=(.45, .25, .12)):
    box(par, x, y, z, w, .2, h, c)

def tree(par, x, y, s=1.0, c=(.2, .62, .22)):
    cyl(par, x, y, 0, .25 * s, 2.2 * s, (.4, .26, .13), v=8); sph(par, x, y, 3.4 * s, 1.7 * s, c, seg=12)

def car(par, x, y, c=(.8, .1, .1), rot=0):
    r = root("car"); r.parent = par; r.location = (x, y, 0); r.rotation_euler = (0, 0, rot)
    box(r, 0, 0, .35, 4.2, 1.8, .8, c, .3); box(r, -.2, 0, 1.1, 2.2, 1.6, .7, (.55, .8, .95), .1)
    for sx in (-1.4, 1.4):
        for sy in (-.9, .9): cyl(r, sx, sy, .1, .35, .25, (.05, .05, .05), v=12, rx=math.pi / 2)
    return r

# ------------------------------------------------------------------ lots / roads
def lawn(par, w, d, c=(.42, .78, .27), path=True, fence=True):
    box(par, 0, 0, 0, w, d, .15, c, .9)
    if path: box(par, 0, -d / 4, .15, 2.4, d / 2, .05, (.8, .78, .72), .8)
    if fence:
        for sx in (-w / 2, w / 2): box(par, sx, 0, .15, .2, d, .9, (1, 1, 1), .5)
        box(par, 0, d / 2, .15, w, .2, .9, (1, 1, 1), .5)
        for i in range(-int(w / 2 - 1), int(w / 2), 3):
            box(par, i, -d / 2, .15, .2, .2, .9, (1, 1, 1))

def pool(par, x, y, w, d, c=(.25, .7, .95)):
    box(par, x, y, .15, w + 1, d + 1, .08, (.9, .9, .88), .6); box(par, x, y, .2, w, d, .1, c, .05)

def jacuzzi(par, x, y):
    cyl(par, x, y, .15, 1.7, .6, (.9, .9, .9), v=24); cyl(par, x, y, .7, 1.45, .08, (.3, .75, 1), rough=.05, v=24)

# ------------------------------------------------------------------ buildings (each returns root)
def _lot(name, w, d, grass=(.42, .78, .27)):
    r = root(name); lawn(r, w, d, grass); return r

def house(name, wall=(1, .78, .55), rf=(.8, .25, .2), w=13, d=9.5, trees=True, extra=None):
    r = _lot(name, 34, 34); by = 4
    box(r, 0, by, .15, w, d, 5.2, wall, .6); gable(r, 0, by, 5.35, w, d, 3.4, rf)
    box(r, w / 4, by, 8, 1.2, 1.2, 2.4, (.6, .35, .3))
    door(r, -1.5, by - d / 2 - .05, .15)
    for dx in (3, 5.2, -4.5): window(r, dx, by - d / 2 - .06, 1.6, 1.6, 1.6)
    for dx in (-4.5, 3, 5.2): window(r, dx, by - d / 2 - .06, 3.9, 1.5, 1.1)
    box(r, 6.5, by - d / 2 - 3, .15, 4.2, 6.5, .06, (.35, .35, .38), .9)
    if trees: tree(r, -12, 10); tree(r, 13, 12, .9); tree(r, -13, -12, .8)
    if extra: extra(r, by)
    return r

def villa(name, wall=(.98, .98, .95), rf=(.2, .22, .28), pool_=True, jac=False, lake=False, pink=False, w=20, d=13):
    r = _lot(name, 52, 52); by = 8
    box(r, 0, by, .15, w, d, 4.6, wall, .5); box(r, -2, by - 1, 4.75, w * .66, d * .75, 3.6, wall, .5)
    box(r, 0, by, 4.6, w + 1.4, d + 1.4, .35, rf, .5); box(r, -2, by - 1, 8.35, w * .66 + 1.2, d * .75 + 1.2, .35, rf, .5)
    for dx in (-7, -3, 1, 5, 8): window(r, dx, by - d / 2 - .06, 1.0, 2.2, 2.6)
    for dx in (-6, -2, 2): window(r, dx, by - d * .75 / 2 - 1.06, 5.0, 2.2, 2.3)
    door(r, -9.2 if False else 6, by - d / 2 - .05, .15, 1.8, 2.8, (.3, .2, .12))
    for sx in (-6, -2): cyl(r, sx, by - d / 2 - 1.6, .15, .4, 4.4, (1, 1, 1), v=12)
    box(r, 0, by - d / 2 - 3, 4.7, 8, 3, .3, (1, 1, 1), .5)
    if lake:
        sph(r, 6, -9, .1, 1, (.2, .65, .95), (11, 7.5, .12), rough=.05)
        box(r, 6, -9, .2, 3.2, .9, .8, (1, .8, .2)); cone4(r, 6, -9, 1, 2.2, 2.2, 1.6, (1, .35, .3))
        sph(r, 10, -11, .5, .9, (1, .5, .1), (1, 1, .5))
    elif pool_:
        pool(r, 6, -8, 14, 6.5)
    if jac: jacuzzi(r, -13, -7)
    tree(r, -20, 12); tree(r, 20, 14, 1.1); tree(r, -20, -12); tree(r, 21, -14, .9)
    return r

def igloo(name):
    r = _lot(name, 34, 34, (.9, .95, 1.0)); by = 4
    sph(r, 0, by, .15, 6.2, (.9, .96, 1), (1, 1, .85), rough=.25, seg=32)
    box(r, 0, by - 6.3, .15, 3.2, 3.4, 2.6, (.88, .94, 1), .3); box(r, 0, by - 7.9, .15, 1.5, .2, 2.0, (.15, .3, .5))
    for i in range(6): sph(r, -8 + i * 3.2, -10 + (i % 2) * 2, .5, .9, (1, 1, 1), (1, 1, .7))
    tree(r, -12, 10, 1, (.75, .9, .95)); tree(r, 12, 11, .9, (.75, .9, .95))
    return r

def modern(name, dog=True):
    r = _lot(name, 40, 40); by = 5
    box(r, 0, by, .15, 15, 9, 4.2, (.85, .86, .9), .4); box(r, 3, by - 1, 4.35, 12, 7.5, 3.6, (.22, .24, .3), .4)
    box(r, -1, by, 7.9, 17, 10, .35, (.15, .15, .18))
    box(r, -2, by - 4.55, .4, 6.5, .12, 3.6, (.55, .85, 1), .05)
    for dx in (4, 7): box(r, dx, by - 4.3, 4.7, 2.2, .12, 2.6, (.55, .85, 1), .05)
    box(r, 9, by - 8, .15, 8, 8, .06, (.3, .3, .33), .9)
    # niche du husky
    box(r, -9, -8, .15, 3.2, 3, 2.2, (.75, .5, .3)); gable(r, -9, -8, 2.35, 3.2, 3, 1.4, (.5, .25, .15), .3)
    box(r, -9, -9.6, .2, 1.4, .15, 1.4, (.1, .08, .06))
    tree(r, -15, 12); tree(r, 15, 14, 1.1)
    return r

def futur(name):
    r = _lot(name, 40, 40, (.55, .85, .7)); by = 4
    cyl(r, 0, by, .15, 6, 4, (.85, .9, .95), .2, v=48); cyl(r, 0, by, 4.1, 8.5, .6, (.7, .78, .9), .2, v=48, rx=0)
    sph(r, 0, by, 5.2, 4.2, (.5, .9, 1), (1, 1, .8), rough=.05, seg=32)
    box(r, 0, by - 6.1, .15, 2.2, .2, 2.8, (.3, .85, .95), .1)
    for a in range(0, 360, 60): cyl(r, 8.5 * math.cos(math.radians(a)), by + 8.5 * math.sin(math.radians(a)), .15, .2, 5, (.8, .9, 1), v=8)
    return r

def bakery(name):
    r = _lot(name, 44, 36, (.6, .6, .6)); by = 4
    box(r, 0, by, .15, 15, 10, 5, (.95, .72, .4), .6); gable(r, 0, by, 5.15, 15, 10, 2.4, (.55, .27, .15))
    for i in range(10): box(r, -6.3 + i * 1.4, by - 5.9, 3.0, 1.3, 2.4, .12, (1, 1, 1) if i % 2 else (.85, .15, .15))
    box(r, 0, by - 5.1, 2.9, 15.3, 1.4, .2, (.8, .2, .2)); sign(r, "BOULANGERIE", 0, by - 5.25, 5.4, 11, 1.9, (.4, .22, .1))
    window(r, -3.5, by - 5.06, 1.0, 4, 1.8); door(r, 3.5, by - 5.05, .15, 1.8, 2.5)
    for i in range(3): box(r, -9 + i * 1.8, -9, .15, 1.2, 1.2, .8, (.7, .45, .2))
    tree(r, -17, 9); tree(r, 17, 9)
    return r

def mall(name):
    r = _lot(name, 72, 62, (.5, .5, .52)); by = 12
    box(r, 0, by, .15, 44, 24, 10, (.88, .9, .95), .5); box(r, 0, by - 12.6, 5, 44, 1.2, .3, (.2, .4, .85))
    box(r, 0, by - 12.05, .15, 14, .3, 4.6, (.45, .8, 1), .05); sign(r, "CENTRE COMMERCIAL", 0, by - 12.2, 10.3, 30, 2.8, (.15, .3, .7))
    for i in range(6): box(r, -16 + i * 6.4, by - 12.1, 5.4, 4, .15, 3.6, (.6, .85, 1), .05)
    box(r, -18, by - 13.5, 6.5, 8, .2, 2.0, (.9, .2, .5)); text(r, "COIFFEUR", -18, by - 13.7, 7.5, 1.0)
    rr = random.Random(2)
    for i in range(12): car(r, -28 + (i % 6) * 10, -14 - (i // 6) * 8, tuple(rr.random() * .8 + .1 for _ in range(3)), math.pi / 2)
    return r

def gaming(name):
    r = _lot(name, 44, 40, (.35, .35, .4)); by = 4
    box(r, 0, by, .15, 20, 13, 6.5, (.23, .16, .4), .4); box(r, 0, by - 6.6, 3, 21, 1.2, .25, (.7, .3, 1), .3)
    sign(r, "SALLE GAMING", 0, by - 6.7, 6.8, 16, 2.2, (.1, .05, .2), (.4, 1, .9))
    window(r, -5, by - 6.56, 1.0, 5, 2.4, -1, (.6, .3, 1)); door(r, 5, by - 6.55, .15, 2.2, 2.6, (.15, .1, .25))
    box(r, -14, -9, .15, 3, 1.1, 2.6, (.1, .1, .12)); box(r, -14, -9.6, 1.4, 2.6, .1, 1.1, (.4, 1, .8), .05)
    return r

def vet(name):
    r = house(name, (.95, 1, .95), (.2, .6, .35), 14, 9.5)
    box(r, 0, 4 - 5.5, 8.6, 3, .3, 1, (1, 1, 1)); box(r, 0, 4 - 5.5, 8.1, 1, .3, 3, (.1, .7, .3)); box(r, 0, 4 - 5.5, 8.1 + 1.0, 3, .3, 1, (.1, .7, .3))
    sign(r, "CLINIQUE VETO", 0, 4 - 5.3, 5.7, 10, 1.6, (.1, .6, .3))
    sph(r, 8, -7, .8, .8, (.6, .4, .25), (1.3, .7, 1)); sph(r, 9, -7, 1.4, .45, (.6, .4, .25)); sph(r, -9, -8, .5, .45, (1, 1, 1), (1, 1.3, .8))
    return r

def cinema(name):
    r = _lot(name, 48, 42, (.4, .4, .43)); by = 4
    box(r, 0, by, .15, 24, 15, 9.5, (.65, .12, .15), .5); box(r, 0, by - 8.5, 5.8, 20, 2.4, .5, (1, .85, .3), .3)
    sign(r, "CINE CLAP", 0, by - 7.7, 8.2, 18, 2.6, (.12, .05, .08), (1, .85, .3))
    for i in range(4): box(r, -7.5 + i * 5, by - 7.62, 1.8, 3.6, .15, 3.4, (.2, .35, .8 - i * .15))
    door(r, 0, by - 7.55, .15, 2.4, 2.6, (.1, .08, .08))
    return r

def garage(name):
    r = _lot(name, 44, 36, (.45, .45, .47)); by = 3
    box(r, 0, by, .15, 22, 12, 6, (.7, .74, .8), .5)
    for i in range(3): box(r, -6.5 + i * 6.5, by - 6.05, .15, 5, .2, 4.3, (.95, .55, .12), .4)
    sign(r, "GARAGE", 0, by - 6.2, 6.4, 10, 1.7, (.15, .15, .2), (1, .6, .15))
    car(r, -10, -9, (.2, .4, .9), .4); car(r, 11, -8, (.9, .85, .1), -.3)
    return r

def ecole(name):
    r = _lot(name, 62, 52); by = 6
    box(r, 0, by, .15, 32, 14, 8, (1, .82, .3), .6); gable(r, 0, by, 8.15, 32, 14, 3.5, (.8, .25, .2))
    box(r, 0, by - 7.3, .15, 8, 2, 6, (1, .9, .5)); box(r, 0, by, 8.15, 5, 5, 4, (1, .82, .3)); cone4(r, 0, by, 12, 6, 6, 3.5, (.8, .25, .2))
    sign(r, "ECOLE", 0, by - 8.4, 6.8, 7, 1.6, (.2, .3, .7))
    for dx in (-12, -8, 8, 12): window(r, dx, by - 7.06, 1.4, 2.4, 2.4); window(r, dx, by - 7.06, 4.8, 2.4, 2.2)
    cyl(r, 14, -8, .15, .12, 9, (.8, .8, .8), v=8); box(r, 15.2, -8, 8, 2.4, .1, 1.4, (.1, .55, .2))
    for i in range(3): box(r, -18 + i * 2.2, -12, .15, 1.8, 1.8, .15, (.9, .3, .3))
    tree(r, -26, 10); tree(r, 26, 10)
    return r

def mairie(name):
    r = _lot(name, 62, 52, (.5, .78, .45)); by = 6
    box(r, 0, by, .15, 24, 12, 9, (.96, .92, .78), .6); box(r, 0, by, 9.15, 25, 13, .6, (.28, .33, .78), .5)
    gable(r, 0, by, 9.7, 18, 12, 3, (.28, .33, .78))
    box(r, 0, by - 4, 9.7, 5, 5, 6, (.96, .92, .78)); cone4(r, 0, by - 4, 15.6, 6.5, 6.5, 4, (.28, .33, .78))
    cyl(r, 0, by - 6.6, 11, 1.4, .25, (1, 1, 1), v=24, rx=math.pi / 2); sign(r, "MAIRIE", 0, by - 6.2, 6.6, 8, 1.5, (.28, .33, .78))
    for i in range(4): cyl(r, -4.5 + i * 3, by - 6.8, .15, .45, 5.4, (1, 1, 1), v=12)
    box(r, 0, by - 6.9, .15, 12, 3, .4, (.85, .85, .85)); box(r, 0, by - 8.5, .15, 12, 2, .25, (.85, .85, .85))
    for dx in (-9.5, 9.5): window(r, dx, by - 6.06, 1.8, 2, 3); window(r, dx, by - 6.06, 5.5, 2, 2.2)
    cyl(r, 11, -8, .15, .15, 11, (.85, .85, .85), v=8); box(r, 12.3, -8, 10, 2.6, .1, 1.5, (.1, .4, .9))
    tree(r, -25, 12); tree(r, 25, 12); tree(r, -24, -14); tree(r, 24, -14)
    return r

def stade(name, w=46, d=30):
    r = _lot(name, 72, 66, (.6, .6, .62)); lawn_c = (.2, .65, .22)
    box(r, 0, 0, .16, w, d, .05, lawn_c, .9)
    for i in range(-int(w / 2), int(w / 2), 6): box(r, i + 3, 0, .22, 3, d, .02, (.17, .58, .2), .9)
    L = (1, 1, 1)
    for yy in (-d / 2, d / 2): box(r, 0, yy, .24, w, .25, .02, L)
    for xx in (-w / 2, w / 2): box(r, xx, 0, .24, .25, d, .02, L)
    box(r, 0, 0, .24, .25, d, .02, L); cyl(r, 0, 0, .24, 4, .02, L, v=32); cyl(r, 0, 0, .27, 3.8, .02, lawn_c, v=32)
    for sx in (-1, 1):
        box(r, sx * (w / 2), 0, .2, .2, 7.3, 2.4, L); box(r, sx * (w / 2 + .3), 0, 2.4, .1, 7.3, .2, L)
    cols = [(.85, .15, .15), (.15, .3, .8)]
    for k in range(5):  # tribune nord (derrière les joueurs)
        box(r, 0, d / 2 + 4 + k * 1.5, .16, w + 6, 1.5, 1 + k * 1.1, cols[1] if k % 2 == 0 else (.9, .9, .9), .6)
    for k in range(4):
        for sx in (-1, 1): box(r, sx * (w / 2 + 4 + k * 1.5), 0, .16, 1.5, d, 1 + k * 1.0, (.9, .8, .2) if k % 2 == 0 else (.9, .9, .9), .6)
    box(r, 0, d / 2 + 11.7, 6.4, w + 8, 4, .3, (.3, .3, .35))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(r, sx * (w / 2 + 9), sy * (d / 2 + 9), .16, .3, 16, (.7, .7, .75), v=8); box(r, sx * (w / 2 + 9), sy * (d / 2 + 9), 16, 3.2, 1.2, 1.6, (1, 1, .8), .2)
    rr = random.Random(5)
    for k in range(60):
        xx = rr.uniform(-w / 2 - 2, w / 2 + 2); kk = rr.randint(0, 3)
        sph(r, xx, d / 2 + 4.5 + kk * 1.5, 2.2 + kk * 1.1, .35, tuple(rr.random() * .7 + .2 for _ in range(3)))
    sign(r, "STADE FC PETITBOURG", 0, -d / 2 - 15, 0.2, 30, 2.2, (.1, .15, .5))
    return r

def chantier(name, label):
    r = _lot(name, 56, 52, (.74, .62, .42))
    for i in range(-3, 4):
        for sx in (-1, 1): cyl(r, sx * 27, i * 7, .15, .35, 1.1, (1, .4, .05), v=10)
        cyl(r, i * 7, -25, .15, .35, 1.1, (1, .4, .05), v=10)
    sign(r, label, 0, -22, 1.0, 18, 4.2, (.95, .75, .1), (.1, .1, .1))
    box(r, -10, 0, .15, 6, 6, 3, (.8, .6, .3)); box(r, 8, 6, .15, 10, 3, 1.2, (.5, .5, .55))
    cyl(r, 16, 12, .15, .6, 18, (.95, .8, .1), v=8); box(r, 8, 12, 17, 17, .8, .8, (.95, .8, .1))
    return r

def filler(name, seed):
    rr = random.Random(seed); pal = [(1, .78, .55), (.95, .6, .7), (.7, .88, .95), (.98, .95, .8), (.75, .95, .75)]
    return house(name, rr.choice(pal), rr.choice([(.8, .25, .2), (.3, .35, .8), (.4, .3, .25)]), 11 + rr.random() * 3, 8.5)

def roads(xs, ys, x0, x1, y0, y1, rw=10):
    r = root("roads"); box(r, (x0 + x1) / 2, (y0 + y1) / 2, -.2, x1 - x0 + 200, y1 - y0 + 200, .2, (.42, .8, .3), .95)
    for x in xs: box(r, x, (y0 + y1) / 2, -.02, rw, y1 - y0 + 100, .06, (.2, .21, .25), .8)
    for y in ys: box(r, (x0 + x1) / 2, y, -.02, x1 - x0 + 100, rw, .06, (.2, .21, .25), .8)
    for x in xs:
        for yy in range(int(y0 - 40), int(y1 + 40), 8): box(r, x, yy, .05, .3, 3.6, .02, (1, 1, 1))
    for y in ys:
        for xx in range(int(x0 - 40), int(x1 + 40), 8): box(r, xx, y, .05, 3.6, .3, .02, (1, 1, 1))
    return r

# ------------------------------------------------------------------ characters
def person(name, coat=(.3, .5, .9), hair=(.2, .13, .08), skin=(.95, .73, .55), pants=(.15, .15, .25), hat=None,
           number=None, tag=None, mayor=False, s=1.0, gk=False):
    r = root(name)
    for sx in (-.2, .2): box(r, sx * s, 0, 0, .3 * s, .3 * s, .85 * s, pants)
    if mayor:
        sph(r, 0, 0, 1.0 * s, .6 * s, coat, (1, .8, .9))
        box(r, 0, -.5 * s, 1.1 * s, .2 * s, .1 * s, .9 * s, (.85, .15, .15))
    else:
        box(r, 0, 0, .8 * s, .72 * s, .42 * s, .8 * s, coat, .5)
    for sx in (-1, 1):
        box(r, sx * .5 * s, 0, .85 * s, .2 * s, .22 * s, .7 * s, coat if not mayor else coat); sph(r, sx * .5 * s, 0, .8 * s, .13 * s, skin, seg=10)
    hz, hr = (1.72, .3) if mayor else (1.58, .26)
    sph(r, 0, 0, hz * s, hr * s, skin, seg=16)
    sph(r, -.09 * s, -(hr - .03) * s, (hz + .04) * s, .04 * s, (0, 0, 0), seg=8); sph(r, .09 * s, -(hr - .03) * s, (hz + .04) * s, .04 * s, (0, 0, 0), seg=8)
    if mayor:
        box(r, 0, -.28 * s, 1.62 * s, .3 * s, .06 * s, .07 * s, (.45, .22, .08))
        box(r, 0, 0, 1.98 * s, .85 * s, .85 * s, .05 * s, (.1, .3, .15)); box(r, 0, 0, 2.0 * s, .52 * s, .52 * s, .34 * s, (.1, .3, .15))
        for sx in (-.1, .1):
            sph(r, sx * s, -.3 * s, 1.77 * s, .08 * s, (1, .8, .1), (1, .3, 1), seg=10)
    elif hat == "cap": box(r, 0, 0, 1.78 * s, .5 * s, .5 * s, .12 * s, coat)
    elif hat == "hair": sph(r, 0, .03 * s, 1.68 * s, .27 * s, hair, (1, 1, .7), seg=12)
    else: sph(r, 0, .03 * s, 1.68 * s, .27 * s, hair, (1, 1, .7), seg=12)
    if number is not None: text(r, str(number), 0, -.23 * s, 1.15 * s, .45 * s, (1, 1, 1))
    if tag: nametag(r, tag, (2.75 if mayor else 2.35) * s)
    return r

TRACK = {"cam": None}
def nametag(par, s, z, size=.4, bg=(.08, .08, .1), fg=(1, 1, 1)):
    t = root("tag"); t.parent = par; t.location = (0, 0, z)
    w = max(2.0, len(s) * size * .58 + .5)
    box(t, 0, 0, -.09, w, size * 1.15, .05, bg, .8)
    text(t, s, 0, 0, 0, size, fg, rot=(0, 0, 0))
    if TRACK["cam"] is not None:
        c = t.constraints.new('TRACK_TO'); c.target = TRACK["cam"]; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
    return t
