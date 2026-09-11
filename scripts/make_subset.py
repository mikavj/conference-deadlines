#!/usr/bin/env python3
"""Create a specialty copy of the site with a filtered database.

Usage:
  python3 scripts/make_subset.py --out ../conference-calendar-neurology \
      --areas neurology,neuroscience --tags uiuc \
      --subtitle "Neurology research meetings and submission deadlines" --discipline neurology --subdir neurology

Records are kept when any of their areas is in --areas OR any of their tags is in --tags.
The target folder receives index.html, manifest.webmanifest, .cpanel.yml, icons/, scripts/, docs/, data/geo.json,
data/zip5.json, data/schema.md and README.md from this project, plus the filtered data/events.json; the build then runs there.
Re-run the command to refresh the copy after the main database changes (the copy's own edits are overwritten).
"""
import argparse, json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--areas', default='')
ap.add_argument('--tags', default='')
ap.add_argument('--subtitle', required=True)
ap.add_argument('--discipline', required=True)
ap.add_argument('--subdir', default='', help='folder under public_html that this copy deploys to on cPanel, e.g. psychiatry')
args = ap.parse_args()
areas = set(a.strip() for a in args.areas.split(',') if a.strip())
tags = set(t.strip() for t in args.tags.split(',') if t.strip())
out = os.path.abspath(args.out)
os.makedirs(os.path.join(out, 'data'), exist_ok=True)
for f in ['index.html', 'manifest.webmanifest', '.cpanel.yml', 'README.md', '.gitignore']:
    if os.path.exists(os.path.join(ROOT, f)): shutil.copy(os.path.join(ROOT, f), out)
if args.subdir:
    cp = os.path.join(out, '.cpanel.yml'); y = open(cp).read()
    y = y.replace('export DEPLOYPATH=$HOME/public_html/', 'export DEPLOYPATH=$HOME/public_html/%s/' % args.subdir.strip('/'))
    open(cp, 'w').write(y)
for d in ['icons', 'scripts', 'docs']:
    shutil.copytree(os.path.join(ROOT, d), os.path.join(out, d), dirs_exist_ok=True)
for f in ['geo.json', 'zip5.json', 'schema.md']:
    shutil.copy(os.path.join(ROOT, 'data', f), os.path.join(out, 'data', f))
db = json.load(open(os.path.join(ROOT, 'data', 'events.json'), encoding='utf-8'))
keep = [e for e in db['events'] if (areas & set(e.get('areas', []))) or (tags & set(e.get('tags', [])))]
db['events'] = keep
db['subtitle'] = args.subtitle
db['discipline'] = args.discipline
db['profiles'] = {}
json.dump(db, open(os.path.join(out, 'data', 'events.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump({'title': db.get('title', 'Conference Deadlines'), 'subtitle': args.subtitle, 'profiles': {}}, open(os.path.join(out, 'data', 'site.json'), 'w', encoding='utf-8'), indent=1)
print('%d of %d records kept for %s' % (len(keep), len(json.load(open(os.path.join(ROOT, 'data', 'events.json')))['events']), out))
subprocess.run([sys.executable, os.path.join(out, 'scripts', 'build.py')], check=True)
