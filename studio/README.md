# Mon Studio — studio d'animation IA indépendant

Application web (ordinateur + téléphone) pour décrire une vidéo, la produire en 3D, suivre la
production en temps réel, la retoucher scène par scène et la télécharger.

**L'utilisation quotidienne ne dépend ni de Claude, ni de Claude Code, ni d'aucune API payante.**
Tout tourne sur votre ordinateur : Python, Blender, FFmpeg, voix open source, modèle de langage local (facultatif).

## Utilisation quotidienne

1. Ouvrez le studio (`http://127.0.0.1:8765` sur le PC, ou votre adresse Tailscale sur le téléphone).
2. Décrivez la vidéo dans le **Centre de commande**. Le panneau « Ce que le moteur a compris » montre l'interprétation *avant* de lancer.
3. Choisissez style, durée, format (9:16 / 16:9 / 1:1) et qualité, puis **Générer**.
4. **Production** : chaque étape avec sa progression réelle (images écrites sur le disque, temps encodé par FFmpeg), erreurs et temps restant mesuré.
5. **Bibliothèque → épisode** : lecture, téléchargement MP4, sous-titres .srt, exports, versions.
6. **Modifier** : « La caméra doit se déplacer vers la gauche », « Ralentis le mouvement », « Change uniquement l'arrière-plan »…
   Le studio affiche quelles scènes seront régénérées et lesquelles seront réutilisées, puis ne recalcule que celles-là.

Commandes : Créer une vidéo · Continuer une histoire · Modifier une scène · Régénérer une scène · Générer un nouvel épisode · Enregistrer le projet.

## Installation (une fois)

| | Linux / macOS | Windows |
|---|---|---|
| Prérequis | Python 3.10+, FFmpeg, Blender 3.6+ (4.x recommandé), espeak-ng | idem (`winget install Gyan.FFmpeg BlenderFoundation.Blender`) |
| Installer | `bash scripts/installer.sh` | `powershell -ExecutionPolicy Bypass -File scripts\installer.ps1` |
| Voix naturelles | `python scripts/telecharger_voix.py` | idem |
| Démarrer | `bash scripts/demarrer.sh` | `scripts\demarrer.bat` |
| Vérifier | `python -m serveur diagnostic` | idem |

Au premier démarrage, un mot de passe est généré et affiché (aussi dans `donnees/MOT_DE_PASSE_INITIAL.txt`).
Changez-le dans **Réglages** ou avec `python -m serveur mot-de-passe`.

Modèle de langage local (facultatif, scénarios plus riches) : installez [Ollama](https://ollama.com), puis
`ollama pull qwen2.5:7b-instruct` et choisissez « Ollama » dans Réglages. Modèles interchangeables
(llama3.1:8b, mistral-nemo, gemma2:9b…) ou tout serveur local compatible OpenAI (llama.cpp, LM Studio).
Sans modèle, le générateur intégré (règles) prend le relais automatiquement.

## Architecture

```
Navigateur (PC / téléphone)            Votre ordinateur
┌─────────────────────┐  HTTPS   ┌───────────────────────────────────────────────┐
│ web/  (HTML/CSS/JS) │ ───────▶ │ serveur/  API FastAPI + auth + file de tâches │
│ aucun secret        │  jeton   │   └─ SQLite (projets, histoires, versions…)   │
└─────────────────────┘          │ moteur/                                       │
                                 │   intent.py   interprétation FR (règles)      │
                                 │   llm.py      modèle local (Ollama…)          │
                                 │   story.py    scénario                        │
                                 │   edits.py    retouches ciblées               │
                                 │   audio.py    voix Piper / espeak-ng          │
                                 │   perf.py     mise en scène image par image   │
                                 │   blender_scene.py  rendu 3D (Blender)        │
                                 │   render_2d.py      aperçu sans Blender       │
                                 │   montage.py  FFmpeg, contrôle qualité        │
                                 │   pipeline.py orchestration + cache           │
                                 └───────────────────────────────────────────────┘
```

Étapes : attente → scénario → personnages → scènes → **audio → animation** → montage → contrôle qualité → rendu final.
L'audio passe avant l'animation : la durée des répliques fixe le timing et la synchronisation labiale.

**Régénération partielle** : chaque scène a deux empreintes (audio, image). Une retouche ne change que les champs
concernés ; les scènes dont l'empreinte est inchangée sont reprises du cache (`donnees/cache`). Changer la caméra de la
scène 2 = re-rendu de la scène 2 seulement, voix réutilisée. Changer la tenue d'un personnage = re-rendu de toutes ses scènes.

**Données** (`studio/donnees/`, à sauvegarder) : base `studio.sqlite3`, `histoires/<id>/` (mémoire + références visuelles
des personnages), `episodes/<id>/v<n>/` (vidéo, sous-titres, scénario `spec.json`, contrôle qualité), `cache/visual/*/scene.blend`
(fichiers sources Blender par scène), `voix/`, `musique/` (déposez-y des musiques libres de droits ; `dispute.mp3`, `mystere.mp3`… sont choisies selon le genre).

## Accès à distance, sécurité, ordinateur éteint

Voir [docs/ACCES_DISTANT.md](docs/ACCES_DISTANT.md).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -q tests                      # rendu 2D, rapide
STUDIO_TEST_BLENDER=1 STUDIO_TEST_TTS=espeak-ng python -m pytest -q tests/test_api.py -k production   # avec Blender
```
Les mêmes tests tournent dans GitHub Actions (`.github/workflows/studio-tests.yml`).

## Limites actuelles (honnêtes)

- Les personnages et décors 3D sont **procéduraux et stylisés** (primitives Blender) : cohérents et animés (gestes, regards,
  expressions, synchro labiale, caméra), mais pas du niveau d'un studio Pixar. Les modèles IA vidéo open source
  (type génération vidéo par diffusion) demandent un GPU puissant (≥ 16–24 Go de VRAM) et ne garantissent pas la cohérence
  des personnages ; ils ne sont pas intégrés dans cette version.
- Sans modèle de langage local, les dialogues viennent d'un répertoire de scènes par genre : corrects mais répétitifs sur les longues durées.
- La qualité des voix dépend du moteur : Piper (naturel) ≫ espeak-ng (robotique).
