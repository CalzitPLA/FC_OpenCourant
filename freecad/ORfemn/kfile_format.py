"""
Helpers for building LS-DYNA keyword (.k) text.

This module deliberately has no FreeCAD or Qt imports so it can be used and
tested with a plain Python interpreter.

Cards are written in LS-DYNA free format (comma separated). An empty field
between commas means "use the default value", and an empty line is a card
with all fields at their defaults.
"""

import json
import os
import re

# Maximum fields per card: standard cards have 8 fields of 10 characters,
# node/element cards up to 10 fields of 8 characters.
FIELDS_PER_CARD = 10

# Template levels, from simplest to most complete
TEMPLATE_LEVELS = ("minimal", "basic", "full")

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.json")

# Keywords that frame a deck; they are added once by build_k_file().
_FRAME_KEYWORDS = ("*KEYWORD", "*END")

BASIC_K_FILE = """\
*KEYWORD
*TITLE
Basic LS-DYNA Model - Getting Started
$
$ Basic LS-DYNA input file template (fixed format)
$ Units: mm, t, s, N, MPa
$ Created by FreeCAD OpenRadioss Workbench
$
*CONTROL_TERMINATION
$#  endtim    endcyc     dtmin    endeng    endmas
     0.001
*CONTROL_TIMESTEP
$#  dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st
       0.0       0.9
*CONTROL_OUTPUT
$#   npopt    neecho    nrefup    iaccop     opifs    ipnint    ikedit    iflush
         1         1         1         1
*DATABASE_BINARY_D3PLOT
$#      dt      lcdt      beam     npltc    psetid
    1.0e-5
*DATABASE_BINARY_D3THDT
$#      dt      lcdt      beam     npltc    psetid
    1.0e-5
*DATABASE_GLSTAT
$#      dt    binary      lcur     ioopt
    1.0e-5
*DATABASE_MATSUM
$#      dt    binary      lcur     ioopt
    1.0e-5
*PART
$# title
Plate
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
         1         1         1
*SECTION_SHELL
$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp
         1         2     0.833         3
$#      t1        t2        t3        t4      nloc     marea      idof    edgset
       1.0       1.0       1.0       1.0
*MAT_ELASTIC
$#     mid        ro         e        pr
         1   7.85e-9  210000.0       0.3
*NODE
$#   nid               x               y               z      tc      rc
       1             0.0             0.0             0.0
       2             1.0             0.0             0.0
       3             1.0             1.0             0.0
       4             0.0             1.0             0.0
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4
       1       1       1       2       3       4
*END
"""


def format_card(values):
    """Format one card as a comma separated line.

    Inner empty values are kept (so later fields stay in position), trailing
    empty values are dropped.
    """
    values = ["" if v is None else str(v).strip() for v in values]
    while values and not values[-1]:
        values.pop()
    return ", ".join(values)


def keyword_block(name, cards):
    """Return the text for one keyword: the keyword line followed by its cards.

    Trailing all-empty cards are dropped; inner ones become blank lines
    (a card with default values).
    """
    lines = [format_card(card) for card in cards]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join([name.strip()] + lines)


def keyword_with_options(keyword, options):
    """Append option suffixes to a keyword, e.g. ('*PART', {'OPTION1': 'INERTIA'}) -> '*PART_INERTIA'.

    Suffixes are added in option order (OPTION, OPTION1, OPTION2, ...) and
    skipped when the keyword already ends with them.
    """
    name = keyword.strip()
    for _key, value in sorted(options.items(), key=lambda item: (len(item[0]), item[0])):
        if not name.upper().endswith("_" + value.upper()):
            name += "_" + value
    return name


def build_keyword(keyword, cards):
    """Build keyword text from filled-in cards of the keyword editor.

    ``cards`` is a list of dicts with ``values`` (field values in position
    order) and optionally ``group``, ``optional`` and ``options`` as stored in
    the keyword database. Optional card groups are only written when at least
    one of their fields is filled in; the options of written groups are added
    to the keyword name.
    """
    filled_groups = {card.get("group", 0) for card in cards
                     if any(str(v).strip() for v in card.get("values", []))}
    written, options = [], {}
    for card in cards:
        group = card.get("group", 0)
        if card.get("optional") and group not in filled_groups:
            continue
        if group in filled_groups:
            options.update(card.get("options") or {})
        written.append(card.get("values", []))
    return keyword_block(keyword_with_options(keyword, options), written)


def template_keyword_text(kw_data):
    """Build keyword text from a template entry.

    A template entry looks like::

        {"name": "*SECTION_SHELL", "parameters": [
            {"name": "SECID", "value": "1"},
            {"name": "T1", "value": "1.0", "card": 1}]}

    Parameters are placed on the card given by ``card`` (default 0) in the
    order listed; an empty ``value`` keeps a field at its default while
    holding its position. Cards skipped in between become blank cards.
    ``field_0`` is accepted as an alias for ``value``.
    """
    name = kw_data.get("name", "").strip()
    if not name:
        return ""

    cards = {}
    for param in kw_data.get("parameters", []):
        value = param.get("value", param.get("field_0", ""))
        cards.setdefault(int(param.get("card", 0)), []).append(value)

    n_cards = max(cards) + 1 if cards else 0
    return keyword_block(name, [cards.get(i, []) for i in range(n_cards)])


def build_k_file(entries, title=None):
    """Assemble a complete deck from ``(keyword_name, text)`` entries.

    ``*KEYWORD`` / ``*END`` entries are skipped because the deck gets exactly
    one of each here.
    """
    lines = ["*KEYWORD"]
    if title:
        lines += ["*TITLE", title]
    lines.append("$ Created by FreeCAD OpenRadioss Workbench")
    for name, text in entries:
        if name.strip().upper() in _FRAME_KEYWORDS:
            continue
        lines.append("$")
        lines.append(f"$ --- {name} ---")
        lines.append(text.rstrip("\n"))
    lines.append("*END")
    return "\n".join(lines) + "\n"


def load_templates(path=TEMPLATES_PATH):
    """Return the ``templates`` mapping from templates.json (ordered as in the file)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("templates", {})


def save_templates(templates, path):
    """Write ``templates`` to ``path`` in templates.json format.

    The file is written to a temporary name first and then renamed, so a
    failed write never leaves a truncated file behind.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"templates": templates}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)


def validate_templates(templates):
    """Return a list of human readable problems (empty if the templates are valid)."""
    errors = []
    for template_id, template in templates.items():
        label = template.get("name") or template_id
        if not template.get("name", "").strip():
            errors.append(f"Template '{template_id}': name is empty")
        if template.get("level", "full") not in TEMPLATE_LEVELS:
            errors.append(f"Template '{label}': level must be one of {', '.join(TEMPLATE_LEVELS)}")
        keywords = template.get("keywords") or []
        if not keywords:
            errors.append(f"Template '{label}': has no keywords")
        for n, kw in enumerate(keywords, 1):
            name = kw.get("name", "").strip()
            kw_label = f"Template '{label}', keyword {n} ({name or 'unnamed'})"
            if len(name) < 2 or not name.startswith("*") or " " in name:
                errors.append(f"{kw_label}: name must be '*' followed by the keyword, without spaces")
            per_card = {}
            for param in kw.get("parameters", []):
                try:
                    card = int(param.get("card", 0))
                except (TypeError, ValueError):
                    errors.append(f"{kw_label}: card of '{param.get('name', '')}' is not a number")
                    continue
                if card < 0:
                    errors.append(f"{kw_label}: card of '{param.get('name', '')}' is negative")
                per_card[card] = per_card.get(card, 0) + 1
            for card, count in sorted(per_card.items()):
                if count > FIELDS_PER_CARD:
                    errors.append(f"{kw_label}: card {card + 1} has {count} fields "
                                  f"(max {FIELDS_PER_CARD})")
    return errors


def make_template_id(name, existing):
    """Return a unique, file-friendly template id derived from ``name``."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "template"
    template_id, n = base, 2
    while template_id in existing:
        template_id, n = f"{base}_{n}", n + 1
    return template_id
