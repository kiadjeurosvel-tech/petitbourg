"""Application des retouches à un scénario existant.

Principe : on modifie UNIQUEMENT les champs concernés de la (des) scène(s) visée(s).
Le pipeline compare ensuite les empreintes (spec.audio_key / spec.visual_key) et ne
recalcule que ce qui a réellement changé : le reste est réutilisé depuis le cache.
"""
from __future__ import annotations

import copy

from . import intent, llm
from .spec import normalize_spec, rnd
from .story import X, INTERJECTIONS


def _who(name, spec):
    if not name:
        return None
    f = intent.fold(name)
    for c in spec["characters"]:
        if intent.fold(c["name"]) == f:
            return c["id"]
    return None


def resolve_scenes(spec: dict, scene_n) -> list[int]:
    n = len(spec["scenes"])
    if scene_n is None:
        return list(range(n))
    if scene_n == -1:
        return [n - 1]
    if 1 <= int(scene_n) <= n:
        return [int(scene_n) - 1]
    raise ValueError(f"La scène {scene_n} n'existe pas (cet épisode a {n} scène(s)).")


def apply_ops(spec: dict, ops: list[dict], idxs: list[int], keep_characters: bool) -> list[str]:
    """Modifie `spec` en place. Retourne des remarques."""
    notes = []
    for op in ops:
        kind = op.get("op")
        for i in idxs:
            sc = spec["scenes"][i]
            if kind == "expressiveness":
                sc["expressiveness"] = round(min(3, max(.2, sc["expressiveness"] * float(op.get("factor", 1.5)))), 2)
            elif kind == "speed":
                f = float(op.get("factor", .6))
                sc["anim_speed"] = round(min(3, max(.25, sc["anim_speed"] * f)), 2)
                sc["camera"]["speed"] = round(min(3, max(.2, sc["camera"]["speed"] * f)), 2)
            elif kind == "camera_move":
                sc["camera"]["move"] = op.get("move", "static")
            elif kind == "camera_shot":
                sc["camera"]["shot"] = op.get("shot", "moyen")
            elif kind == "set":
                sc["set"] = op.get("set", sc["set"])
                sc["variant"] = 0
            elif kind == "background_variant":
                sc["variant"] = (sc["variant"] + 1) % 6
            elif kind == "lighting":
                sc["lighting"] = op.get("lighting", "normal")
            elif kind == "time":
                sc["time"] = op.get("time", "jour")
            elif kind == "duration":
                sc["min_duration"] = max(1.5, min(30, sc["min_duration"] + float(op.get("delta", 2))))
                if float(op.get("delta", 2)) > 0:
                    sc["min_duration"] = max(sc["min_duration"], _scene_estimate(sc) + float(op.get("delta", 2)))
            elif kind == "emotion":
                who = _who(op.get("who"), spec)
                for ln in sc["lines"]:
                    if who is None or ln["who"] == who:
                        ln["emotion"] = op.get("emotion", "neutre")
            elif kind == "dialogue":
                who = _who(op.get("who"), spec)
                target = next((ln for ln in sc["lines"] if who is None or ln["who"] == who), None)
                if target:
                    target["text"] = op.get("text", target["text"])
                elif who or sc["characters"]:
                    sc["lines"].append({"who": who or sc["characters"][0], "text": op.get("text", ""), "emotion": "neutre"})
    # apparence : concerne le personnage partout (cohérence)
    for op in ops:
        if op.get("op") == "look":
            if keep_characters:
                notes.append("Changement d'apparence ignoré : vous avez demandé de conserver les personnages.")
                continue
            who = _who(op.get("who"), spec)
            targets = [c for c in spec["characters"] if who is None or c["id"] == who]
            if who is None and len(targets) > 1:
                cast = set(c for i in idxs for c in spec["scenes"][i]["characters"])
                targets = [c for c in targets if c["id"] in cast][:1]
            for c in targets:
                c["look"][op["field"]] = op["value"]
                notes.append(f"Apparence de {c['name']} modifiée : toutes ses scènes seront re-rendues.")
    return notes


def _scene_estimate(sc):
    return sum(len(ln["text"]) / 14 + .35 for ln in sc["lines"]) + 1.2


def plan_edit(spec: dict, text: str, scene_n, settings: dict, log=print) -> tuple[dict, dict]:
    """Retourne (nouvelle spec, infos) sans rien rendre."""
    parsed = intent.parse_edit(text)
    if scene_n is None:
        scene_n = parsed["scene"]
    ops = parsed["ops"]
    source = "regles"
    if not ops and llm.enabled(settings):
        try:
            ops = llm.edit_ops(text, settings, log=log)
            source = llm.describe(settings)
            parsed["understood"] = [f"{o['op']} " + ", ".join(f"{k}={v}" for k, v in o.items() if k != "op") for o in ops]
        except Exception as ex:  # noqa: BLE001
            log(f"Modèle local indisponible pour la retouche ({ex}).")
    idxs = resolve_scenes(spec, scene_n)
    new = copy.deepcopy(spec)
    notes = apply_ops(new, ops, idxs, parsed["keep_characters"])
    new = normalize_spec(new)
    return new, {"ops": ops, "understood": parsed["understood"], "notes": notes, "scenes": [i + 1 for i in idxs],
                 "source": source, "unknown": not ops}


def regenerate_scene(spec: dict, scene_n, rewrite_dialogue: bool, seed) -> tuple[dict, dict]:
    """Nouvelle prise d'une scène : autre interprétation (gestes, caméra), personnages inchangés."""
    idxs = resolve_scenes(spec, scene_n if scene_n is not None else 1)
    new = copy.deepcopy(spec)
    r = rnd(seed)
    for i in idxs:
        sc = new["scenes"][i]
        sc["seed"] = r.randint(1, 10**8)
        sc["camera"]["move"] = r.choice(["static", "dolly_in", "dolly_out", "pan_left", "pan_right", "orbit", "crane_up"])
        if rewrite_dialogue:
            ids = sc["characters"] or [c["id"] for c in new["characters"][:2]]
            pool = [ex for stage in X.get(new["genre"], X["comedie"]).values() for ex in stage]
            ex = r.choice(pool)
            slots = {"A": ids[0], "B": ids[1] if len(ids) > 1 else ids[0], "C": ids[2] if len(ids) > 2 else ids[0]}
            sc["lines"] = [{"who": slots[s], "text": t.replace("{T}", "ça"), "emotion": e} for s, t, e in ex]
            if len(ids) > 2:
                s, t, e = r.choice(INTERJECTIONS)
                sc["lines"].append({"who": slots["C"], "text": t, "emotion": e})
    return normalize_spec(new), {"scenes": [i + 1 for i in idxs], "understood": ["Nouvelle prise" + (" avec nouveau dialogue" if rewrite_dialogue else "")]}
