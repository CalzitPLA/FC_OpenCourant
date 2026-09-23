#!/usr/bin/env python3
"""
Add per-field default values and descriptions to keywords_with_parameters.json.

The Radioss "LS-DYNA input" documentation pages have a table
``Field | Contents | SI Unit Example``. For every card field of every keyword
this script looks up the field in that table and stores

    card["defaults"]    = {"field_3": "0", ...}      (only fields with a default)
    card["field_help"]  = {"field_3": "Poisson's ratio. Default = 0 (Real)", ...}

Defaults are taken from "Default = <number>" or, in option lists, from the
first value of "= <number> ... (Default)".

Usage:
    python3 tools/keyword_db/extract_field_info.py [--docs DIR] [--db FILE]

Requirements:
    - beautifulsoup4 library: pip install beautifulsoup4
"""

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS = [ROOT / 'data' / 'local_documentation', ROOT / 'data' / 'docs']
DEFAULT_DB = ROOT / 'freecad' / 'ORfemn' / 'keywords_with_parameters.json'

FIELDS_PER_CARD = 10
NUMBER = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
DEFAULT_EQUALS = re.compile(r'default\s*=\s*(' + NUMBER + r')', re.IGNORECASE)
DEFAULT_OPTION = re.compile(r'=\s*(' + NUMBER + r')(?:\s*or\s*' + NUMBER + r')*\s*\(default\)', re.IGNORECASE)
MAX_HELP_LENGTH = 300


def normalize(name):
    """Normalize a field name for matching.

    Whitespace is dropped because the docs split subscripts off with a space
    ('surf_ID ex') while the card headers in the database join them ('surf_IDex').
    """
    return re.sub(r'\s+', '', name).lower()


def base_name(name):
    """Field name without a trailing parenthetical, e.g. 'VID (I)' -> 'vid'."""
    return normalize(re.sub(r'\([^)]*\)\s*$', '', name))


def parse_default(contents):
    match = DEFAULT_EQUALS.search(contents) or DEFAULT_OPTION.search(contents)
    return match.group(1) if match else None


def parse_field_table(html_path):
    """Return {normalized field name: contents text} from the page's field tables."""
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
    fields = {}
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not rows:
            continue
        header = [c.get_text(' ', strip=True).lower() for c in rows[0].find_all(['td', 'th'])]
        if len(header) < 2 or header[0] != 'field' or not header[1].startswith('content'):
            continue
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            name = cells[0].get_text(' ', strip=True)
            contents = re.sub(r'\s+', ' ', cells[1].get_text(' ', strip=True))
            if name:
                fields.setdefault(normalize(name), contents)
                fields.setdefault(base_name(name), contents)
    return fields


def doc_file_for(keyword, docs_dir):
    match = re.search(r'/rad/([^/]+_lsdyna_r\.htm)', keyword.get('documentation', ''))
    return docs_dir / match.group(1) if match else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--docs', type=Path, nargs='+', default=DEFAULT_DOCS,
                        help='Directories with the *_lsdyna_r.htm pages, searched in order')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB, help='keywords_with_parameters.json to update')
    args = parser.parse_args()

    keywords = json.loads(args.db.read_text(encoding='utf-8'))
    n_fields = n_help = n_defaults = n_missing_docs = 0

    for keyword in keywords:
        cards = keyword.get('parameters') or []
        if not cards:
            continue
        doc_file = None
        for doc_dir in args.docs:
            name = keyword.get('doc_page') or getattr(doc_file_for(keyword, doc_dir), 'name', None)
            if name and (doc_dir / name).exists():
                doc_file = doc_dir / name
                break
        if not doc_file:
            n_missing_docs += 1
            continue
        table = parse_field_table(doc_file)

        for card in cards:
            defaults, field_help = {}, {}
            for i in range(FIELDS_PER_CARD):
                name = card.get(f'field_{i}', '')
                if not name:
                    continue
                n_fields += 1
                # 'NID/set_ID' may be documented as one row or as its parts
                candidates = [name] + name.split('/')
                contents = next((table.get(normalize(c)) or table.get(base_name(c))
                                 for c in candidates
                                 if table.get(normalize(c)) or table.get(base_name(c))), None)
                if not contents:
                    continue
                field_help[f'field_{i}'] = contents[:MAX_HELP_LENGTH]
                n_help += 1
                default = parse_default(contents)
                if default is not None:
                    defaults[f'field_{i}'] = default
                    n_defaults += 1
            card['defaults'] = defaults
            card['field_help'] = field_help

    args.db.write_text(json.dumps(keywords, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Fields: {n_fields}, with description: {n_help}, with default: {n_defaults}")
    if n_missing_docs:
        print(f"Keywords without a local documentation page: {n_missing_docs}")
    print(f"Updated {args.db}")


if __name__ == '__main__':
    main()
