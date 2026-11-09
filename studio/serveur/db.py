"""Base SQLite locale (aucun service externe)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, notes TEXT DEFAULT '', draft TEXT DEFAULT '{}',
  created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS stories (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT, genre TEXT, style TEXT, format TEXT, memory TEXT DEFAULT '{}', created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS characters (id INTEGER PRIMARY KEY, story_id INTEGER REFERENCES stories(id) ON DELETE CASCADE,
  cid TEXT, name TEXT, gender TEXT, role TEXT, look TEXT, voice TEXT, ref_image TEXT, created REAL, UNIQUE(story_id, cid));
CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY, story_id INTEGER REFERENCES stories(id) ON DELETE CASCADE,
  number INTEGER, title TEXT, prompt TEXT, current_version INTEGER, status TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, episode_id INTEGER REFERENCES episodes(id) ON DELETE CASCADE,
  number INTEGER, spec TEXT, note TEXT, parent_id INTEGER, status TEXT, result TEXT DEFAULT '{}', created REAL);
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, kind TEXT, status TEXT, params TEXT, title TEXT,
  project_id INTEGER, story_id INTEGER, episode_id INTEGER, version_id INTEGER,
  stages TEXT DEFAULT '[]', log TEXT DEFAULT '', error TEXT, result TEXT DEFAULT '{}',
  created REAL, started REAL, finished REAL, updated REAL);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
"""
JSON_COLS = {"draft", "memory", "look", "voice", "spec", "result", "params", "stages"}


class DB:
    def __init__(self, path: Path):
        self.path = path
        self._local = threading.local()
        self.lock = threading.RLock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "c", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA foreign_keys=ON")
            self._local.c = c
        return c

    @staticmethod
    def _row(r):
        if r is None:
            return None
        d = dict(r)
        for k in JSON_COLS & d.keys():
            if isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        return d

    def q(self, sql, args=()):
        with self.lock:
            return [self._row(r) for r in self.conn().execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        with self.lock:
            return self._row(self.conn().execute(sql, args).fetchone())

    def insert(self, table, **vals):
        vals = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_COLS and not isinstance(v, str) else v) for k, v in vals.items()}
        now = time.time()
        if table != "characters" and table != "versions":
            vals.setdefault("updated", now)
        vals.setdefault("created", now)
        cols = ",".join(vals)
        with self.lock:
            c = self.conn()
            cur = c.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(vals))})", tuple(vals.values()))
            c.commit()
            return cur.lastrowid

    def update(self, table, id_, **vals):
        if not vals:
            return
        vals = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_COLS and not isinstance(v, str) else v) for k, v in vals.items()}
        if table in ("projects", "stories", "episodes", "jobs"):
            vals.setdefault("updated", time.time())
        sets = ",".join(f"{k}=?" for k in vals)
        with self.lock:
            c = self.conn()
            c.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*vals.values(), id_))
            c.commit()

    def delete(self, table, id_):
        with self.lock:
            c = self.conn()
            c.execute(f"DELETE FROM {table} WHERE id=?", (id_,))
            c.commit()
