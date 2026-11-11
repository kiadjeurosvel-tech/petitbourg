import os, json, base64, subprocess, re, requests
TEXT = ("Habitants de Port-Lanterne, grande nouvelle : le village a maintenant son groupe de discussion ! "
        "Vous y retrouvez les nouvelles vidéos, vous discutez entre voisins et vous partagez vos idées. "
        "Pour qu'une demande soit construite, elle reste en commentaire sous la vidéo. "
        "Le lien est en bio. Merci au maire, qui s'occupe du groupe !")
CH = [("Habitants de Port-Lanterne,", .53, 3.33), ("grande nouvelle :", 3.33, 5.13), ("le village a maintenant", 5.13, 7.53), ("son groupe de discussion !", 7.53, 10.2),
      ("Vous y retrouvez les", 10.2, 12.33), ("nouvelles vidéos,", 12.33, 14.2), ("vous discutez entre", 14.2, 16.33), ("voisins et vous partagez", 16.33, 18.87), ("vos idées.", 18.87, 20.07),
      ("Pour qu'une demande", 20.07, 22.2), ("soit construite,", 22.2, 24.0), ("elle reste en commentaire", 24.0, 26.6), ("sous la vidéo.", 26.6, 28.2),
      ("Le lien est en", 28.2, 29.93), ("bio. Merci au maire,", 29.93, 32.0), ("qui s'occupe du groupe !", 32.0, 34.3)]
SPEED = float(os.environ.get("SPEED", "0.88"))
r = requests.post("https://api.elevenlabs.io/v1/text-to-speech/TX3LPaxmHKxFdv7VOQHJ/with-timestamps?output_format=mp3_44100_128",
                  headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                  json={"text": TEXT, "model_id": "eleven_multilingual_v2", "language_code": "fr",
                        "voice_settings": {"stability": .5, "similarity_boost": .8, "style": .15, "speed": SPEED, "use_speaker_boost": True}}, timeout=180)
r.raise_for_status(); j = r.json()
open("voice.mp3", "wb").write(base64.b64decode(j["audio_base64"]))
al = j["alignment"]; cs, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
full = "".join(cs); pos = 0; segs = []
for txt, w0, w1 in CH:
    i = full.find(txt, pos); assert i >= 0, txt
    k = i + len(txt) - 1; pos = k + 1
    while full[i] == " ": i += 1
    a, b = st[i], en[k]; segs.append((txt, a, b, w0, w1))
segs2 = []
t = 0.35  # new timeline cursor
fa = []; fv = []; labs = []
fv.append("[1:v]trim=start=0:end=0.53,setpts=(PTS-STARTPTS)*%.4f,fps=30[v_i]" % (0.35 / 0.53)); labs.append("[v_i]")
for n, (txt, a, b, w0, w1) in enumerate(segs):
    a0 = max(0, a - .03); b0 = b + .05; nat = b0 - a0
    end = txt.rstrip()[-1]; pause = .5 if end in "!." else (.3 if end in ",:" else .12)
    nd = nat + pause; old = w1 - w0; f = nd / old
    print(f"{n+1:2d} {txt:28s} nat={nat:.2f} old={old:.2f} new={nd:.2f} videofactor={f:.2f} start={t:.2f}")
    fa.append(f"[0:a]atrim=start={a0:.3f}:end={b0:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={max(0,nat-.04):.3f}:d=0.04,adelay={int(t*1000)}|{int(t*1000)}[c{n}]")
    fv.append(f"[1:v]trim=start={w0}:end={w1},setpts=(PTS-STARTPTS)*{f:.4f},fps=30[v{n}]"); labs.append(f"[v{n}]")
    t += nd
fv.append("[1:v]trim=start=34.3:end=35.02,setpts=PTS-STARTPTS,fps=30[v_t]"); labs.append("[v_t]"); total = t + .72
fc = fv + fa
fc.append("".join(labs) + f"concat=n={len(labs)}:v=1:a=0[vout]")
fc.append("".join(f"[c{n}]" for n in range(len(segs))) + f"amix=inputs={len(segs)}:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=7,apad=whole_dur={total:.2f}[aout]")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voice.mp3", "-i", "extra/video.mp4", "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", "out.mp4"], check=True)
print("done total", total)
