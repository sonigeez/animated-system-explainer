---
name: animated-system-explainer
description: Build a shareable, single-file animated explainer of a system design, protocol or data flow, as one HTML page with several short "videos" (play/pause, step-by-step captions, clickable step markers, a video tab strip) plus a written "read" tab with static diagrams. Use this whenever someone wants to show their team how something works between parts of a system, such as a device, a mobile app and a backend, keys or tokens moving, an auth or sync flow, encryption, a data pipeline, an OTA or pairing sequence, even if they only say "make an artifact for the team", "make a page for the team", "animate this flow", "visualise how X works", "explainer page", or "turn this design into something shareable".
license: MIT
compatibility: Any agent that can read and write files and run Python 3. Optional - node (script check), cwebp (image shrinking), Playwright for Python (headless screenshots).
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
combine different keys and reach the same key). Let the user correct it. A
pretty animation of a fuzzy explanation reads as "still not understandable";
an explicit explanation followed by a visual language fixes it.

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

### 4. Build, check, deliver

`<skill-dir>` is wherever this skill is installed (the folder holding this
file).

```bash
python3 <skill-dir>/scripts/build.py src.html out.html --img device=/path/to/photo.png
python3 <skill-dir>/scripts/check.py out.html --out shots/
```

`build.py` embeds images as small WebP data URIs, makes the page pure ASCII
(hosts that guess the wrong charset turn arrows and crosses into mojibake),
adds a charset meta and syntax-checks the scripts with node when available.

`check.py` serves the page on a local port and, with Playwright for Python
installed, fails on script errors or sideways scrolling at phone width, and
saves a screenshot of the settled frame of every step plus the read tab. Look
at a few of the images (the combine and failure steps first) and fix overlaps
before delivering. Without Playwright it prints a local URL; use whatever
browser tool you have, or ask the user to open it. In any browser console,
`explainer.videos`, `explainer.seek(videoIndex, seconds)` and
`explainer.view('read')` drive the page. Browsers and many agent tools cannot
screenshot `file://` URLs, which is why it serves the folder.

Deliver the built file the way your environment allows:

- If you have a tool that publishes or hosts pages (an artifact or canvas
  tool, a docs connector), publish `out.html` there. Republish to the same
  target to keep the link. If a publish is refused because someone else
  changed it, compare their version with your last build and merge before
  publishing again.
- Otherwise hand over the file. It works opened from disk, attached to a
  message, or on any static host (GitHub Pages, Netlify, an S3 bucket).

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

When asked for "the HTML", send the built file, and save the source and the
build next to the project, for example `docs/<topic>.src.html` and
`docs/<topic>.html`, so later edits start from the source.

## Design defaults

- Pick a look specific to the subject. The example's terminal theme (hex rain,
  typewriter title, bracketed stage, monospace) suits security topics; it is
  not mandatory.
- Single theme is fine when chosen on purpose; set every colour explicitly.
- Respect reduced motion (the engine shows settled frames and stops the rain).
- Phone width: the stage SVG scales, the strip scrolls, step text wraps.
