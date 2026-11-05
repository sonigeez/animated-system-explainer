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
content. Read it before editing a page. `scripts/scaffold.py` turns a storyboard
into a new page built on the same engine, so you rarely edit the example itself.

## Workflow

### 1. Understand the design before drawing it

The animation is only as clear as your own model of the system. If the code
or docs for the system are in the workspace, read them first: take the actor
names, endpoints, message names and the order of calls from the code, not only
from the user's summary, and say where they disagree. If the flow is
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

Show the storyboard to the user as a short table before writing any page, and
let them correct it:

| video | step | caption (one line) | formula row | what moves |
|---|---|---|---|---|
| deliver | sign | Stripe signs the event body with the shared secret | event -> hmac -> signature | - |
| deliver | send | the event and its signature go to the gateway | event + signature | event, signature: Stripe -> gateway |

Then write the same storyboard as JSON for `scaffold.py`. The format is in
`assets/storyboard-example.json`: `actors` (2-4, left to right), `keys` (id,
name, owner actor, `secret`, `square`), `videos` with `steps` (`label`, `text`,
optional `formula`, optional `move: {key or keys, from, to}`), and an optional
`read` block.

### 2. Keep the watch view minimal

The audience is a team skimming a link. Show the high-level design only: short
captions, no bench history, no bug write-ups, no internal file paths or
command names unless the audience needs them. Put depth in the read tab.

### 3. Scaffold, then make it real

`<skill-dir>` is wherever this skill is installed (the folder holding this
file).

```bash
python3 <skill-dir>/scripts/scaffold.py storyboard.json topic.src.html
```

This writes a page that already works: the actors on the stage, the legend,
every video and step with paced times, placeholder motion (a step with `move`
sends its keys along the lanes, a formula-only step pops its keys in beside
their owner), and a read tab with a piece table and a sequence diagram. It
builds and passes `check.py` as it is. What it cannot know is marked `TODO`.

1. Replace the placeholder motion in `SCENES` with the real story: combines,
   flashes, notes, failures, holds (engine.md sections 4 and 5). Delete the
   `hop`/`pop` helpers when nothing uses them.
2. Draw the actors' real shapes, or put in a product photo with an
   `__IMG:<name>__` placeholder (engine.md section 8).
3. Fill the read tab: rewrite the sequence rows into the true call sequence,
   fill the piece table, add the comparisons and Q&A this audience needs.
4. Clear every `TODO`; `build.py` lists the ones left.
5. Pace generously: holds of 0.4-0.8 s at each stop, about 1.5 s or more per
   step. To slow one video, scale its clock (see engine.md section 5).

To start from the finished PKCE page instead (for example a similar auth
flow), copy `assets/example-pkce-login.src.html` and replace the content parts
listed in engine.md section 1.

### 4. Build, check, deliver

```bash
python3 <skill-dir>/scripts/build.py src.html out.html --img device=/path/to/photo.png
python3 <skill-dir>/scripts/check.py out.html --out shots/
```

`build.py` embeds images as small WebP data URIs, makes the page pure ASCII
(hosts that guess the wrong charset turn arrows and crosses into mojibake),
adds a charset meta and syntax-checks the scripts with node when available.

`check.py` serves the page on a local port and, with Playwright for Python
installed, renders the settled frame of every step and fails on:

- script or console errors, and sideways scrolling at phone width;
- labels that overlap each other or stick out of the stage or a read-tab
  diagram;
- objects that `reset()` does not put back: it plays every frame a second time
  in reverse order and names any object that looks different;
- formula items or `lit` entries that name a key not in `KEYS`, and step times
  out of order.

It warns, without failing, about captions that wrap at desktop width, steps
on screen under 1.2 s, and video, step and duration counts outside the ranges
above. It saves `contact-sheet.png` (every step in one image, one row per
video, problem frames outlined in red), one image per step and the read tab.
Fix every problem, then open the contact sheet and check that each frame says
what its caption says before delivering. Without Playwright it prints a local URL; use whatever
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
- "Add a step" or "reorder these": edit `VIDEOS` and the scene by hand;
  rerun `scaffold.py` only for a fresh start, as it overwrites your edits.
- "Weird symbols": rebuild with `build.py`; prefer `->`, `[x]`, `[ok]` in copy.
- "Make X clickable": the step diamonds already seek; follow that pattern.
- "Add how Y works": add one video and one read section with its own sequence
  diagram, using the same key glyphs.

When asked for "the HTML", send the built file, and save the storyboard, the
source and the build next to the project, for example
`docs/<topic>.storyboard.json`, `docs/<topic>.src.html` and `docs/<topic>.html`,
so later edits start from the source.

## Design defaults

- Pick a look specific to the subject. The example's terminal theme (hex rain,
  typewriter title, bracketed stage, monospace) suits security topics; it is
  not mandatory.
- Single theme is fine when chosen on purpose; set every colour explicitly.
- Respect reduced motion (the engine shows settled frames and stops the rain).
- Phone width: the stage SVG scales, the strip scrolls, step text wraps.
