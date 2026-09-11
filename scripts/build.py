#!/usr/bin/env python3
"""Build step for Conference Deadlines.

Sources
  data/site.json            title, subtitle and the field profiles (psychiatry, neurology, ...)
  data/meetings/*.json      one file per meeting series, each a JSON array of editions

Outputs (all generated, all committed, none edited by hand)
  data/events.json          the served database (all records plus site settings)
  index.html                the embedded snapshot between the DATA markers is replaced
  data/events.csv, data/deadlines.csv
  calendar.ics              subscription feed for every meeting
  calendar-<profile>.ics    subscription feed per field profile
  ics/<id>.ics              one calendar file per meeting
  <profile>/index.html      redirect stub so that /psychiatry/ opens the psychiatry view
  manifest-<profile>.webmanifest
  .cpanel.yml               the copy list is regenerated; the DEPLOYPATH line is kept as found

Usage: python3 scripts/build.py            (from the project root)
       python3 scripts/build.py --check    (validate only, write nothing)

A folder without data/meetings/ (a standalone copy made by scripts/make_subset.py) is built from data/events.json instead.
"""
import csv, datetime, glob, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'events.json')
SITE = os.path.join(ROOT, 'data', 'site.json')
MEETINGS = os.path.join(ROOT, 'data', 'meetings')
INDEX = os.path.join(ROOT, 'index.html')
GEO = os.path.join(ROOT, 'data', 'geo.json')
ICS_DIR = os.path.join(ROOT, 'ics')
CPANEL = os.path.join(ROOT, '.cpanel.yml')

TAGS = set('''general-psychiatry child-adolescent geriatric addiction forensic consultation-liaison neuroscience
psychopharmacology biological-psychiatry schizophrenia mood-disorders anxiety trauma suicide sleep autism adhd
eating-disorders ocd neuromodulation psychotherapy behavioral psychology education community emergency perinatal
genetics epidemiology global international psychosomatic clinical-trials cultural womens-mental-health neuropsychology health-services
epilepsy stroke headache movement-disorders multiple-sclerosis dementia neuromuscular neurocritical-care primary-care hospital-medicine geriatrics
palliative-care diabetes endocrine obesity cardiovascular electrophysiology interventional pulmonary critical-care emergency-medicine anesthesia oncology
cancer-research radiation-oncology hematology breast-cancer gastroenterology hepatology nephrology rheumatology infectious-disease pediatrics neonatology
obstetrics gynecology maternal-fetal reproductive surgery thoracic-surgery plastic-surgery orthopedics urology otolaryngology radiology neuroradiology imaging
nuclear-medicine pathology dermatology ophthalmology vision-research rehabilitation allergy immunology public-health medical-education residency informatics
decision-science health-economics quality-safety translational nicotine alcohol pharmacy nursing integrated-care student-resident-research
uiuc illinois entrepreneurship autonomic-disorders brain-injury delirium neurosurgery'''.split())
REMOVED_TAGS = {'industry-cme', 'regional-illinois', 'europe', 'resident-friendly'}
AREAS = set('''psychiatry neurology neuroscience psychology addiction-medicine internal-medicine family-medicine hospital-medicine geriatrics
palliative-care endocrinology cardiology pulmonary-critical-care emergency-medicine anesthesiology oncology hematology gastroenterology nephrology
rheumatology infectious-disease pediatrics obstetrics-gynecology surgery orthopedics urology otolaryngology radiology nuclear-medicine pathology
dermatology ophthalmology rehabilitation allergy-immunology public-health medical-education informatics health-services pharmacy nursing sleep-medicine'''.split())
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
REQUIRED = ['id', 'name', 'short_name', 'organizer', 'start_date', 'end_date', 'city', 'country', 'areas', 'tags', 'deadlines']


def series_key(eid):
    m = re.match(r'^(.*)-(19|20)\d{2}$', eid)
    return m.group(1) if m else eid


def kind_of(label):
    l = (label or '').lower()
    if 'open' in l: return 'opens'
    if re.search(r'notif|decision|accept', l): return 'notification'
    if re.search(r'regist|housing|hotel', l): return 'registration'
    if re.search(r'award|grant|fellow|scholar|travel', l): return 'award'
    return 'submission'


def load():
    """Return (site, events, origin) where origin maps id -> file the record came from."""
    site = json.load(open(SITE, encoding='utf-8')) if os.path.exists(SITE) else {}
    origin, events = {}, []
    files = sorted(glob.glob(os.path.join(MEETINGS, '*.json')))
    if files:
        for f in files:
            try:
                recs = json.load(open(f, encoding='utf-8'))
            except json.JSONDecodeError as e:
                sys.exit('error: %s is not valid JSON: %s' % (os.path.relpath(f, ROOT), e))
            if not isinstance(recs, list): sys.exit('error: %s must contain a JSON array' % os.path.relpath(f, ROOT))
            for r in recs:
                events.append(r); origin[r.get('id', '?')] = os.path.relpath(f, ROOT)
    else:
        db = json.load(open(DATA, encoding='utf-8'))
        events = db.get('events', [])
        for k in ('title', 'subtitle', 'profiles'):
            if k in db and k not in site: site[k] = db[k]
        for r in events: origin[r.get('id', '?')] = 'data/events.json'
    site.setdefault('title', 'Conference Deadlines')
    site.setdefault('subtitle', 'Research meetings and submission deadlines')
    site.setdefault('profiles', {})
    return site, events, origin


def validate(site, events, origin):
    errors, warnings, seen = [], [], {}
    for ev in events:
        eid = ev.get('id', '?')
        for k in REQUIRED:
            if k not in ev: errors.append('%s: missing field %s' % (eid, k))
        if eid in seen: errors.append('%s: duplicate id in %s and %s' % (eid, seen[eid], origin.get(eid)))
        seen[eid] = origin.get(eid)
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', str(eid)): errors.append('%s: id must be lower case kebab case' % eid)
        exp = series_key(eid) + '.json'
        if origin.get(eid, '').startswith('data/meetings/') and os.path.basename(origin[eid]) != exp:
            warnings.append('%s: lives in %s but the series file for this id would be data/meetings/%s' % (eid, origin[eid], exp))
        for k in ('start_date', 'end_date'):
            v = ev.get(k)
            if v is not None and not DATE.match(str(v)): errors.append('%s: %s is not YYYY-MM-DD (%r)' % (eid, k, v))
        if ev.get('start_date') and ev.get('end_date') and ev['end_date'] < ev['start_date']:
            errors.append('%s: end_date before start_date' % eid)
        if not ev.get('areas'): errors.append('%s: areas is empty; every record needs at least one area' % eid)
        for a in ev.get('areas', []):
            if a not in AREAS: warnings.append('%s: area %r is not in the vocabulary' % (eid, a))
        for t in ev.get('tags', []):
            if t not in TAGS: warnings.append('%s: tag %r is not in the vocabulary' % (eid, t))
        lat, lon = ev.get('lat'), ev.get('lon')
        if (lat is None) != (lon is None): errors.append('%s: lat and lon must both be set' % eid)
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180): errors.append('%s: lat/lon out of range' % eid)
        if ev.get('country') and not re.match(r'^[A-Z]{2}$', ev['country']): errors.append('%s: country must be ISO alpha-2' % eid)
        for d in ev.get('deadlines', []):
            if not d.get('label'): errors.append('%s: deadline without label' % eid)
            if d.get('date') is not None and not DATE.match(str(d['date'])): errors.append('%s: deadline %r has a bad date %r' % (eid, d.get('label'), d.get('date')))
        if not ev.get('start_date'): warnings.append('%s: no start_date published' % eid)
        for txt in (ev.get('description') or '', ev.get('notes') or ''):
            if '\u2014' in txt or '\u2013' in txt: warnings.append('%s: text contains an em or en dash' % eid)
    for key, p in site.get('profiles', {}).items():
        if not re.match(r'^[a-z0-9-]+$', key): errors.append('profile %r: key must be lower case letters, digits and hyphens (it becomes a folder name)' % key)
        if not p.get('label') or not p.get('subtitle'): errors.append('profile %r: label and subtitle are required' % key)
        for a in p.get('areas', []):
            if a not in AREAS: warnings.append('profile %r: area %r is not in the vocabulary' % (key, a))
        if not matches_any(events, p): warnings.append('profile %r matches no records' % key)
    return errors, warnings


def matches(ev, p):
    return bool(set(ev.get('areas', [])) & set(p.get('areas', []))) or bool(set(ev.get('tags', [])) & set(p.get('tags', [])))


def matches_any(events, p):
    return any(matches(e, p) for e in events)


# ---------- calendar files ----------

def ics_escape(s):
    return str(s or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r\n', '\\n').replace('\n', '\\n')


def fold(line):
    out, chunk, n = [], '', 0
    for ch in line:
        b = len(ch.encode('utf-8'))
        if n + b > 73:
            out.append(chunk); chunk = ' '; n = 1
        chunk += ch; n += b
    out.append(chunk)
    return '\r\n'.join(out)


def dstr(s):
    return s.replace('-', '')


def next_day(s):
    return (datetime.date.fromisoformat(s) + datetime.timedelta(days=1)).isoformat().replace('-', '')


def fmt_range(a, b):
    if not a: return 'dates not yet published'
    da = datetime.date.fromisoformat(a); db_ = datetime.date.fromisoformat(b) if b else da
    if da == db_: return da.strftime('%b %d, %Y').replace(' 0', ' ')
    if da.year != db_.year: return da.strftime('%b %d, %Y') + ' to ' + db_.strftime('%b %d, %Y')
    if da.month != db_.month: return da.strftime('%b %d') + ' to ' + db_.strftime('%b %d, %Y')
    return da.strftime('%b %d') + ' to ' + db_.strftime('%d, %Y')


def place(ev):
    parts = [p for p in (ev.get('city'), ev.get('region_name')) if p]
    if ev.get('country') and ev['country'] != 'US': parts.append(ev['country'])
    return ', '.join(parts)


def vevent(uid, start, end_excl, summary, description, location, url, alarms, stamp):
    L = ['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp, 'DTSTART;VALUE=DATE:' + start, 'DTEND;VALUE=DATE:' + end_excl, 'SUMMARY:' + ics_escape(summary)]
    if description: L.append('DESCRIPTION:' + ics_escape(description))
    if location: L.append('LOCATION:' + ics_escape(location))
    if url: L.append('URL:' + url)
    for days in alarms:
        L += ['BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:' + ics_escape(summary), 'TRIGGER:-P%dDT15H' % max(0, days - 1), 'END:VALARM']
    L.append('END:VEVENT')
    return L


def event_lines(ev, stamp, alarms=(30, 7, 1)):
    out = []
    loc = place(ev) + (', ' + ev['venue'] if ev.get('venue') else '')
    dls = [d for d in ev.get('deadlines', []) if d.get('date')]
    dl_text = '\n'.join('%s: %s%s' % (d['label'], d['date'], ' (estimated)' if d.get('estimated') else '') for d in dls)
    url = ev.get('edition_url') or ev.get('organizer_url') or ''
    desc = (ev.get('description') or '') + ('\n\nDeadlines\n' + dl_text if dl_text else '') + '\n\n' + url
    if ev.get('start_date'):
        out += vevent(ev['id'] + '@conference-calendar', dstr(ev['start_date']), next_day(ev.get('end_date') or ev['start_date']), ev['name'], desc.strip(), loc, url, [7], stamp)
    for d in dls:
        if kind_of(d['label']) in ('opens', 'notification'): continue
        summ = 'Deadline: %s %s%s' % (ev.get('short_name') or ev['name'], d['label'].lower(), ' (estimated)' if d.get('estimated') else '')
        dd = ((d.get('note') or '') + '\n' if d.get('note') else '') + 'Meeting: %s, %s, %s\n%s' % (ev['name'], fmt_range(ev.get('start_date'), ev.get('end_date')), loc, d.get('url') or url)
        slug = re.sub(r'[^a-z0-9]+', '-', d['label'].lower())
        out += vevent('%s-%s-%s@conference-calendar' % (ev['id'], dstr(d['date']), slug), dstr(d['date']), next_day(d['date']), summ, dd, loc, d.get('url') or url, list(alarms), stamp)
    return out


def calendar(lines, name):
    all_lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Conference Deadlines//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
                 'X-WR-CALNAME:' + ics_escape(name), 'X-PUBLISHED-TTL:P1D'] + lines + ['END:VCALENDAR']
    return '\r\n'.join(fold(l) for l in all_lines) + '\r\n'


# ---------- other outputs ----------

def write_csvs(events):
    cols = ['id', 'name', 'short_name', 'organizer', 'organizer_url', 'edition_url', 'areas', 'tags', 'start_date', 'end_date', 'format', 'city', 'region_name',
            'country', 'venue', 'lat', 'lon', 'description', 'deadlines', 'confidence', 'notes', 'sources']
    buf = io.StringIO(); w = csv.writer(buf, lineterminator='\r\n'); w.writerow(cols)
    for ev in events:
        row = dict(ev)
        row['areas'] = '; '.join(ev.get('areas', []))
        row['tags'] = '; '.join(ev.get('tags', []))
        row['deadlines'] = '; '.join('%s = %s%s' % (d['label'], d['date'], ' (estimated)' if d.get('estimated') else '') for d in ev.get('deadlines', []) if d.get('date'))
        row['sources'] = '; '.join(s['url'] for s in ev.get('sources', []) if s.get('url'))
        w.writerow([row.get(c, '') if row.get(c) is not None else '' for c in cols])
    open(os.path.join(ROOT, 'data', 'events.csv'), 'w', encoding='utf-8', newline='').write(buf.getvalue())
    buf = io.StringIO(); w = csv.writer(buf, lineterminator='\r\n')
    w.writerow(['event_id', 'meeting', 'deadline', 'date', 'estimated', 'kind', 'city', 'country', 'url'])
    for ev in events:
        for d in ev.get('deadlines', []):
            if not d.get('date'): continue
            w.writerow([ev['id'], ev['name'], d['label'], d['date'], 'yes' if d.get('estimated') else 'no', kind_of(d['label']), ev.get('city') or '', ev.get('country') or '', d.get('url') or ev.get('edition_url') or ''])
    open(os.path.join(ROOT, 'data', 'deadlines.csv'), 'w', encoding='utf-8', newline='').write(buf.getvalue())


def embed(html, marker, payload):
    start, end = '<!--%s-->' % marker, '<!--/%s-->' % marker
    i, j = html.index(start) + len(start), html.index(end)
    return html[:i] + payload + html[j:]


def redirect_stub(key, profile, title):
    target = '../?site=%s' % key
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta http-equiv="refresh" content="0; url=%s">\n'
            '<title>%s: %s</title>\n<link rel="canonical" href="%s">\n</head>\n<body>\n<p>Opening the %s view. <a href="%s">Continue</a></p>\n'
            '<script>location.replace("%s" + location.hash);</script>\n</body>\n</html>\n') % (target, title, profile['label'], target, profile['label'].lower(), target, target)


def write_cpanel(profiles):
    deploy = '$HOME/public_html/'
    if os.path.exists(CPANEL):
        m = re.search(r'export DEPLOYPATH=(\S+)', open(CPANEL).read())
        if m: deploy = m.group(1)
    lines = ['---',
             '# cPanel Git Version Control deployment. Runs when you click "Deploy HEAD Commit" in cPanel',
             '# (Files, Git Version Control, Manage, Pull or Deploy) or when you push directly to the cPanel repository.',
             '# The copy list below is regenerated by scripts/build.py; only the DEPLOYPATH line is kept as you set it.',
             'deployment:', '  tasks:',
             '    - export DEPLOYPATH=' + deploy,
             '    - /bin/mkdir -p $DEPLOYPATH',
             '    - /bin/cp index.html manifest.webmanifest calendar.ics $DEPLOYPATH',
             '    - /bin/cp -R data icons ics $DEPLOYPATH']
    for key in sorted(profiles):
        lines.append('    - /bin/cp calendar-%s.ics manifest-%s.webmanifest $DEPLOYPATH' % (key, key))
        lines.append('    - /bin/cp -R %s $DEPLOYPATH' % key)
    open(CPANEL, 'w').write('\n'.join(lines) + '\n')


def main():
    check = '--check' in sys.argv
    site, events, origin = load()
    for ev in events:
        if 'region_name' not in ev and 'region' in ev: ev['region_name'] = ev.pop('region')
        for d in ev.get('deadlines', []): d.setdefault('estimated', False)
        ev['tags'] = [t for t in ev.get('tags', []) if t not in REMOVED_TAGS]
    events.sort(key=lambda e: (e.get('start_date') or '9999', e['id']))
    errors, warnings = validate(site, events, origin)
    for w in warnings: print('warning:', w)
    for e in errors: print('error:', e)
    if errors:
        print('%d error(s). Nothing written.' % len(errors)); sys.exit(1)
    profiles = site.get('profiles', {})
    print('%d meetings, %d deadlines, %d profiles, %d warnings' % (len(events), sum(len(e.get('deadlines', [])) for e in events), len(profiles), len(warnings)))
    if check: return
    today = datetime.date.today().isoformat()
    db = {'generated': today, 'title': site['title'], 'subtitle': site['subtitle'], 'profiles': profiles, 'events': events}
    json.dump(db, open(DATA, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    html = open(INDEX, encoding='utf-8').read()
    html = embed(html, 'DATA', json.dumps(db, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    if os.path.exists(GEO): html = embed(html, 'GEO', open(GEO, encoding='utf-8').read().strip())
    open(INDEX, 'w', encoding='utf-8').write(html)
    write_csvs(events)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    os.makedirs(ICS_DIR, exist_ok=True)
    for f in os.listdir(ICS_DIR):
        if f.endswith('.ics'): os.remove(os.path.join(ICS_DIR, f))
    per_event = {}
    for ev in events:
        per_event[ev['id']] = event_lines(ev, stamp)
        open(os.path.join(ICS_DIR, ev['id'] + '.ics'), 'w', encoding='utf-8', newline='').write(calendar(per_event[ev['id']], ev['name']))
    open(os.path.join(ROOT, 'calendar.ics'), 'w', encoding='utf-8', newline='').write(calendar(sum(per_event.values(), []), site['title']))
    for f in glob.glob(os.path.join(ROOT, 'calendar-*.ics')) + glob.glob(os.path.join(ROOT, 'manifest-*.webmanifest')): os.remove(f)
    base_manifest = json.load(open(os.path.join(ROOT, 'manifest.webmanifest')))
    for key, p in profiles.items():
        lines = sum((per_event[e['id']] for e in events if matches(e, p)), [])
        open(os.path.join(ROOT, 'calendar-%s.ics' % key), 'w', encoding='utf-8', newline='').write(calendar(lines, '%s: %s' % (site['title'], p['label'])))
        m = dict(base_manifest); m['name'] = '%s: %s' % (site['title'], p['label']); m['short_name'] = p['label']; m['start_url'] = './?site=%s' % key
        json.dump(m, open(os.path.join(ROOT, 'manifest-%s.webmanifest' % key), 'w'), indent=2)
        os.makedirs(os.path.join(ROOT, key), exist_ok=True)
        open(os.path.join(ROOT, key, 'index.html'), 'w', encoding='utf-8').write(redirect_stub(key, p, site['title']))
    write_cpanel(profiles)
    print('wrote data/events.json, index.html snapshot, CSV files, calendar.ics, %d files in ics/, and %s' % (
        len(events), ', '.join('/%s/ with calendar-%s.ics' % (k, k) for k in sorted(profiles)) or 'no profile files'))


if __name__ == '__main__':
    main()
