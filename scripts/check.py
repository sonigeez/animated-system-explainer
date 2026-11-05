#!/usr/bin/env python3
"""Check a built explainer page in a real browser and screenshot every step.

Serves the page's folder on a local port (browsers and many agent tools cannot
screenshot file:// URLs), then, if Playwright for Python is installed:

  - loads the page at desktop width and at phone width (400 px), with CSS
    transitions turned off so every frame is the settled one,
  - fails on any script error or console error,
  - fails if the page body scrolls sideways at phone width,
  - lints the video data: step order, formula items and legend entries that
    name a key that does not exist, and (as warnings) videos, steps and holds
    that are too short, too long or too many,
  - pauses the player and, at the settled frame of every step of every video:
      * fails if two visible labels overlap or a label sticks out of the stage,
      * warns if the step caption wraps onto a second line at desktop width,
      * saves a screenshot of the stage,
  - replays every frame in reverse order and fails if any frame looks different
    the second time: an object a scene sets but reset() does not put back
    leaks into whatever plays next,
  - checks labels in the read tab's diagrams for overlap and clipping too,
  - saves contact-sheet.png: every step in one image, one row per video,
    with problem frames outlined in red. Look at that first.

Without Playwright it serves the page and prints the URL plus the snippet to
run in any browser tool, so a human or an agent with its own browser can do the
same checks by hand.

The page must expose window.explainer (the bundled engine does):
  { videos: [{tab, duration, lit, steps: [{start, label, text, formula}]}], keys: [...],
    seek(i, t), pause(), view('watch'|'read') }
(`keys`, `lit` and `formula` are optional: without them the key checks are skipped.)

usage:
  check.py page.html [--out shots/] [--serve-only]
  pip install playwright && python -m playwright install chromium   # optional, once
"""
import argparse
import base64
import functools
import html
import http.server
import os
import socketserver
import sys
import threading

# Pacing and size guidance, matching SKILL.md. Breaking these is a warning, not a failure.
VIDEOS_RANGE = (4, 7)
STEPS_RANGE = (2, 5)
DURATION_RANGE = (6.0, 12.0)
MIN_STEP = 1.2        # seconds a step stays on screen; aim for about 1.5
OPERATORS = {'+', '=', '->'}
OVERLAP = 2.0         # labels must overlap by more than this (stage units) in both directions to count
CLIP = 1.0            # how far a label may stick out of the viewBox

NO_TRANSITIONS = '*,*::before,*::after{transition:none!important;animation:none!important}'

# Visible state of one SVG: every drawn element that is not fully transparent, with its
# box in viewBox units, its effective opacity and its paint; plus the visible labels.
SCAN_JS = r'''
(svg) => {
  if (!svg || !svg.getScreenCTM()) return null;
  const r1 = (v) => Math.round(v * 2) / 2;
  const inv = svg.getScreenCTM().inverse();
  const vb = svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width
    ? svg.viewBox.baseVal : { x: 0, y: 0, width: svg.clientWidth, height: svg.clientHeight };
  const DRAWN = new Set(['rect', 'circle', 'ellipse', 'line', 'path', 'polygon', 'polyline', 'text', 'image', 'use']);
  function alpha(el) {
    let a = 1;
    for (let e = el; e && e !== svg.parentNode; e = e.parentNode) {
      const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 0;
      a *= parseFloat(cs.opacity);
    }
    return a;
  }
  function name(el) {
    const parts = [];
    for (let e = el; e && e !== svg; e = e.parentNode) {
      if (e.id) { parts.unshift('#' + e.id); break; }
      parts.unshift(e.tagName + '[' + [...e.parentNode.children].indexOf(e) + ']');
    }
    return parts.join(' > ');
  }
  const state = {}, labels = [];
  svg.querySelectorAll('*').forEach((el) => {
    if (!DRAWN.has(el.tagName) || el.closest('defs, clipPath, mask, symbol')) return;
    const a = alpha(el);
    if (a < 0.02) return;
    const b = el.getBBox(), m = inv.multiply(el.getScreenCTM());
    const xs = [], ys = [];
    [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]].forEach(([x, y]) => {
      xs.push(m.a * x + m.c * y + m.e); ys.push(m.b * x + m.d * y + m.f);
    });
    const box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    const cs = getComputedStyle(el), txt = el.tagName === 'text' ? el.textContent.trim() : '';
    const key = name(el);
    state[key] = [box.map(r1).join(','), r1(a * 10) / 10, cs.fill, cs.stroke, el.getAttribute('class') || '', txt].join(' | ');
    if (txt) labels.push({ id: key, text: txt, box });
  });
  return { state, labels, vb: [vb.x, vb.y, vb.width, vb.height] };
}
'''

CAPTION_JS = r'''
() => {
  const el = document.getElementById('stepText');
  if (!el) return null;
  const lh = parseFloat(getComputedStyle(el).lineHeight) || parseFloat(getComputedStyle(el).fontSize) * 1.45;
  const row = el.parentElement;   /* the pill and the caption share one wrapping row */
  return Math.max(el.getBoundingClientRect().height, row.getBoundingClientRect().height) > lh * 1.6 ? el.textContent : null;
}
'''


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(folder):
    handler = functools.partial(QuietHandler, directory=folder)
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def frames(videos):
    """The settled moment of each step: just before the next step starts."""
    for i, v in enumerate(videos):
        starts = [s['start'] for s in v['steps']] + [v['duration']]
        for j, s in enumerate(v['steps']):
            yield i, j, v['tab'], s['label'], max(s['start'], starts[j + 1] - 0.05)


def lint(videos, keys):
    """Static checks on the video data. Returns (problems, warnings, flagged (video, step) pairs)."""
    problems, warnings, flagged = [], [], set()
    if not VIDEOS_RANGE[0] <= len(videos) <= VIDEOS_RANGE[1]:
        warnings.append(f'{len(videos)} videos; {VIDEOS_RANGE[0]}-{VIDEOS_RANGE[1]} usually tells the story best')
    known = set(keys) if keys is not None else None
    for i, v in enumerate(videos):
        where = f'video {i + 1} ({v["tab"]})'
        steps, D = v['steps'], v['duration']
        if not steps:
            problems.append(f'{where}: has no steps')
            continue
        if not DURATION_RANGE[0] <= D <= DURATION_RANGE[1]:
            warnings.append(f'{where}: lasts {D:g} s; aim for {DURATION_RANGE[0]:g}-{DURATION_RANGE[1]:g} s')
        if not STEPS_RANGE[0] <= len(steps) <= STEPS_RANGE[1]:
            warnings.append(f'{where}: {len(steps)} steps; aim for {STEPS_RANGE[0]}-{STEPS_RANGE[1]}')
        if len(v['tab']) > 10:
            warnings.append(f'{where}: tab label "{v["tab"]}" is long and may wrap under its icon')
        starts = [s['start'] for s in steps]
        if starts[0] != 0:
            warnings.append(f'{where}: the first step starts at {starts[0]:g} s; its caption shows from 0 anyway')
        for j in range(1, len(starts)):
            if starts[j] <= starts[j - 1]:
                flagged.add((i, j))
                problems.append(f'{where}: step {j + 1} starts at {starts[j]:g} s, not after step {j} ({starts[j - 1]:g} s)')
        if starts[-1] >= D:
            flagged.add((i, len(starts) - 1))
            problems.append(f'{where}: the last step starts at {starts[-1]:g} s, at or after the end ({D:g} s)')
        ends = starts[1:] + [D]
        for j, (a, b) in enumerate(zip(starts, ends)):
            if 0 < b - a < MIN_STEP:
                warnings.append(f'{where}: step {j + 1} "{steps[j]["label"]}" is on screen {b - a:.1f} s; give it about 1.5 s')
        if known is None:
            continue
        for k in v.get('lit') or []:
            if k not in known:
                problems.append(f'{where}: lit names "{k}", which is not in KEYS')
        for j, s in enumerate(steps):
            for item in s.get('formula') or []:
                if item in OPERATORS or item in known or item[:2] in ('t:', 'x:'):
                    continue
                flagged.add((i, j))
                problems.append(f'{where} step {j + 1}: formula item "{item}" is not a key, an operator, '
                                f'"t:text" or "x:text" (it would render as "{item[2:]}")')
    return problems, warnings, flagged


def label_problems(scan, where):
    """Labels that overlap each other or stick out of the viewBox."""
    if not scan:
        return []
    out = []
    x0, y0, w, h = scan['vb']
    labels = scan['labels']
    for lb in labels:
        x1, y1, x2, y2 = lb['box']
        if x1 < x0 - CLIP or y1 < y0 - CLIP or x2 > x0 + w + CLIP or y2 > y0 + h + CLIP:
            out.append(f'{where}: label "{lb["text"]}" sticks out of the {w:g}x{h:g} viewBox '
                       f'(x {x1:.0f}..{x2:.0f}, y {y1:.0f}..{y2:.0f})')
    for a in range(len(labels)):
        for b in range(a + 1, len(labels)):
            p, q = labels[a]['box'], labels[b]['box']
            dx = min(p[2], q[2]) - max(p[0], q[0])
            dy = min(p[3], q[3]) - max(p[1], q[1])
            if dx > OVERLAP and dy > OVERLAP:
                out.append(f'{where}: labels "{labels[a]["text"]}" and "{labels[b]["text"]}" overlap')
    return out


def diff_states(first, second):
    """Objects whose visible state differs between two scans of the same frame, named by their
    nearest id (a group with an id counts as one object)."""
    names = []
    for k in sorted(set(first) | set(second)):
        if first.get(k) != second.get(k):
            root = k.split(' > ')[0]
            how = ('visible only when earlier frames played first' if k not in second else
                   'visible only when later frames played first' if k not in first else 'drawn differently')
            item = f'{root} ({how})'
            if item not in names:
                names.append(item)
    return names


def contact_sheet(page, out, videos, shots, flagged):
    """One image with every step: a row per video, a column per step."""
    cols = max(len(v['steps']) for v in videos)
    rows = []
    for i, v in enumerate(videos):
        cells = []
        for j, s in enumerate(v['steps']):
            path = shots.get((i, j))
            img = ''
            if path and os.path.exists(path):
                img = '<img src="data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode() + '">'
            formula = ' '.join(s.get('formula') or [])
            cells.append(
                f'<div class="cell{" bad" if (i, j) in flagged else ""}">{img}'
                f'<div class="cap"><b>{i + 1}.{j + 1} {html.escape(s["label"])}</b> {html.escape(s["text"])}</div>'
                + (f'<div class="f">{html.escape(formula)}</div>' if formula else '') + '</div>')
        cells += ['<div></div>'] * (cols - len(cells))
        rows.append(f'<div class="vt">{i + 1:02d} {html.escape(v["tab"])}  -  {html.escape(v.get("title", ""))}</div>'
                    + f'<div class="row">{"".join(cells)}</div>')
    doc = ('<!doctype html><meta charset="utf-8"><style>'
           'body{margin:0;padding:16px;background:#111;color:#ddd;font:12px/1.35 Menlo,Consolas,monospace}'
           f'.row{{display:grid;grid-template-columns:repeat({cols},380px);gap:10px;margin:0 0 18px}}'
           '.vt{font-weight:700;color:#fff;margin:0 0 6px}'
           '.cell{border:2px solid #333;background:#000}.cell.bad{border-color:#ff5050}'
           '.cell img{display:block;width:100%}.cap{padding:5px 7px 2px}.f{padding:0 7px 6px;color:#999}'
           '</style>' + ''.join(rows))
    page.set_viewport_size({'width': 32 + cols * 390, 'height': 400})
    page.set_content(doc)
    path = os.path.join(out, 'contact-sheet.png')
    page.screenshot(path=path, full_page=True)
    return path


def run_playwright(url, out):
    from playwright.sync_api import sync_playwright
    problems, warnings = [], []
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, width, height in (('desktop', 1100, 900), ('phone', 400, 860)):
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.on('pageerror', lambda e, l=label: problems.append(f'[{l}] script error: {e}'))
            page.on('console', lambda m, l=label: m.type == 'error' and problems.append(f'[{l}] console error: {m.text}'))
            page.goto(url, wait_until='load')
            page.add_style_tag(content=NO_TRANSITIONS)
            page.evaluate('document.fonts ? document.fonts.ready.then(() => 0) : 0')
            page.wait_for_timeout(600)
            if not page.evaluate('!!window.explainer'):
                problems.append(f'[{label}] window.explainer is missing; is this built from the bundled engine?')
                page.close()
                continue
            if page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1'):
                problems.append(f'[{label}] page scrolls sideways at {width}px')
            if label == 'desktop':
                videos = page.evaluate('window.explainer.videos')
                keys = page.evaluate('window.explainer.keys || null')
                lp, lw, flagged = lint(videos, keys)
                problems += lp
                warnings += lw
                if keys is None:
                    warnings.append('window.explainer.keys is missing, so formula and legend keys were not checked')
                page.evaluate('window.explainer.pause()')
                stage = page.locator('.stage svg').first
                shots, first = {}, {}
                order = list(frames(videos))
                for i, j, tab, step, t in order:
                    page.evaluate(f'window.explainer.seek({i}, {t})')
                    page.wait_for_timeout(80)
                    where = f'video {i + 1} ({tab}) step {j + 1} "{step}" at {t:.2f} s'
                    scan = stage.evaluate(SCAN_JS)
                    first[(i, j)] = scan['state'] if scan else {}
                    lp = label_problems(scan, where)
                    if lp:
                        flagged.add((i, j))
                        problems += lp
                    wrapped = page.evaluate(CAPTION_JS)
                    if wrapped:
                        warnings.append(f'{where}: caption wraps at desktop width; keep it to one line: "{wrapped}"')
                    path = os.path.join(out, f'{i + 1:02d}-{tab}-{j + 1}-{step}.png')
                    page.locator('.stage').first.screenshot(path=path)
                    shots[(i, j)] = path
                    print(f'frame  video {i + 1} {tab:<10} step {j + 1} {step:<10} t={t:5.2f}  {path}')
                # Same frames, other order: a pure scene renders identically whatever played before.
                leaks = {}
                for i, j, tab, step, t in reversed(order):
                    page.evaluate(f'window.explainer.seek({i}, {t})')
                    page.wait_for_timeout(30)
                    scan = stage.evaluate(SCAN_JS)
                    for item in diff_states(first[(i, j)], scan['state'] if scan else {}):
                        flagged.add((i, j))
                        leaks.setdefault(item, []).insert(0, f'{i + 1}.{j + 1}')
                for item, where in leaks.items():
                    seen = ', '.join(where[:6]) + (f' and {len(where) - 6} more' if len(where) > 6 else '')
                    problems.append(f'{item}: the frame depends on what played before, so reset() does not '
                                    f'put it back (frames {seen})')
                sheet = contact_sheet(browser.new_page(), out, videos, shots, flagged)
                print(f'sheet  all steps            {sheet}')
            page.evaluate("window.explainer.view('read')")
            page.wait_for_timeout(300)
            for n, svg in enumerate(page.locator('#readView svg:not(.g)').all()):
                problems += label_problems(svg.evaluate(SCAN_JS), f'[{label}] read tab diagram {n + 1}')
            path = os.path.join(out, f'read-{label}.png')
            page.screenshot(path=path, full_page=True)
            print(f'read   {label:<8} {path}')
            page.close()
        browser.close()
    return list(dict.fromkeys(problems)), list(dict.fromkeys(warnings))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page')
    ap.add_argument('--out', default='explainer-shots')
    ap.add_argument('--serve-only', action='store_true', help='serve and wait; check by hand')
    a = ap.parse_args()

    page = os.path.abspath(a.page)
    if not os.path.isfile(page):
        sys.exit(f'no such file: {a.page}')
    httpd, port = serve(os.path.dirname(page))
    url = f'http://127.0.0.1:{port}/{os.path.basename(page)}'

    try:
        import playwright  # noqa: F401
        have_pw = True
    except ImportError:
        have_pw = False

    if a.serve_only or not have_pw:
        if not have_pw:
            print('Playwright not installed: serving for a manual check instead.')
        print(f'open {url}')
        print('then, in the browser console or your browser tool:')
        print('  explainer.videos                 // videos and step start times')
        print('  explainer.seek(videoIndex, sec)  // pause and show that frame')
        print("  explainer.view('read')           // the written tab")
        print('Ctrl-C to stop.')
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        httpd.shutdown()
        return

    problems, warnings = run_playwright(url, a.out)
    httpd.shutdown()
    if warnings:
        print('\nwarnings:')
        for w in warnings:
            print('  ' + w)
    if problems:
        print('\nproblems:')
        for p in problems:
            print('  ' + p)
        print(f'\nfailed: {len(problems)} problem(s). Start with {os.path.join(a.out, "contact-sheet.png")} (problem frames are outlined in red).')
        sys.exit(1)
    print(f'\nok: no script errors, overlaps, clipped labels, reset leaks or sideways scroll.'
          f'\nLook at {os.path.join(a.out, "contact-sheet.png")} first, then any single frame in {a.out}/.')


if __name__ == '__main__':
    main()
