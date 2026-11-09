import bpy, sys, json, math, os, random, time
T0 = time.time()
def lg(m): print(f'[T {time.time()-T0:6.1f}s] {m}', flush=True)
sys.path.insert(0, os.path.dirname(__file__))
import lib3d as L
A = sys.argv[sys.argv.index("--") + 1:]
EP, TM, OUT, MODE = json.load(open(A[0])), json.load(open(A[1])), A[2], A[3]
FPS = 15; CELL = 80
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except Exception: pass
for k, v in (("taa_render_samples", 6), ("use_gtao", True), ("gtao_distance", 2.5), ("use_soft_shadows", True), ("shadow_cascade_size", '1024'), ("shadow_cube_size", '1024')):
    try: setattr(sc.eevee, k, v)
    except Exception: pass
sc.render.resolution_x, sc.render.resolution_y = 540, 960
sc.render.fps = FPS; sc.render.image_settings.file_format = 'PNG'
try: sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
except Exception: pass

# --- camera, light, sky
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50; cam.data.clip_end = 1500
L.TRACK["cam"] = cam
tgt = bpy.data.objects.new("tgt", None); sc.collection.objects.link(tgt)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
sun = bpy.data.lights.new("sun", 'SUN'); sun.energy = 3.0; sun.angle = .08
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(48), math.radians(8), math.radians(28))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (.5, .72, 1, 1); w.node_tree.nodes["Background"].inputs[1].default_value = .55

def join(rt):
    ms = [o for o in bpy.data.objects if o.parent == rt and o.type == 'MESH']
    if len(ms) > 1:
        try:
            with bpy.context.temp_override(active_object=ms[0], selected_editable_objects=ms, selected_objects=ms): bpy.ops.object.join()
        except Exception as ex: print("join fail", ex)
def joinall():
    for o in [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name not in ("tgt",)]: join(o)

# --- city layout
def P(i, j): return (CELL * i, CELL * j)
def omar_extra(r, by):
    for sx in (-1, 1): L.cyl(r, 9 + sx * 1.6, -7, .15, .1, 3.2, (.5, .3, .15), v=8)
    L.box(r, 9, -7, 3.3, 3.6, .15, .15, (.5, .3, .15)); L.box(r, 8.4, -7, 1.1, .7, .5, .06, (.9, .2, .2)); L.box(r, 9.6, -7, 1.1, .7, .5, .06, (.9, .2, .2))
    L.sph(r, -8, -9, .35, .35, (.95, .6, .2), (1.5, .8, 1)); L.sph(r, -7.3, -9, .75, .25, (.95, .6, .2))
LOTS = {
 "mairie": (L.mairie, 0, 4, {}), "ecole": (L.ecole, -1, 4, {}), "stade": (L.stade, 1, 4, {}),
 "pikta": (L.villa, -3, 2, dict(lake=True, wall=(.98, .96, .9), rf=(.25, .3, .45))),
 "omar": (L.house, -2, 2, dict(wall=(1, .85, .6), rf=(.75, .25, .2), extra=omar_extra)),
 "rose": (L.villa, -1, 2, dict(wall=(1, .72, .82), rf=(.8, .3, .5))),
 "elina": (L.villa, 0, 2, dict(jac=True, wall=(.98, .98, .95), rf=(.2, .22, .3))),
 "keiton": (L.igloo, 1, 2, {}), "raph": (L.modern, 2, 2, {}), "hvk": (L.futur, 3, 2, {}),
 "hopital": (L.chantier, -2, 4, dict(label="HOPITAL ?")), "parc": (L.chantier, 2, 4, dict(label="PARC ?")), "caserne": (L.chantier, 3, 4, dict(label="CASERNE ?")),
 "boul": (L.bakery, -3, 6, {}), "mall": (L.mall, -2, 6, {}), "gaming": (L.gaming, -1, 6, {}), "vet": (L.vet, 0, 6, {}),
 "cine": (L.cinema, 1, 6, {}), "garage": (L.garage, 2, 6, {}),
}
used = {(v[1], v[2]) for v in LOTS.values()}
roots, pos = {}, {}
for k, (fn, i, j, kw) in LOTS.items():
    r = fn(k, **kw); x, y = P(i, j); r.location = (x, y, 0); roots[k] = r; pos[k] = (x, y)
for i in range(-3, 4):
    for j in range(0, 7):
        if (i, j) in used: continue
        r = L.filler(f"f{i}_{j}", i * 31 + j); r.location = P(i, j) + (0,)
L.roads([CELL * i + CELL / 2 for i in range(-5, 4)], [CELL * j + CELL / 2 for j in range(-1, 8)], -300, 300, 0, 560)

# --- characters
def lotp(k, dx=2.6, dy=-7.5): x, y = pos[k]; return (x + dx, y + dy)
C = {}
def mk(cid, tag, at, **kw):
    kw.setdefault("tag", tag); r = L.person(cid, **kw); r.location = (at[0], at[1], 0); C[cid] = r; return r
BLUE, RED, GRN, YEL = (.15, .35, .85), (.85, .15, .15), (.1, .65, .25), (.95, .8, .1)
mayor = L.person("mayor", coat=(.12, .5, .28), mayor=True, s=1.0, tag="LE MAIRE"); mayor.location = (0, 0, 0)
hair = lambda i: [(.1, .07, .05), (.45, .25, .1), (.8, .6, .2), (.05, .05, .05)][i % 4]
owners = {"omar": ("@mar_64kk", (.2, .5, .9)), "rose": ("@nd.k601", (.9, .4, .6)), "elina": ("@elina.2286", (.7, .3, .8)), "keiton": ("@keitonakamuraaaalp", (.3, .75, .85)),
          "raph": ("@raph_ikih", (.35, .35, .4)), "pikta": ("@pikta", (.95, .6, .2)), "hvk": ("@hvksilix", (.3, .9, .9)),
          "boul": ("@bhgd.974", (.9, .75, .5)), "mall": ("@theoxtar", (.2, .3, .7)), "gaming": ("@goku25603", (.5, .2, .8)),
          "cine": ("@nathan.2402", (.8, .2, .3)), "garage": ("@gabibel803", (.95, .5, .1)), "vet": ("@raph_ikih", (.2, .7, .4)),
          "ecole": ("@la.vie.en.couleur69", (.95, .8, .2)), "parc": ("@lacsorbx", (.2, .7, .3)), "hopital": ("@i.abdhi", (.9, .9, .95)), "caserne": ("@cindydoudie", (.4, .5, .3))}
for n, (k, (tag, coat)) in enumerate(owners.items()):
    off = (2.6, -7.5)
    if k in ("mall", "cine", "garage", "gaming", "boul"): off = (4, -9)
    if k in ("hopital", "parc", "caserne"): off = (0, -19)
    mk("o_" + k, tag, lotp(k, *off), coat=coat, hair=hair(n), pants=(.2, .2, .3))
sx, sy = pos["stade"]
TEAM = [("gaetan", "Gaetan  GK", 1, GRN, (-8, -3)), ("timeo", "Timeo  GK", 16, GRN, (-4, -3)), ("dan", "Dan  GK", 12, GRN, (0, -3)),
        ("robin", "Robin  LD", 2, BLUE, (-8, -8)), ("brjc", "Brjc  MDC", 6, BLUE, (-4, -8)), ("sidy", "Sidy  CAPITAINE", 10, BLUE, (0, -8)),
        ("eden", "Eden  AD", 11, RED, (4, -8)), ("mak", "Mak  ATT", 9, RED, (8, -8)), ("marlon", "Marlon  ATT", 7, RED, (12, -8))]
for n, (cid, tag, num, col, (dx, dy)) in enumerate(TEAM):
    mk(cid, tag, (sx + dx, sy + dy - 4), coat=col, hair=hair(n), pants=(1, 1, 1), number=num)
mk("evan", "Coach Evan", (sx - 11, sy - 12), coat=(.1, .1, .12), pants=(.1, .1, .12), hair=hair(1))
mk("gilet", "@billiejean130", (6, 311), coat=(1, .85, .1), hair=hair(2))

lg('built'); joinall(); lg('joined')

# --- animation helpers
def F(t): return int(round(t * FPS)) + 1
def kf(o, prop, f, v=None, interp='LINEAR', idx=-1):
    if v is not None: setattr(o, prop, v)
    o.keyframe_insert(prop, frame=f, index=idx)
    ad = o.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            if fc.data_path == prop:
                for p in fc.keyframe_points:
                    if p.co[0] == f: p.interpolation = interp
def pop(o, f0):
    for p in (f0 - 1, ):
        kf(o, "scale", 1, (.001, .001, .001)); kf(o, "scale", f0 - 1, (.001, .001, .001))
    kf(o, "scale", f0 + 4, (1.12, 1.12, 1.12)); kf(o, "scale", f0 + 8, (1, 1, 1))
def hide0(o): o.scale = (.001, .001, .001)

scenes = EP["scenes"]; TS = TM["scenes"]; NF = F(TM["dur"])
sc.frame_start, sc.frame_end = 1, NF
pend = {}
for s in scenes:
    for k in s.get("new", []): pend[k] = True; hide0(roots[k])
    for k in s.get("show", []): pend[k] = True; hide0(C[k] if k in C else mayor)
for si, s in enumerate(scenes):
    f0 = F(TS[si]["t0"]); f1 = F(TS[si]["t1"])
    for k in s.get("new", []): pop(roots[k], f0 + 6)
    for k in s.get("show", []): pop(C.get(k, mayor) if k != "mayor" else mayor, f0 + 4)
    for k in s.get("hide", []):
        o = C.get(k, mayor); kf(o, "scale", f0, (1, 1, 1)); kf(o, "scale", f0 + 1, (.001, .001, .001))
    shots = s["shots"]; wts = [sh.get("w", 1) for sh in shots]; tot = sum(wts); acc = 0; fr = f0
    for n, sh in enumerate(shots):
        a = fr; acc += wts[n]; b = f1 - 1 if n == len(shots) - 1 else f0 + int((f1 - f0) * acc / tot) - 1
        fr = b + 1
        if "lot" in sh: x, y = pos[sh["lot"]]; c0 = c1 = (x + sh.get("dx", 0), y + sh.get("dy", -4), sh.get("cz", 2.5))
        elif "who" in sh:
            o = C.get(sh["who"], mayor); c0 = c1 = (o.location.x + sh.get("dx", 0), o.location.y, sh.get("cz", 1.3))
        else: c0, c1 = sh["c0"], sh.get("c1", sh["c0"])
        if "c1z" in sh: c1 = (c1[0], c1[1], sh["c1z"])
        for e, c, kk in ((a, c0, "0"), (b, c1, "1")):
            d = sh["d" + kk] if "d" + kk in sh else sh["d0"]; az = math.radians(sh.get("a" + kk, sh.get("a0", 0))); el = math.radians(sh.get("e" + kk, sh.get("e0", 8)))
            kf(cam, "location", e, (c[0] + d * math.sin(az) * math.cos(el), c[1] - d * math.cos(az) * math.cos(el), c[2] + d * math.sin(el)))
            kf(tgt, "location", e, c)
        mp = sh.get("mayor")
        if mp:
            if isinstance(mp, str): mx, my = lotp(mp, -2.6, -7.5)
            else: mx, my = mp[0], mp[1]
            mayor.location = (mx, my, 0); kf(mayor, "location", a, None, 'CONSTANT', 0); kf(mayor, "location", a, None, 'CONSTANT', 1)
# idle bobbing
for o in list(C.values()) + [mayor]:
    ph = random.randint(0, 8)
    for f, z in ((1 + ph, 0), (5 + ph, .07), (9 + ph, 0)):
        o.location.z = z; o.keyframe_insert("location", frame=f, index=2)
    try:
        fc = [c for c in o.animation_data.action.fcurves if c.data_path == "location" and c.array_index == 2][0]; fc.modifiers.new('CYCLES')
    except Exception: pass

if MODE == "preview":
    fl = []
    for si, s in enumerate(scenes):
        f0 = F(TS[si]["t0"]); f1 = F(TS[si]["t1"]); n = len(s["shots"]); wts = [sh.get("w", 1) for sh in s["shots"]]; tot = sum(wts); acc = 0
        for k in range(n): fl.append(f0 + int((f1 - f0) * (acc + wts[k] * .45) / tot)); acc += wts[k]
    for k, f in enumerate(fl):
        sc.frame_set(f); bpy.context.view_layer.update(); sc.render.filepath = f"{OUT}/p_{k:03d}.png"
        lg(f"frame {f} cam={tuple(round(v,1) for v in cam.matrix_world.translation)} tgt={tuple(round(v,1) for v in tgt.matrix_world.translation)}")
        bpy.ops.render.render(write_still=True); lg("rendered")
else:
    sc.render.filepath = OUT + "/f_"; bpy.ops.render.render(animation=True)
