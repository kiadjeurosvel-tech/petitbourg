"""API HTTP du studio (FastAPI). Sert aussi l'interface web."""
from __future__ import annotations

import io
import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from moteur import audio, llm, render
from moteur.spec import FORMATS, QUALITIES, SETS, STYLES, frame_size

from . import auth
from .config import WEB_DIR, Config
from .production import COMMANDS, Studio, UserError

VERSION = "1.0.0"


def create_app(cfg: Config | None = None, start_worker: bool = True) -> FastAPI:
    cfg = cfg or Config()
    studio = Studio(cfg)
    limiter = auth.RateLimiter()
    app = FastAPI(title="Studio d'animation", version=VERSION, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.studio = studio
    app.state.cfg = cfg

    origins = list(cfg.data.get("allowed_origins", [])) + ["http://localhost:8765", "http://127.0.0.1:8765"]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"], max_age=3600)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/media"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.exception_handler(UserError)
    async def user_error(_, ex: UserError):
        return JSONResponse({"detail": str(ex)}, status_code=400)

    @app.exception_handler(ValueError)
    async def value_error(_, ex: ValueError):
        return JSONResponse({"detail": str(ex)}, status_code=400)

    if start_worker:
        @app.on_event("startup")
        def _start():
            studio.start()

        @app.on_event("shutdown")
        def _stop():
            studio.stop()

    def require(request: Request):
        h = request.headers.get("authorization", "")
        tok = h[7:] if h.lower().startswith("bearer ") else ""
        if not tok or not auth.verify_token(cfg.secret, tok, cfg.data.get("token_gen", 0)):
            raise HTTPException(401, "Session expirée ou invalide. Reconnectez-vous.")
        return True

    def media(rel: str | None):
        if not rel:
            return None
        rel = rel.replace("\\", "/")
        return f"/api/media/{quote(rel)}?{auth.sign_media(cfg.secret, rel)}"

    def vrel(ep_id, number, name):
        p = studio.version_dir(ep_id, number) / name
        return str(p.relative_to(cfg.data_dir)) if p.exists() else None

    # ------------------------------------------------------------------ public
    @app.get("/api/health")
    def health():
        return {"ok": True, "name": "studio", "version": VERSION, "password_set": bool(cfg.data.get("password_hash"))}

    @app.post("/api/auth/login")
    async def login(request: Request):
        ip = request.client.host if request.client else "?"
        if limiter.blocked(ip):
            raise HTTPException(429, "Trop de tentatives. Réessayez dans une minute.")
        body = await request.json()
        if not auth.check_password(str(body.get("password", "")), cfg.data.get("password_hash")):
            limiter.failed(ip)
            time.sleep(.5)
            raise HTTPException(401, "Mot de passe incorrect.")
        tok, exp = auth.make_token(cfg.secret, cfg.data.get("token_gen", 0))
        return {"token": tok, "exp": exp}

    @app.get("/api/media/{rel:path}")
    def get_media(rel: str, exp: str = "", sig: str = "", download: int = 0):
        if not auth.verify_media(cfg.secret, rel, exp, sig):
            raise HTTPException(403, "Lien expiré.")
        p = (cfg.data_dir / rel).resolve()
        if not str(p).startswith(str(cfg.data_dir)) or not p.is_file():
            raise HTTPException(404, "Fichier introuvable.")
        kw = {"filename": p.name} if download else {}
        return FileResponse(p, headers={"Cache-Control": "private, max-age=3600"}, **kw)

    # ------------------------------------------------------------------ système
    @app.get("/api/system", dependencies=[Depends(require)])
    def system():
        s = cfg.settings
        b = render.find_blender(s.get("blender_path"))
        st = audio.engines_status(cfg.data_dir / "voix")
        try:
            kind, _ = render.choose_renderer(s)
        except RuntimeError as ex:
            kind = f"erreur : {ex}"
        usage = shutil.disk_usage(cfg.data_dir)
        return {
            "version": VERSION, "renderer": kind, "blender": {"path": b, "version": render.blender_version(b)},
            "virtual_display": render.needs_virtual_display(), "xvfb": bool(shutil.which("xvfb-run")),
            "ffmpeg": bool(shutil.which("ffmpeg")), "tts": st, "tts_selected": audio.pick_engine(s.get("tts_engine", "auto"), cfg.data_dir / "voix"),
            "llm": {"provider": s["llm_provider"], "model": s["llm_model"], "suggested": llm.SUGGESTED_MODELS},
            "disk_free_gb": round(usage.free / 1e9, 1), "data_dir": str(cfg.data_dir),
            "queue": studio.db.one("SELECT COUNT(*) n FROM jobs WHERE status='queued'")["n"], "current_job": studio.current_job,
            "options": {"formats": list(FORMATS), "qualities": list(QUALITIES), "styles": STYLES, "sets": SETS, "commands": COMMANDS},
        }

    @app.get("/api/settings", dependencies=[Depends(require)])
    def get_settings():
        return {"settings": cfg.settings, "allowed_origins": cfg.data.get("allowed_origins", [])}

    @app.put("/api/settings", dependencies=[Depends(require)])
    async def put_settings(request: Request):
        body = await request.json()
        if body.get("llm_url") and not llm._is_local(body["llm_url"]):
            raise UserError("L'adresse du modèle doit être locale (ordinateur ou réseau privé).")
        s = cfg.update_settings(body.get("settings", body))
        if isinstance(body.get("allowed_origins"), list):
            cfg.data["allowed_origins"] = [str(o).rstrip("/") for o in body["allowed_origins"] if str(o).startswith("https://")]
            cfg.save()
        return {"settings": s}

    @app.get("/api/llm/models", dependencies=[Depends(require)])
    def llm_models(provider: str = "", url: str = ""):
        s = cfg.settings
        if provider:
            s["llm_provider"] = provider
        if url:
            s["llm_url"] = url
        return llm.list_models(s)

    @app.post("/api/auth/password", dependencies=[Depends(require)])
    async def change_password(request: Request):
        body = await request.json()
        if not auth.check_password(str(body.get("old", "")), cfg.data.get("password_hash")):
            raise HTTPException(401, "Ancien mot de passe incorrect.")
        new = str(body.get("new", ""))
        if len(new) < 10:
            raise UserError("Le nouveau mot de passe doit contenir au moins 10 caractères.")
        cfg.data["password_hash"] = auth.hash_password(new)
        cfg.data["token_gen"] = cfg.data.get("token_gen", 0) + 1  # déconnecte les autres appareils
        cfg.save()
        tok, exp = auth.make_token(cfg.secret, cfg.data["token_gen"])
        return {"token": tok, "exp": exp}

    # ------------------------------------------------------------------ commandes
    @app.post("/api/interpret", dependencies=[Depends(require)])
    async def interpret(request: Request):
        return studio.resolve(await request.json())

    @app.post("/api/produce", dependencies=[Depends(require)])
    async def produce(request: Request):
        body = await request.json()
        if not (body.get("text") or "").strip() and body.get("command") in (None, "auto", "create", "edit_scene"):
            raise UserError("Décrivez d'abord la vidéo (ou la modification) souhaitée.")
        return studio.request(body)

    @app.post("/api/episodes/{ep_id}/export", dependencies=[Depends(require)])
    async def export(ep_id: int, request: Request):
        body = await request.json()
        fmt, method = body.get("format"), body.get("method", "flou")
        ep = studio.db.one("SELECT * FROM episodes WHERE id=?", (ep_id,))
        if not ep or fmt not in FORMATS:
            raise UserError("Épisode ou format invalide.")
        version = int(body.get("version") or ep["current_version"] or 0)
        if method == "natif":
            return {"job": studio.request({"command": "rerender", "episode_id": ep_id, "format": fmt,
                                           "quality": body.get("quality"), "text": f"Rendu natif {fmt}"})["job"]}
        if method not in ("flou", "recadrage"):
            raise UserError("Méthode d'export inconnue.")
        return {"job": studio.submit("export", {"episode_id": ep_id, "version": version, "format": fmt, "method": method},
                                     f"Export {fmt} ({method}) — {ep['title']}")}

    # ------------------------------------------------------------------ tâches
    def job_view(j):
        if not j:
            return None
        j = dict(j)
        j.pop("log", None)
        if j.get("status") == "done" and j.get("episode_id"):
            res = j.get("result") or {}
            if res.get("export"):
                j["export_url"] = media(res["export"])
            if res.get("version"):
                j["video_url"] = media(vrel(j["episode_id"], res["version"], "video.mp4"))
                j["thumb_url"] = media(vrel(j["episode_id"], res["version"], "miniature.jpg"))
        return j

    @app.get("/api/jobs", dependencies=[Depends(require)])
    def jobs(active: int = 0, limit: int = 30):
        if active:
            rows = studio.db.q("SELECT * FROM jobs WHERE status IN ('queued','running','cancelling') ORDER BY id")
            rows += studio.db.q("SELECT * FROM jobs WHERE status NOT IN ('queued','running','cancelling') AND finished > ? ORDER BY id DESC",
                                (time.time() - 1800,))
        else:
            rows = studio.db.q("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (min(200, limit),))
        return [job_view(studio.job(r["id"])) for r in rows]

    @app.get("/api/jobs/{jid}", dependencies=[Depends(require)])
    def job(jid: int, log: int = 0):
        j = studio.job(jid)
        if not j:
            raise HTTPException(404, "Tâche introuvable.")
        v = job_view(j)
        if log:
            v["log"] = j.get("log", "")
        return v

    @app.post("/api/jobs/{jid}/cancel", dependencies=[Depends(require)])
    def cancel(jid: int):
        studio.cancel(jid)
        return job_view(studio.job(jid))

    @app.post("/api/jobs/{jid}/retry", dependencies=[Depends(require)])
    def retry(jid: int):
        return job_view(studio.retry(jid))

    # ------------------------------------------------------------------ bibliothèque
    @app.get("/api/projects", dependencies=[Depends(require)])
    def projects():
        rows = studio.db.q("""SELECT p.*, (SELECT COUNT(*) FROM stories s WHERE s.project_id=p.id) n_stories,
               (SELECT COUNT(*) FROM episodes e JOIN stories s ON s.id=e.story_id WHERE s.project_id=p.id) n_episodes
               FROM projects p ORDER BY p.updated DESC""")
        return rows

    @app.post("/api/projects", dependencies=[Depends(require)])
    async def save_project(request: Request):
        b = await request.json()
        name = (b.get("name") or "").strip()[:120]
        if b.get("id"):
            p = studio.db.one("SELECT * FROM projects WHERE id=?", (b["id"],))
            if not p:
                raise HTTPException(404, "Projet introuvable.")
            studio.db.update("projects", p["id"], name=name or p["name"], notes=b.get("notes", p["notes"]), draft=b.get("draft", p["draft"]))
            return studio.db.one("SELECT * FROM projects WHERE id=?", (p["id"],))
        if not name:
            raise UserError("Donnez un nom au projet.")
        pid = studio.db.insert("projects", name=name, notes=b.get("notes", ""), draft=b.get("draft", {}))
        return studio.db.one("SELECT * FROM projects WHERE id=?", (pid,))

    @app.delete("/api/projects/{pid}", dependencies=[Depends(require)])
    def delete_project(pid: int):
        studio.delete_project(pid)
        return {"ok": True}

    @app.get("/api/projects/{pid}/sauvegarde", dependencies=[Depends(require)])
    def backup(pid: int, videos: int = 0):
        p = studio.db.one("SELECT * FROM projects WHERE id=?", (pid,))
        if not p:
            raise HTTPException(404, "Projet introuvable.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            stories = studio.db.q("SELECT * FROM stories WHERE project_id=?", (pid,))
            dump = {"project": p, "stories": []}
            for s in stories:
                chars = studio.db.q("SELECT * FROM characters WHERE story_id=?", (s["id"],))
                eps = studio.db.q("SELECT * FROM episodes WHERE story_id=?", (s["id"],))
                for e in eps:
                    e["versions"] = studio.db.q("SELECT * FROM versions WHERE episode_id=?", (e["id"],))
                    for v in e["versions"]:
                        vd = studio.version_dir(e["id"], v["number"])
                        for name in ("spec.json", "sous-titres.srt", "qc.json", "miniature.jpg") + (("video.mp4",) if videos else ()):
                            if (vd / name).exists():
                                z.write(vd / name, f"episodes/{e['number']:03d}_{e['id']}/v{v['number']}/{name}")
                ref = studio.story_dir(s["id"])
                if ref.exists():
                    for f in ref.rglob("*"):
                        if f.is_file():
                            z.write(f, f"histoires/{s['id']}/{f.relative_to(ref)}")
                dump["stories"].append({**s, "characters": chars, "episodes": eps})
            z.writestr("projet.json", json.dumps(dump, ensure_ascii=False, indent=1))
        buf.seek(0)
        from moteur.intent import fold
        safe = "".join(ch for ch in fold(p["name"]) if ch.isascii() and (ch.isalnum() or ch in " -_"))[:40].strip() or "projet"
        utf = quote(f"sauvegarde_{p['name'][:40]}.zip")
        return StreamingResponse(buf, media_type="application/zip",
                                 headers={"Content-Disposition": f"attachment; filename=\"sauvegarde_{safe}.zip\"; filename*=UTF-8''{utf}"})

    @app.get("/api/stories", dependencies=[Depends(require)])
    def stories(project_id: int | None = None):
        q = """SELECT s.*, p.name project_name, (SELECT COUNT(*) FROM episodes e WHERE e.story_id=s.id) n_episodes
               FROM stories s JOIN projects p ON p.id=s.project_id"""
        rows = studio.db.q(q + (" WHERE s.project_id=?" if project_id else "") + " ORDER BY s.updated DESC", (project_id,) if project_id else ())
        return rows

    @app.get("/api/stories/{sid}", dependencies=[Depends(require)])
    def story(sid: int):
        s = studio.db.one("SELECT s.*, p.name project_name FROM stories s JOIN projects p ON p.id=s.project_id WHERE s.id=?", (sid,))
        if not s:
            raise HTTPException(404, "Histoire introuvable.")
        s["characters"] = characters(sid)
        s["episodes"] = episodes(story_id=sid)
        return s

    @app.patch("/api/stories/{sid}", dependencies=[Depends(require)])
    async def patch_story(sid: int, request: Request):
        b = await request.json()
        vals = {}
        if "title" in b:
            vals["title"] = str(b["title"])[:120]
        if isinstance(b.get("memory"), dict):
            vals["memory"] = b["memory"]
        studio.db.update("stories", sid, **vals)
        if "memory" in vals:
            d = studio.story_dir(sid)
            d.mkdir(parents=True, exist_ok=True)
            (d / "memoire.json").write_text(json.dumps(vals["memory"], ensure_ascii=False, indent=1))
        return story(sid)

    @app.get("/api/characters", dependencies=[Depends(require)])
    def characters(story_id: int | None = None):
        q = "SELECT c.*, s.title story_title FROM characters c JOIN stories s ON s.id=c.story_id"
        rows = studio.db.q(q + (" WHERE c.story_id=?" if story_id else "") + " ORDER BY c.id DESC", (story_id,) if story_id else ())
        for r in rows:
            r["ref_url"] = media(r.get("ref_image"))
        return rows

    @app.patch("/api/characters/{cid}", dependencies=[Depends(require)])
    async def patch_character(cid: int, request: Request):
        b = await request.json()
        c = studio.db.one("SELECT * FROM characters WHERE id=?", (cid,))
        if not c:
            raise HTTPException(404, "Personnage introuvable.")
        vals = {}
        if b.get("name"):
            vals["name"] = str(b["name"])[:40]
        if isinstance(b.get("role"), str):
            vals["role"] = b["role"][:120]
        studio.db.update("characters", cid, **vals)
        return studio.db.one("SELECT * FROM characters WHERE id=?", (cid,))

    def ep_view(e):
        cur = e.get("current_version")
        e["thumb_url"] = media(vrel(e["id"], cur, "miniature.jpg")) if cur else None
        e["video_url"] = media(vrel(e["id"], cur, "video.mp4")) if cur else None
        return e

    @app.get("/api/episodes", dependencies=[Depends(require)])
    def episodes(story_id: int | None = None):
        q = """SELECT e.*, s.title story_title, s.project_id FROM episodes e JOIN stories s ON s.id=e.story_id"""
        rows = studio.db.q(q + (" WHERE e.story_id=?" if story_id else "") + " ORDER BY e.updated DESC", (story_id,) if story_id else ())
        return [ep_view(r) for r in rows]

    @app.get("/api/episodes/{ep_id}", dependencies=[Depends(require)])
    def episode(ep_id: int):
        e = studio.db.one("""SELECT e.*, s.title story_title, s.project_id FROM episodes e JOIN stories s ON s.id=e.story_id WHERE e.id=?""", (ep_id,))
        if not e:
            raise HTTPException(404, "Épisode introuvable.")
        ep_view(e)
        vs = studio.db.q("SELECT * FROM versions WHERE episode_id=? ORDER BY number DESC", (ep_id,))
        out_v = []
        for v in vs:
            res = v.get("result") or {}
            exports = []
            ed = studio.version_dir(ep_id, v["number"]) / "exports"
            if ed.exists():
                for f in sorted(ed.glob("*.mp4")):
                    rel = str(f.relative_to(cfg.data_dir))
                    exports.append({"name": f.stem, "url": media(rel), "download": media(rel) + "&download=1"})
            vid = vrel(ep_id, v["number"], "video.mp4")
            out_v.append({"id": v["id"], "number": v["number"], "note": v["note"], "status": v["status"], "created": v["created"],
                          "format": v["spec"]["format"], "quality": v["spec"]["quality"], "result": res,
                          "video_url": media(vid), "download_url": (media(vid) + "&download=1") if vid else None,
                          "srt_url": media(vrel(ep_id, v["number"], "sous-titres.srt")),
                          "thumb_url": media(vrel(ep_id, v["number"], "miniature.jpg")), "exports": exports})
        e["versions"] = out_v
        cur = next((v for v in vs if v["number"] == e["current_version"]), vs[0] if vs else None)
        if cur:
            spec = cur["spec"]
            keys = (cur.get("result") or {}).get("scene_keys", {})
            e["spec"] = spec
            e["scenes"] = []
            for sc in spec["scenes"]:
                k = keys.get(sc["id"])
                clip = cfg.data_dir / "cache" / "visual" / k / "clip.mp4" if k else None
                rel = str(clip.relative_to(cfg.data_dir)) if clip and clip.exists() else None
                e["scenes"].append({**sc, "clip_url": media(rel)})
            e["size"] = frame_size(spec["format"], spec["quality"])
        return e

    @app.post("/api/episodes/{ep_id}/current", dependencies=[Depends(require)])
    async def set_current(ep_id: int, request: Request):
        b = await request.json()
        v = studio.db.one("SELECT * FROM versions WHERE episode_id=? AND number=? AND status='done'", (ep_id, int(b.get("version", 0))))
        if not v:
            raise UserError("Version introuvable ou non terminée.")
        studio.db.update("episodes", ep_id, current_version=v["number"])
        return episode(ep_id)

    @app.delete("/api/episodes/{ep_id}", dependencies=[Depends(require)])
    def delete_episode(ep_id: int):
        studio.delete_episode(ep_id)
        return {"ok": True}

    @app.get("/api/library/videos", dependencies=[Depends(require)])
    def videos(state: str = "terminees"):
        if state == "en_cours":
            return [job_view(studio.job(j["id"])) for j in studio.db.q("SELECT id FROM jobs WHERE status IN ('queued','running','cancelling') ORDER BY id")]
        q = """SELECT v.id, v.number, v.note, v.status, v.created, v.result, e.id episode_id, e.title, e.number ep_number, e.current_version,
               s.title story_title FROM versions v JOIN episodes e ON e.id=v.episode_id JOIN stories s ON s.id=e.story_id WHERE v.status='done' """
        q += "AND v.number = e.current_version" if state == "terminees" else "AND v.number <> e.current_version"
        rows = studio.db.q(q + " ORDER BY v.created DESC LIMIT 200")
        for r in rows:
            r["thumb_url"] = media(vrel(r["episode_id"], r["number"], "miniature.jpg"))
            r["video_url"] = media(vrel(r["episode_id"], r["number"], "video.mp4"))
            r["duration"] = (r.get("result") or {}).get("duration")
            r.pop("result", None)
        return rows

    # ------------------------------------------------------------------ interface web
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


def default_app():
    return create_app()


if os.environ.get("STUDIO_IMPORT_APP"):
    app = default_app()
