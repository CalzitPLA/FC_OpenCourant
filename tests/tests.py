#!/usr/bin/env python3
"""
Tests for the FreeCAD-independent parts of the OpenRadioss workbench.

Run with:  python tests/tests.py
"""

import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_DIR = os.path.join(ROOT, "freecad", "ORfemn")

# Load kfile_format directly so the tests do not need FreeCAD (or clash with
# FreeCAD's own `freecad` package).
_spec = importlib.util.spec_from_file_location("kfile_format", os.path.join(MODULE_DIR, "kfile_format.py"))
kfile_format = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kfile_format)


def fixed_fields(line, widths):
    """Split a fixed-format card line into stripped fields."""
    fields, pos = [], 0
    for width in widths:
        fields.append(line[pos:pos + width].strip())
        pos += width
    return fields


def cards_of(deck, keyword):
    """Return the non-comment card lines following ``keyword`` in ``deck``."""
    lines = deck.splitlines()
    start = lines.index(keyword) + 1
    cards = []
    for line in lines[start:]:
        if line.startswith("*"):
            break
        if not line.startswith("$"):
            cards.append(line)
    return cards


class FormatCardTest(unittest.TestCase):
    def test_trailing_empty_fields_dropped(self):
        self.assertEqual(kfile_format.format_card(["1", "2", "", ""]), "1, 2")

    def test_inner_empty_fields_kept(self):
        self.assertEqual(kfile_format.format_card(["1", "", "3"]), "1, , 3")

    def test_values_stripped_and_none_is_empty(self):
        self.assertEqual(kfile_format.format_card([" 1 ", None, 2.5]), "1, , 2.5")

    def test_keyword_block_drops_trailing_empty_cards(self):
        text = kfile_format.keyword_block("*PART", [["title"], [], ["1", "1", "1"], [], []])
        self.assertEqual(text, "*PART\ntitle\n\n1, 1, 1")


class BuildKeywordTest(unittest.TestCase):
    PART = [
        {"values": ["Plate"], "group": 0},
        {"values": ["1", "1", "1"], "group": 0},
        {"values": ["", "", "", "2.0"], "group": 1, "optional": True, "options": {"OPTION1": "INERTIA"}},
        {"values": ["", ""], "group": 1, "optional": True, "options": {"OPTION1": "INERTIA"}},
        {"values": [""], "group": 2, "optional": True, "options": {"OPTION2": "CONTACT"}},
    ]

    def test_empty_optional_groups_are_left_out(self):
        cards = [dict(c) for c in self.PART]
        cards[2] = dict(cards[2], values=[])
        self.assertEqual(kfile_format.build_keyword("*PART", cards), "*PART\nPlate\n1, 1, 1")

    def test_filled_optional_group_is_written_whole_and_named(self):
        text = kfile_format.build_keyword("*PART", self.PART)
        self.assertEqual(text, "*PART_INERTIA\nPlate\n1, 1, 1\n, , , 2.0")

    def test_required_empty_cards_become_blank_lines(self):
        cards = [{"values": ["1"]}, {"values": []}, {"values": ["3"]}]
        self.assertEqual(kfile_format.build_keyword("*X", cards), "*X\n1\n\n3")

    def test_option_order_and_no_duplicate_suffix(self):
        self.assertEqual(kfile_format.keyword_with_options("*PART", {"OPTION2": "CONTACT", "OPTION1": "INERTIA"}),
                         "*PART_INERTIA_CONTACT")
        self.assertEqual(kfile_format.keyword_with_options("*AIRBAG_LINEAR_FLUID_ID", {"OPTION": "ID"}),
                         "*AIRBAG_LINEAR_FLUID_ID")


class KeywordDatabaseTest(unittest.TestCase):
    """Sanity checks of the keyword database built by tools/keyword_db/."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(os.path.join(MODULE_DIR, "keywords_with_parameters.json"), encoding="utf-8") as f:
            cls.keywords = json.load(f)

    def test_deck_keywords_are_valid(self):
        for kw in self.keywords:
            with self.subTest(kw["name"]):
                self.assertRegex(kw.get("keyword", ""), r"^\*[A-Z0-9_\-]+$")

    def test_documentation_links_are_absolute(self):
        for kw in self.keywords:
            with self.subTest(kw["name"]):
                self.assertTrue(kw.get("documentation", "").startswith("https://"), kw.get("documentation"))

    def test_cards(self):
        with_cards = [kw for kw in self.keywords if kw.get("parameters")]
        self.assertGreater(len(with_cards), 200)
        for kw in with_cards:
            for card in kw["parameters"]:
                self.assertIn("group", card)
                for key in card.get("defaults", {}):
                    self.assertTrue(card.get(key), f"{kw['name']}: default for unnamed {key}")


class TemplateTest(unittest.TestCase):
    def setUp(self):
        self.templates = kfile_format.load_templates()

    def test_templates_present(self):
        self.assertGreater(len(self.templates), 0)

    def test_every_template_generates_keywords(self):
        for template_id, template in self.templates.items():
            with self.subTest(template=template_id):
                self.assertIn(template.get("level"), ("minimal", "basic", "full"))
                self.assertTrue(template.get("keywords"))
                for kw in template["keywords"]:
                    text = kfile_format.template_keyword_text(kw)
                    self.assertTrue(text.startswith("*"), text)
                    self.assertEqual(text.splitlines()[0], kw["name"])
                    for card in text.splitlines()[1:]:
                        self.assertLessEqual(len(card.split(",")), kfile_format.FIELDS_PER_CARD, card)

    def test_card_placement(self):
        kw = {"name": "*SECTION_SHELL", "parameters": [
            {"name": "SECID", "value": "1"},
            {"name": "ELFORM", "value": "2"},
            {"name": "T1", "value": "1.0", "card": 1},
            {"name": "T2", "value": "1.0", "card": 1},
        ]}
        self.assertEqual(kfile_format.template_keyword_text(kw), "*SECTION_SHELL\n1, 2\n1.0, 1.0")

    def test_field_0_alias(self):
        kw = {"name": "*CONTROL_TERMINATION", "parameters": [{"name": "ENDTIM", "field_0": "1.0"}]}
        self.assertEqual(kfile_format.template_keyword_text(kw), "*CONTROL_TERMINATION\n1.0")

    def test_part_has_heading_card(self):
        part = self.templates["basic"]["keywords"][3]
        self.assertEqual(part["name"], "*PART")
        self.assertEqual(kfile_format.template_keyword_text(part), "*PART\nPart 1\n1, 1, 1")


class TemplateStorageTest(unittest.TestCase):
    def valid(self):
        return {"t": {"name": "T", "level": "basic", "description": "", "keywords": [
            {"name": "*CONTROL_TERMINATION", "parameters": [{"name": "ENDTIM", "value": "1.0"}]}]}}

    def test_shipped_templates_are_valid(self):
        self.assertEqual(kfile_format.validate_templates(kfile_format.load_templates()), [])

    def test_valid(self):
        self.assertEqual(kfile_format.validate_templates(self.valid()), [])

    def test_invalid_templates_reported(self):
        cases = {
            "name": lambda t: t["t"].update(name=" "),
            "level": lambda t: t["t"].update(level="expert"),
            "no keywords": lambda t: t["t"].update(keywords=[]),
            "keyword name": lambda t: t["t"]["keywords"][0].update(name="*"),
            "card not a number": lambda t: t["t"]["keywords"][0]["parameters"][0].update(card="x"),
            "negative card": lambda t: t["t"]["keywords"][0]["parameters"][0].update(card=-1),
            "too many fields": lambda t: t["t"]["keywords"][0]["parameters"].extend(
                {"name": f"F{i}", "value": ""} for i in range(kfile_format.FIELDS_PER_CARD)),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                templates = self.valid()
                mutate(templates)
                self.assertEqual(len(kfile_format.validate_templates(templates)), 1)

    def test_save_load_roundtrip_keeps_order(self):
        templates = {"b": self.valid()["t"], "a": dict(self.valid()["t"], name="Ä")}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "templates.json")
            kfile_format.save_templates(templates, path)
            self.assertEqual(kfile_format.load_templates(path), templates)
            self.assertEqual(list(kfile_format.load_templates(path)), ["b", "a"])
            self.assertEqual(os.listdir(os.path.dirname(path)), ["templates.json"])

    def test_make_template_id(self):
        self.assertEqual(kfile_format.make_template_id("My Crash-Box 2", {}), "my_crash_box_2")
        self.assertEqual(kfile_format.make_template_id("Basic", {"basic": 1, "basic_2": 1}), "basic_3")
        self.assertEqual(kfile_format.make_template_id("!!!", {}), "template")


class BuildKFileTest(unittest.TestCase):
    def test_single_frame(self):
        deck = kfile_format.build_k_file([
            ("*KEYWORD", "*KEYWORD"),
            ("*CONTROL_TERMINATION", "*CONTROL_TERMINATION\n1.0"),
            ("*END", "*END"),
        ], title="Test")
        lines = deck.splitlines()
        self.assertEqual(lines[0], "*KEYWORD")
        self.assertEqual(lines[1:3], ["*TITLE", "Test"])
        self.assertEqual(lines[-1], "*END")
        self.assertEqual(lines.count("*KEYWORD"), 1)
        self.assertEqual(lines.count("*END"), 1)
        self.assertIn("*CONTROL_TERMINATION\n1.0", deck)


class BasicKFileTest(unittest.TestCase):
    """The basic template uses fixed format, so column positions matter."""

    deck = kfile_format.BASIC_K_FILE

    def test_frame(self):
        lines = self.deck.splitlines()
        self.assertEqual(lines[0], "*KEYWORD")
        self.assertEqual(lines[-1], "*END")

    def test_part(self):
        title, card = cards_of(self.deck, "*PART")
        self.assertEqual(title, "Plate")
        self.assertEqual(fixed_fields(card, [10] * 3), ["1", "1", "1"])

    def test_section_shell_has_thickness_card(self):
        card1, card2 = cards_of(self.deck, "*SECTION_SHELL")
        self.assertEqual(fixed_fields(card1, [10] * 4), ["1", "2", "0.833", "3"])
        self.assertEqual(fixed_fields(card2, [10] * 4), ["1.0"] * 4)

    def test_mat_elastic(self):
        (card,) = cards_of(self.deck, "*MAT_ELASTIC")
        self.assertEqual(fixed_fields(card, [10] * 4), ["1", "7.85e-9", "210000.0", "0.3"])

    def test_nodes(self):
        cards = cards_of(self.deck, "*NODE")
        self.assertEqual(len(cards), 4)
        for nid, card in enumerate(cards, 1):
            fields = fixed_fields(card, [8, 16, 16, 16])
            self.assertEqual(fields[0], str(nid))
            for value in fields[1:]:
                float(value)

    def test_element_shell(self):
        (card,) = cards_of(self.deck, "*ELEMENT_SHELL")
        self.assertEqual(fixed_fields(card, [8] * 6), ["1", "1", "1", "2", "3", "4"])

    def test_control_timestep(self):
        (card,) = cards_of(self.deck, "*CONTROL_TIMESTEP")
        self.assertEqual(fixed_fields(card, [10] * 2), ["0.0", "0.9"])

    def test_no_line_longer_than_80(self):
        for line in self.deck.splitlines():
            self.assertLessEqual(len(line), 80, line)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=2).result.wasSuccessful() else 1)
