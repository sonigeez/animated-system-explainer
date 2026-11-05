# Engine reference: `assets/example-pkce-login.src.html`

The example is a complete, working explainer of an OAuth PKCE login (mobile
app, browser, auth server; four videos plus a read tab). `scripts/scaffold.py`
starts new pages from it: it keeps the **engine** and generates the
**content** from a storyboard (section 10). To start from the example by hand,
copy it and replace the content. Line numbers are approximate.

## Contents
1. File map: engine vs content
2. The timeline model (how a video renders)
3. Data formats: VIDEOS, steps, formula items, KEYS
4. Helpers
5. Adding or changing a video
6. Read view pieces
7. Player behaviour you get for free
8. Theming and images
9. Pitfalls already hit
10. What scaffold.py generates

## 1. File map

| Lines | Part | Keep or replace |
|---|---|---|
| 1-8 | `<title>`, viewport meta, Google Fonts link, layout comment | replace title and comment |
| 9-33 | `:root` tokens, body, hex-rain canvas, scanline overlay | keep; retheme via tokens (section 8) |
| 34-146 | read-view CSS, header, legend, stage, transport, strip CSS | keep |
| 151-163 | header: shell prompt, watch/read switch, typed title, lede | edit the prompt text and video count |
| 166-221 | **stage SVG**: lanes, actors, moving objects, notes, `#tokens` layer | **replace** actors and objects |
| 224-237 | transport (formula row, step pill, bar, controls) and video strip | keep |
| 240-304 | **read view article** | **replace** text; keep the component classes |
| 310-326 | **`KEYS`** legend, `glyph()`, `svgGlyph()` | **replace** the KEYS entries |
| 327-359 | **`VIDEOS`** | **replace** |
| 360-380 | helpers (`seg`, `ease`, `spring`, `kf`, ...) | keep |
| 381-408 | element lookup `E`, tokens `K`, `HOME`, `place`, `note`, `flash`, `lanes`, `reset()` | edit `E` ids, `K`, `HOME`, `lanes`, `reset()` |
| 409-465 | **`SCENES`**, one function per video | **replace** |
| 466-496 | hex rain | keep (or delete with the canvas for a calm theme) |
| 497-610 | player: tabs, steps, formula row, typewriter, timing, keyboard | keep |
| 611-642 | read-view builders: glyph fill and `seq()` sequence diagram | **replace** the rows inside `seq()` |
| 643-668 | watch/read switch (edit its title and lede strings), `#read` hash, boot | keep |

## 2. The timeline model

Every frame calls `reset(t)` and then `SCENES[vid](t)`. `t` is seconds into the
current video. All motion is a pure function of `t`:

- No CSS transitions or accumulated state drive the stage, so seeking,
  clickable step markers, reduced-motion still frames and `window.seek(i, t)`
  all show exactly the right frame.
- `reset()` puts every object in its default state (hidden, home position).
  A scene only states what differs. Forgetting to reset a new object makes it
  leak into other videos.
- Reduced motion: `shown()` renders the settled end frame of the current step
  instead of `t`.

## 3. Data formats

```js
{ tab: 'exchange',                                  // label under the strip icon, short
  title: 'The app proves it started the login',     // typed into <h1>
  lede: 'One or two sentences of context.',
  lit: ['ver', 'chal', 'code', 'tok'],              // legend entries to light up
  D: 9.2,                                           // duration in seconds
  steps: [[0,   'send',  'the app sends the code and the verifier, directly', ['code', '+', 'ver']],
          [2.6, 'check', 'server: sha256(verifier) = stored challenge?', ['ver', '->', 't:sha256', '=', 'chal']],
          [4.6, 'token', 'match: the server issues an access token', ['tok']]],
  icon: '<path d="M3 7h12M12 4l3 3-3 3"/>' }       // 20x20 stroke icon for the strip
```

- A step is `[start seconds, pill label, one-line text, formula items or null]`.
  Step starts also place the clickable diamonds on the progress bar.
- Formula items: a `KEYS` id renders its glyph; `'+'`, `'='`, `'->'` render as
  operators; `'t:text'` is plain text; `'x:text'` is red (rejected, erased).
- `KEYS`: `{ id: { c: 'var(--token)', priv: true|false, name: 'legend label', square?: true } }`.
  Solid ring = secret, dashed ring = may be seen, square = issued or derived
  item. Colour = who made it. Keep this language identical in the legend, the
  stage, the formula row and the read view.

## 4. Helpers

| Helper | Use |
|---|---|
| `seg(t, a, b)` | 0..1 progress of t between a and b, clamped |
| `ease(x)`, `spring(x)`, `bump(t, a, b)` | cubic ease-out, damped overshoot (pops), 0-1-0 pulse |
| `kf(t, [[t0,x0,y0],[t1,x1,y1],...])` | eased path; repeat a point to hold, e.g. pause at a middle actor |
| `place(el, [x,y], scale, opacity)` | move a token or group (always use this for tokens) |
| `at(el, x, y, s)`, `op(el, v)`, `scaleAround(el, cx, cy, s)` | raw transform and opacity, for static SVG parts |
| `note(el, text, x, y, opacity, color)` | the two floating captions `E.note1` / `E.note2` |
| `flash(t, t0, x, y, color)` | burst at a point: a combine, a match (green), a rejection (red) |
| `token(kind)` | create a glyph group in the `#tokens` layer (always on top) |
| `lanes(a, b, c)` | light the lanes that something is travelling on |

Two caption slots are usually enough: switch the text by time range
(`if (t > 4.6) note(...)`), as in the `exchange` and `stolen` scenes.

## 5. Adding or changing a video

1. Add any new static object to the stage SVG with `opacity="0"` and an id; add
   the id to the `E` list; hide it in `reset()`. New moving keys go in `K`.
2. Add the entry to `VIDEOS` and the scene function to `SCENES` at the same
   index. The `--video 01/NN` count in the header updates itself.
3. Lay the scene out as overlapping time windows: appear, move, hold, combine,
   leave. Fade with `seg(t, a, a+0.15)`, pop with `spring(seg(t, a, a+0.6))`.
4. To slow one video down without retiming every number, wrap its clock:
   `function login(T) { const t = T / 1.5; ... }` and multiply its `D` and step
   starts by the same factor.
5. Stage coordinates: viewBox 800 x 330, actors on x = 120 / 400 / 680, the
   front-channel lane on y = 244, an optional back channel on y = 292,
   captions on y = 322 (bottom) or y = 30 (top). Keep labels inside the viewBox
   and away from actor labels.

## 6. Read view pieces

- `<span data-g="kind"></span>` anywhere in the article becomes the key glyph.
- `seq()` builds a sequence diagram: actor columns with dashed lifelines,
  numbered rows, `arrow(x0, x1, y, dashed)`, glyphs `G(kind, x, y)`, operators
  `O('+', x, y)`, text `T(text, x, y, anchor)`. Copy it as `seq2()` for a second
  diagram. Write `->` in SVG text as `-&gt;`.
- Components: `.tw > table` (scrolls on phones), `.combos > .combo` (two cards
  side by side), `.bytes` + `.bcap` (a layout bar for formats and headers),
  `dl.qa` (questions), `p.big` (opening line), `td.yes` / `td.no`.
- Section headings render as `## name` in the accent colour.

## 7. Player behaviour you get for free

Autoplay through all videos and stop at the end; play/pause; previous/next;
repeat-this-video toggle; clickable step diamonds; tab strip; Space and arrow
keys (ignored on the read tab); typewriter title; `#read` / `#watch` deep
links; reduced-motion still frames; hex rain paused under reduced motion.

`window.explainer` is the control API that `scripts/check.py` and any browser
tool can use: `videos` (tabs, titles, durations, `lit`, and steps with start,
label, text and formula), `keys` (the `KEYS` ids), `pause()`,
`seek(videoIndex, seconds)` (pauses, switches to the watch tab, renders that
frame) and `view('watch' | 'read')`. Keep it when you edit the engine:
`check.py` needs `keys`, `lit` and `formula` for its key checks.

## 8. Theming and images

All colours are tokens on `:root`. The example is single-theme dark on purpose
(terminal look, `color-scheme: dark`). For another look, change the tokens and
fonts, and drop the rain canvas plus `body::after` for a calm page. Keep one
accent for "ok", one colour per party that creates keys or items, and a red for
failures.

For a real product, put its photo on the stage instead of a drawn shape:
`<image href="__IMG:device__" x="78" y="48" width="84" height="125"/>`, then
build with `--img device=photo.png`. Many hosts (chat artifacts, sandboxed
previews) block external images, so embed them.

## 9. Pitfalls already hit

- **Mojibake.** Arrows and crosses showed as "a-hat" garbage on a published
  page. Build with `scripts/build.py`, which makes the output pure ASCII.
  Prefer ASCII glyphs in copy anyway: `->`, `[x]`, `[ok]`.
- **Overlapping labels.** Captions near an actor collide with its labels; put
  them at the top (y = 30) or bottom (y = 322) bands.
- **Too fast.** First drafts run too quickly to follow. Hold 0.4-0.8 s at every
  stop and give each step at least about 1.5 s.
- **Previewing.** Many browser tools cannot screenshot `file://`. Use
  `scripts/check.py`, which serves the folder and drives `window.explainer`.
- **Leaks between videos.** An object a scene shows but `reset()` does not hide
  appears in every video that plays after it. `check.py` replays all frames in
  reverse order and names the object.
- **Typos in formula rows.** An unknown key id in a formula renders as a
  truncated word (`'cod'` shows as `d`). `check.py` fails on it.

`check.py` catches overlaps, clipping, leaks and key typos automatically; it
cannot tell whether a frame shows what its caption says. Look at
`contact-sheet.png` for that.

## 10. What scaffold.py generates

`scaffold.py storyboard.json out.src.html` keeps everything marked "keep" in
section 1 and generates the rest:

- **Stage.** Actors at x = 200/600 (2 actors), 120/400/680 (3) or
  100/300/500/700 (4), each a 96 x 104 box (y = 62-166) with its label on
  y = 204 and an optional `sub` text inside. Lanes `lane1..` join neighbours on
  y = 244, with optional labels on y = 236.
- **Keys.** `KEYS` colours follow the owner actor: `--otk`, `--key`, `--seal`,
  then `--p4` (added to `:root`). `HOME[k]` puts each key beside its owner
  (x + 62, stacked from y = 60); `OWNER[k]` is the owner's index.
- **Timing.** A step lasts 2 s; a `move` step lasts longer when it crosses
  several lanes. `D` is the sum plus 0.2 s.
- **Placeholder motion.** `hop(t, key, from, to, start, dx, shown)` sends a key
  down to the lane, along it and up into the target actor;
  `pop(t, key, start)` springs a key in at its home; `crossing(...)` lights the
  lanes it travels on. Each scene calls them under `if (t >= start)` guards, in
  step order, so a later step takes over a key from an earlier one. Replace
  them with real motion.
- **`lanes(...)`** takes one boolean per lane, in order.
- **Read tab.** A piece table from `KEYS`, the steps as a list, a Q&A slot, and
  a data-driven `seq()`: rows are `{ move: [key, from, to], text }`,
  `{ at: actor, keys: [...], text }` or `{ text }`. Same helpers as the
  example's hand-written `seq()`; rewrite the rows into the real sequence.
- **TODO markers** wherever a decision is left. `build.py` lists the remaining
  ones.
