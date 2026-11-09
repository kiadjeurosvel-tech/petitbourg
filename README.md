# Petitbourg — production automatique

Série TikTok @petitbourg.village : 1 abonné = 1 habitant, le top commentaire décide.

## Fonctionnement
1. Claude lit les commentaires TikTok (PC connecté), écrit `episodes/jour_N.json` et le pousse.
2. GitHub Actions (`.github/workflows/episode.yml`) : contrôle de date → voix « Liam » (API ElevenLabs, secret `ELEVENLABS_API_KEY`) → rendu (`engine/render.py`) → MP4 + description dans **Releases**.
3. `state.json` garde le dernier jour publié.

## Règle absolue
Un épisode par jour, **jamais avant le lendemain** (fuseau Europe/Berlin). `scripts/gate.py` refuse sinon.

## Format d'un épisode
Voir `docs/example_jour2.json`. Types de scènes : `title`, `place`, `panel`, `cards`, `vote`.
Bâtiments (`build.type`) : `chapel`, `house`, `shop` (avec `label`), `lot` (`l1`/`l2`).
Avatars : `assets/avatars/<pseudo>.png` (uniquement si ce n'est pas un vrai visage), sinon initiale.

## Test local sans voix
`python3 engine/render.py docs/example_jour2.json out --dry --preview 1,10,20`

## Studio d’animation (application web)
Voir [studio/README.md](studio/README.md) : interface web + moteur local (Blender, FFmpeg, voix open source), indépendant de Claude.
