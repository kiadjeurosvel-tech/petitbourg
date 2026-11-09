"""Le studio : file d'attente des tâches, exécution des productions, mémoire des histoires."""
from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
from pathlib import Path

from moteur import edits, intent, montage, pipeline, story
from moteur.spec import FORMATS, QUALITIES, STYLES, frame_size, normalize_spec

from .config import Config
from .db import DB

COMMANDS = {
    "create": "Créer une vidéo",
    "continue": "Continuer une histoire",
    "new_episode": "Générer un nouvel épisode",
    "edit_scene": "Modifier une scène",
    "regenerate_scene": "Régénérer une scène",
    "rerender": "Nouveau rendu",
    "export": "Exporter",
}


class UserError(Exception):
    """Erreur compréhensible par l'utilisateur (renvoyée telle quelle)."""


class JobReporter(pipeline.Reporter):
    def __init__(self, studio: "Studio", job_id: int):
        self.s, self.id = studio, job_id
        self.stages = [{"key": k, "label": lab, "status": "pending", "done": None, "total": None, "unit": None,
                        "detail": None, "eta": None, "started": None, "finished": None} for k, lab in pipeline.STAGES]
        self._last = 0.0
        self._log = []

    def _flush(self, force=False):
        now = time.time()
        if force or now - self._last > .5:
            self._last = now
            self.s.db.update("jobs", self.id, stages=self.stages, log="\n".join(self._log[-300:]))

    def stage(self, key, status, done=None, total=None, unit=None, detail=None, eta=None):
        for st in self.stages:
            if st["key"] == key:
                changed = st["status"] != status
                if st["started"] is None and status in ("running", "done", "error"):
                    st["started"] = time.time()
                st.update(status=status, done=done, total=total, unit=unit, eta=round(eta, 1) if eta is not None else None)
                if detail is not None:
                    st["detail"] = detail
                if status in ("done", "error", "skipped"):
                    st["finished"] = time.time()
                    st["eta"] = None
                self._flush(force=changed)
                return

    def skip(self, key, detail):
        self.stage(key, "skipped", detail=detail)

    def log(self, msg):
        self._log.append(time.strftime("%H:%M:%S ") + str(msg))
        self._flush()

    def cancelled(self):
        return self.id in self.s.cancel_flags


class Studio:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.db = DB(cfg.data_dir / "studio.sqlite3")
        self.cancel_flags: set[int] = set()
        self._wake = threading.Event()
        self._stop = False
        self._thread = None
        self.current_job = None
        # tâches interrompues par un arrêt du serveur
        for j in self.db.q("SELECT id FROM jobs WHERE status IN ('running','cancelling')"):
            self.db.update("jobs", j["id"], status="error", error="Interrompu : le serveur a été arrêté pendant la production. Vous pouvez relancer.",
                           finished=time.time())
        for v in self.db.q("SELECT id FROM versions WHERE status='running'"):
            self.db.update("versions", v["id"], status="error")

    # ------------------------------------------------------------------ file d'attente
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="studio-worker", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop = True
        self._wake.set()

    def _loop(self):
        import logging
        log = logging.getLogger("studio")
        while not self._stop:
            try:
                self._tick()
            except Exception:  # noqa: BLE001 — le moteur ne doit jamais s'arrêter sur une erreur imprévue
                log.exception("Erreur dans la boucle du moteur")
                time.sleep(2)

    def _tick(self):
        job = self.db.one("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
        if not job:
            self._wake.wait(2)
            self._wake.clear()
            return
        self.run_job(job)

    def submit(self, kind: str, params: dict, title: str) -> dict:
        jid = self.db.insert("jobs", kind=kind, status="queued", params=params, title=title,
                             project_id=params.get("project_id"), story_id=params.get("story_id"), episode_id=params.get("episode_id"),
                             stages=JobReporter(self, 0).stages)
        self._wake.set()
        return self.job(jid)

    def job(self, jid):
        j = self.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if j and j["status"] == "queued":
            j["queue_position"] = self.db.one("SELECT COUNT(*) n FROM jobs WHERE status='queued' AND id<?", (jid,))["n"] + 1
        return j

    def cancel(self, jid):
        j = self.db.one("SELECT status FROM jobs WHERE id=?", (jid,))
        if not j:
            raise UserError("Tâche introuvable.")
        if j["status"] == "queued":
            self.db.update("jobs", jid, status="cancelled", finished=time.time())
        elif j["status"] == "running":
            self.cancel_flags.add(jid)
            self.db.update("jobs", jid, status="cancelling")

    def retry(self, jid):
        j = self.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if not j or j["status"] not in ("error", "cancelled"):
            raise UserError("Seule une tâche en erreur ou annulée peut être relancée.")
        p = dict(j["params"])
        p["retry_of"] = jid
        if j["version_id"]:
            p["resume_version"] = j["version_id"]
        return self.submit(j["kind"], p, j["title"])

    def run_job(self, job):
        jid = job["id"]
        rep = JobReporter(self, jid)
        self.current_job = jid
        self.db.update("jobs", jid, status="running", started=time.time())
        rep.stage("attente", "done", detail="pris en charge par le moteur")
        try:
            if job["kind"] == "export":
                res = self._export(job, rep)
            else:
                res = self._produce(job, rep)
            self.db.update("jobs", jid, status="done", finished=time.time(), result=res, stages=rep.stages, log="\n".join(rep._log[-300:]))
        except pipeline.Cancelled:
            self._fail_version(job, "cancelled")
            for st in rep.stages:
                if st["status"] == "running":
                    st["status"] = "cancelled"
            self.db.update("jobs", jid, status="cancelled", finished=time.time(), stages=rep.stages)
        except Exception as ex:  # noqa: BLE001
            msg = str(ex) if isinstance(ex, (UserError, RuntimeError, ValueError)) else f"{type(ex).__name__}: {ex}"
            rep.log(traceback.format_exc())
            import logging
            logging.getLogger("studio").error("Tâche %s en échec : %s\n%s", jid, msg, traceback.format_exc())
            for st in rep.stages:
                if st["status"] == "running":
                    st["status"] = "error"
                    st["detail"] = msg[:500]
            self._fail_version(job, "error")
            self.db.update("jobs", jid, status="error", error=msg[:4000], finished=time.time(), stages=rep.stages,
                           log="\n".join(rep._log[-300:]))
        finally:
            self.cancel_flags.discard(jid)
            self.current_job = None

    def _fail_version(self, job, status):
        j = self.db.one("SELECT version_id, episode_id FROM jobs WHERE id=?", (job["id"],))
        if j and j["version_id"]:
            self.db.update("versions", j["version_id"], status=status)
            ep = self.db.one("SELECT * FROM episodes WHERE id=?", (j["episode_id"],))
            if ep and ep["status"] == "running":
                done = self.db.one("SELECT id FROM versions WHERE episode_id=? AND status='done' ORDER BY number DESC LIMIT 1", (ep["id"],))
                self.db.update("episodes", ep["id"], status="done" if done else status)

    # ------------------------------------------------------------------ contexte d'histoire
    def story_context(self, story_id) -> dict:
        st = self.db.one("SELECT * FROM stories WHERE id=?", (story_id,))
        if not st:
            raise UserError("Histoire introuvable.")
        chars = self.db.q("SELECT * FROM characters WHERE story_id=? ORDER BY id", (story_id,))
        n = self.db.one("SELECT COALESCE(MAX(number),0) n FROM episodes WHERE story_id=?", (story_id,))["n"]
        return {"story_title": st["title"], "genre": st["genre"], "memory": st["memory"] or {}, "episode_n": n + 1,
                "characters": [{"id": c["cid"], "name": c["name"], "gender": c["gender"], "role": c["role"],
                                "look": c["look"], "voice": c["voice"]} for c in chars],
                "style": st["style"], "format": st["format"]}

    def story_dir(self, story_id) -> Path:
        return self.cfg.data_dir / "histoires" / str(story_id)

    def version_dir(self, episode_id, number) -> Path:
        return self.cfg.data_dir / "episodes" / str(episode_id) / f"v{number}"

    def _latest_story(self, project_id=None):
        if project_id:
            return self.db.one("SELECT * FROM stories WHERE project_id=? ORDER BY updated DESC LIMIT 1", (project_id,))
        return self.db.one("SELECT * FROM stories ORDER BY updated DESC LIMIT 1")

    def _sync_characters(self, story_id, spec):
        for c in spec["characters"]:
            row = self.db.one("SELECT id FROM characters WHERE story_id=? AND cid=?", (story_id, c["id"]))
            if row:
                self.db.update("characters", row["id"], name=c["name"], look=c["look"], voice=c["voice"], role=c.get("role", ""))
            else:
                self.db.insert("characters", story_id=story_id, cid=c["id"], name=c["name"], gender=c["gender"], role=c.get("role", ""),
                               look=c["look"], voice=c["voice"])

    # ------------------------------------------------------------------ résolution d'une demande
    def resolve(self, p: dict) -> dict:
        """Détermine la commande et la cible à partir du texte et des sélections de l'interface (sans rien lancer)."""
        text = (p.get("text") or "").strip()
        parsed = intent.parse_request(text)
        cmd = p.get("command") or "auto"
        if cmd == "auto":
            cmd = parsed["command"]
        s = self.cfg.settings
        out = {"command": cmd, "parsed": parsed, "label": COMMANDS.get(cmd, cmd),
               "duration": p.get("duration") or parsed["duration"] or s["default_duration"],
               "format": p.get("format") or parsed["format"] or s["default_format"],
               "style": p.get("style") or parsed["style"] or s["default_style"],
               "quality": p.get("quality") or s["default_quality"],
               "subtitles": p.get("subtitles", s["subtitles"]),
               "project_id": p.get("project_id"), "story_id": p.get("story_id"), "episode_id": p.get("episode_id"),
               "scene": p.get("scene") if p.get("scene") is not None else parsed["scene"], "warnings": []}
        if out["format"] not in FORMATS:
            out["format"] = "9:16"
        if out["quality"] not in QUALITIES:
            out["quality"] = "standard"
        if out["style"] not in STYLES:
            out["style"] = "cartoon3d"
        try:
            out["duration"] = max(5, min(600, int(float(out["duration"]))))
        except (TypeError, ValueError):
            out["duration"] = 30
        if cmd in ("continue", "new_episode") and not out["story_id"]:
            st = self._latest_story(out["project_id"])
            if not st:
                out["warnings"].append("Aucune histoire existante : une nouvelle histoire sera créée.")
                out["command"], out["label"] = "create", COMMANDS["create"]
            else:
                out["story_id"] = st["id"]
                out["story_title"] = st["title"]
        if cmd in ("edit_scene", "regenerate_scene", "rerender") and not out["episode_id"]:
            q = "SELECT e.* FROM episodes e JOIN stories s ON s.id=e.story_id"
            args = ()
            if out["story_id"]:
                q += " WHERE e.story_id=?"
                args = (out["story_id"],)
            ep = self.db.one(q + " ORDER BY e.updated DESC LIMIT 1", args)
            if not ep:
                raise UserError("Aucun épisode à modifier : créez d'abord une vidéo.")
            out["episode_id"] = ep["id"]
        if cmd == "edit_scene":
            ep = self.db.one("SELECT * FROM episodes WHERE id=?", (out["episode_id"],))
            v = self.db.one("SELECT * FROM versions WHERE episode_id=? AND number=?", (ep["id"], ep["current_version"]))
            if not v:
                raise UserError("Cet épisode n'a pas encore de version terminée.")
            new, info = edits.plan_edit(v["spec"], text, out["scene"], self.cfg.settings, log=lambda m: None)
            out["edit"] = info
            out["plan"] = pipeline.plan(new, self.cfg.settings, self.cfg.data_dir)
            if info["unknown"]:
                out["warnings"].append("Je n'ai reconnu aucune modification précise dans ce texte. Exemples : « plus expressif », "
                                       "« caméra vers la gauche », « ralentis », « change uniquement l'arrière-plan ».")
        return out

    def request(self, p: dict) -> dict:
        r = self.resolve(p)
        if r["command"] == "edit_scene" and r.get("edit", {}).get("unknown"):
            raise UserError(r["warnings"][-1])
        params = {**{k: r[k] for k in ("command", "duration", "format", "style", "quality", "subtitles", "project_id",
                                       "story_id", "episode_id", "scene")},
                  "text": p.get("text") or "", "rewrite_dialogue": bool(p.get("rewrite_dialogue")), "parsed": r["parsed"]}
        title = (p.get("text") or COMMANDS.get(r["command"], "")).strip()[:90] or COMMANDS.get(r["command"])
        job = self.submit("produce", params, f"{COMMANDS.get(r['command'])} — {title}")
        return {"job": job, "resolved": r}

    # ------------------------------------------------------------------ production
    def _produce(self, job, rep: JobReporter):
        p = job["params"]
        cmd = p["command"]
        s = self.cfg.settings
        rep.log(f"Commande : {COMMANDS.get(cmd, cmd)}")
        rep.stage("scenario", "running", detail="interprétation de la demande")
        seed = int(time.time() * 1000) % 10**9

        if p.get("resume_version"):
            v = self.db.one("SELECT * FROM versions WHERE id=?", (p["resume_version"],))
            if v and v["spec"]:
                ep = self.db.one("SELECT * FROM episodes WHERE id=?", (v["episode_id"],))
                st = self.db.one("SELECT * FROM stories WHERE id=?", (ep["story_id"],))
                rep.stage("scenario", "done", detail="scénario existant repris (relance)")
                return self._render_version(job, rep, st, ep, v, v["spec"], memory_update=v["number"] == 1 and cmd != "rerender")

        if cmd in ("create", "continue", "new_episode"):
            req = dict(p["parsed"], command=cmd, prompt=p["text"], duration=p["duration"], format=p["format"],
                       style=p["style"], quality=p["quality"], subtitles=p["subtitles"])
            if cmd == "create":
                ctx = {"default_duration": p["duration"]}
                if p["parsed"].get("use_previous_characters"):
                    prev = self._latest_story(p.get("project_id"))
                    if prev:
                        ctx = self.story_context(prev["id"]) | {"memory": {}}
                        rep.log(f"Personnages repris de « {prev['title']} ».")
            else:
                ctx = self.story_context(p["story_id"])
            spec, used = story.write_screenplay(req, ctx, s, seed, log=rep.log)
            rep.stage("scenario", "done", detail=f"« {spec['title']} » — {len(spec['scenes'])} scène(s) · générateur : "
                      + ("intégré (règles)" if used == "regles" else used))
            if cmd == "create":
                project_id = p.get("project_id")
                if not project_id:
                    project_id = self.db.insert("projects", name=spec["title"], draft={})
                story_id = self.db.insert("stories", project_id=project_id, title=spec["title"], genre=spec["genre"],
                                          style=spec["style"], format=spec["format"], memory={})
                number = 1
            else:
                story_id = p["story_id"]
                project_id = self.db.one("SELECT project_id FROM stories WHERE id=?", (story_id,))["project_id"]
                number = ctx["episode_n"]
            ep_id = self.db.insert("episodes", story_id=story_id, number=number, title=spec["title"], prompt=p["text"],
                                   current_version=None, status="running")
            v_id = self.db.insert("versions", episode_id=ep_id, number=1, spec=spec, note=p["text"][:300] or COMMANDS[cmd],
                                  parent_id=None, status="running")
            self.db.update("jobs", job["id"], project_id=project_id, story_id=story_id, episode_id=ep_id, version_id=v_id)
            self._sync_characters(story_id, spec)
            st = self.db.one("SELECT * FROM stories WHERE id=?", (story_id,))
            ep = self.db.one("SELECT * FROM episodes WHERE id=?", (ep_id,))
            v = self.db.one("SELECT * FROM versions WHERE id=?", (v_id,))
            return self._render_version(job, rep, st, ep, v, spec, memory_update=True)

        # retouches : nouvelle version de l'épisode
        ep = self.db.one("SELECT * FROM episodes WHERE id=?", (p["episode_id"],))
        if not ep:
            raise UserError("Épisode introuvable.")
        st = self.db.one("SELECT * FROM stories WHERE id=?", (ep["story_id"],))
        base = self.db.one("SELECT * FROM versions WHERE episode_id=? AND number=?", (ep["id"], ep["current_version"])) \
            or self.db.one("SELECT * FROM versions WHERE episode_id=? ORDER BY number DESC LIMIT 1", (ep["id"],))
        if not base:
            raise UserError("Aucune version de départ pour cet épisode.")
        if cmd == "edit_scene":
            spec, info = edits.plan_edit(base["spec"], p["text"], p.get("scene"), s, log=rep.log)
            if info["unknown"]:
                raise UserError("Aucune modification reconnue dans la demande.")
            note = f"Scène(s) {', '.join(map(str, info['scenes']))} : " + "; ".join(info["understood"])
            for n_ in info["notes"]:
                rep.log(n_)
        elif cmd == "regenerate_scene":
            spec, info = edits.regenerate_scene(base["spec"], p.get("scene"), p.get("rewrite_dialogue"), seed)
            note = f"Nouvelle prise de la scène {', '.join(map(str, info['scenes']))}"
        elif cmd == "rerender":
            spec = normalize_spec(base["spec"], fmt=p.get("format"), quality=p.get("quality"))
            if "subtitles" in p:
                spec["subtitles"] = bool(p["subtitles"])
            note = f"Nouveau rendu {spec['format']} · {spec['quality']}"
        else:
            raise UserError(f"Commande inconnue : {cmd}")
        rep.stage("scenario", "done", detail=note)
        number = self.db.one("SELECT MAX(number) n FROM versions WHERE episode_id=?", (ep["id"],))["n"] + 1
        v_id = self.db.insert("versions", episode_id=ep["id"], number=number, spec=spec, note=note, parent_id=base["id"], status="running")
        self.db.update("episodes", ep["id"], status="running")
        self.db.update("jobs", job["id"], project_id=st["project_id"], story_id=st["id"], episode_id=ep["id"], version_id=v_id)
        self._sync_characters(st["id"], spec)
        v = self.db.one("SELECT * FROM versions WHERE id=?", (v_id,))
        return self._render_version(job, rep, st, ep, v, spec, memory_update=False)

    def _render_version(self, job, rep, st, ep, v, spec, memory_update):
        vdir = self.version_dir(ep["id"], v["number"])
        res = pipeline.produce(spec, vdir, self.story_dir(st["id"]), self.cfg.settings, self.cfg.data_dir, rep)
        self.db.update("versions", v["id"], status="done", result=res)
        self.db.update("episodes", ep["id"], current_version=v["number"], status="done", title=spec["title"])
        # références visuelles des personnages
        refs = self.story_dir(st["id"]) / "references"
        from moteur.spec import stable_hash
        for c in spec["characters"]:
            p = refs / f"{c['id']}_{stable_hash(c['look'])}.png"
            if p.exists():
                row = self.db.one("SELECT id FROM characters WHERE story_id=? AND cid=?", (st["id"], c["id"]))
                if row:
                    self.db.update("characters", row["id"], ref_image=str(p.relative_to(self.cfg.data_dir)))
        if memory_update:
            self._update_memory(st, ep, spec)
        self.db.update("stories", st["id"])
        if res["qc"]["checks"] and any(not c["ok"] for c in res["qc"]["checks"]):
            rep.log("Avertissements du contrôle qualité : " + "; ".join(c["name"] for c in res["qc"]["checks"] if not c["ok"]))
        rep.log(f"Terminé en {res['elapsed']} s · scènes rendues : {res['scenes_rendered'] or 'aucune'} · réutilisées : {res['scenes_reused'] or 'aucune'}")
        return {"episode_id": ep["id"], "version": v["number"], **{k: res[k] for k in ("duration", "renderer", "tts", "scenes_rendered", "scenes_reused", "elapsed")}}

    def _update_memory(self, st, ep, spec):
        mem = dict(st["memory"] or {})
        eps = [e for e in mem.get("episodes", []) if e.get("n") != ep["number"]]
        eps.append({"n": ep["number"], "title": spec["title"], "summary": spec["memory_out"]["summary"], "ending": spec["memory_out"]["ending"]})
        eps.sort(key=lambda e: e["n"])
        facts = list(dict.fromkeys((mem.get("facts") or []) + spec["memory_out"]["facts"]))[-30:]
        mem.update(episodes=eps[-50:], ending=spec["memory_out"]["ending"], facts=facts,
                   summary=" ".join(f"Ép. {e['n']} : {e['summary']}" for e in eps[-6:])[:2500])
        self.db.update("stories", st["id"], memory=mem)
        d = self.story_dir(st["id"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "memoire.json").write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ exports
    def _export(self, job, rep: JobReporter):
        p = job["params"]
        v = self.db.one("SELECT v.*, e.id eid FROM versions v JOIN episodes e ON e.id=v.episode_id WHERE e.id=? AND v.number=?",
                        (p["episode_id"], p["version"]))
        if not v or v["status"] != "done":
            raise UserError("Version introuvable ou non terminée.")
        for k in ("scenario", "personnages", "scenes", "audio", "animation", "montage", "controle"):
            rep.skip(k, "non nécessaire pour un export")
        vdir = self.version_dir(v["eid"], v["number"])
        out = vdir / "exports" / f"{p['format'].replace(':', 'x')}_{p['method']}.mp4"
        out.parent.mkdir(exist_ok=True)
        short = min(frame_size(v["spec"]["format"], v["spec"]["quality"]))
        rep.stage("final", "running", 0, 100, "%", f"export {p['format']} ({p['method']})")
        montage.export_format(vdir / "video.mp4", out, p["format"], p["method"], short,
                              lambda x: rep.stage("final", "running", int(x * 100), 100, "%"), rep.cancelled)
        rep.stage("final", "done", 100, 100, "%", f"{out.stat().st_size / 1e6:.1f} Mo")
        return {"episode_id": v["eid"], "version": v["number"], "export": str(out.relative_to(self.cfg.data_dir))}

    # ------------------------------------------------------------------ suppression
    def delete_episode(self, ep_id):
        self.db.delete("episodes", ep_id)
        shutil.rmtree(self.cfg.data_dir / "episodes" / str(ep_id), ignore_errors=True)

    def delete_project(self, pid):
        eps = self.db.q("SELECT e.id FROM episodes e JOIN stories s ON s.id=e.story_id WHERE s.project_id=?", (pid,))
        sts = self.db.q("SELECT id FROM stories WHERE project_id=?", (pid,))
        self.db.delete("projects", pid)
        for e in eps:
            shutil.rmtree(self.cfg.data_dir / "episodes" / str(e["id"]), ignore_errors=True)
        for s_ in sts:
            shutil.rmtree(self.story_dir(s_["id"]), ignore_errors=True)
