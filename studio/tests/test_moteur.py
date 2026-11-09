"""Tests unitaires du moteur (interprétation, scénario, retouches, empreintes)."""
import json

from moteur import edits, intent, spec, story


def test_parse_request_exemples_utilisateur():
    r = intent.parse_request("Crée une animation 3D de deux personnages qui se disputent dans un restaurant.")
    assert (r["command"], r["genre"], r["set"], r["n_characters"], r["style"]) == ("create", "dispute", "restaurant", 2, "cartoon3d")
    r = intent.parse_request("Crée un épisode de 2 minutes avec les personnages de mon histoire précédente.")
    assert r["command"] == "new_episode" and r["duration"] == 120 and r["use_previous_characters"]
    assert intent.parse_request("Continue automatiquement l'histoire précédente.")["command"] == "continue"
    r = intent.parse_request("Crée une animation cinématographique avec une caméra dynamique.")
    assert r["camera_dynamic"] and r["style"] == "cinematique" and r["set"] is None
    r = intent.parse_request("Reprends la scène 4 et améliore les expressions faciales.")
    assert r["command"] == "edit_scene" and r["scene"] == 4
    r = intent.parse_request("Génère une histoire mystérieuse en 3D au format vertical 9:16.")
    assert r["format"] == "9:16" and r["genre"] == "mystere" and r["style"] == "mystere"


def test_durees_et_noms():
    assert intent.parse_duration(intent.fold("1 min 30")) == 90
    assert intent.parse_duration(intent.fold("45 secondes")) == 45
    assert intent.parse_duration(intent.fold("trois minutes")) == 180
    assert intent.parse_request("Léa et Hugo se disputent")["names"] == ["Léa", "Hugo"]


def test_parse_edit_exemples_utilisateur():
    ops = lambda t: [o["op"] for o in intent.parse_edit(t)["ops"]]  # noqa: E731
    assert ops("Le personnage doit être plus expressif.") == ["expressiveness"]
    assert intent.parse_edit("La caméra doit se déplacer vers la gauche.")["ops"][0]["move"] == "pan_left"
    assert ops("Ralentis le mouvement de cette scène.") == ["speed"]
    e = intent.parse_edit("Change uniquement l'arrière-plan.")
    assert e["only"] == "background" and ops("Change uniquement l'arrière-plan.") == ["background_variant"]
    assert intent.parse_edit("Conserve exactement le même personnage.")["keep_characters"]


def _spec(text="Léa et Hugo se disputent au restaurant, 40 secondes", seed=1):
    return story.write_screenplay(intent.parse_request(text) | {"quality": "brouillon"}, {}, {}, seed)[0]


def test_scenario_regles_valide_et_deterministe():
    a, b = _spec(), _spec()
    assert a == b
    assert len(a["scenes"]) >= 3 and all(sc["lines"] for sc in a["scenes"])
    assert {c["name"] for c in a["characters"]} == {"Léa", "Hugo"}
    assert spec.normalize_spec(a) == a  # normalisation idempotente (sinon le cache ne servirait jamais)


def test_spec_invalide_est_corrigee():
    s = spec.normalize_spec({"characters": [{"name": "X", "look": {"skin": "rouge"}}],
                             "scenes": [{"set": "lune-inconnue", "camera": {"move": "vol"}, "lines": [{"who": "zz", "text": "Salut"}]}]})
    sc = s["scenes"][0]
    assert sc["set"] in spec.SETS and sc["camera"]["move"] == "static" and sc["lines"][0]["who"] == "c1"
    assert s["characters"][0]["look"]["skin"].startswith("#")


def test_retouche_ne_touche_que_la_scene_visee():
    s = _spec()
    chars = {c["id"]: c for c in s["characters"]}
    before = [spec.visual_key(sc, s, chars, spec.audio_key(sc, chars, "t"), "r") for sc in s["scenes"]]
    new, info = edits.plan_edit(s, "La caméra doit se déplacer vers la gauche", 2, {})
    chars2 = {c["id"]: c for c in new["characters"]}
    after = [spec.visual_key(sc, new, chars2, spec.audio_key(sc, chars2, "t"), "r") for sc in new["scenes"]]
    changed = [i + 1 for i, (x, y) in enumerate(zip(before, after)) if x != y]
    assert changed == [2] and info["scenes"] == [2]
    # l'audio de la scène modifiée est conservé (seule la caméra change)
    assert spec.audio_key(s["scenes"][1], chars, "t") == spec.audio_key(new["scenes"][1], chars2, "t")


def test_arriere_plan_seul_conserve_personnages():
    s = _spec()
    new, _ = edits.plan_edit(s, "Change uniquement l'arrière-plan. Conserve exactement le même personnage.", 1, {})
    assert new["characters"] == s["characters"]
    assert new["scenes"][0]["variant"] != s["scenes"][0]["variant"]
    assert new["scenes"][0]["lines"] == s["scenes"][0]["lines"]


def test_changement_apparence_touche_toutes_les_scenes_du_personnage():
    s = _spec()
    new, info = edits.plan_edit(s, "Donne à Léa une veste rouge", 1, {})
    lea = next(c for c in new["characters"] if c["name"] == "Léa")
    assert lea["look"]["outfit"] == intent.COLORS["rouge"]
    assert any("toutes ses scènes" in n for n in info["notes"])


def test_regenerer_scene_change_prise_pas_personnages():
    s = _spec()
    new, info = edits.regenerate_scene(s, 1, False, 42)
    assert new["characters"] == s["characters"] and new["scenes"][0]["seed"] != s["scenes"][0]["seed"]
    assert new["scenes"][1:] == s["scenes"][1:]


def test_continuation_utilise_memoire():
    s = _spec()
    ctx = {"characters": s["characters"], "memory": {"ending": "Le secret est révélé."}, "story_title": "T", "episode_n": 2}
    s2, _ = story.write_screenplay({"command": "continue", "duration": 30}, ctx, {}, 3)
    assert [c["id"] for c in s2["characters"]][:2] == [c["id"] for c in s["characters"]][:2]
    assert s2["characters"][0]["look"] == s["characters"][0]["look"]
    assert "Le secret est révélé." in json.dumps(s2["scenes"][0]["lines"], ensure_ascii=False)


def test_llm_refuse_adresse_non_locale():
    from moteur import llm
    assert not llm._is_local("https://api.example.com/v1")
    assert llm._is_local("http://127.0.0.1:11434")
    out = llm.list_models({"llm_provider": "ollama", "llm_url": "https://api.example.com"})
    assert not out["ok"]
