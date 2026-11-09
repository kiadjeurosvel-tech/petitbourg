"""Interprétation des demandes en français par règles (toujours disponible, déterministe).

Deux fonctions :
- `parse_request(text)`  : demande de production (créer, continuer, nouvel épisode…)
- `parse_edit(text)`     : demande de modification d'une scène → liste d'opérations

Le modèle de langage local (voir llm.py) peut compléter, mais ce module seul
suffit pour faire fonctionner le studio.
"""
from __future__ import annotations

import re
import unicodedata

from .spec import SETS

NUM_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
             "neuf": 9, "dix": 10, "quinze": 15, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
             "soixante": 60, "deux cents": 200}

SET_WORDS = {
    "restaurant": ["restaurant", "resto", "brasserie", "cafe", "bistrot", "diner"],
    "rue": ["rue", "ville", "trottoir", "quartier", "avenue", "centre-ville"],
    "foret": ["foret", "bois", "jungle", "arbres"],
    "salon": ["salon", "maison", "appartement", "chez eux", "chez lui", "chez elle", "canape"],
    "bureau": ["bureau", "entreprise", "open space", "travail"],
    "manoir": ["manoir", "chateau", "cimetiere", "maison hantee", "nuit noire"],
    "plage": ["plage", "mer", "ocean", "ile", "sable"],
    "espace": ["espace", "planete", "vaisseau", "etoiles", "lune", "galaxie"],
    "classe": ["classe", "ecole", "college", "lycee", "professeur"],
}
GENRE_WORDS = {
    "dispute": ["dispute", "disputent", "dispute", "querelle", "engueul", "conflit", "se battent", "clash", "rivaux", "rivalite"],
    "mystere": ["myster", "enquete", "secret", "disparu", "disparition", "etrange", "inquietant", "horreur", "fantome", "hante", "suspense"],
    "comedie": ["drole", "comique", "comedie", "humour", "rigol", "gag", "absurde"],
    "aventure": ["aventure", "quete", "tresor", "voyage", "explor", "mission", "action"],
    "romance": ["amour", "romance", "romantique", "rendez-vous", "coup de foudre", "amoureux"],
    "drame": ["drame", "triste", "emouvant", "adieu", "deuil", "dramatique"],
}
STYLE_WORDS = {
    "cinematique": ["cinemat", "film", "cinema", "epique"],
    "mystere": ["myster", "sombre", "nuit", "inquietant", "horreur", "noir"],
    "pastel": ["pastel", "doux", "mignon", "enfant", "tendre"],
    "cartoon3d": ["cartoon", "3d", "dessin anime", "pixar"],
}
STOP_NAMES = {"Crée", "Cree", "Créer", "Génère", "Genere", "Générer", "Fais", "Fait", "Une", "Un", "Le", "La", "Les", "Continue",
              "Reprends", "Change", "Ralentis", "Conserve", "Garde", "Modifie", "Régénère", "Ajoute", "Mon", "Ma", "Mes", "Avec",
              "Dans", "Il", "Elle", "Ils", "Elles", "Puis", "Et", "Je", "Tu", "Nous", "Vous", "On", "Scène", "Episode", "Épisode",
              "Caméra", "Camera", "Animation", "Vidéo", "Video", "Histoire", "Format", "Style", "Plan", "Personnage", "Personnages"}

COLORS = {"rouge": "#d64545", "bleu": "#2f6fd6", "bleue": "#2f6fd6", "vert": "#2fa36b", "verte": "#2fa36b", "jaune": "#e8c53a",
          "orange": "#e0873a", "violet": "#8a4fd6", "violette": "#8a4fd6", "rose": "#e06a9a", "noir": "#1c1c22", "noire": "#1c1c22",
          "blanc": "#f2f2f2", "blanche": "#f2f2f2", "gris": "#8c8c8c", "grise": "#8c8c8c", "marron": "#6b3e1f", "brun": "#5a3a22",
          "brune": "#5a3a22", "blond": "#d9b36c", "blonde": "#d9b36c", "roux": "#a8322a", "rousse": "#a8322a", "turquoise": "#16a3a3"}


def fold(s: str) -> str:
    """minuscules sans accents"""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("’", "'")


def _num(tok: str):
    tok = tok.strip()
    if tok.isdigit():
        return int(tok)
    return NUM_WORDS.get(fold(tok))


def parse_duration(t: str):
    """retourne des secondes ou None ; t est déjà « fold »"""
    m = re.search(r"(\d+)\s*(?:min(?:ute)?s?|mn)\s*(?:et\s*)?(\d+)?\s*(?:s|sec|secondes?)?", t)
    if m:
        return int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)
    m = re.search(r"(\d+)\s*(?:s|sec|secondes?)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(une|deux|trois|quatre|cinq|dix)\s+minutes?", t)
    if m:
        return NUM_WORDS[m.group(1)] * 60
    m = re.search(r"\b(dix|quinze|vingt|trente|quarante|cinquante|soixante)\s+secondes?", t)
    if m:
        return NUM_WORDS[m.group(1)]
    if "minute et demie" in t:
        return 90
    if "demi-minute" in t or "demi minute" in t:
        return 30
    return None


def parse_format(t: str):
    if re.search(r"9\s*[:/x]\s*16|vertical|portrait|tiktok|reels?|shorts?", t):
        return "9:16"
    if re.search(r"16\s*[:/x]\s*9|horizontal|paysage|youtube|cinema\s*large", t):
        return "16:9"
    if re.search(r"1\s*[:/x]\s*1|carre|instagram\s*post", t):
        return "1:1"
    return None


def _first(t: str, table: dict):
    best, pos = None, 10**9
    for key, words in table.items():
        for w in words:
            m = re.search(r"\b" + re.escape(w), t)
            if m and m.start() < pos:
                best, pos = key, m.start()
    return best


NAME_FOLLOWERS = {"et", "doit", "dit", "est", "se", "a", "va", "parle", "veut", "devient", "rencontre", "retrouve", "decouvre", "crie", "regarde", "doivent"}


def parse_names(text: str, known=None) -> list[str]:
    """Prénoms : noms connus de l'histoire, ou mots à majuscule (en début de phrase seulement
    s'ils sont suivis de « et », « doit », « dit »…)."""
    names = []
    for k in known or []:
        if re.search(r"\b" + re.escape(fold(k)) + r"\b", fold(text)) and k not in names:
            names.append(k)
    for sentence in re.split(r"[.!?\n]+", text):
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'-]+", sentence)
        for i, w in enumerate(words):
            w = w.strip("'-")
            if not (len(w) > 2 and w[0].isupper() and w[1:].islower()):
                continue
            if w in STOP_NAMES or fold(w) in SET_WORDS or w in names:
                continue
            if i == 0 and not (len(words) > 1 and fold(words[1]) in NAME_FOLLOWERS):
                continue
            names.append(w)
    return names[:6]


def parse_scene_ref(t: str):
    m = re.search(r"scene\s*(?:n[°o]?\s*)?(\d+)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(premiere|deuxieme|seconde|troisieme|quatrieme|cinquieme|derniere)\s+scene", t)
    if m:
        return {"premiere": 1, "deuxieme": 2, "seconde": 2, "troisieme": 3, "quatrieme": 4, "cinquieme": 5, "derniere": -1}[m.group(1)]
    return None


def parse_request(text: str) -> dict:
    """Analyse une demande libre. Ne lève jamais d'exception."""
    raw = text or ""
    t = fold(raw)
    out = {"command": "create", "duration": parse_duration(t), "format": parse_format(t), "style": None,
           "genre": _first(t, GENRE_WORDS), "set": _first(t, SET_WORDS), "n_characters": None,
           "names": parse_names(raw), "scene": parse_scene_ref(t), "camera_dynamic": False, "topic": None,
           "use_previous_characters": False, "notes": []}
    # style
    if "3d" in t or "3 d" in t:
        out["style"] = "cartoon3d"
    st = _first(t, {k: v for k, v in STYLE_WORDS.items() if k != "cartoon3d"})
    if st:
        out["style"] = st
    if re.search(r"camera\s+(dynamique|mobile|qui bouge)|plans?\s+dynamiques?|mouvements? de camera", t):
        out["camera_dynamic"] = True
        out["style"] = out["style"] or "cinematique"
    # nombre de personnages
    m = re.search(r"\b(\d+|un|une|deux|trois|quatre|cinq|six)\s+(?:personnages?|amis?|enfants?|personnes?|heros|filles?|garcons?|freres?|soeurs?|collegues?|voisins?)", t)
    if m:
        out["n_characters"] = _num(m.group(1))
    elif re.search(r"\b(un couple|deux amis|duo)\b", t):
        out["n_characters"] = 2
    # sujet : « à propos de … », « au sujet de … », « pour … »
    m = re.search(r"(?:a propos d[eu']s?|au sujet d[eu']s?|a cause d[eu']s?|qui parle(?:nt)? d[eu']s?)\s*([^,.;!?]{3,60})", t)
    if m:
        # retrouve le segment dans le texte original pour garder les accents
        start = m.start(1)
        out["topic"] = raw[start:start + len(m.group(1))].strip()
    # commande
    if re.search(r"(regenere|refais|recommence|nouvelle prise)\b.*scene|scene.*\b(regenere|refais)", t):
        out["command"] = "regenerate_scene"
    elif out["scene"] is not None and re.search(r"\b(reprends|modifie|ameliore|change|corrige|retouche|rends|ralenti|accelere)", t):
        out["command"] = "edit_scene"
    elif re.search(r"\b(continue|poursui[st]|la suite|suite de|episode suivant)\b", t):
        out["command"] = "continue"
    elif re.search(r"nouvel episode|nouveau episode|un episode|personnages de (mon|l')|meme(s)? personnages", t):
        out["command"] = "new_episode"
    if re.search(r"personnages de (mon|ma|l')|memes? personnages|histoire precedente", t):
        out["use_previous_characters"] = True
    return out


# --------------------------------------------------------------------------- modifications

def parse_edit(text: str) -> dict:
    """Transforme une consigne de retouche en opérations.

    Retour : {"ops": [...], "scene": n|None, "only": "background"|None, "keep_characters": bool,
              "understood": [phrases lisibles], "unknown": bool}
    Chaque op : {"op": nom, ...paramètres}
    """
    raw = text or ""
    t = fold(raw)
    ops, understood = [], []

    def add(op, label, **kw):
        ops.append({"op": op, **kw})
        understood.append(label)

    keep = bool(re.search(r"(conserve|garde|meme|identique|ne change pas).{0,25}personnage|personnage.{0,20}(identique|inchange)", t))
    only_bg = bool(re.search(r"(uniquement|seulement|juste)\s+(l'|le |la )?(arriere[- ]plan|decor|fond)", t))

    # expressivité
    if re.search(r"(plus|davantage|tres)\s+(expressi|anime|vivant|emoti)|expressions? faciales?|ameliore.{0,30}expression|plus d'emotion|exager", t):
        add("expressiveness", "Expressions et gestes plus marqués", factor=1.6)
    elif re.search(r"moins\s+(expressi|anime)|plus sobre|plus calme", t):
        add("expressiveness", "Jeu plus sobre", factor=.6)

    # vitesse
    if re.search(r"ralenti|plus lent|moins vite|au ralenti|doucement", t):
        add("speed", "Mouvements ralentis", factor=.6)
    elif re.search(r"accelere|plus vite|plus rapide|rythme plus", t):
        add("speed", "Mouvements accélérés", factor=1.5)

    # caméra
    cam = None
    if re.search(r"camera.{0,40}(vers la |a )gauche|travelling (vers la )?gauche|panoramique (vers la )?gauche", t):
        cam = ("pan_left", "Caméra qui se déplace vers la gauche")
    elif re.search(r"camera.{0,40}(vers la |a )droite|travelling (vers la )?droite|panoramique (vers la )?droite", t):
        cam = ("pan_right", "Caméra qui se déplace vers la droite")
    elif re.search(r"zoom(e|er)?\b(?! arriere)|rapproche|avance vers|plus pres", t):
        cam = ("dolly_in", "Caméra qui se rapproche")
    elif re.search(r"zoom arriere|dezoom|recule|eloigne|plus loin", t):
        cam = ("dolly_out", "Caméra qui recule")
    elif re.search(r"tourne autour|orbite|circulaire|360", t):
        cam = ("orbit", "Caméra qui tourne autour des personnages")
    elif re.search(r"camera.{0,30}(monte|s'eleve|plongee|du dessus|grue)", t):
        cam = ("crane_up", "Caméra qui s'élève")
    elif re.search(r"camera.{0,30}(fixe|immobile|stable|ne bouge pas)", t):
        cam = ("static", "Caméra fixe")
    elif re.search(r"camera.{0,30}(dynamique|vivante|a l'epaule|tremble)", t):
        cam = ("handheld", "Caméra dynamique à l'épaule")
    if cam:
        add("camera_move", cam[1], move=cam[0])
    if re.search(r"gros plan|plan serre|visage de pres", t):
        add("camera_shot", "Cadrage en gros plan", shot="gros_plan")
    elif re.search(r"plan large|plan d'ensemble|vue d'ensemble", t):
        add("camera_shot", "Cadrage large", shot="large")
    elif re.search(r"plan moyen|plan americain", t):
        add("camera_shot", "Cadrage moyen", shot="moyen")

    # arrière-plan / décor
    new_set = None
    for key, words in SET_WORDS.items():
        if any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in words):
            if re.search(r"(arriere[- ]plan|decor|fond|lieu|endroit|place|deplace|dans (un|une|la|le)|en |sur (la|le|une|un))", t):
                new_set = key
                break
    bg_word = re.search(r"arriere[- ]plan|decor|\bfond\b", t)
    if new_set:
        add("set", f"Décor : {SETS[new_set]}", set=new_set)
    elif bg_word and re.search(r"change|modifie|autre|nouveau|different|remplace", t):
        add("background_variant", "Nouvel arrière-plan (même lieu, autre variante)")

    # lumière / moment
    if re.search(r"plus sombre|assombri|moins de lumiere", t):
        add("lighting", "Éclairage plus sombre", lighting="sombre")
    elif re.search(r"plus lumineu|plus clair|eclaire", t):
        add("lighting", "Éclairage plus lumineux", lighting="lumineux")
    elif re.search(r"dramatique|contraste", t):
        add("lighting", "Éclairage dramatique", lighting="dramatique")
    if re.search(r"\b(la nuit|de nuit|en nuit)\b", t):
        add("time", "Scène de nuit", time="nuit")
    elif re.search(r"coucher de soleil|crepuscule|le soir|en soiree", t):
        add("time", "Scène au coucher du soleil", time="soir")
    elif re.search(r"\b(en plein jour|de jour|le jour|le matin)\b", t):
        add("time", "Scène de jour", time="jour")

    # émotion
    emo = None
    for pat, e, lab in ((r"colere|furieu|enerve|agace", "colere", "colère"), (r"joyeu|heureu|content|sourire|rire", "joie", "joie"),
                        (r"triste|pleur|malheureu", "triste", "tristesse"), (r"surpri|etonne|choque", "surprise", "surprise"),
                        (r"peur|effraye|terrifi|angoiss", "peur", "peur"), (r"pensif|reflechi|songeur", "reflexion", "réflexion")):
        if re.search(r"(plus|tres|davantage|en|l'air)\s+\w*\s*(" + pat + ")", t) or re.search(r"(doit|doivent|devrait)\s+(etre|paraitre|avoir l'air)\s+\w*\s*(" + pat + ")", t):
            emo = (e, lab)
            break
    if emo:
        who = _named_character(raw)
        add("emotion", f"Émotion : {emo[1]}" + (f" ({who})" if who else ""), emotion=emo[0], who=who)

    # dialogue :  X doit dire « … »   /  dit "…"
    m = re.search(r"(?:dire|dit|dise|disent|repond(?:re)?)\s*[:,]?\s*[«\"“']\s*(.+?)\s*[»\"”']", raw, flags=re.I)
    if m:
        who = _named_character(raw[:m.start()])
        add("dialogue", f"Nouvelle réplique : « {m.group(1)} »", text=m.group(1), who=who)

    # durée
    if re.search(r"(plus longue|rallonge|prolonge|dure plus)", t):
        add("duration", "Scène plus longue", delta=3)
    elif re.search(r"(plus courte|raccourci|dure moins)", t):
        add("duration", "Scène plus courte", delta=-2)

    # apparence (couleur de vêtements / cheveux) — touche le personnage dans TOUTES ses scènes
    if not keep:
        for part, field in ((r"(cheveux|coiffure)", "hair"), (r"(veste|haut|chemise|t-shirt|tenue|vetement|robe|pull|manteau)", "outfit"), (r"(pantalon|jean|jupe)", "pants")):
            m = re.search(part + r"\s+(?:en\s+)?(\w+)", t) or re.search(r"(\w+)\s+" + part, t)
            if m:
                for g in m.groups()[::-1]:
                    if g in COLORS:
                        who = _named_character(raw)
                        add("look", f"Personnage{(' ' + who) if who else ''} : {field} → {g}", field=field, value=COLORS[g], who=who)
                        break

    if keep:
        understood.append("Personnages conservés à l'identique")
    if only_bg:
        ops = [o for o in ops if o["op"] in ("set", "background_variant", "lighting", "time")]
        if not ops:
            ops.append({"op": "background_variant"})
            understood.insert(0, "Nouvel arrière-plan (même lieu, autre variante)")
        understood = [u for u in understood if not u.startswith(("Expressions", "Jeu", "Mouvements", "Caméra", "Cadrage", "Émotion", "Nouvelle réplique", "Scène plus"))]
    return {"ops": ops, "scene": parse_scene_ref(t), "only": "background" if only_bg else None,
            "keep_characters": keep, "understood": understood, "unknown": not ops}


def _named_character(raw: str):
    names = parse_names(raw)
    return names[0] if names else None
