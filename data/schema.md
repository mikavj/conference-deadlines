# Database schema

Source files: `data/site.json` (title, subtitle, field profiles) and `data/meetings/<series>.json`, one file per meeting series holding a JSON array of Meeting records (all editions of that meeting). The series name is the id without its trailing year. `scripts/build.py` validates these and assembles `data/events.json`, the served file:

```
{
  "generated": "2026-09-11",        set by the build script
  "title": "Conference Deadlines",
  "subtitle": "...",
  "profiles": { "psychiatry": { "label", "subtitle", "areas": [...], "tags": [...] }, ... },
  "events": [ Meeting, ... ]
}
```

A profile includes a record when any of the record's areas is in the profile's `areas` or any of its tags is in the profile's `tags`.

## Meeting

| Field | Type | Notes |
|---|---|---|
| id | string | Unique, kebab case, stable across rebuilds (`aagp-annual-2027`). Used in share links, calendar UIDs and `ics/<id>.ics`. Never rename an id once published: share links carry tracked and hidden ids, and calendar subscriptions match events by UID. A new edition gets a new id with its year. |
| name | string | Full meeting name with year. |
| short_name | string | Label used in calendar cells and file names (`AAGP 2027`). |
| organizer | string | Society or company. |
| organizer_url | string or null | |
| edition_url | string or null | Page for this specific edition. |
| areas | array of strings | Required, at least one, from the area vocabulary in `scripts/build.py` (psychiatry, neurology, cardiology, ...). Decides which field profiles show the record. |
| tags | array of strings | Controlled vocabulary listed below. |
| start_date, end_date | `YYYY-MM-DD` or null | Null when the edition is announced without dates. |
| city | string | |
| region_name | string or null | State, province or country subdivision. Research files may use `region`; the build renames it. |
| country | string | ISO 3166 alpha-2 (`US`, `CA`, `GB`). Drives the region filter. |
| venue | string or null | |
| lat, lon | number or null | Decimal degrees of the venue or city. Both or neither. |
| format | `in-person`, `hybrid`, `virtual` or null | |
| description | string | One or two factual sentences. No promotional language, no emojis, no dashes. |
| deadlines | array of Deadline | Sorted by the app; order in the file does not matter. |
| prior_edition | object or null | `{year, start_date, end_date, city, deadlines:[{label, date}]}`. Shown in the detail panel and used to justify estimates. |
| sources | array | `{url, accessed, note}`. Listed in the detail panel and in the Data sources panel. |
| confidence | `high`, `medium`, `low` | Shown in the detail panel. |
| notes | string or null | Maintainer notes shown after the confidence rating. |

## Deadline

| Field | Type | Notes |
|---|---|---|
| label | string | Free text. Words in the label decide the kind: `open` = submission opens (informational, no countdown); `notif`, `decision`, `accept` = notification; `regist`, `housing`, `hotel` = registration (triangle mark); `award`, `grant`, `fellow`, `scholar`, `travel` = award (triangle mark); anything else = submission (square mark, used for countdowns). |
| date | `YYYY-MM-DD` | Deadlines without a date are dropped by the app. |
| url | string or null | Page where the date is stated. |
| estimated | boolean | True when the date is inferred from the prior edition. Shown as an outlined square and labelled "estimated". |
| note | string or null | Time of day, time zone, membership requirements. |

## Share link compatibility

Share links encode filter values and ids and carry a version field (`sv`). On load the page drops any topic or area that the current database no longer has, ignores tracked or hidden ids it cannot find (they stay in the link and return if the record returns), and treats every setting as optional, so links made against an earlier database keep working after new meetings, areas or tags are added.

## Tags

general-psychiatry, child-adolescent, geriatric, addiction, forensic, consultation-liaison, neuroscience, psychopharmacology, biological-psychiatry, schizophrenia, mood-disorders, anxiety, trauma, suicide, sleep, autism, adhd, eating-disorders, ocd, neuromodulation, psychotherapy, behavioral, psychology, education, community, emergency, perinatal, genetics, epidemiology, global, europe, international, regional-illinois, resident-friendly, psychosomatic, industry-cme, clinical-trials, cultural, womens-mental-health, neuropsychology, health-services, the specialty tags listed in `scripts/build.py`, `uiuc` (University of Illinois campus and system events) and `illinois` (state level events)

Add new tags to the `TAGS` set in `scripts/build.py` and to `TAG_LABELS` in `index.html` (the app falls back to the raw tag when no label exists).

## Adding another field

Add records with the new area in `data/meetings/`, then add a profile for it in `data/site.json` and rebuild. The build creates `/<key>/`, its calendar feed and manifest.
