#!/usr/bin/env python3
"""
Rebuild the card layouts ("parameters") of keywords_with_parameters.json from
the local Radioss "LS-DYNA input" documentation pages.

Card layout tables in these pages look like::

    (1)     | (2)    | (3) | ... | (8)          <- column header
    *PART_{OPTION1}                              <- keyword line (skipped)
    part_title                                   <- title card (one wide field)
    part_ID | sec_ID | mat_ID | HGID | EOSID | | |

Every row below the header that is not the keyword line becomes one card.
Each cell is one field (a cell spanning several columns is still one field in
free format); empty cells are kept as unnamed placeholder fields so later
fields stay in position.

Each table is one card group. The text in front of a later table says when
its cards are used, e.g. "OPTION1 = INERTIA, insert the following lines";
this is stored per card as ``condition``, the parsed ``options``,
``repeat`` (the card may be given several times) and ``optional`` (the
group is only written when filled in).

The script also
  - finds the keyword's own documentation page when the database only links
    to an overview page (e.g. all *MAT_* keywords), and makes the link absolute,
  - stores the keyword as written in a deck under ``keyword``
    (e.g. "*MAT_001 (ELASTIC)" -> "*MAT_ELASTIC").

Afterwards the per-field defaults and descriptions are added again (see
extract_field_info.py).

Usage:
    python3 tools/keyword_db/extract_cards.py [--docs DIR] [--db FILE] [--dry-run]
"""

import argparse
import difflib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

import extract_field_info

ROOT = Path(__file__).resolve().parents[2]
DOC_DIRS = [ROOT / 'data' / 'local_documentation', ROOT / 'data' / 'docs']
DOC_BASE_URL = 'https://help.altair.com/hwsolvers/rad/topics/solvers/rad/'
# Standard cards have 8 fields; element/node cards (8-character fields) up to 10
FIELDS_PER_CARD = 10
COLUMN_HEADER = re.compile(r'^\(\d+\)$')
OPTION = re.compile(r'(OPTION\d?)\s*=\s*([A-Z][A-Z0-9_]*)')
# Intro text of a card group that marks it as optional (only written when filled in)
OPTIONAL_HINT = re.compile(r'\b(optional|insert|add|if|repeat)\b', re.IGNORECASE)
# Pages whose names differ too much from the keyword to be found automatically
PAGE_OVERRIDES = {'*EOS_001 (LINEAR_POLYNOMIAL)': 'eos_polynomial_lsdyna_r.htm'}
PAGE_SUFFIXES = ('_lsdyna_r.htm', '_lsdayna_r.htm', '_ls_dyna_r.htm', '_r.htm', '.htm')


def cell_text(cell):
    return re.sub(r'\s+', ' ', cell.get_text(' ', strip=True)).strip()


def is_layout_table(rows):
    """A card layout table starts with a (1) (2) ... column header row."""
    if not rows:
        return False
    header = [cell_text(c) for c in rows[0].find_all(['td', 'th'])]
    return len(header) >= 2 and all(COLUMN_HEADER.match(h) for h in header if h) and any(header)


def text_before(table):
    """Text between the previous table (or the page start) and ``table``."""
    parts = []
    for element in table.previous_elements:
        if getattr(element, 'name', None) == 'table':
            break
        if isinstance(element, NavigableString) and element.strip() and element.find_parent('table') is None:
            parts.append(element.strip())
    return re.sub(r'\s+', ' ', ' '.join(reversed(parts))).replace(' ,', ',').strip()


def parse_page(html_path):
    """Return (keyword line, cards) documented on a page.

    Each card is a dict with ``names`` (field names), ``group`` (table index),
    ``condition`` (intro text of later groups), ``options``, ``repeat`` and ``optional``.
    """
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
    keyword_line, cards, group = '', [], -1
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not is_layout_table(rows):
            continue
        group += 1
        condition = text_before(table) if group else ''
        options = dict(OPTION.findall(condition))
        repeat = 'repeat' in condition.lower()
        optional = bool(options or OPTIONAL_HINT.search(condition))
        for row in rows[1:]:
            names = [cell_text(c) for c in row.find_all(['td', 'th'])]
            if not any(names):
                continue
            if len(names) == 1 and names[0].startswith('*'):
                keyword_line = keyword_line or names[0]
                continue
            if all(COLUMN_HEADER.match(n) for n in names if n):
                continue  # repeated column header
            names = names[:FIELDS_PER_CARD]
            while names and not names[-1]:
                names.pop()
            cards.append({'names': names, 'group': group, 'condition': condition,
                          'options': options, 'repeat': repeat, 'optional': optional})
    return keyword_line, cards


def parse_cards(html_path):
    """Return the list of cards (lists of field names) documented on a page."""
    return [card['names'] for card in parse_page(html_path)[1]]


def deck_keyword(keyword_line, name):
    """Keyword as written in a deck: last alternative, without {OPTION} placeholders."""
    candidates = re.findall(r'\*[A-Z0-9_{}\-]+', keyword_line or '') or [name.split(' (')[0]]
    return re.sub(r'_?\{[^}]*\}', '', candidates[-1])


def compact(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def page_stem(filename):
    for suffix in PAGE_SUFFIXES:
        if filename.endswith(suffix):
            return filename[:-len(suffix)]
    return filename


def find_doc_page(keyword, pages):
    """Return the documentation page of ``keyword`` from ``pages`` ({filename: path})."""
    if PAGE_OVERRIDES.get(keyword['name']) in pages:
        return pages[PAGE_OVERRIDES[keyword['name']]]
    linked = extract_field_info.doc_file_for(keyword, Path('.'))
    if linked and linked.name in pages and not linked.name.endswith(('mat_lsdyna_r.htm',)):
        stem = page_stem(linked.name)
        if '_' in stem:  # not an overview page like control_lsdyna_r.htm
            return pages[linked.name]

    name = re.sub(r'\{[^}]*\}', '', keyword['name'].lstrip('*'))
    by_compact = {compact(page_stem(f)): f for f in pages}
    wanted = compact(name)
    if wanted in by_compact:
        return pages[by_compact[wanted]]
    code = re.match(r'(MAT_[A-Z]?\d+(?:_[A-Z]+)?)\s*\(', name)
    if code:
        prefix = compact(code.group(1))
        hits = [f for c, f in by_compact.items() if c.startswith(prefix)]
        # MAT_001 must not match MAT_001_FLUID: prefer the page whose words follow the code
        exact = [f for f in hits if compact(page_stem(f)).startswith(wanted[:len(prefix) + 3])]
        hits = exact or hits
        if len(hits) == 1:
            return pages[hits[0]]
    close = difflib.get_close_matches(wanted, list(by_compact), n=1, cutoff=0.85)
    return pages[by_compact[close[0]]] if close else None


def to_parameters(cards):
    """Convert cards to the database schema used by the workbench."""
    parameters = []
    for card_info in cards:
        names = card_info['names']
        card = {f'field_{i}': (names[i] if i < len(names) else '') for i in range(FIELDS_PER_CARD)}
        card['name'] = next((n for n in names if n), '')
        card['description'] = ''
        card['group'] = card_info['group']
        if card_info['condition']:
            card['condition'] = card_info['condition']
        if card_info['options']:
            card['options'] = card_info['options']
        if card_info['repeat']:
            card['repeat'] = True
        if card_info['optional']:
            card['optional'] = True
        parameters.append(card)
    return parameters


def field_names(parameters):
    return [[p.get(f'field_{i}', '') for i in range(FIELDS_PER_CARD)] for p in parameters or []]


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--docs', type=Path, nargs='+', default=DOC_DIRS,
                        help='Documentation directories, searched in order')
    parser.add_argument('--db', type=Path, default=extract_field_info.DEFAULT_DB)
    parser.add_argument('--dry-run', action='store_true', help='Only report what would change')
    args = parser.parse_args()

    keywords = json.loads(args.db.read_text(encoding='utf-8'))
    pages = {}
    for doc_dir in reversed(args.docs):  # earlier directories win
        pages.update({p.name: p for p in doc_dir.glob('*.htm')})
    stats = {'no_page': [], 'no_cards': [], 'new': 0, 'changed': [], 'same': 0, 'relinked': 0}

    for keyword in keywords:
        doc_file = find_doc_page(keyword, pages)
        if not doc_file:
            stats['no_page'].append(keyword['name'])
            continue
        url = DOC_BASE_URL + doc_file.name
        if keyword.get('documentation') != url:
            stats['relinked'] += 1
            keyword['documentation'] = url
        keyword['doc_page'] = doc_file.name
        keyword_line, cards = parse_page(doc_file)
        keyword['keyword'] = deck_keyword(keyword_line, keyword['name'])
        parameters = to_parameters(cards)
        if not parameters:
            stats['no_cards'].append(keyword['name'])
            keyword['parameters'] = []
            continue
        old = field_names(keyword.get('parameters'))
        new = field_names(parameters)
        if not old:
            stats['new'] += 1
        elif old != new:
            stats['changed'].append(keyword['name'])
        else:
            stats['same'] += 1
        keyword['parameters'] = parameters

    with_cards = sum(1 for k in keywords if k.get('parameters'))
    print(f"Keywords: {len(keywords)}, with cards now: {with_cards}")
    print(f"  newly filled: {stats['new']}, unchanged: {stats['same']}, changed: {len(stats['changed'])}, "
          f"documentation link fixed: {stats['relinked']}")
    if stats['changed']:
        print(f"  changed: {', '.join(stats['changed'])}")
    if stats['no_cards']:
        print(f"  page without card table: {', '.join(stats['no_cards'])}")
    if stats['no_page']:
        print(f"  no local page: {', '.join(stats['no_page'])}")

    if args.dry_run:
        return
    args.db.write_text(json.dumps(keywords, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Updated {args.db}; adding defaults and descriptions ...")
    import sys
    sys.argv = [sys.argv[0], '--docs', *map(str, args.docs), '--db', str(args.db)]
    extract_field_info.main()


if __name__ == '__main__':
    main()
