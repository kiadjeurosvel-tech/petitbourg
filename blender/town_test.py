import bpy, math, sys, random
from mathutils import Vector
random.seed(4)
OUT = sys.argv[sys.argv.index("--")+1]
FPS, SEC = 12, 6
sc = bpy.context.scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.device = 'CPU'
try: sc.cycles.use_denoising = True
except Exception: pass
sc.render.resolution_x, sc.render.resolution_y = 540, 960
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, FPS*SEC
sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = OUT + "/f_"
try: sc.view_settings.view_transform = 'Standard'
except Exception: pass

def mat(rgb, rough=.55):
    m = bpy.data.materials.new("m"); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    return m
def box(x, y, z, sx, sy, sz, m):
    bpy.ops.mesh.primitive_cube_add(location=(x, y, z + sz/2)); o = bpy.context.object
    o.scale = (sx/2, sy/2, sz/2); o.data.materials.append(m); return o
def roof(x, y, z, sx, sy, h, m):
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=max(sx, sy)*.75, depth=h, location=(x, y, z + h/2), rotation=(0, 0, math.pi/4))
    o = bpy.context.object; o.scale = (sx/max(sx, sy), sy/max(sx, sy), 1); o.data.materials.append(m); return o
def sphere(x, y, z, r, m, sc_=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, z)); o = bpy.context.object
    o.scale = sc_; bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o

green = mat((.45, .8, .25)); road = mat((.18, .19, .22)); white = mat((.95, .95, .95)); curb = mat((.9, .9, .9))
box(0, 0, -.05, 120, 120, .05, green)
for i in range(-5, 6):
    box(i*10, 0, 0, 1.6, 120, .06, road); box(0, i*10, 0, 120, 1.6, .06, road)
    box(i*10, 0, .07, .12, 120, .01, white); box(0, i*10, .07, 120, .12, .01, white)

def house(x, y, wall, rf, s=1):
    box(x, y, 0, 4*s, 3.4*s, 2.4*s, mat(wall)); roof(x, y, 2.4*s, 4.4*s, 3.8*s, 1.8*s, mat(rf))
    box(x, y-1.72*s, .01, .9*s, .1, 1.5*s, mat((.35, .22, .12)))
    for dx in (-1.2*s, 1.2*s): box(x+dx, y-1.72*s, 1.0*s, .8*s, .08, .8*s, mat((1, .9, .5)))
cols = [((1, .75, .6), (.85, .3, .25)), ((.95, .45, .65), (.3, .35, .8)), ((.98, .98, .95), (.9, .45, .4)), ((.6, .85, .95), (.25, .25, .5)), ((.85, .85, .9), (.2, .2, .25))]
spots = [(-6, 4), (0, 4), (6, 4), (-3, -4), (3, -4)]
for (x, y), (w, r) in zip(spots, cols): house(x, y, w, r)
# mairie
box(0, 22, 0, 12, 7, 5, mat((.95, .9, .75))); roof(0, 22, 5, 13, 8, 3, mat((.3, .35, .8)))
box(0, 22, 5, 2.4, 2.4, 3.6, mat((.95, .9, .75))); roof(0, 22, 8.6, 3, 3, 2.2, mat((.3, .35, .8)))
box(0, 18.4, .01, 4, .3, 3, mat((.3, .35, .8)))
# ecole
box(-22, 14, 0, 12, 6, 4, mat((1, .85, .3))); roof(-22, 14, 4, 12.6, 6.6, 2, mat((.8, .25, .2)))
# arbres
for _ in range(40):
    x, y = random.uniform(-50, 50), random.uniform(-50, 50)
    if abs(x % 10) < 2.5 or abs(y % 10) < 2.5: continue
    box(x, y, 0, .4, .4, 1.4, mat((.4, .25, .12))); sphere(x, y, 2.2, 1.2, mat((.2, .6, .22)))
# maire
mc = mat((.2, .55, .3)); skin = mat((.95, .72, .55)); hatm = mat((.15, .35, .2))
mx, my = 0, 15.5
sphere(mx, my, .9, .8, mc, (1, .8, 1.2)); sphere(mx, my, 2.2, .6, skin)
box(mx, my, 2.7, 1.3, 1.3, .1, hatm); box(mx, my, 2.75, .8, .8, .5, hatm)
sphere(mx-.2, my-.5, 2.3, .1, mat((0, 0, 0))); sphere(mx+.2, my-.5, 2.3, .1, mat((0, 0, 0)))
# lumieres
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50), 0, math.radians(30))); bpy.context.object.data.energy = 4
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (.55, .75, 1, 1)
# camera : survol -> gros plan maisons -> maire
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 30
tgt = bpy.data.objects.new("t", None); sc.collection.objects.link(tgt)
tr = cam.constraints.new('TRACK_TO'); tr.target = tgt; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
keys = [(1, (30, -40, 30), (0, 8, 0)), (int(FPS*2.5), (6, -14, 5), (0, 4, 1.5)), (int(FPS*4.5), (-5, 8, 4), (0, 18, 2)), (FPS*SEC, (0, 11, 3.2), (0, 16, 2.2))]
for f, c, t in keys:
    cam.location = c; cam.keyframe_insert("location", frame=f); tgt.location = t; tgt.keyframe_insert("location", frame=f)
for o in (cam, tgt):
    for fc in o.animation_data.action.fcurves:
        for k in fc.keyframe_points: k.interpolation = 'BEZIER'
bpy.ops.render.render(animation=True)
