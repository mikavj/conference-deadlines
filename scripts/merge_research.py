#!/usr/bin/env python3
"""Merge research files (JSON arrays of meeting records) into data/meetings/.

Usage: python3 scripts/merge_research.py file1.json [file2.json ...]

Each record goes into the series file for its id: the id without its trailing year, so
aagp-annual-2027 and aagp-annual-2028 both live in data/meetings/aagp-annual.json.
A record whose id already exists anywhere is replaced in place; a new id is appended to
its series file, which is created if needed. Run scripts/build.py afterwards.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEETINGS = os.path.join(ROOT, 'data', 'meetings')


def series_key(eid):
    m = re.match(r'^(.*)-(19|20)\d{2}$', eid)
    return m.group(1) if m else eid


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    os.makedirs(MEETINGS, exist_ok=True)
    files = {}
    where = {}
    for f in glob.glob(os.path.join(MEETINGS, '*.json')):
        recs = json.load(open(f, encoding='utf-8'))
        files[f] = recs
        for r in recs: where[r['id']] = f
    changed, added, replaced = set(), 0, 0
    for path in sys.argv[1:]:
        items = json.load(open(path, encoding='utf-8'))
        if isinstance(items, dict): items = items.get('events', [])
        for e in items:
            if not e.get('id'): sys.exit('error: a record in %s has no id' % path)
            if e['id'] in where:
                f = where[e['id']]
                files[f] = [e if r['id'] == e['id'] else r for r in files[f]]
                replaced += 1
            else:
                f = os.path.join(MEETINGS, series_key(e['id']) + '.json')
                files.setdefault(f, []).append(e); where[e['id']] = f
                added += 1
            changed.add(f)
    for f in changed:
        files[f].sort(key=lambda r: (r.get('start_date') or '9999', r['id']))
        json.dump(files[f], open(f, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('%d added, %d replaced, %d series files written. Now run: python3 scripts/build.py' % (added, replaced, len(changed)))


if __name__ == '__main__':
    main()
