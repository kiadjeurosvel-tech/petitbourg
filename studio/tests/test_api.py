"""Tests de bout en bout de l'API : authentification, production réelle (rendu 2D + FFmpeg),
progression, retouche partielle, export, sécurité des médias."""
import os
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from serveur import auth
from serveur.app import create_app
from serveur.config import Config

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg requis")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    cfg = Config(tmp_path_factory.mktemp("donnees"))
    cfg.data["password_hash"] = auth.hash_password("motdepasse-test")
    cfg.save()
    renderer = "blender" if os.environ.get("STUDIO_TEST_BLENDER") else "2d"
    cfg.update_settings({"renderer": renderer, "tts_engine": os.environ.get("STUDIO_TEST_TTS", "silence"), "music": False})
    app = create_app(cfg, start_worker=True)
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"password": "motdepasse-test"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


def wait(c, jid, timeout=900):
    seen_running = False
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if any(s["status"] == "running" for s in j["stages"]):
            seen_running = True
        if j["status"] in ("done", "error", "cancelled"):
            return j, seen_running
        time.sleep(.3)
    raise TimeoutError(jid)


def test_auth_obligatoire(client):
    anon = TestClient(client.app)
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/projects").status_code == 401
    assert anon.post("/api/auth/login", json={"password": "faux"}).status_code == 401
    assert anon.get("/api/projects", headers={"Authorization": "Bearer abc.def"}).status_code == 401


def test_production_complete_puis_retouche_partielle(client):
    r = client.post("/api/produce", json={"text": "Léa et Hugo se disputent dans un restaurant, 20 secondes, format vertical",
                                          "quality": "brouillon"})
    assert r.status_code == 200, r.text
    assert r.json()["resolved"]["format"] == "9:16"
    job, seen = wait(client, r.json()["job"]["id"])
    assert job["status"] == "done", job.get("error")
    stages = {s["key"]: s for s in job["stages"]}
    assert all(stages[k]["status"] == "done" for k in ("scenario", "personnages", "scenes", "audio", "animation", "montage", "controle", "final"))
    assert stages["animation"]["done"] == stages["animation"]["total"] > 0  # progression réelle (images écrites)
    ep = client.get(f"/api/episodes/{job['episode_id']}").json()
    assert ep["current_version"] == 1 and len(ep["scenes"]) >= 2

    # la vidéo est servie (avec Range pour la lecture mobile) et est un vrai MP4
    url = ep["versions"][0]["video_url"]
    v = client.get(url, headers={"Range": "bytes=0-99"})
    assert v.status_code == 206 and len(v.content) == 100
    full = client.get(url).content
    p = os.path.join(os.path.dirname(__file__), "_tmp.mp4")
    open(p, "wb").write(full)
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", p],
                             capture_output=True, text=True).stdout
        assert "video" in out and "audio" in out
    finally:
        os.remove(p)
    # lien de média falsifié refusé
    assert client.get(url.replace("sig=", "sig=x")).status_code == 403

    # aperçu de retouche : seule la scène 2 doit être recalculée
    plan = client.post("/api/interpret", json={"command": "edit_scene", "episode_id": ep["id"], "scene": 2,
                                               "text": "La caméra doit se déplacer vers la gauche."}).json()
    redo = [s["n"] for s in plan["plan"]["scenes"] if not s["visual_cached"]]
    assert redo == [2]
    r = client.post("/api/produce", json={"command": "edit_scene", "episode_id": ep["id"], "scene": 2,
                                          "text": "La caméra doit se déplacer vers la gauche."})
    job2, _ = wait(client, r.json()["job"]["id"])
    assert job2["status"] == "done", job2.get("error")
    assert job2["result"]["scenes_rendered"] == [2]
    assert 1 in job2["result"]["scenes_reused"]
    ep2 = client.get(f"/api/episodes/{ep['id']}").json()
    assert ep2["current_version"] == 2 and len(ep2["versions"]) == 2

    # export carré rapide
    r = client.post(f"/api/episodes/{ep['id']}/export", json={"format": "1:1", "method": "flou"})
    job3, _ = wait(client, r.json()["job"]["id"])
    assert job3["status"] == "done", job3.get("error")
    ep3 = client.get(f"/api/episodes/{ep['id']}").json()
    assert ep3["versions"][0]["exports"]

    # continuer l'histoire : même histoire, épisode 2, mêmes personnages
    r = client.post("/api/produce", json={"command": "continue", "story_id": ep["story_id"], "text": "", "duration": 15, "quality": "brouillon"})
    job4, _ = wait(client, r.json()["job"]["id"])
    assert job4["status"] == "done", job4.get("error")
    st = client.get(f"/api/stories/{ep['story_id']}").json()
    assert len(st["episodes"]) == 2 and len(st["memory"]["episodes"]) == 2
    assert all(c["ref_url"] for c in st["characters"])  # références visuelles créées

    # bibliothèque & sauvegarde
    assert client.get("/api/library/videos?state=terminees").json()
    assert client.get("/api/library/videos?state=anciennes").json()
    z = client.get(f"/api/projects/{st['project_id']}/sauvegarde")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    # nom de projet accentué : en-tête de téléchargement valide
    pid = client.post("/api/projects", json={"name": "Ça déménage — été"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/sauvegarde").status_code == 200


def test_retouche_incomprise_refusee(client):
    eps = client.get("/api/episodes").json()
    r = client.post("/api/produce", json={"command": "edit_scene", "episode_id": eps[0]["id"], "text": "bonjour"})
    assert r.status_code == 400


def test_annulation(client):
    r = client.post("/api/produce", json={"text": "Une aventure en forêt de 2 minutes", "quality": "brouillon"})
    jid = r.json()["job"]["id"]
    client.post(f"/api/jobs/{jid}/cancel")
    j, _ = wait(client, jid)
    assert j["status"] == "cancelled"
    assert client.post(f"/api/jobs/{jid}/retry").status_code == 200


@pytest.mark.skipif(os.name == "nt", reason="faux binaire shell")
def test_qr_et_adresse_telephone(client, tmp_path, monkeypatch):
    # faux binaire « tailscale » connecté
    fake = tmp_path / "tailscale"
    fake.write_text('#!/bin/sh\necho \'{"BackendState":"Running","Self":{"DNSName":"mon-pc.tail1234.ts.net."}}\'\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    sysinfo = client.get("/api/system").json()
    if sysinfo["phone_url"] is None:  # cache de 60 s rempli par un test précédent
        pytest.skip("cache de détection Tailscale déjà rempli")
    assert sysinfo["phone_url"] == "https://mon-pc.tail1234.ts.net"
    r = client.get("/api/qr", params={"u": sysinfo["phone_url"]})
    assert r.status_code == 200 and b"<svg" in r.content
    assert client.get("/api/qr", params={"u": "javascript:alert(1)"}).status_code == 400


def test_mot_de_passe_par_entree_standard(tmp_path):
    import sys
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
    r = subprocess.run([sys.executable, "-m", "serveur", "mot-de-passe", "--stdin", "--donnees", str(tmp_path)],
                       input="un-mot-de-passe-solide\n", text=True, capture_output=True, env=env,
                       cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode == 0, r.stderr
    cfg = Config(tmp_path)
    assert auth.check_password("un-mot-de-passe-solide", cfg.data["password_hash"])
    r = subprocess.run([sys.executable, "-m", "serveur", "mot-de-passe", "--stdin", "--donnees", str(tmp_path)],
                       input="court\n", text=True, capture_output=True, env=env, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode != 0
