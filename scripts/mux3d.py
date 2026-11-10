"""mux3d.py work_dir frames_dir out.mp4 : assemble frames + overlays + subtitles + voice"""
import sys, json, subprocess, os
w, fr, out = sys.argv[1:4]; ov = json.load(open(w + "/overlays.json")); dur = json.load(open(w + "/timing.json"))["dur"]
cmd = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", "15", "-i", fr + "/f_%04d.png"]
for o in ov: cmd += ["-i", w + "/" + o["png"]]
cmd += ["-i", w + "/voice.mp3"]
f = ["[0:v]scale=1080:1920:flags=lanczos,fps=30,eq=saturation=1.5:contrast=1.1:brightness=0.02:gamma=0.95[b0]"]
for i, o in enumerate(ov):
    f.append(f"[b{i}][{i+1}:v]overlay={o['x']}:{o['y']}:enable='between(t,{o['t0']:.2f},{o['t1']:.2f})'[b{i+1}]")
f.append(f"[b{len(ov)}]ass={w}/subs.ass:fontsdir=assets,format=yuv420p[v]")
cmd += ["-filter_complex", ";".join(f), "-map", "[v]", "-map", f"{len(ov)+1}:a", "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", out]
subprocess.run(cmd, check=True)
