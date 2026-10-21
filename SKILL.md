---
name: animated-system-explainer
description: Build a shareable, single-file animated explainer of a system design, protocol or data flow, as an HTML artifact with several short "videos" (play/pause, step-by-step captions, clickable step markers, a video tab strip) plus a written "read" tab with static diagrams. Use this whenever someone wants to show their team how something works between parts of a system, such as a device, a mobile app and a backend, keys or tokens moving, an auth or sync flow, encryption, a data pipeline, an OTA or pairing sequence, even if they only say "make an artifact for the team", "animate this flow", "visualise how X works", "explainer page", or "turn this design into something shareable".
---

# Animated system explainer

Produces one self-contained HTML page that teaches a system design in two ways:

- **watch**: 4-7 short videos (6-12 s each). One stage shows the actors (for
  example a mobile app, a browser and an auth server), and objects such as
  keys, codes, files and requests move between them. Each video has 2-5 steps
  with a one-line caption and an optional formula row (for example
  `sha256(verifier) = stored challenge`).
- **read**: the same story written down, with a key table, sequence diagrams,
  side-by-side comparisons, a byte/layout bar, a "who can read what" table and
  short Q&A.

The working reference is `assets/example-pkce-login.src.html` (an OAuth PKCE login).
`references/engine.md` maps which parts of it are reusable engine and which are
content. Read it before editing the example.

## Workflow

### 1. Understand the design before drawing it

The animation is only as clear as your own model of the system. If the flow is
not already settled in the conversation, explain it in chat first in plain
words: who holds what, what moves where, and the one or two "aha" moments (for
example: two parties compute the same hash at different times, or two sides
combine different keys and reach the same key). Let the
user correct it. A pretty animation of a fuzzy explanation got the response
"still not very understandable"; an explicit explanation followed by a visual
language fixed it.

Settle these before writing code:

- **Actors**: 2-4 columns on one stage (left to right in the order data flows).
- **Moving things**: what travels (keys, a file, a request, a token).
- **Visual language**: colour = owner, solid ring = secret, dashed ring =
  public, square = derived/session item. Show it in a legend that lights up
  per video.
- **Storyboard**: one video per phase (set up, create, transfer, open, failure
  or attack, consume). For each, list the steps and the formula row.

### 2. Keep the watch view minimal

The audience is a team skimming a link. Show the high-level design only: short
captions, no bench history, no bug write-ups, no internal file paths or
command names unless the audience needs them. Put depth in the read tab.

### 3. Build from the example

1. Copy `assets/example-pkce-login.src.html` to the working directory.
2. Replace the content parts listed in `references/engine.md` (title, stage
   SVG, `KEYS`, `VIDEOS`, `SCENES`, `reset()`, read article, `seq()` rows).
   Keep the engine: player, timeline model, rain, view switch.
3. For a real product, use its photo on the stage with an `__IMG:<name>__`
   placeholder (`<image href="__IMG:device__" .../>`, see engine.md section 8).
4. Pace generously: holds of 0.4-0.8 s at each stop, about 1.5 s or more per
   step. To slow one video, scale its clock (see engine.md section 5).

### 4. Build, check once, publish

```bash
python3 <skill-dir>/scripts/build.py src.html out.html --img device=/path/to/photo.png
```

The build embeds images as small WebP data URIs, makes the page pure ASCII
(published pages have shown arrows and crosses as mojibake), adds a charset
meta and syntax-checks the scripts with node.

Then take one look: serve the folder (`python3 -m http.server 8765 --bind 127.0.0.1`),
open it in the browser pane, and call `window.seek(videoIndex, seconds)` to
inspect a frame mid-animation. The pane cannot screenshot `file://` URLs. Stop
the server afterwards.

Publish `out.html` with the Artifact tool (run its quickstart once for a new
artifact). Republish the same file path to keep the URL. If a publish is
refused because a newer version exists, compare it with your previous build;
if it only differs by the platform's page wrapper or by lines you replaced,
publish your file again.

### 5. Iterate on feedback

Typical requests and what to do:

- "Too much text": cut captions to one line, move detail to the read tab.
- "Looks copied from my reference": keep the reference's structure (multiple
  videos, steps, controls) but give it its own palette, type and details.
- "Not understandable": go back to step 1, explain in chat, then add the
  missing moments as explicit steps with formula rows.
- "Moves too fast": scale that video's clock.
- "Weird symbols": rebuild with `build.py`; prefer `->`, `[x]`, `[ok]` in copy.
- "Make X clickable": the step diamonds already seek; follow that pattern.
- "Add how Y works": add one video and one read section with its own sequence
  diagram, using the same key glyphs.

When asked for "the HTML", send the built file (and save a copy next to the
project, for example `docs/<topic>.html`).

## Design defaults

- Pick a look specific to the subject. The example's terminal theme (hex rain,
  typewriter title, bracketed stage, monospace) suits security topics; it is
  not mandatory.
- Single theme is fine when chosen on purpose; set every colour explicitly.
- Respect reduced motion (the engine shows settled frames and stops the rain).
- Phone width: the stage SVG scales, the strip scrolls, step text wraps.
