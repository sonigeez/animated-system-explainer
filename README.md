# animated-system-explainer

A [Claude skill](https://docs.claude.com/en/docs/claude-code/skills) that turns a
system design into a shareable, single-file animated explainer: a few short
"videos" that show keys, codes, files and requests moving between the parts of a
system, plus a written "read" tab with diagrams.

Ask Claude something like *"make an artifact for the team that shows how our
OAuth login works"* or *"visualise our OTA update flow"*, and it will explain
the design back to you, storyboard it, and build the page.

## What the page looks like

Open [`examples/pkce-login.html`](examples/pkce-login.html) in a browser. It
explains an OAuth PKCE login in four videos (start, login, exchange, stolen
code) and a read tab.

- **Watch tab**: one stage with the actors, a legend of the keys (colour = who
  made it, solid ring = secret, dashed ring = may be seen), a one-line caption
  and a formula row per step, clickable step markers, play/pause, previous/next,
  repeat, a tab strip of videos, keyboard shortcuts.
- **Read tab** (`#read` deep link): the same story written down, with a key
  table, a sequence diagram, side-by-side comparisons, request formats and Q&A.
- One self-contained HTML file. Works as a Claude artifact, on any static host,
  or from disk. Respects reduced motion.

## Install

**Claude Code**

```bash
git clone https://github.com/sonigeez/animated-system-explainer ~/.claude/skills/animated-system-explainer
```

**Claude.ai / desktop app**: download `animated-system-explainer.skill` from the
[latest release](https://github.com/sonigeez/animated-system-explainer/releases/latest)
and upload it in Claude's skill settings.

## How it works

| Path | What it is |
|---|---|
| `SKILL.md` | The workflow Claude follows: understand the design first, keep the watch view minimal, build from the example, check one frame, publish, iterate. |
| `references/engine.md` | Which parts of the example are reusable engine and which are content; data formats, animation helpers, pitfalls. |
| `assets/example-pkce-login.src.html` | Editable source of the example. Every frame is a pure function of time, so seeking and step markers always land on the right frame. |
| `scripts/build.py` | Turns a source page into the publishable file: embeds images as small WebP data URIs, makes the page pure ASCII (no mojibake when a host guesses the wrong charset), syntax-checks the scripts. |
| `examples/pkce-login.html` | The built example. |
| `evals/evals.json` | Test prompts for evaluating the skill. |

Build a page by hand:

```bash
python3 scripts/build.py my-explainer.src.html my-explainer.html --img device=photo.png
```

`cwebp` (image shrinking) and `node` (script check) are used when installed.

## License

[MIT](LICENSE)
