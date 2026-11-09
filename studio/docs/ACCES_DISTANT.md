# Accès à distance, sécurité et fonctionnement ordinateur éteint

## 1. Principe

Le **calcul** (Blender, FFmpeg, voix, modèle de langage) tourne sur **votre ordinateur**. GitHub Pages n'est
qu'un hébergeur de fichiers statiques : il ne peut rien calculer. L'interface, elle, peut être ouverte :

| Option | Adresse | Quand l'utiliser |
|---|---|---|
| A. Sur le PC | `http://127.0.0.1:8765` | toujours disponible |
| B. Réseau local | `python -m serveur --hote 0.0.0.0` puis `http://IP-du-PC:8765` | téléphone sur le même Wi-Fi (non chiffré : à éviter hors de chez vous) |
| C. **Tailscale (recommandé)** | `https://mon-pc.<tailnet>.ts.net` | partout, gratuit, privé, HTTPS automatique |
| D. Cloudflare Tunnel | `https://studio.mondomaine.fr` | adresse publique stable (nécessite un nom de domaine) |
| E. GitHub Pages | `https://kiadjeurosvel-tech.github.io/petitbourg/` | même interface ; se connecte à l'adresse C ou D |

### C. Tailscale (recommandé)
1. Installez Tailscale sur le PC et sur le téléphone (même compte). C'est un réseau privé chiffré : le studio n'est **pas** exposé sur Internet.
2. Sur le PC : `tailscale serve --bg 8765` → Tailscale fournit `https://<nom-du-pc>.<tailnet>.ts.net` avec un certificat HTTPS.
3. Sur le téléphone : ouvrez cette adresse, connectez-vous, puis « Ajouter à l'écran d'accueil » (l'interface s'installe comme une application).

### D. Cloudflare Tunnel
`cloudflared tunnel --url http://127.0.0.1:8765` donne une adresse temporaire (`*.trycloudflare.com`) qui **change à chaque lancement**.
Pour une adresse stable : tunnel nommé + domaine géré par Cloudflare (≈ 10 €/an pour le domaine). Le studio est alors
accessible publiquement : seul le mot de passe le protège — choisissez-en un long (≥ 16 caractères).

### E. GitHub Pages — à lire avant
- Le dépôt `petitbourg` est **privé**. GitHub Pages sur un dépôt privé nécessite un abonnement payant (GitHub Pro).
  Rendre le dépôt public exposerait aussi tout le reste du projet. **Recommandation : utilisez directement l'adresse
  Tailscale (option C)** — c'est la même interface, servie par le moteur, sans configuration supplémentaire.
- Si vous activez Pages (Settings → Pages → Source : GitHub Actions), le workflow `studio-pages.yml` publie `studio/web`.
  Au premier lancement, l'interface demande l'adresse du moteur (https obligatoire). L'origine
  `https://kiadjeurosvel-tech.github.io` est autorisée par défaut (Réglages → Origines autorisées).

## 2. Sécurité

- **Aucun secret dans le navigateur ni dans le dépôt.** Pas de token GitHub, pas de clé d'API. Le navigateur ne garde
  qu'un jeton de session signé (30 jours) ; changer le mot de passe déconnecte tous les appareils.
- Mot de passe stocké haché (PBKDF2-SHA256, 240 000 itérations) dans `donnees/config.json` (non versionné).
- Limitation : 5 essais de connexion par minute et par adresse.
- Les vidéos sont servies par des liens signés valables 12 h (nécessaires pour la lecture sur mobile).
- CORS restreint aux origines autorisées ; en-têtes anti-iframe et anti-sniffing ; CSP sur l'interface.
- Le serveur écoute par défaut uniquement sur `127.0.0.1`. L'exposition passe par Tailscale/Cloudflare (HTTPS).
- Le modèle de langage n'accepte que des adresses locales ou du réseau privé : impossible d'envoyer vos demandes à une API en ligne par erreur.

## 3. Quand l'ordinateur est éteint

Rien ne peut tourner sur un ordinateur éteint. Trois solutions :

1. **Mode cloud GitHub Actions (inclus, gratuit dans les limites)**
   - Application GitHub mobile → dépôt → Actions → « Studio — production cloud » → *Run workflow* → texte, durée, format.
   - Ou : ouvrir une issue dont le titre commence par `[studio]` (le texte de l'issue = la demande). Seules vos issues
     (propriétaire du dépôt) déclenchent une production.
   - La vidéo arrive dans **Releases** (lien posté en commentaire de l'issue).
   - Limites : CPU uniquement (une vidéo de 30 s en qualité standard ≈ 10–25 min), pas de modèle de langage, pas de
     mémoire des histoires du PC (production autonome), 2 000 minutes/mois sur un dépôt privé gratuit, 6 h max par tâche.
   - Aucun token n'est nécessaire : le workflow utilise le jeton temporaire fourni par GitHub.
2. **Mise en veille au lieu d'extinction + réveil réseau** (Wake-on-LAN via un routeur/Raspberry Pi) : simple et gratuit,
   mais dépend du matériel.
3. **Machine toujours allumée** : mini-PC, ou serveur loué. Exemple gratuit : Oracle Cloud « Always Free » (4 cœurs ARM,
   24 Go RAM, Blender ARM disponible) — rendu CPU lent mais fonctionnel. Une machine avec GPU (location à l'heure) accélère
   fortement le rendu, mais devient payante.

## 4. Sauvegarde

Le dossier `studio/donnees/` contient tout (base, mémoires, vidéos, sources). Copiez-le régulièrement (disque externe,
NAS). Par projet : Bibliothèque → Projets → « Sauvegarde » (archive .zip avec scénarios, mémoire, références et, au choix, les vidéos).
