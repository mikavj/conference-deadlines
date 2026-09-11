#!/usr/bin/env python3
"""Re-fetch the source pages recorded in data/events.json and report what changed.

For every meeting: fetches each source URL (and deadline URLs), reports HTTP failures,
and checks whether the recorded dates still appear on the page in any common spelling.
Writes a summary to stdout and a JSON report to data/source-check.json.

Usage: python3 scripts/check_sources.py [--only id1,id2] [--timeout 20]
Standard library only. Pages behind bot protection show as HTTP 403 or 503; treat those as "unknown", not "changed".
"""
import datetime, hashlib, html, json, os, re, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'events.json')
REPORT = os.path.join(ROOT, 'data', 'source-check.json')
UA = 'Mozilla/5.0 (compatible; conference-calendar source check; +https://github.com/)'
MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def spellings(iso_date):
    y, m, d = (int(x) for x in iso_date.split('-'))
    full, abbr = MON[m - 1], MON[m - 1][:3]
    forms = ['%s %d, %d' % (full, d, y), '%s %d %d' % (full, d, y), '%d %s %d' % (d, full, y), '%s %d, %d' % (abbr, d, y), '%s. %d, %d' % (abbr, d, y),
             '%d %s %d' % (d, abbr, y), '%s %d' % (full, d), '%s %d' % (abbr, d), '%d/%d/%d' % (m, d, y), '%d/%d/%d' % (d, m, y), iso_date,
             '%s %d%s' % (full, d, 'th' if 11 <= d % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th'))]
    return forms


def fetch(url, timeout):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(3_000_000)
            text = raw.decode('utf-8', 'replace')
            return r.status, text
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:
        return None, str(e)


def visible_text(page):
    page = re.sub(r'(?is)<(script|style|noscript).*?</\1>', ' ', page)
    page = re.sub(r'(?s)<[^>]+>', ' ', page)
    page = html.unescape(page)
    return re.sub(r'\s+', ' ', page)


def main():
    args = sys.argv[1:]
    only = None
    timeout = 20
    if '--only' in args: only = set(args[args.index('--only') + 1].split(','))
    if '--timeout' in args: timeout = int(args[args.index('--timeout') + 1])
    db = json.load(open(DATA, encoding='utf-8'))
    old = {}
    if os.path.exists(REPORT):
        try: old = {r['url']: r for r in json.load(open(REPORT)).get('pages', [])}
        except Exception: old = {}
    pages, cache = [], {}
    flagged = []
    for ev in db['events']:
        if only and ev['id'] not in only: continue
        urls = []
        for s in ev.get('sources', []):
            if s.get('url'): urls.append(s['url'])
        for d in ev.get('deadlines', []):
            if d.get('url'): urls.append(d['url'])
        urls = list(dict.fromkeys(urls))
        problems = []
        for url in urls:
            if url not in cache:
                status, page = fetch(url, timeout)
                time.sleep(0.5)
                text = visible_text(page) if page else ''
                cache[url] = {'url': url, 'status': status, 'hash': hashlib.sha1(text.encode()).hexdigest() if text else None, 'text': text}
            c = cache[url]
            rec = {'url': url, 'status': c['status'], 'hash': c['hash'], 'checked': datetime.date.today().isoformat()}
            prev = old.get(url)
            rec['changed_since_last_check'] = bool(prev and prev.get('hash') and c['hash'] and prev['hash'] != c['hash'])
            pages.append(rec)
            if c['status'] is None or c['status'] >= 400:
                problems.append('%s -> HTTP %s' % (url, c['status']))
                continue
            for d in ev.get('deadlines', []):
                if d.get('date') and (d.get('url') == url or not d.get('url')) and not d.get('estimated'):
                    if not any(f.lower() in c['text'].lower() for f in spellings(d['date'])):
                        problems.append('%s: "%s" %s not found on %s' % (ev['id'], d['label'], d['date'], url))
            if rec['changed_since_last_check']:
                problems.append('%s changed since the last check' % url)
        if problems:
            flagged.append({'id': ev['id'], 'name': ev['name'], 'problems': problems})
            print('\n' + ev['id'])
            for p in problems: print('  ' + p)
    json.dump({'checked': datetime.date.today().isoformat(), 'pages': pages, 'flagged': flagged}, open(REPORT, 'w'), indent=1)
    print('\n%d meetings flagged of %d checked. Report: %s' % (len(flagged), len([e for e in db['events'] if not only or e['id'] in only]), REPORT))
    print('Flagged ids: ' + ','.join(f['id'] for f in flagged))


if __name__ == '__main__':
    main()
