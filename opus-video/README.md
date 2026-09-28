# OPUS 5.5 — film procédural

35 secondes, 1920×1080, 60 fps. Tout est généré par du code : aucune image, aucune vidéo,
aucun son ni aucune musique d'origine externe. Seules les polices sont externes (Inter Tight
et JetBrains Mono, licence OFL, dans `fonts/`).

**Résultat : [`opus-5.5.mp4`](opus-5.5.mp4)**

## Le film

| Temps | Scène | Ce qu'on voit | Ce qu'on entend |
|---|---|---|---|
| 0:00 | Prompt | Un curseur tape `> build me something impossible.`, les lettres s'enroulent et sont aspirées vers le centre | Frappes de clavier, aspiration |
| 0:02.4 | Big bang | Flash, anneaux de choc, 1 500 particules projetées, flou radial | Impact grave, souffle, débris |
| 0:03.6 | Rafale | 16 mots en 4,8 s (THINK / DEEPER / READ …), un style de typographie cinétique différent par mot | Un impact par mot |
| 0:08.4 | L'esprit | Réseau 3D de 880 nœuds et impulsions lumineuses, « SEE THE WHOLE SYSTEM. », plongée dans le réseau | Nappe, pings, whoosh |
| 0:13.2 | Le build | Éditeurs de code en parallaxe qui s'écrivent seuls, terminal avec 1 284 tests qui passent, tampon SHIPPED | Clics, bips de données, riser, impact métallique |
| 0:18.6 | La forme | 4 200 particules : sphère → cube → nœud torique → « 5.5 » | Swells inversés, morphs, scintillement |
| 0:23.4 | Warp | Hyperespace, portails qui accélèrent, implosion puis un seul point de lumière dans le silence | Grondement, riser, passages de portails, inspiration |
| 0:28.2 | Révélation | Explosion, rayons, titre **OPUS 5.5**, reflet lumineux, `> ready when you are.` | BOOM, traîne, frappes |

## Comment c'est fait

- `timeline.mjs` est la **source unique de vérité** : chaque moment de l'image et chaque son
  en découle (`src/timeline.json`). L'image et le son ne peuvent donc pas se désynchroniser.
- `src/engine.js` est un moteur de rendu déterministe : `renderFrame(t)` est une fonction pure
  du temps (hasard seedé). Les scènes sont dessinées en Canvas 2D, puis passent par un shader
  WebGL2 de post-traitement : aberration chromatique, flou radial, bloom par mipmaps,
  glitch par blocs, inversion, flash, distorsion en barillet, vignettage et grain.
- `render.mjs` pilote Chromium en headless (Playwright) sur plusieurs workers et capture chaque image.
- `audio.py` synthétise tout le sound design avec numpy/scipy (oscillateurs, bruit filtré
  en balayage via STFT, reverb à réponse impulsionnelle synthétique), en 48 kHz / 24 bits.
- `build.sh` enchaîne tout et encode en H.264 (High, BT.709, yuv420p) avec de l'AAC à 320 kb/s.

## Reconstruire

```bash
./build.sh                          # tout reconstruire
node render.mjs --stills 3.7,28.6   # extraire quelques images pour vérifier
# aperçu en temps réel : servir le dossier et ouvrir /src/index.html?play
```
