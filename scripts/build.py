#!/usr/bin/env python3
"""Build a publishable single-file explainer page from an editable source page.

What it does, in order:
  1. Replaces every  __IMG:<name>__  placeholder with a data: URI of the image
     passed as  --img <name>=<path>.  Raster images are shrunk to --max-px tall
     and re-encoded as WebP when `cwebp` is installed (a 1-2 MB photo becomes
     a few KB), otherwise embedded as-is.
  2. Makes the page pure ASCII. Published artifacts can be decoded with the
     wrong charset, which turns arrows and crosses into mojibake ("a-hat" plus
     junk). Non-ASCII characters become \\uXXXX inside <script>, CSS escapes
     inside <style>, and &#N; entities everywhere else. A <meta charset> is
     added at the top as a second guard.
  3. Syntax-checks every inline <script> with `node --check` when node exists.
  4. Writes the output and prints its size.

usage:
  build.py SRC.html OUT.html [--img device=photo.png ...] [--max-px 400]
"""
import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile

MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
        '.gif': 'image/gif', '.svg': 'image/svg+xml'}


def data_uri(path, max_px):
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.webp') and shutil.which('cwebp'):
        fd, tmp = tempfile.mkstemp(suffix='.webp')
        os.close(fd)
        try:
            subprocess.run(['cwebp', '-quiet', '-q', '82', '-alpha_q', '90', '-resize', '0', str(max_px),
                            path, '-o', tmp], check=True)
            raw = open(tmp, 'rb').read()
        finally:
            os.unlink(tmp)
        return 'data:image/webp;base64,' + base64.b64encode(raw).decode(), len(raw)
    raw = open(path, 'rb').read()
    return f'data:{MIME.get(ext, "application/octet-stream")};base64,' + base64.b64encode(raw).decode(), len(raw)


def js_escape(c):
    o = ord(c)
    if o <= 0xFFFF:
        return '\\u%04x' % o
    o -= 0x10000
    return '\\u%04x\\u%04x' % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF))


def asciify(html):
    out, pos = [], 0
    for m in re.finditer(r'(<script\b[^>]*>)(.*?)(</script>)|(<style\b[^>]*>)(.*?)(</style>)', html, re.S | re.I):
        out.append(''.join(c if ord(c) < 128 else '&#%d;' % ord(c) for c in html[pos:m.start()]))
        if m.group(1):
            out.append(m.group(1) + ''.join(c if ord(c) < 128 else js_escape(c) for c in m.group(2)) + m.group(3))
        else:
            out.append(m.group(4) + ''.join(c if ord(c) < 128 else '\\%x ' % ord(c) for c in m.group(5)) + m.group(6))
        pos = m.end()
    out.append(''.join(c if ord(c) < 128 else '&#%d;' % ord(c) for c in html[pos:]))
    return ''.join(out)


def node_check(html):
    if not shutil.which('node'):
        print('note: node not found, scripts not syntax-checked')
        return True
    ok = True
    for i, m in enumerate(re.finditer(r'<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S | re.I)):
        fd, tmp = tempfile.mkstemp(suffix='.js')
        with os.fdopen(fd, 'w') as f:
            f.write(m.group(1))
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        os.unlink(tmp)
        if r.returncode != 0:
            ok = False
            print(f'script #{i + 1} has a syntax error:\n{r.stderr.strip()}', file=sys.stderr)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--img', action='append', default=[], metavar='NAME=PATH')
    ap.add_argument('--max-px', type=int, default=400, help='max image height in pixels (default 400)')
    a = ap.parse_args()

    html = open(a.src, encoding='utf-8').read()
    for spec in a.img:
        name, _, path = spec.partition('=')
        if not path or not os.path.exists(path):
            sys.exit(f'--img {spec}: expected NAME=PATH to an existing file')
        uri, n = data_uri(path, a.max_px)
        token = f'__IMG:{name}__'
        if token not in html:
            print(f'warning: {token} does not appear in {a.src}')
        html = html.replace(token, uri)
        print(f'embedded {name}: {n / 1024:.1f} KB')
    left = sorted(set(re.findall(r'__IMG:([A-Za-z0-9_-]+)__', html)))
    if left:
        sys.exit('unfilled image placeholders: ' + ', '.join(left) + ' (pass --img NAME=PATH)')

    if not re.search(r'<meta\s+charset', html[:2000], re.I):
        html = '<meta charset="utf-8">\n' + html
    html = asciify(html)
    assert all(ord(c) < 128 for c in html)

    if not node_check(html):
        sys.exit('build failed: fix the script errors above')
    with open(a.out, 'w', encoding='ascii') as f:
        f.write(html)
    print(f'wrote {a.out} ({len(html) / 1024:.1f} KB, ascii-only)')


if __name__ == '__main__':
    main()
