"""
Interested companies -> LinkedIn company IDs.

Reads every .txt file in interested_companies/ (one company per line), looks each
name up with LinkedIn's public company typeahead, and caches the result in
interested_companies/company_ids.json so lookups only happen once.

The IDs drive two filters:
  - job search:     f_C=<id,...>              (only jobs posted by these companies)
  - people search:  currentCompany=["<id>"]   (only people who work there NOW)

Review / refresh the mapping:
    python company_directory.py            # look up new names, print the mapping
    python company_directory.py --refresh  # look every name up again

If a name maps to the wrong company page, edit company_ids.json by hand
(set "id" to the right number, or null to ignore that company).
"""
import glob
import json
import os
import re
import sys
import time

import requests

COMPANIES_DIR = 'interested_companies'
CACHE_FILE = os.path.join(COMPANIES_DIR, 'company_ids.json')
TYPEAHEAD_URL = 'https://www.linkedin.com/jobs-guest/api/typeaheadHits'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/129 Safari/537.36'}

# Words that don't distinguish one company from another when comparing names
NOISE_WORDS = {'inc', 'llc', 'ltd', 'limited', 'pvt', 'private', 'corp', 'corporation', 'co',
               'company', 'plc', 'gmbh', 'ag', 'sa', 'india', 'in', 'the', 'group', 'global',
               'technologies', 'technology', 'tech', 'labs', 'software', 'systems', 'solutions'}


def normalize(name):
    words = re.sub(r'[^a-z0-9& ]', ' ', str(name).lower().replace('&', ' & ')).split()
    core = [w for w in words if w not in NOISE_WORDS]
    return ' '.join(core or words)


def load_interested():
    """Unique company names from every list file, in file order."""
    names, seen = [], set()
    for path in sorted(glob.glob(os.path.join(COMPANIES_DIR, '*.txt'))):
        with open(path) as f:
            for line in f:
                name = line.strip()
                if name and not name.startswith('#') and name.lower() not in seen:
                    seen.add(name.lower())
                    names.append(name)
    return names


def _load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def lookup(name):
    """Best LinkedIn company page for a name: exact name match first, then a close prefix match."""
    for attempt in range(3):
        resp = requests.get(TYPEAHEAD_URL, headers=UA, timeout=15,
                            params={'origin': 'jserp', 'typeaheadType': 'COMPANY', 'query': name})
        if resp.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        resp.raise_for_status()
        break
    else:
        return None
    hits = [h for h in resp.json() if h.get('type') == 'COMPANY']
    target = normalize(name)
    for hit in hits:
        if normalize(hit['displayName']) == target:
            return {'id': hit['id'], 'display': hit['displayName']}
    for hit in hits[:3]:
        display = normalize(hit['displayName'])
        if display.startswith(target + ' ') or target.startswith(display + ' '):
            return {'id': hit['id'], 'display': hit['displayName']}
    return {'id': None, 'display': None}


def company_ids(refresh=False, verbose=False):
    """{company name: linkedin company id} for every interested company that has a page."""
    cache = _load_cache()
    names = load_interested()
    missing = [n for n in names if refresh or n not in cache]
    if missing:
        print(f"🏢 Looking up LinkedIn pages for {len(missing)} companies...")
        for i, name in enumerate(missing, 1):
            try:
                result = lookup(name)
            except requests.RequestException as e:
                print(f"   ⚠️  {name}: {e}")
                continue
            if result is not None:
                cache[name] = result
            if verbose:
                shown = f"{result['display']} ({result['id']})" if result and result['id'] else 'NOT FOUND'
                print(f"   [{i}/{len(missing)}] {name:<32} -> {shown}")
            if i % 20 == 0:
                _save_cache(cache)
            time.sleep(0.7)
        _save_cache(cache)
    return {n: cache[n]['id'] for n in names if cache.get(n, {}).get('id')}


def id_for(company_name):
    """LinkedIn company ID for one name (interested list first, otherwise a fresh lookup)."""
    cache = _load_cache()
    for name, entry in cache.items():
        if entry.get('id') and normalize(name) == normalize(company_name):
            return entry['id']
    result = lookup(company_name)
    return result['id'] if result else None


if __name__ == '__main__':
    ids = company_ids(refresh='--refresh' in sys.argv, verbose=True)
    cache = _load_cache()
    names = load_interested()
    not_found = [n for n in names if not cache.get(n, {}).get('id')]
    print(f"\n✅ {len(ids)}/{len(names)} companies mapped to a LinkedIn page  (saved: {CACHE_FILE})")
    for n in names:
        e = cache.get(n, {})
        if e.get('id') and normalize(e['display']) != normalize(n):
            print(f"   ⚠️  check: {n!r} -> {e['display']!r} ({e['id']})")
    if not_found:
        print(f"   ❌ not found ({len(not_found)}): {', '.join(not_found)}")
