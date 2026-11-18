"""prep3d.py episode.json out_dir [--dry] : voix ElevenLabs (cache), timing.json, subs.ass, overlays/*.png + overlays.json"""
import sys, os, json, re, shutil
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import render as R
from PIL import Image, ImageDraw, ImageFont
ep = json.load(open(sys.argv[1])); out = sys.argv[2]; dry = "--dry" in sys.argv
os.makedirs(out + "/ov", exist_ok=True)
FONT = os.path.join(ROOT, "assets", "Poppins-Bold.ttf"); Fn = lambda s: ImageFont.truetype(FONT, s)
scenes = ep["scenes"]; parts, offs, pos = [], [], 0
for s in scenes:
    s["_first"] = pos
    for ln in s["lines"]: parts.append(ln); pos += len(ln) + 1
text = " ".join(parts)
mp3 = out + "/voice.mp3"; cache = os.path.join(ROOT, "episodes", "voice_cache", ep["out_name"])
if not dry and os.path.exists(cache + ".json") and json.load(open(cache + ".json"))["text"] == text:
    shutil.copy(cache + ".mp3", mp3); dur, starts = json.load(open(cache + ".json"))["timing"]
else:
    dur, starts = R.tts(text, ep.get("voice_id", R.DEFAULT_VOICE), mp3, dry=dry)
    if not dry:
        os.makedirs(os.path.dirname(cache), exist_ok=True); shutil.copy(mp3, cache + ".mp3")
        json.dump({"text": text, "timing": [dur, starts]}, open(cache + ".json", "w"))
DUR = dur + 2.0
ts = []
for i, s in enumerate(scenes): ts.append(0.0 if i == 0 else max(0.0, starts[s["_first"]] - 0.15))
tm = {"dur": DUR, "scenes": [{"t0": ts[i], "t1": ts[i + 1] if i + 1 < len(ts) else DUR} for i in range(len(ts))]}
json.dump(tm, open(out + "/timing.json", "w"))
# ---- sous-titres
caps = R.build_captions(text, starts, DUR, ep.get("highlight", []))
def tc(t): h = int(t // 3600); m = int(t % 3600 // 60); return f"{h}:{m:02d}:{t % 60:05.2f}"
ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "", "[V4+ Styles]",
       "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
       "Style: D,Poppins,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,2,60,60,300,1", "", "[Events]",
       "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
def scol(a):
    si = max([i for i in range(len(tm["scenes"])) if tm["scenes"][i]["t0"] <= a + 0.05] or [0]); sp = scenes[si].get("speaker")
    return "&H00%02X%02X%02X&" % (sp["color"][2], sp["color"][1], sp["color"][0]) if sp else "&HFFFFFF&"
for a, b, t in caps:
    cc = scol(a)
    t = re.sub(r"\[(.*?)\]", lambda m: "{\\c&H00D7FF&}" + m.group(1) + "{\\c" + cc + "}", t); t = "{\\c" + cc + "}" + t
    ass.append(f"Dialogue: 0,{tc(a)},{tc(b)},D,,0,0,0,,{t}")
open(out + "/subs.ass", "w").write("\n".join(ass))
# ---- surcouches
COL = {"red": (215, 40, 40), "green": (40, 160, 70), "orange": (240, 130, 20), "blue": (40, 90, 200), "gold": (245, 190, 20), "dark": (25, 25, 30)}
def rr(d, box, r, fill, outline=None, w=0): d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)
def mk_label(txt, color, size=64):
    f = Fn(size); w = int(f.getlength(txt)) + 90; h = size + 50
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); rr(d, (0, 0, w - 1, h - 1), 26, COL.get(color, color), (255, 255, 255), 6)
    d.text((w // 2, h // 2), txt, font=f, fill=(255, 255, 255), anchor="mm"); return im
def mk_card(user, txt, likes):
    W = 940; fu, ft = Fn(34), Fn(40); lines, cur = [], ""
    for wd in txt.split():
        if ft.getlength(cur + " " + wd) > W - 200: lines.append(cur); cur = wd
        else: cur = (cur + " " + wd).strip()
    lines.append(cur); H = 110 + 52 * len(lines)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); rr(d, (0, 0, W - 1, H - 1), 30, (255, 255, 255), (230, 230, 230), 3)
    d.ellipse((28, 28, 108, 108), fill=(110, 130, 200)); d.text((68, 68), user[0].upper(), font=Fn(44), fill=(255, 255, 255), anchor="mm")
    d.text((130, 26), "@" + user.lstrip("@"), font=fu, fill=(110, 110, 120))
    for i, l in enumerate(lines): d.text((130, 70 + 52 * i), l, font=ft, fill=(15, 15, 20))
    d.text((W - 60, H // 2), "♥", font=Fn(46), fill=(240, 50, 90), anchor="mm"); d.text((W - 60, H // 2 + 46), str(likes), font=Fn(28), fill=(100, 100, 100), anchor="mm")
    return im
def mk_goal(txt, frac):
    W, H = 900, 150; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); rr(d, (0, 0, W - 1, H - 1), 30, (255, 255, 255), (30, 30, 30), 5)
    d.text((40, 28), txt, font=Fn(40), fill=(20, 20, 20)); rr(d, (40, 88, W - 40, 126), 19, (235, 235, 235), (40, 40, 40), 3)
    rr(d, (44, 92, 44 + int((W - 88) * frac), 122), 15, (235, 70, 50)); return im
def mk_opt(letter, txt, color):
    f = Fn(60); w = int(f.getlength(txt)) + 190; im = Image.new("RGBA", (w, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr(d, (0, 0, w - 1, 129), 34, (255, 255, 255), COL.get(color, (40, 40, 40)), 8); d.ellipse((16, 16, 114, 114), fill=COL.get(color, (40, 40, 40)))
    d.text((65, 65), letter, font=Fn(72), fill=(255, 255, 255), anchor="mm"); d.text((140, 65), txt, font=f, fill=(20, 20, 20), anchor="lm"); return im
def mk_speaker(user, role, color):
    f = Fn(64)
    while f.size > 34 and f.getlength(user) > 800: f = Fn(f.size - 4)
    w = int(max(f.getlength(user) + 110, 520)); h = 190
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr(d, (0, 0, w - 1, h - 1), 34, COL.get(color, color), (255, 255, 255), 8)
    d.text((w // 2, 62), user, font=f, fill=(255, 255, 255), anchor="mm")
    rr(d, (24, 112, w - 25, h - 22), 22, (255, 255, 255)); d.text((w // 2, 149), role, font=Fn(40), fill=(20, 20, 25), anchor="mm"); return im
ovs = []
for si, s in enumerate(scenes):
    sp = s.get("speaker")
    if sp: s.setdefault("overlays", []).append({"type": "speaker", "user": sp["name"], "role": sp["role"], "color": sp["color"], "y": 210})
    for k, o in enumerate(s.get("overlays", [])):
        t = o["type"]
        if t == "badge" or t == "label": im = mk_label(o["text"], o.get("color", "red"), o.get("size", 64))
        elif t == "card": im = mk_card(o["user"], o["text"], o.get("likes", 1))
        elif t == "speaker": im = mk_speaker(o["user"], o["role"], tuple(o["color"]))
        elif t == "goal": im = mk_goal(o["text"], o["frac"])
        elif t == "option": im = mk_opt(o["letter"], o["text"], o.get("color", "blue"))
        fn = f"ov/s{si}_{k}.png"; im.save(out + "/" + fn)
        a = tm["scenes"][si]["t0"] + o.get("t0", 0); b = (tm["scenes"][si]["t0"] + o["t1"]) if "t1" in o else tm["scenes"][si]["t1"]
        ovs.append({"png": fn, "x": o.get("x", (1080 - im.width) // 2), "y": o.get("y", 200), "t0": a, "t1": b})
json.dump(ovs, open(out + "/overlays.json", "w"))
open(out + "/description.txt", "w").write(ep.get("description", ""))
print("OK", round(DUR, 1), "s", len(text), "chars", len(ovs), "overlays")
