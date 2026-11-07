"""Rule: one episode per day, never before the next day (Europe/Berlin).
Prints the episode path to render, or exits 1."""
import json, os, sys, datetime
from zoneinfo import ZoneInfo
st = json.load(open("state.json"))
nxt = st["last_day"] + 1
path = f"episodes/jour_{nxt}.json"
if not os.path.exists(path):
    print(f"Aucun épisode {path} à produire."); sys.exit(1)
ep = json.load(open(path))
today = datetime.datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
if ep.get("day") != nxt:
    print(f"Erreur : {path} doit avoir day={nxt}."); sys.exit(1)
if today <= st["last_date"]:
    print(f"REFUSÉ : le Jour {st['last_day']} date du {st['last_date']}. Jour {nxt} possible à partir de demain."); sys.exit(1)
if ep.get("date") != today:
    print(f"REFUSÉ : date de l'épisode {ep.get('date')} ≠ aujourd'hui {today}."); sys.exit(1)
open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a").write(f"episode={path}\nday={nxt}\ndate={today}\n")
print("OK", path)
