#!/usr/bin/env python3
"""Start a new explainer from a storyboard instead of hand-editing the example.

Reads a storyboard JSON (actors, keys, videos and their steps; see
assets/storyboard-example.json) and writes an editable source page that already
works end to end:

  - the stage with 2-4 actors laid out left to right, lanes between neighbours,
  - KEYS (colour = the actor that makes it) and VIDEOS with paced step times,
  - placeholder scenes: a step with "move" sends its key(s) along the lanes
    from one actor to another, a step with only a formula pops its keys in
    next to the actor that makes them,
  - a read tab skeleton: a piece table from KEYS, a sequence diagram with one
    row per step, the steps as a list, and a Q&A slot,
  - the engine (player, timeline, helpers, rain, control API) copied unchanged
    from assets/example-pkce-login.src.html.

Everything that still needs a human or agent touch is marked TODO. The
placeholder motion is only a start: replace it with the real story
(references/engine.md section 5), then build and check as usual.

usage:
  scaffold.py storyboard.json out.src.html
  scaffold.py --example > storyboard.json      # print the example storyboard to start from
"""
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, '..', 'assets', 'example-pkce-login.src.html')
EXAMPLE = os.path.join(HERE, '..', 'assets', 'storyboard-example.json')

ACTOR_X = {2: [200, 600], 3: [120, 400, 680], 4: [100, 300, 500, 700]}
OWNER_COLOURS = ['var(--otk)', 'var(--key)', 'var(--seal)', 'var(--p4)']
ICONS = [
    '<circle cx="10" cy="10" r="6.5"/><path d="M10 6.5V10l2.5 1.5"/>',
    '<path d="M3 7h12M12 4l3 3-3 3M17 13H5M8 16l-3-3 3-3"/>',
    '<rect x="3.5" y="4" width="13" height="12"/><path d="M3.5 7.5h13M7 11h6"/>',
    '<path d="M4 16V9M10 16V4M16 16v-5"/>',
    '<circle cx="7" cy="10" r="3.2"/><circle cx="13" cy="10" r="3.2"/>',
    '<path d="M10 3l6 2.4V10c0 3.6-2.6 6-6 7-3.4-1-6-3.4-6-7V5.4z"/><path d="M7.5 10l1.8 1.8L12.8 8.2"/>',
    '<path d="M4 10h12M10 4v12"/>',
]
OPERATORS = {'+', '=', '->'}
STEP = 2.0          # seconds per step without a move
HOP = 0.35          # seconds per lane a moving key crosses
HOLD = 0.6          # seconds a step holds still after its motion

js = json.dumps


def esc(s):
    return html.escape(str(s), quote=True)


def fail(msg):
    sys.exit(f'storyboard: {msg}')


class Board:
    """The storyboard, validated, with actor names resolved to indices and step times worked out."""

    def __init__(self, raw):
        self.title = raw.get('title') or fail('needs a "title"')
        actors = raw.get('actors') or fail('needs "actors"')
        if not 2 <= len(actors) <= 4:
            fail(f'{len(actors)} actors; use 2-4 (more do not fit one stage)')
        self.actors = [a if isinstance(a, dict) else {'name': a} for a in actors]
        self.names = [a['name'] for a in self.actors]
        self.X = ACTOR_X[len(self.actors)]
        self.lane_labels = raw.get('lanes') or []
        self.slug = re.sub(r'[^a-z0-9]+', '-', (raw.get('slug') or self.title).lower()).strip('-')[:16] or 'system'

        self.keys = {}
        per_owner = {}
        for kid, k in (raw.get('keys') or fail('needs "keys"')).items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', kid):
                fail(f'key id "{kid}" must be a plain identifier (letters, digits, _)')
            if kid in ('t', 'x'):
                fail(f'key id "{kid}" clashes with the "t:" and "x:" formula prefixes')
            o = self.actor(k.get('owner'), f'key "{kid}" owner')
            m = per_owner.get(o, 0)
            per_owner[o] = m + 1
            self.keys[kid] = {'name': k.get('name', kid), 'owner': o, 'secret': bool(k.get('secret')),
                              'square': bool(k.get('square')), 'home': [self.X[o] + 62, 60 + 36 * m]}

        self.videos = []
        for vi, v in enumerate(raw.get('videos') or fail('needs "videos"')):
            tab = v.get('tab') or fail(f'video {vi + 1} needs a "tab"')
            steps, t = [], 0.0
            for si, s in enumerate(v.get('steps') or fail(f'video "{tab}" needs "steps"')):
                where = f'video "{tab}" step {si + 1}'
                if isinstance(s, list):
                    s = dict(zip(('label', 'text', 'formula'), s))
                formula = s.get('formula')
                for item in formula or []:
                    if item not in OPERATORS and item[:2] not in ('t:', 'x:') and item not in self.keys:
                        fail(f'{where}: formula item "{item}" is not a key id, an operator (+ = ->), "t:text" or "x:text"')
                move = None
                if s.get('move'):
                    mv = s['move']
                    mk = mv.get('key') or mv.get('keys') or fail(f'{where}: "move" needs "key"')
                    mk = [mk] if isinstance(mk, str) else list(mk)
                    for k in mk:
                        if k not in self.keys:
                            fail(f'{where}: moves unknown key "{k}"')
                    a, b = self.actor(mv.get('from'), f'{where} move "from"'), self.actor(mv.get('to'), f'{where} move "to"')
                    if a == b:
                        fail(f'{where}: "move" goes from {self.names[a]} to itself')
                    move = (mk, a, b)
                    if not formula:
                        formula = [x for k in mk for x in ('+', k)][1:]
                length = max(STEP, 0.8 + HOP * abs(move[2] - move[1]) + HOLD) if move else STEP
                steps.append({'start': round(t, 2), 'label': s.get('label') or fail(f'{where} needs a "label"'),
                              'text': s.get('text') or fail(f'{where} needs a "text"'),
                              'formula': formula or None, 'move': move})
                t += length
            lit = []
            for s in steps:
                for k in (s['formula'] or []) + (s['move'][0] if s['move'] else []):
                    if k in self.keys and k not in lit:
                        lit.append(k)
            self.videos.append({'tab': tab, 'title': v.get('title') or f'TODO: title for {tab}',
                                'lede': v.get('lede') or 'TODO: one or two sentences of context.',
                                'icon': v.get('icon') or ICONS[vi % len(ICONS)], 'lit': lit,
                                'D': round(t + 0.2, 2), 'steps': steps})
        read = raw.get('read') or {}
        self.read_title = read.get('title') or f'How {self.title} works'
        self.read_lede = read.get('lede') or 'Everything from the videos, written down.'
        self.read_big = read.get('big') or 'TODO: one sentence: what the system does and the one idea that makes it work.'

    def actor(self, ref, where):
        if isinstance(ref, int) and 0 <= ref < len(self.names):
            return ref
        if ref in self.names:
            return self.names.index(ref)
        fail(f'{where}: "{ref}" is not one of the actors {self.names}')


# ---------------------------------------------------------------- page parts

def stage_html(b):
    n = len(b.actors)
    out = [f'<section class="stage" aria-label="{esc(", ".join(b.names))}">',
           '    <span class="br tl"></span><span class="br tr"></span><span class="br bl"></span><span class="br brr"></span>',
           f'    <svg viewBox="0 0 800 330" role="img" aria-label="{esc(" -> ".join(b.names))}, left to right. TODO: say what moves between them." id="svg">',
           '      <!-- lanes between neighbouring actors (y = 244). TODO: add a back channel on y = 292 if one skips an actor. -->']
    for i in range(n - 1):
        x1, x2 = b.X[i] + 56, b.X[i + 1] - 56
        out.append(f'      <line id="lane{i + 1}" class="lane" x1="{x1}" y1="244" x2="{x2}" y2="244"/>')
        if i < len(b.lane_labels) and b.lane_labels[i]:
            out.append(f'      <text class="sub" x="{(x1 + x2) // 2}" y="236" text-anchor="middle">{esc(b.lane_labels[i])}</text>')
    for i, a in enumerate(b.actors):
        x = b.X[i]
        out.append(f'\n      <!-- {esc(a["name"])}. TODO: draw its real shape, or put its photo here '
                   f'(references/engine.md section 8) -->')
        out.append(f'      <rect class="dev" x="{x - 48}" y="62" width="96" height="104" rx="8"/>')
        if a.get('sub'):
            out.append(f'      <text class="sub" x="{x}" y="118" text-anchor="middle">{esc(a["sub"])}</text>')
        out.append(f'      <text class="lbl" x="{x}" y="204" text-anchor="middle">{esc(a["name"])}</text>')
    out += ['',
            '      <!-- combine flash -->',
            '      <g id="flash" opacity="0">',
            '        <circle id="flashRing" r="10" fill="none" stroke="var(--ink)" stroke-width="2"/>',
            '        <circle id="flashCore" r="6" fill="var(--ink)"/>',
            '      </g>',
            '',
            '      <!-- notes: top band y = 30, bottom band y = 322 -->',
            '      <text id="note1" class="tag" x="0" y="0" text-anchor="middle" fill="var(--ink2)" opacity="0"></text>',
            '      <text id="note2" class="tag" x="0" y="0" text-anchor="middle" fill="var(--ink2)" opacity="0"></text>',
            '',
            '      <g id="tokens"></g>',
            '    </svg>',
            '  </section>']
    return '\n'.join(out)


def keys_js(b):
    rows = []
    for kid, k in b.keys.items():
        sq = ', square: true' if k['square'] else ''
        rows.append(f"    {kid}: {{ c: '{OWNER_COLOURS[k['owner']]}', priv: {str(k['secret']).lower()}, "
                    f"name: {js(k['name'])}{sq} }}")
    return ('  /* TODO: colour = the actor that makes the key; solid ring (priv: true) = secret,\n'
            '     dashed = may be seen, square = issued or derived item. */\n'
            '  const KEYS = {\n' + ',\n'.join(rows) + '\n  };\n')


def videos_js(b):
    vids = []
    for v in b.videos:
        steps = ',\n              '.join(
            f"[{s['start']:g}, {js(s['label'])}, {js(s['text'])}, {js(s['formula']) if s['formula'] else 'null'}]"
            for s in v['steps'])
        vids.append(f"    {{ tab: {js(v['tab'])}, title: {js(v['title'])},\n"
                    f"      lede: {js(v['lede'])},\n"
                    f"      lit: {js(v['lit'])}, D: {v['D']:g},\n"
                    f"      steps: [{steps}],\n"
                    f"      icon: {js(v['icon'])} }}")
    return '  const VIDEOS = [\n' + ',\n'.join(vids) + '\n  ];\n'


def fn_name(tab, used):
    name = re.sub(r'\W+', '_', tab).strip('_') or 'video'
    if name[0].isdigit():
        name = 'v_' + name
    while name in used:
        name += '_'
    used.add(name)
    return name


def scenes_js(b, helpers):
    n = len(b.actors)
    lanes = [f'lane{i + 1}' for i in range(n - 1)]
    home = ', '.join(f'{k}: {js(v["home"])}' for k, v in b.keys.items())
    owner = ', '.join(f'{k}: {v["owner"]}' for k, v in b.keys.items())
    out = [
        '  /* ---------------- stage objects (generated from the storyboard) ---------------- */',
        f'  const X = {js(b.X)}, LANE_Y = 244, ACTOR_Y = 90;   /* actor centres; front lane; where a key rests on an actor */',
        '  const E = {};',
        f'  {js(lanes + ["flash", "flashRing", "flashCore", "note1", "note2", "tokens"])}.forEach((k) => E[k] = $(k));',
        helpers['token'],
        '  const K = {};',
        '  Object.keys(KEYS).forEach((k) => { K[k] = token(k); });   /* TODO: add a second token for a key shown twice at once */',
        f'  const HOME = {{ {home} }};   /* where each key sits beside the actor that makes it */',
        f'  const OWNER = {{ {owner} }};',
        helpers['place'],
        helpers['note'],
        helpers['flash'],
        f'  const LANES = {js(lanes)};',
        "  const lanes = (...on) => LANES.forEach((id, i) => E[id].classList.toggle('on', !!on[i]));",
        '',
        '  function reset(t) {',
        '    lanes();',
        '    Object.values(K).forEach((g) => op(g, 0));',
        '    [E.flash, E.note1, E.note2].forEach((e) => op(e, 0));',
        '    /* TODO: put every object you add back to its default here, or it leaks into other videos */',
        '  }',
        '',
        '  /* ---- TODO: placeholder motion from the storyboard. Replace it with the real story, then delete these. ---- */',
        '  const spot = (k, a, dx) => a === OWNER[k] ? HOME[k] : [X[a] + dx, ACTOR_Y];',
        '  function hop(t, k, a, b, s, dx, shown) { /* key k travels from actor a to b from s; shown = already on stage */',
        f'    const A = spot(k, a, dx), B = spot(k, b, dx), d = Math.abs(b - a) * {HOP};',
        '    place(K[k], kf(t, [[s + 0.2, A[0], A[1]], [s + 0.5, X[a] + dx, LANE_Y], [s + 0.5 + d, X[b] + dx, LANE_Y], [s + 0.8 + d, B[0], B[1]]]),',
        '          1, shown ? 1 : seg(t, s, s + 0.15));',
        '  }',
        f'  const crossing = (t, a, b, s) => t > s + 0.5 && t < s + 0.5 + Math.abs(b - a) * {HOP};',
        '  const pop = (t, k, s) => place(K[k], HOME[k], spring(seg(t, s + 0.1, s + 0.7)), seg(t, s + 0.1, s + 0.25));',
        '',
        '  const SCENES = [',
    ]
    used = set()
    fns = []
    for vi, v in enumerate(b.videos):
        name = fn_name(v['tab'], used)
        body = [f'    /* {vi + 1} - {v["tab"]}: ' + ' / '.join(f'{s["start"]:g} {s["label"]}' for s in v['steps']) + ' */',
                f'    function {name}(t) {{']
        lane_on = [[] for _ in lanes]
        shown = set()   # a key already on stage in this video stays where it is
        for s in v['steps']:
            st = f'{s["start"]:g}'
            if s['move']:
                mk, a, bb = s['move']
                for m, k in enumerate(mk):
                    on = ', true' if k in shown else ''
                    body.append(f"      if (t >= {st}) hop(t, '{k}', {a}, {bb}, {st}, {-32 * m}{on});")
                    shown.add(k)
                for L in range(min(a, bb), max(a, bb)):
                    lane_on[L].append(f'crossing(t, {a}, {bb}, {st})')
            else:
                for k in s['formula'] or []:
                    if k in b.keys and k not in shown:
                        body.append(f"      if (t >= {st}) pop(t, '{k}', {st});")
                        shown.add(k)
        args = ', '.join(' || '.join(c) if c else 'false' for c in lane_on)
        body.append(f'      lanes({args});')
        body.append('    }')
        fns.append('\n'.join(body))
    out.append(',\n'.join(fns))
    out.append('  ];\n')
    return '\n'.join(out) + '\n'


def read_html(b):
    rows = '\n'.join(
        f'      <tr><td><span data-g="{kid}"></span>{esc(k["name"])}</td><td>{esc(b.names[k["owner"]])}</td>'
        f'<td>TODO</td><td>TODO</td></tr>' for kid, k in b.keys.items())
    steps = '\n'.join(f'      <li>{esc(s["text"][:1].upper() + s["text"][1:])}.</li>' for v in b.videos for s in v['steps'])
    return f'''<article class="read" id="readView" hidden>
    <p class="big">{esc(b.read_big)}</p>
    <p>TODO: the problem this design solves, in two sentences.</p>

    <h2>the pieces</h2>
    <p>Solid rings must stay secret. Dashed rings may be seen by others.</p>
    <div class="tw"><table>
      <tr><th>piece</th><th>made by</th><th>travels</th><th>lifetime</th></tr>
{rows}
    </table></div>

    <h2>the flow</h2>
    <div class="seqwrap" id="seq"></div>
    <!-- TODO: merge these into the real sequence; drop the ones the diagram already says. -->
    <ol>
{steps}
    </ol>

    <!-- TODO: add what helps this audience: .combos (two cards side by side), .bytes + .bcap (a format),
         a "who sees what" table, request formats. See references/engine.md section 6. -->

    <h2>questions</h2>
    <dl class="qa">
      <dt>TODO: the first question your team will ask</dt>
      <dd>TODO: a short answer.</dd>
    </dl>
  </article>'''


def seq_js(b):
    rows = []
    for v in b.videos:
        for s in v['steps']:
            text = js(html.escape(s['text'], quote=False))   # SVG text: escape <, > and &
            if s['move']:
                mk, a, bb = s['move']
                rows.append(f"      {{ move: [{js(mk[0])}, {a}, {bb}], text: {text} }}")
            else:
                ks = [k for k in (s['formula'] or []) if k in b.keys]
                if ks:
                    rows.append(f"      {{ at: {b.keys[ks[0]]['owner']}, keys: {js(ks[:3])}, text: {text} }}")
                else:
                    rows.append(f"      {{ text: {text} }}")
    return f'''  (function seq() {{
    /* TODO: one row per storyboard step. Rewrite into the real call sequence (fewer, truer rows).
       Row kinds: {{ move: [key, fromActor, toActor], text }}, {{ at: actor, keys: [...], text }}, {{ text }}. */
    const X = {js(b.X)}, NAMES = {js(b.names)}, top = 54, RH = 60;
    const ROWS = [
{(',' + chr(10)).join(rows)}
    ];
    const H = top + ROWS.length * RH + 8, y = (i) => top + i * RH + RH / 2;
    const G = (k, x, yy, sc) => `<g transform="translate(${{x}},${{yy}}) scale(${{sc || 0.8}})">${{glyph(k)}}</g>`;
    const T = (txt, x, yy, anchor) => `<text class="sq" x="${{x}}" y="${{yy + 4}}" text-anchor="${{anchor || 'start'}}">${{txt}}</text>`;
    const N = (n, yy) => `<text class="sqn" x="20" y="${{yy + 4}}">${{n}}</text>`;
    const arrow = (x0, x1, yy, dashed) => {{
      const d = x1 > x0 ? 1 : -1, dash = dashed ? ' stroke-dasharray="5 4"' : '';
      return `<line x1="${{x0}}" y1="${{yy}}" x2="${{x1}}" y2="${{yy}}" stroke="var(--ink2)" stroke-width="1.6"${{dash}}/>` +
             `<path d="M${{x1 - 9 * d}} ${{yy - 5}} L${{x1}} ${{yy}} L${{x1 - 9 * d}} ${{yy + 5}}" fill="none" stroke="var(--ink2)" stroke-width="1.6"/>`;
    }};
    let s = `<svg viewBox="0 0 800 ${{H}}" role="img" aria-label="${{ROWS.length}} steps between ${{NAMES.join(', ')}}.">`;
    NAMES.forEach((n, i) => {{
      s += `<text class="sqa" x="${{X[i]}}" y="30" text-anchor="middle">${{n}}</text>`;
      s += `<line x1="${{X[i]}}" y1="42" x2="${{X[i]}}" y2="${{H - 6}}" stroke="var(--line)" stroke-width="1.6" stroke-dasharray="2 6"/>`;
    }});
    ROWS.forEach((r, i) => {{
      const yy = y(i);
      s += N(i + 1, yy);
      if (r.move) {{
        const [k, a, b] = r.move, d = b > a ? 1 : -1, mid = (X[a] + X[b]) / 2;
        s += arrow(X[a] + 20 * d, X[b] - 20 * d, yy) + G(k, mid, yy) + T(r.text, mid, yy - 18, 'middle');
      }} else if (r.keys) {{
        const x = X[r.at], left = x > 400, w = 24 + (r.keys.length - 1) * 28;   /* text goes where there is room */
        s += r.keys.map((k, n) => G(k, left ? x - n * 28 : x + n * 28, yy)).join('');
        s += left ? T(r.text, x - w, yy, 'end') : T(r.text, x + w, yy);
      }} else {{
        s += T(r.text, 50, yy);
      }}
    }});
    s += '</svg>';
    $('seq').innerHTML = s;
  }})();
'''


# ---------------------------------------------------------------- assembly

def sub_once(pattern, repl, text, what, flags=re.S):
    new, n = re.subn(pattern, lambda m: repl, text, count=1, flags=flags)
    if n != 1:
        sys.exit(f'scaffold: could not find {what} in {ENGINE}; the example changed, update scaffold.py')
    return new


def grab(pattern, text, what):
    m = re.search(pattern, text, re.S)
    if not m:
        sys.exit(f'scaffold: could not find {what} in {ENGINE}; the example changed, update scaffold.py')
    return m.group(0).rstrip('\n')


def scaffold(b):
    src = open(ENGINE, encoding='utf-8').read()
    helpers = {
        'token': grab(r'  function token\(kind\)[^\n]*', src, 'token()'),
        'place': grab(r'  const place = [^\n]*', src, 'place()'),
        'note': grab(r'  function note\([^\n]*', src, 'note()'),
        'flash': grab(r'  function flash\(.*?\n  \}', src, 'flash()'),
    }
    n = len(b.videos)
    owners = ', '.join(f'{c.split("--")[1].rstrip(")")} = {b.names[i]}' for i, c in enumerate(OWNER_COLOURS[:len(b.actors)]))
    out = src
    out = sub_once(r'<title>.*?</title>', f'<title>{esc(b.title)}</title>', out, '<title>')
    out = sub_once(r'/\* Layout:.*?\*/',
                   '/* Layout: prompt header / key legend / bracketed stage / formula + transport / video strip.\n'
                   '   TODO: pick a look for the subject (references/engine.md section 8); the terminal theme is the default.\n'
                   f'   Key language: colour = who makes it ({owners}). Solid = secret, dashed = may be seen, square = issued. */',
                   out, 'the layout comment')
    bad = grab(r'--bad:#[0-9a-fA-F]+;', out, 'the --bad colour token')
    out = out.replace(bad, bad + ' --p4:#c792ea;', 1)   # colour for a fourth actor's keys
    out = sub_once(r'dev@[^:]*:~\$', f'dev@{b.slug}:~$', out, 'the shell prompt')
    out = sub_once(r'(<span id="count">)\d+/\d+', f'<span id="count">01/{n:02d}', out, 'the video count')
    out = sub_once(r'<section class="stage".*?</section>', stage_html(b), out, 'the stage section')
    out = sub_once(r'<article class="read" id="readView" hidden>.*?</article>', read_html(b), out, 'the read article')
    out = sub_once(r'  const KEYS = \{.*?\n  \};\n', keys_js(b), out, 'KEYS')
    out = sub_once(r'  const VIDEOS = \[.*?\n  \];\n', videos_js(b), out, 'VIDEOS')
    out = sub_once(r'  const E = \{\};.*?(?=  /\* -+ hex rain)', scenes_js(b, helpers), out, 'the stage objects and SCENES')
    out = sub_once(r'  \(function seq\(\) \{.*?\n  \}\)\(\);\n', seq_js(b), out, 'seq()')
    out = sub_once(r"typeTitle\('[^']*'\);(\s*)swapLede\('[^']*'\);",
                   f"typeTitle({js(b.read_title)});\n      swapLede({js(b.read_lede)});", out, 'the read view title')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('storyboard', nargs='?')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--example', action='store_true', help='print the example storyboard and exit')
    ap.add_argument('--force', action='store_true', help='overwrite OUT if it exists')
    a = ap.parse_args()
    if a.example:
        sys.stdout.write(open(EXAMPLE, encoding='utf-8').read())
        return
    if not a.storyboard or not a.out:
        ap.error('give STORYBOARD.json and OUT.src.html (or --example)')
    if os.path.exists(a.out) and not a.force:
        sys.exit(f'{a.out} exists; pass --force to overwrite it (it may hold edits)')
    try:
        raw = json.load(open(a.storyboard, encoding='utf-8'))
    except (OSError, ValueError) as e:
        sys.exit(f'storyboard: {e}')
    b = Board(raw)
    page = scaffold(b)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(page)
    todos = page.count('TODO')
    print(f'wrote {a.out}: {len(b.actors)} actors, {len(b.keys)} keys, {len(b.videos)} videos, '
          f'{sum(len(v["steps"]) for v in b.videos)} steps, {todos} TODOs')
    print('next: replace the placeholder motion and the TODOs, then build.py and check.py')


if __name__ == '__main__':
    main()
