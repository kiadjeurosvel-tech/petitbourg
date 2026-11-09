"""Modèles de langage LOCAUX, interchangeables.

Fournisseurs :
- "regles"  : aucun modèle, générateur intégré (par défaut si rien ne répond).
- "ollama"  : serveur Ollama local (http://127.0.0.1:11434), modèles au choix
              (qwen2.5:7b-instruct, llama3.1:8b, mistral-nemo, gemma2:9b…).
- "openai_local" : tout serveur local compatible OpenAI (llama.cpp server, LM Studio, vLLM…).

Sécurité / indépendance : seules les adresses locales ou du réseau privé sont acceptées,
pour éviter d'envoyer par erreur les demandes à une API payante en ligne.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.request
from urllib.parse import urlparse

SUGGESTED_MODELS = ["qwen2.5:7b-instruct", "llama3.1:8b", "mistral-nemo", "gemma2:9b", "qwen2.5:3b-instruct"]


def _is_local(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        if host in ("localhost",) or host.endswith(".local"):
            return True
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if not (ip.is_private or ip.is_loopback):
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


def enabled(settings: dict) -> bool:
    return (settings.get("llm_provider") or "regles") in ("ollama", "openai_local")


def describe(settings: dict) -> str:
    return f"{settings.get('llm_provider')}:{settings.get('llm_model')}"


def _post(url: str, payload: dict, timeout: float) -> dict:
    if not _is_local(url):
        raise RuntimeError(f"adresse non locale refusée : {url}")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — adresse locale vérifiée
        return json.loads(r.read().decode())


def _extract_json(txt: str):
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def chat_json(messages: list[dict], settings: dict, log=print):
    provider = settings.get("llm_provider") or "regles"
    model = settings.get("llm_model") or SUGGESTED_MODELS[0]
    timeout = float(settings.get("llm_timeout") or 600)
    if provider == "ollama":
        base = (settings.get("llm_url") or "http://127.0.0.1:11434").rstrip("/")
        log(f"Modèle local : Ollama / {model}")
        res = _post(f"{base}/api/chat", {"model": model, "messages": messages, "stream": False, "format": "json",
                                         "options": {"temperature": .8, "num_ctx": 8192}}, timeout)
        return _extract_json(res.get("message", {}).get("content", ""))
    if provider == "openai_local":
        base = (settings.get("llm_url") or "http://127.0.0.1:8080/v1").rstrip("/")
        log(f"Modèle local : {base} / {model}")
        res = _post(f"{base}/chat/completions", {"model": model, "messages": messages, "temperature": .8,
                                                 "response_format": {"type": "json_object"}}, timeout)
        return _extract_json(res["choices"][0]["message"]["content"])
    return None


def list_models(settings: dict) -> dict:
    """Interroge le serveur local pour lister les modèles installés (pour la page Réglages)."""
    provider = settings.get("llm_provider") or "regles"
    try:
        if provider == "ollama":
            base = (settings.get("llm_url") or "http://127.0.0.1:11434").rstrip("/")
            if not _is_local(base):
                return {"ok": False, "error": "adresse non locale", "models": []}
            with urllib.request.urlopen(f"{base}/api/tags", timeout=3) as r:  # noqa: S310
                data = json.loads(r.read().decode())
            return {"ok": True, "models": [m["name"] for m in data.get("models", [])]}
        if provider == "openai_local":
            base = (settings.get("llm_url") or "http://127.0.0.1:8080/v1").rstrip("/")
            if not _is_local(base):
                return {"ok": False, "error": "adresse non locale", "models": []}
            with urllib.request.urlopen(f"{base}/models", timeout=3) as r:  # noqa: S310
                data = json.loads(r.read().decode())
            return {"ok": True, "models": [m["id"] for m in data.get("data", [])]}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": str(ex), "models": []}
    return {"ok": True, "models": [], "note": "générateur intégré (aucun modèle)"}


EDIT_SYSTEM = """Tu convertis une consigne de retouche vidéo en opérations JSON. Réponds UNIQUEMENT en JSON :
{"ops": [ ... ]} avec des opérations parmi :
{"op":"expressiveness","factor":0.5..2}, {"op":"speed","factor":0.4..2}, {"op":"camera_move","move":un de [static,dolly_in,dolly_out,pan_left,pan_right,orbit,crane_up,handheld]},
{"op":"camera_shot","shot":"large"|"moyen"|"gros_plan"}, {"op":"set","set":un de [restaurant,rue,foret,salon,bureau,manoir,plage,espace,classe]},
{"op":"background_variant"}, {"op":"lighting","lighting":"normal"|"lumineux"|"sombre"|"dramatique"}, {"op":"time","time":"jour"|"soir"|"nuit"},
{"op":"emotion","emotion":un de [neutre,joie,colere,triste,surprise,peur,reflexion],"who":prénom ou null},
{"op":"dialogue","text":"nouvelle réplique","who":prénom ou null}, {"op":"duration","delta":secondes}.
N'invente rien qui ne soit pas demandé. Liste vide si rien ne correspond."""


def edit_ops(text: str, settings: dict, log=print) -> list[dict]:
    data = chat_json([{"role": "system", "content": EDIT_SYSTEM}, {"role": "user", "content": text}], settings, log=log)
    ops = data.get("ops") if isinstance(data, dict) else None
    return [o for o in ops or [] if isinstance(o, dict) and isinstance(o.get("op"), str)]
