#!/usr/bin/env python3
"""Check a built explainer page in a real browser and screenshot every step.

Serves the page's folder on a local port (browsers and many agent tools cannot
screenshot file:// URLs), then, if Playwright for Python is installed:

  - loads the page at desktop width and at phone width (400 px),
  - fails on any script error or console error,
  - fails if the page body scrolls sideways at phone width,
  - pauses the player and screenshots the settled frame of every step of
    every video, plus the read tab, into --out,
  - prints one line per frame so the agent can look at the images.

Without Playwright it serves the page and prints the URL plus the snippet to
run in any browser tool, so a human or an agent with its own browser can do the
same checks by hand.

The page must expose window.explainer (the bundled engine does):
  { videos: [{tab, duration, steps: [{start, label, text}]}], seek(i, t), pause(), view('watch'|'read') }

usage:
  check.py page.html [--out shots/] [--serve-only]
  pip install playwright && python -m playwright install chromium   # optional, once
"""
import argparse
import functools
import http.server
import os
import socketserver
import sys
import threading


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


def run_playwright(url, out):
    from playwright.sync_api import sync_playwright
    problems = []
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, width, height in (('desktop', 1100, 900), ('phone', 400, 860)):
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.on('pageerror', lambda e, l=label: problems.append(f'[{l}] script error: {e}'))
            page.on('console', lambda m, l=label: m.type == 'error' and problems.append(f'[{l}] console error: {m.text}'))
            page.goto(url, wait_until='load')
            page.wait_for_timeout(600)
            if not page.evaluate('!!window.explainer'):
                problems.append(f'[{label}] window.explainer is missing; is this built from the bundled engine?')
                page.close()
                continue
            if page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1'):
                problems.append(f'[{label}] page scrolls sideways at {width}px')
            if label == 'desktop':
                videos = page.evaluate('window.explainer.videos')
                page.evaluate('window.explainer.pause()')
                for i, j, tab, step, t in frames(videos):
                    page.evaluate(f'window.explainer.seek({i}, {t})')
                    page.wait_for_timeout(120)
                    path = os.path.join(out, f'{i + 1:02d}-{tab}-{j + 1}-{step}.png')
                    page.locator('.stage').screenshot(path=path)
                    print(f'frame  video {i + 1} {tab:<10} step {j + 1} {step:<10} t={t:5.2f}  {path}')
            page.evaluate("window.explainer.view('read')")
            page.wait_for_timeout(300)
            path = os.path.join(out, f'read-{label}.png')
            page.screenshot(path=path, full_page=True)
            print(f'read   {label:<8} {path}')
            page.close()
        browser.close()
    return problems


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

    problems = run_playwright(url, a.out)
    httpd.shutdown()
    if problems:
        print('\nproblems:')
        for p in problems:
            print('  ' + p)
        sys.exit(1)
    print(f'\nok: no script errors, no sideways scroll; screenshots in {a.out}/')


if __name__ == '__main__':
    main()
