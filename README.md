# animated-system-explainer

[![skills.sh](https://skills.sh/b/sonigeez/animated-system-explainer)](https://skills.sh/sonigeez/animated-system-explainer)

An [Agent Skill](https://agentskills.io) that turns a system design into a
shareable, single-file animated explainer: a few short "videos" that show keys,
codes, files and requests moving between the parts of a system, plus a written
"read" tab with diagrams.

It works with any agent that supports the `SKILL.md` format, such as Claude Code,
Codex, Cursor, GitHub Copilot, Gemini CLI, Windsurf, OpenCode and Amp. It also
works with agents that don't: point them at `SKILL.md`.

Ask your agent something like *"make a page for the team that shows how our
OAuth login works"* or *"visualise our OTA update flow"*. It explains the design
back to you, storyboards it, builds the page and screenshots every step to
check it.

## What the page looks like

Open [`examples/pkce-login.html`](examples/pkce-login.html) in a browser. It
explains an OAuth PKCE login in four videos (start, login, exchange, stolen
code) and a read tab.

- **Watch tab**:
  - One stage with the actors.
  - A legend of the keys: colour shows who made it, a solid ring is secret, a
    dashed ring may be seen.
  - A one-line caption and a formula row per step.
  - Clickable step markers, play/pause, previous/next, repeat, a tab strip of
    videos, and keyboard shortcuts.
- **Read tab** (`#read` deep link): the same story written down, with a key
  table, a sequence diagram, side-by-side comparisons, request formats and Q&A.
- **One self-contained HTML file.** Open it from disk, put it on any static
  host, or publish it wherever your agent publishes pages. It respects reduced
  motion.

## Install

**Any agent, with [skills.sh](https://skills.sh)**

```bash
npx skills add sonigeez/animated-system-explainer
```

That installs into the current project. Add `-g` for your user directory, and
`-a <agent>` to pick agents, for example `-a codex -a cursor`.

**By hand**: clone into your agent's skills directory.

```bash
git clone https://github.com/sonigeez/animated-system-explainer ~/.claude/skills/animated-system-explainer
```

| Agent | User directory | Project directory |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.agents/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.agents/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.agents/skills/` |
| Amp | `~/.config/agents/skills/` | `.agents/skills/` |

Paths are as listed by the [skills CLI](https://github.com/vercel-labs/skills).
Check your agent's docs if one has changed.

**Claude.ai / Claude desktop**: download `animated-system-explainer.skill` from
the [latest release](https://github.com/sonigeez/animated-system-explainer/releases/latest)
and upload it in Claude's skill settings.

**Agents without skill support**: tell the agent to read `SKILL.md` in this repo
and follow it.

## Requirements

Python 3. Optional, used when installed:

- `node`: syntax-checks the page's scripts.
- `cwebp`: shrinks embedded photos.
- Playwright for Python: headless screenshots of every step.

```bash
pip install playwright && python -m playwright install chromium
```

## How it works

| Path | What it is |
|---|---|
| `SKILL.md` | The workflow the agent follows: understand the design first, keep the watch view minimal, build from the example, check every step, deliver, iterate. |
| `references/engine.md` | Which parts of the example are reusable engine and which are content; data formats, animation helpers, pitfalls. |
| `assets/example-pkce-login.src.html` | Editable source of the example. Every frame is a pure function of time, so seeking and step markers always land on the right frame. |
| `scripts/build.py` | Builds the publishable file: embeds images, makes the page pure ASCII, adds a charset tag, syntax-checks the scripts. |
| `scripts/check.py` | Serves the page and checks it in a headless browser. It reports script errors and sideways scroll at phone width, and saves one screenshot per step plus the read tab. |
| `examples/pkce-login.html` | The built example. |
| `evals/evals.json` | Test prompts for evaluating the skill. |

By hand:

```bash
python3 scripts/build.py my-explainer.src.html my-explainer.html --img device=photo.png
python3 scripts/check.py my-explainer.html --out shots/
```

In a browser console, `explainer.seek(videoIndex, seconds)`,
`explainer.view('read')` and `explainer.videos` drive any page built with
the bundled engine.

## License

[MIT](LICENSE)
