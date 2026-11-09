"""Génération de scénario.

1. Si un modèle de langage local est configuré et répond : il écrit le scénario (JSON).
2. Sinon (ou en cas de réponse invalide) : générateur intégré par règles, déterministe.

Dans les deux cas, le résultat passe par spec.normalize_spec.
"""
from __future__ import annotations

import json
import re

from . import llm
from .intent import fold
from .spec import (CAMERA_MOVES, SETS, normalize_spec, rnd, make_look)

NAMES_F = ["Léa", "Inès", "Chloé", "Camille", "Sarah", "Nora", "Awa", "Jeanne", "Zoé", "Maya", "Lina", "Rose"]
NAMES_M = ["Hugo", "Malik", "Yanis", "Théo", "Karim", "Lucas", "Moussa", "Paul", "Nathan", "Sami", "Victor", "Omar"]

GENRE_SET = {"dispute": "restaurant", "mystere": "manoir", "comedie": "salon", "aventure": "foret", "romance": "plage", "drame": "rue"}
TOPICS = {
    "dispute": ["l'addition", "la dernière part de tarte", "un secret répété à tout le monde", "la place près de la fenêtre"],
    "mystere": ["la lettre anonyme", "la clé disparue", "les bruits dans le couloir", "le portrait qui a bougé"],
    "comedie": ["le gâteau d'anniversaire raté", "le perroquet du voisin", "la recette secrète de mamie"],
    "aventure": ["la carte au trésor", "le vieux coffre", "la boussole qui s'affole"],
    "romance": ["le premier rendez-vous", "la lettre jamais envoyée", "le bracelet perdu"],
    "drame": ["le départ en train", "la vieille promesse", "la maison familiale vendue"],
}
TITLES = {
    "dispute": ["Tout ça pour {T}", "La dispute", "Rien ne va plus"], "mystere": ["Le mystère de {T}", "Minuit moins une", "Ce qui se cache"],
    "comedie": ["Le jour où tout a raté", "Catastrophe en vue", "{T} !"], "aventure": ["À la recherche de {T}", "L'expédition", "Au-delà des arbres"],
    "romance": ["{T}", "Au bord de l'eau", "Juste nous deux"], "drame": ["{T}", "Ce qu'on ne dit pas", "Le dernier jour"],
}

# Échanges par genre et par étape : listes de (locuteur, texte, émotion). A, B = personnages ; C = un tiers éventuel.
X = {
 "dispute": {
  "ouverture": [[("A", "Bon. On peut parler de {T} ?", "neutre"), ("B", "Encore ? On en a déjà parlé hier.", "reflexion"), ("A", "Non, toi tu as parlé. Moi j'ai écouté.", "colere")],
                [("B", "Tu fais une de ces têtes… Qu'est-ce qu'il y a ?", "surprise"), ("A", "Tu le sais très bien. {T}.", "colere")],
                [("A", "Je te préviens, ce soir je ne lâche rien.", "colere"), ("B", "Parfait. Moi non plus.", "colere")]],
  "montee": [[("B", "Tu exagères toujours tout !", "colere"), ("A", "Moi ? C'est toi qui as commencé avec {T} !", "colere")],
             [("A", "Tu te souviens de ce que tu m'avais promis ?", "triste"), ("B", "Ce n'était pas une promesse, c'était une idée.", "neutre"), ("A", "Ah, pratique !", "colere")],
             [("B", "Baisse d'un ton, tout le monde nous regarde.", "peur"), ("A", "Qu'ils regardent ! Je n'ai rien à cacher, moi.", "colere")],
             [("A", "Chaque fois c'est pareil.", "colere"), ("B", "Chaque fois tu dis « chaque fois ».", "colere")]],
  "crise": [[("A", "Ça suffit !", "colere"), ("B", "Non, ça ne suffit pas ! Pas cette fois !", "colere"), ("A", "Alors dis-le, vas-y !", "colere")],
            [("B", "Tu veux la vérité ? Très bien.", "colere"), ("B", "C'est moi qui ai tout raconté.", "triste"), ("A", "… Quoi ?", "surprise")],
            [("C", "Excusez-moi… tout va bien ici ?", "peur"), ("A", "NON !", "colere"), ("B", "Oui !", "colere")]],
  "retournement": [[("A", "Attends… pourquoi tu souris ?", "surprise"), ("B", "Parce qu'on se dispute pour {T}. Franchement.", "joie")],
                   [("B", "Tu sais quoi ? Tu as raison.", "reflexion"), ("A", "… Pardon ? Répète ça.", "surprise")]],
  "fin": [[("A", "Bon… on partage ?", "joie"), ("B", "On partage. Mais la prochaine fois, c'est moi qui choisis.", "joie")],
          [("B", "Promis, je ne recommencerai plus.", "triste"), ("A", "Tu dis toujours ça.", "reflexion"), ("B", "Cette fois, c'est vrai.", "joie")]],
  "suspense": [[("A", "Au fait… qui t'a parlé de {T} ?", "reflexion"), ("B", "Ça… je ne peux pas te le dire.", "peur")]],
 },
 "mystere": {
  "ouverture": [[("A", "Tu as entendu ça ?", "peur"), ("B", "Le vent. C'est juste le vent.", "neutre"), ("A", "Le vent ne frappe pas trois coups.", "peur")],
                [("B", "Regarde. {T}. Elle n'était pas là ce matin.", "surprise"), ("A", "Ne touche à rien.", "peur")]],
  "montee": [[("A", "Quelqu'un est venu ici cette nuit.", "reflexion"), ("B", "Les portes étaient fermées à clé.", "peur")],
             [("B", "Il y a des traces… elles mènent vers l'escalier.", "surprise"), ("A", "Alors on monte. Doucement.", "reflexion")],
             [("A", "Tout ça a un rapport avec {T}, j'en suis sûr.", "reflexion"), ("B", "Comment tu peux en être si sûr ?", "peur")]],
  "crise": [[("B", "La lumière ! Elle s'est éteinte !", "peur"), ("A", "Reste près de moi !", "peur")],
            [("A", "Il y a quelqu'un derrière toi…", "peur"), ("B", "Ne plaisante pas avec ça.", "peur"), ("A", "Je ne plaisante pas.", "peur")]],
  "retournement": [[("B", "Attends… cette écriture. Je la reconnais.", "surprise"), ("A", "C'est impossible.", "surprise")],
                   [("A", "Ce n'était pas un fantôme. Quelqu'un voulait nous faire peur.", "reflexion"), ("B", "Mais qui ? Et pourquoi ?", "reflexion")]],
  "fin": [[("A", "On a la réponse. Enfin presque.", "reflexion"), ("B", "Presque, c'est déjà beaucoup.", "joie")]],
  "suspense": [[("B", "Regarde la fenêtre…", "peur"), ("A", "Il y a quelqu'un. Il nous observe.", "peur")]],
 },
 "comedie": {
  "ouverture": [[("A", "J'ai une idée géniale.", "joie"), ("B", "Oh non. Pas encore une idée géniale.", "peur")],
                [("B", "Pourquoi la cuisine est couverte de farine ?", "surprise"), ("A", "C'est… artistique.", "joie")]],
  "montee": [[("A", "Fais-moi confiance, je maîtrise.", "joie"), ("B", "Tu as dit ça la dernière fois. Et les pompiers sont venus.", "reflexion")],
             [("B", "C'est quoi ce bruit ?", "surprise"), ("A", "Rien. Enfin… {T}.", "peur")],
             [("A", "Étape deux : on improvise !", "joie"), ("B", "Il n'y avait pas d'étape un !", "colere")]],
  "crise": [[("B", "Ça fume ! Pourquoi ça fume ?", "peur"), ("A", "C'est normal ! Enfin… je crois.", "peur")],
            [("A", "Plan B !", "surprise"), ("B", "On n'a pas de plan B !", "colere"), ("A", "Alors plan C !", "joie")]],
  "retournement": [[("B", "Attends… en fait, c'est délicieux.", "surprise"), ("A", "Je te l'avais dit. Génie.", "joie")]],
  "fin": [[("A", "Bon. On ne dit rien à personne ?", "joie"), ("B", "À personne. Jamais.", "joie")]],
  "suspense": [[("B", "Euh… pourquoi le voisin est à la porte avec un extincteur ?", "surprise"), ("A", "Ah.", "peur")]],
 },
 "aventure": {
  "ouverture": [[("A", "D'après {T}, c'est par ici.", "reflexion"), ("B", "Tu sais lire une carte, au moins ?", "reflexion"), ("A", "Évidemment. Elle est juste… à l'envers.", "joie")],
                [("B", "On y est. Le point de départ.", "joie"), ("A", "Alors c'est parti !", "joie")]],
  "montee": [[("A", "Tu entends ? De l'eau. On approche.", "reflexion"), ("B", "Ou on tourne en rond depuis une heure.", "colere")],
             [("B", "Le chemin s'arrête ici.", "surprise"), ("A", "Non. Il continue… sous les racines.", "joie")]],
  "crise": [[("A", "Le pont ! Il va céder !", "peur"), ("B", "Cours ! Ne regarde pas en bas !", "peur")],
            [("B", "On est perdus, avoue-le.", "colere"), ("A", "On n'est pas perdus. On explore.", "reflexion")]],
  "retournement": [[("A", "Regarde ce symbole… c'est le même que sur {T} !", "surprise"), ("B", "Alors on était sur la bonne piste depuis le début.", "joie")]],
  "fin": [[("B", "On l'a fait !", "joie"), ("A", "On l'a fait. Ensemble.", "joie")]],
  "suspense": [[("A", "Attends… il y a une deuxième carte cachée dedans.", "surprise"), ("B", "Ça veut dire que ce n'est que le début.", "reflexion")]],
 },
 "romance": {
  "ouverture": [[("A", "Tu es venu.", "joie"), ("B", "Tu croyais que j'allais rater {T} ?", "joie")],
                [("B", "Je suis un peu en retard, pardon.", "peur"), ("A", "Treize minutes. Mais qui compte ?", "joie")]],
  "montee": [[("A", "Je dois t'avouer quelque chose.", "peur"), ("B", "Moi aussi. Toi d'abord.", "reflexion")],
             [("B", "Tu te souviens de notre première rencontre ?", "joie"), ("A", "Tu avais renversé ton café sur moi.", "joie")]],
  "crise": [[("A", "Je pars demain. Pour un an.", "triste"), ("B", "… Et tu me le dis maintenant ?", "triste")]],
  "retournement": [[("B", "Alors je viens avec toi.", "joie"), ("A", "Tu es sérieux ?", "surprise")]],
  "fin": [[("A", "Promets-moi une chose.", "joie"), ("B", "Tout ce que tu veux.", "joie")]],
  "suspense": [[("A", "Attends, qui t'a envoyé cette lettre ?", "surprise"), ("B", "Je… je ne sais pas.", "peur")]],
 },
 "drame": {
  "ouverture": [[("A", "C'est aujourd'hui, alors.", "triste"), ("B", "Oui. {T}.", "triste")]],
  "montee": [[("B", "On aurait dû se parler plus tôt.", "triste"), ("A", "On a eu peur. Tous les deux.", "reflexion")],
             [("A", "Tu te rappelles quand on était petits ?", "joie"), ("B", "On croyait que rien ne changerait jamais.", "triste")]],
  "crise": [[("B", "Pourquoi tu ne m'as rien dit ?", "colere"), ("A", "Parce que je savais que tu essaierais de me retenir.", "triste")]],
  "retournement": [[("A", "Je ne pars pas pour toujours.", "reflexion"), ("B", "Alors reviens. C'est tout ce que je demande.", "triste")]],
  "fin": [[("B", "Prends soin de toi.", "triste"), ("A", "Toi aussi. On se revoit bientôt.", "joie")]],
  "suspense": [[("A", "Au fait… il y a quelque chose dans la boîte aux lettres.", "surprise"), ("B", "C'est ton écriture…", "surprise")]],
 },
}
INTERJECTIONS = [("C", "Hé ! Qu'est-ce qui se passe ici ?", "surprise"), ("C", "Je peux dire quelque chose ?", "reflexion"),
                 ("C", "Vous êtes sérieux, là ?", "colere"), ("C", "Moi, je n'ai rien vu.", "peur")]
RECALL = [("A", "Après ce qui s'est passé la dernière fois… {E}", "reflexion"), ("B", "Je n'arrête pas d'y penser.", "reflexion")]
STAGE_ACTION = {"dispute": {"crise": "dispute", "montee": "dispute"}, "mystere": {"ouverture": "peur", "crise": "peur", "montee": "reflexion"},
                "comedie": {"crise": "surprise", "fin": "rire"}, "aventure": {"montee": "marcher", "crise": "peur"},
                "romance": {"fin": "rire"}, "drame": {"crise": "triste", "fin": "triste"}}
SECONDS_PER_SCENE = 9.0


def _stages(n: int, cliffhanger: bool) -> list[str]:
    order = ["ouverture", "montee", "crise", "retournement", "fin"]
    if n <= 1:
        return ["crise"]
    if n == 2:
        return ["ouverture", "fin"]
    weights = [.2, .3, .25, .1, .15]
    counts = [max(1, round(w * n)) for w in weights]
    while sum(counts) > n:
        i = max(range(5), key=lambda k: counts[k] if k not in (0, 4) else 0)
        counts[i] -= 1
    while sum(counts) < n:
        counts[1] += 1
    out = [s for s, c in zip(order, counts) for _ in range(c)]
    out[-1] = "suspense" if cliffhanger else "fin"
    return out


def _new_characters(req: dict, r, existing: list[dict]) -> list[dict]:
    names = [n for n in req.get("names") or [] if n not in {c["name"] for c in existing}]
    n = req.get("n_characters") or max(2, len(names))
    n = max(1, min(4, n))
    used = {c["name"] for c in existing}
    pool_f = [x for x in NAMES_F if x not in used]
    pool_m = [x for x in NAMES_M if x not in used]
    r.shuffle(pool_f)
    r.shuffle(pool_m)
    out = []
    for i in range(n):
        if i < len(names):
            name = names[i]
            gender = "f" if fold(name).endswith(("a", "e", "ie", "ine", "elle")) and fold(name) not in ("hugo",) else "m"
        else:
            gender = "f" if i % 2 == 0 else "m"
            name = (pool_f if gender == "f" else pool_m).pop()
        cid = f"c{len(existing) + i + 1}"
        out.append({"id": cid, "name": name, "gender": gender, "look": make_look(f"{name}-{r.random()}", gender)})
    return out


def rules_screenplay(req: dict, ctx: dict, seed) -> dict:
    """Générateur intégré. `ctx` = {"characters": [...], "memory": {...}, "story_title": str, "episode_n": int}"""
    r = rnd(seed)
    command = req.get("command", "create")
    existing = list(ctx.get("characters") or [])
    genre = req.get("genre") or ctx.get("genre") or ("mystere" if req.get("style") == "mystere" else r.choice(["dispute", "comedie", "aventure", "mystere"]))
    topic = (req.get("topic") or "").strip() or r.choice(TOPICS[genre])
    topic = re.sub(r"\s+(au|aux|dans|à|a|en|chez|sur|pendant)\s.*$", "", topic, flags=re.I)  # « l'addition au restaurant » → « l'addition »
    set_ = req.get("set") or ctx.get("set") or GENRE_SET[genre]
    duration = float(req.get("duration") or ctx.get("default_duration") or 30)
    n_scenes = max(1, min(30, round(duration / SECONDS_PER_SCENE)))

    if existing and command in ("continue", "new_episode"):
        cast = existing[: max(2, min(4, req.get("n_characters") or len(existing)))]
        extra = _new_characters({"names": [n for n in req.get("names") or [] if n not in {c["name"] for c in existing}], "n_characters": 0}, r, existing) if req.get("names") else []
        cast += [c for c in extra if c["name"] in (req.get("names") or [])]
    else:
        cast = _new_characters(req, r, existing)
    slots = {"A": cast[0]["id"], "B": cast[1]["id"] if len(cast) > 1 else cast[0]["id"], "C": cast[2]["id"] if len(cast) > 2 else None}

    pools = {k: list(v) for k, v in X[genre].items()}
    for v in pools.values():
        r.shuffle(v)
    used_idx = {k: 0 for k in pools}
    ending = (ctx.get("memory") or {}).get("ending") or ""
    stages = _stages(n_scenes, command in ("continue", "new_episode") or genre == "mystere")
    dynamic = req.get("camera_dynamic") or req.get("style") == "cinematique"
    moves_dyn = ["dolly_in", "orbit", "pan_left", "crane_up", "dolly_out", "pan_right", "handheld"]
    scenes = []
    for i, stage in enumerate(stages):
        pool = pools.get(stage) or pools["montee"]
        ex = pool[used_idx[stage] % len(pool)]
        used_idx[stage] = used_idx.get(stage, 0) + 1
        lines = []
        if i == 0 and command == "continue" and ending:
            lines += [(s, t.replace("{E}", ending), e) for s, t, e in RECALL]
        lines += list(ex)
        if slots["C"] and stage in ("montee", "crise") and r.random() < .6 and not any(s == "C" for s, _, _ in lines):
            lines.insert(r.randint(1, len(lines)), r.choice(INTERJECTIONS))
        out_lines = []
        for s, txt, emo in lines:
            who = slots.get(s) or slots["A"]
            txt = re.sub(r"(^|[.!?…]\s+)([a-zàâçéèêëîïôûù])", lambda m: m.group(1) + m.group(2).upper(), txt.replace("{T}", topic))
            out_lines.append({"who": who, "text": txt, "emotion": emo})
        chars = []
        for ln in out_lines:
            if ln["who"] not in chars:
                chars.append(ln["who"])
        for k in ("A", "B"):
            if slots[k] not in chars:
                chars.append(slots[k])
        if dynamic:
            move = moves_dyn[i % len(moves_dyn)]
            shot = ["moyen", "gros_plan", "large"][i % 3]
        else:
            move = "static" if i % 3 else ("dolly_in" if i else "dolly_out")
            shot = "gros_plan" if stage == "crise" else ("large" if i == 0 else "moyen")
        if genre == "dispute" and stage == "crise" and dynamic:
            move = "handheld"
        action = "entree" if (i == 0 and command == "create") else STAGE_ACTION.get(genre, {}).get(stage, "parler")
        time = "nuit" if genre == "mystere" or req.get("style") == "mystere" else ("soir" if genre == "romance" and stage in ("fin", "suspense") else "jour")
        scenes.append({
            "id": f"s{i + 1}", "set": set_, "variant": 0, "time": time,
            "lighting": "sombre" if genre == "mystere" else ("dramatique" if stage == "crise" and genre in ("drame", "dispute") else "normal"),
            "mood": stage, "summary": f"{stage.capitalize()} — " + " / ".join(ln["text"] for ln in out_lines[:2]),
            "characters": chars, "action": action, "lines": out_lines,
            "camera": {"move": move, "shot": shot, "speed": 1.2 if dynamic else .8},
            "expressiveness": 1.3 if genre in ("dispute", "comedie") else 1.0, "anim_speed": 1.0,
            "min_duration": 3.0, "seed": r.randint(1, 10**8),
        })
    tpl = r.choice(TITLES[genre])
    title_t = tpl.replace("{T}", topic[:1].upper() + topic[1:]) if tpl.startswith("{T}") else tpl.replace("{T}", topic)
    if command in ("continue", "new_episode") and ctx.get("story_title"):
        title = f"{ctx['story_title']} — épisode {ctx.get('episode_n', 2)}"
    else:
        title = title_t
    last = scenes[-1]["lines"][-1]["text"] if scenes[-1]["lines"] else ""
    names = " et ".join(c["name"] for c in cast[:2])
    return {
        "title": title, "genre": genre, "target_duration": duration,
        "logline": f"{names} — {topic} ({SETS.get(set_, set_)}).",
        "characters": cast, "scenes": scenes,
        "memory_out": {"summary": f"{names} : {topic}. " + " ".join(s["lines"][0]["text"] for s in scenes[:3] if s["lines"]),
                       "ending": last, "facts": [f"Lieu : {SETS.get(set_, set_)}", f"Sujet : {topic}"]},
    }


# --------------------------------------------------------------------------- modèle local

LLM_SYSTEM = """Tu es scénariste pour un studio d'animation 3D. Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte autour.
Format :
{"title": str, "logline": str, "genre": un de [dispute, mystere, comedie, aventure, romance, drame],
 "characters": [{"id": "c1", "name": str, "gender": "f"|"m", "role": str}],
 "scenes": [{"set": un de %(sets)s, "time": "jour"|"soir"|"nuit", "lighting": "normal"|"lumineux"|"sombre"|"dramatique",
             "summary": str, "characters": ["c1","c2"], "action": un de [parler, dispute, marcher, entree, surprise, rire, triste, reflexion, peur],
             "lines": [{"who": "c1", "text": "réplique courte en français", "emotion": un de [neutre, joie, colere, triste, surprise, peur, reflexion]}],
             "camera": {"move": un de %(moves)s, "shot": "large"|"moyen"|"gros_plan"}}],
 "memory_out": {"summary": "résumé de l'épisode", "ending": "dernière situation, pour enchaîner", "facts": ["faits importants à retenir"]}}
Règles : répliques courtes (max 15 mots), 2 à 4 répliques par scène, scènes d'environ 9 secondes, histoire cohérente avec un début, un conflit et une fin (ou un suspense)."""


def llm_screenplay(req: dict, ctx: dict, settings: dict, log) -> dict | None:
    duration = float(req.get("duration") or 30)
    n = max(1, min(30, round(duration / SECONDS_PER_SCENE)))
    mem = ctx.get("memory") or {}
    parts = [f"Demande : {req.get('prompt', '')}", f"Nombre de scènes : {n} (durée visée {int(duration)} s)."]
    if ctx.get("characters"):
        parts.append("Personnages existants (garde EXACTEMENT ces id et noms) : " +
                     json.dumps([{"id": c["id"], "name": c["name"], "gender": c["gender"], "role": c.get("role", "")} for c in ctx["characters"]], ensure_ascii=False))
    if mem:
        parts.append("Mémoire de l'histoire : " + json.dumps({k: mem.get(k) for k in ("summary", "ending", "facts", "episodes")}, ensure_ascii=False)[:3000])
    if req.get("command") == "continue":
        parts.append("Écris la SUITE directe de l'épisode précédent, en partant de sa fin.")
    elif req.get("command") == "new_episode":
        parts.append("Écris un NOUVEL épisode avec les mêmes personnages.")
    if req.get("set"):
        parts.append(f"Lieu principal : {req['set']}.")
    msgs = [{"role": "system", "content": LLM_SYSTEM % {"sets": list(SETS), "moves": CAMERA_MOVES}},
            {"role": "user", "content": "\n".join(parts)}]
    data = llm.chat_json(msgs, settings, log=log)
    if not isinstance(data, dict) or not data.get("scenes"):
        return None
    # garder les apparences des personnages existants
    known = {c["id"]: c for c in ctx.get("characters") or []}
    chars = []
    for c in data.get("characters") or []:
        if not isinstance(c, dict):
            continue
        if c.get("id") in known:
            chars.append(known[c["id"]])
        else:
            chars.append(c)
    data["characters"] = chars or list(known.values())
    data["target_duration"] = duration
    return data


def write_screenplay(req: dict, ctx: dict, settings: dict, seed, log=print) -> tuple[dict, str]:
    """Retourne (spec normalisée, nom du générateur utilisé)."""
    used = "regles"
    raw = None
    if llm.enabled(settings):
        try:
            raw = llm_screenplay(req, ctx, settings, log)
            if raw:
                used = llm.describe(settings)
            else:
                log("Le modèle local n'a pas renvoyé de scénario exploitable → générateur intégré.")
        except Exception as ex:  # noqa: BLE001 — on bascule toujours sur les règles
            log(f"Modèle local indisponible ({ex}) → générateur intégré.")
            raw = None
    if raw is None:
        raw = rules_screenplay(req, ctx, seed)
    raw.setdefault("target_duration", req.get("duration") or 30)
    spec = normalize_spec(raw, fmt=req.get("format"), quality=req.get("quality"), style=req.get("style"))
    if "subtitles" in req:
        spec["subtitles"] = bool(req["subtitles"])
    # personnages existants : on impose leur apparence et leur voix d'origine (cohérence visuelle)
    known = {c["id"]: c for c in ctx.get("characters") or []}
    spec["characters"] = [known.get(c["id"], c) if known.get(c["id"], {}).get("name") == c["name"] else c for c in spec["characters"]]
    return spec, used
