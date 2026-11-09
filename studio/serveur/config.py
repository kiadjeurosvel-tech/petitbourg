"""Configuration persistante (dossier de données + config.json)."""
from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

DEFAULT_SETTINGS = {
    "renderer": "auto",          # auto | blender | 2d
    "blender_path": "",
    "tts_engine": "auto",        # auto | piper | espeak-ng | silence
    "llm_provider": "regles",    # regles | ollama | openai_local
    "llm_model": "qwen2.5:7b-instruct",
    "llm_url": "",
    "llm_timeout": 600,
    "default_quality": "standard",
    "default_format": "9:16",
    "default_style": "cartoon3d",
    "default_duration": 30,
    "subtitles": True,
    "music": True,
    "keep_blend": True,
}
EDITABLE = set(DEFAULT_SETTINGS)


class Config:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir or os.environ.get("STUDIO_DATA") or ROOT / "donnees").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("cache", "voix", "musique", "episodes", "histoires", "sauvegardes"):
            (self.data_dir / sub).mkdir(exist_ok=True)
        self.path = self.data_dir / "config.json"
        self._lock = threading.Lock()
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        changed = False
        if not self.data.get("secret"):
            self.data["secret"] = secrets.token_hex(32)
            changed = True
        self.data.setdefault("allowed_origins", ["https://kiadjeurosvel-tech.github.io"])
        self.data.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            if k not in self.data["settings"]:
                self.data["settings"][k] = v
                changed = True
        if changed or not self.path.exists():
            self.save()

    @property
    def settings(self) -> dict:
        return dict(self.data["settings"])

    def update_settings(self, values: dict) -> dict:
        with self._lock:
            for k, v in values.items():
                if k in EDITABLE:
                    self.data["settings"][k] = v
            self.save()
        return self.settings

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    @property
    def secret(self) -> bytes:
        return bytes.fromhex(self.data["secret"])
