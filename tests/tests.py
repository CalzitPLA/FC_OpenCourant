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

_spec = importlib.util.spec_from_file_location("radioss_runner", os.path.join(MODULE_DIR, "radioss_runner.py"))
radioss_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(radioss_runner)


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


LEGACY_VTK = """# vtk DataFile Version 3.0
vtk output
ASCII
DATASET UNSTRUCTURED_GRID
FIELD FieldData 2
TIME 1 1 double
0.5
CYCLE 1 1 int
10
POINTS 4 float
0 0 0
1 0 0
1 1 0
0 1 0

CELLS 1 5
4 0 1 2 3

CELL_TYPES 1
9

POINT_DATA 4
SCALARS NODE_ID int 1
LOOKUP_TABLE default
1
2
3
4

VECTORS Velocity float
0 0 0 0 0 0 0 0 0 0 0 0
VECTORS Displacement float
0 0 0 0.1 0 0 0.1 0 0 0 0 0
CELL_DATA 1
SCALARS ELEMENT_ID int 1
LOOKUP_TABLE default
7
TENSORS Stress float
100 0 0
0 0 0
0 0 0
"""


class RadiossRunnerTest(unittest.TestCase):
    def test_result_files(self):
        for name in ("job_0000.out", "job_0001.rad", "job_0000_0001.rst", "jobA001", "jobA012.vtu", "job.pvd", "jobT01"):
            self.assertTrue(radioss_runner.is_result_file(name, "job"), name)
        for name in ("job.k", "job_notes.txt", "jobAx", "other_0000.out"):
            self.assertFalse(radioss_runner.is_result_file(name, "job"), name)

    def test_listing_summary_and_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            normal = os.path.join(tmp, "a.out")
            with open(normal, "w") as f:
                f.write("WARNING ID :   1084\n** WARNING IN MATERIAL LAW1\n\n"
                        "     TERMINATION WITH WARNING\n              0 ERROR(S)\n              1 WARNING(S)\n")
            self.assertEqual(radioss_runner.listing_summary(normal), (0, 1))
            self.assertEqual(radioss_runner.listing_messages(normal, "WARNING"),
                             ["WARNING ID :   1084 ** WARNING IN MATERIAL LAW1"])
            early = os.path.join(tmp, "b.out")
            with open(early, "w") as f:
                f.write(" +=====+\n   NODES\n +=====+\n\nERROR ID :    760\n** ERROR TRAPPED\n\n RADIOSS STOP DUE TO INPUT ERROR\n")
            self.assertEqual(radioss_runner.listing_summary(early), (1, None))
            self.assertEqual(radioss_runner.listing_messages(early), ["ERROR ID :    760 ** ERROR TRAPPED [NODES]"])
            self.assertEqual(radioss_runner.listing_summary(os.path.join(tmp, "missing.out")), (None, None))

    def test_job_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("job_0000.rad", "job_0001.rad", "job_0002.rad", "jobA001", "jobA002", "jobA001.vtu", "x_0001.rad"):
                open(os.path.join(tmp, name), "w").close()
            self.assertEqual([os.path.basename(f) for f in radioss_runner.engine_inputs(tmp, "job")],
                             ["job_0001.rad", "job_0002.rad"])
            self.assertEqual([os.path.basename(f) for f in radioss_runner.animation_files(tmp, "job")],
                             ["jobA001", "jobA002"])

    def test_legacy_vtk_to_vtu_keeps_all_arrays(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as tmp:
            legacy, vtu = os.path.join(tmp, "a.vtk"), os.path.join(tmp, "a.vtu")
            with open(legacy, "w") as f:
                f.write(LEGACY_VTK)
            self.assertEqual(radioss_runner.legacy_vtk_to_vtu(legacy, vtu), 0.5)
            root = ET.parse(vtu).getroot()
            names = [a.get("Name") for a in root.iter("DataArray")]
            for name in ("TIME", "NODE_ID", "Velocity", "Displacement", "ELEMENT_ID", "Stress", "Stress von Mises"):
                self.assertIn(name, names)
            arrays = {a.get("Name"): a for a in root.iter("DataArray")}
            self.assertEqual(arrays["Displacement"].text.split()[3], "0.1")
            self.assertEqual(arrays["Stress"].get("NumberOfComponents"), "9")
            self.assertAlmostEqual(float(arrays["Stress von Mises"].text), 100.0)  # uniaxial stress
            self.assertEqual(arrays["types"].text, "9")
            self.assertEqual(arrays["offsets"].text, "4")

    def test_von_mises_pure_shear(self):
        self.assertAlmostEqual(radioss_runner._von_mises([0, 10, 0, 10, 0, 0, 0, 0, 0]), 10 * 3 ** 0.5)

    def test_environment(self):
        inst = radioss_runner.Installation("/opt/or")
        env = inst.environment(threads=3, base={"LD_LIBRARY_PATH": "/x"})
        self.assertEqual(env["RAD_CFG_PATH"], "/opt/or/hm_cfg_files")
        self.assertEqual(env["OMP_NUM_THREADS"], "3")
        self.assertTrue(env["LD_LIBRARY_PATH"].endswith(os.pathsep + "/x"))
        self.assertEqual(inst.starter_command("/w/job.k", 2)[1:], ["-i", "job.k", "-nt", "2", "-np", "1"])
        self.assertTrue(radioss_runner.Installation("/nonexistent").problems())


@unittest.skipIf(radioss_runner.Installation().problems(), "OpenCourant/OpenRadioss not installed (~/OpenCourant, ~/OpenRadioss, ...)")
class OpenRadiossIntegrationTest(unittest.TestCase):
    """Runs the real solver on the basic template (about 1 s)."""

    def test_basic_k_file_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = os.path.join(tmp, "basic.k")
            with open(deck, "w") as f:
                f.write(kfile_format.BASIC_K_FILE)
            result = radioss_runner.run_job(deck, threads=1, log=lambda _line: None)
            self.assertEqual(radioss_runner.listing_summary(result["starter_out"])[0], 0)
            self.assertTrue(all(radioss_runner.normal_termination(o) for o in result["engine_outs"]))
            self.assertEqual(len(result["vtk_files"]), 100)
            self.assertAlmostEqual(result["times"][-1], 0.001, delta=2e-5)
            self.assertTrue(os.path.exists(os.path.join(tmp, "basic.pvd")))


_spec = importlib.util.spec_from_file_location("deck_writer", os.path.join(MODULE_DIR, "fem", "deck_writer.py"))
deck_writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deck_writer)


def block_model(nx=4, ny=1, nz=1, size=10.0, **overrides):
    """A cantilever block of hexahedra along x, fixed at x = 0 (for the deck writer tests)."""
    nodes, nid = {}, {}
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                n = len(nodes) + 1
                nodes[n] = (i * size, j * size, k * size)
                nid[i, j, k] = n
    elements = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                elements.append((len(elements) + 1, [
                    nid[i, j, k], nid[i + 1, j, k], nid[i + 1, j + 1, k], nid[i, j + 1, k],
                    nid[i, j, k + 1], nid[i + 1, j, k + 1], nid[i + 1, j + 1, k + 1], nid[i, j + 1, k + 1]]))
    tip = [n for (i, _j, _k), n in nid.items() if i == nx]
    top = [[nid[i, j, nz], nid[i + 1, j, nz], nid[i + 1, j + 1, nz], nid[i, j + 1, nz]]
           for i in range(nx) for j in range(ny)]  # counter-clockwise from above: normal +z (outward)
    model = {
        "title": "block", "end_time": 0.002, "output_interval": 0.0005, "load_curve": "ramp",
        "nodes": nodes,
        "parts": [{"pid": 1, "title": "Steel", "kind": "solid", "elform": 1,
                   "material": {"rho": 7.9e-9, "E": 210000.0, "nu": 0.3}, "elements": elements}],
        "fixed": [{"title": "Fixed", "nodes": [n for (i, _j, _k), n in nid.items() if i == 0],
                   "dofs": (1, 1, 1, 1, 1, 1)}],
        "node_forces": [{"title": "Force", "loads": {n: (0.0, 0.0, 100.0 / len(tip)) for n in tip}}],
        "pressures": [{"title": "Pressure", "pressure": 0.01, "segments": top}],
        "gravity": (0.0, 0.0, -9806.65),
        "extra": "*KEYWORD\n*DATABASE_GLSTAT\n1.0e-4\n*END",
    }
    model.update(overrides)
    return model, tip


class DeckWriterTest(unittest.TestCase):
    def test_keywords_and_cards(self):
        model, _tip = block_model()
        deck = deck_writer.write_deck(model)
        lines = deck.splitlines()
        self.assertEqual((lines[0], lines[-1]), ("*KEYWORD", "*END"))
        self.assertEqual(deck.count("*KEYWORD"), 1)
        self.assertEqual(deck.count("*END"), 1)
        for keyword in ("*CONTROL_TERMINATION", "*DATABASE_BINARY_D3PLOT", "*DEFINE_CURVE", "*PART",
                        "*SECTION_SOLID", "*MAT_ELASTIC", "*NODE", "*ELEMENT_SOLID", "*SET_NODE_LIST",
                        "*BOUNDARY_SPC_SET", "*LOAD_NODE_POINT", "*LOAD_SEGMENT", "*LOAD_BODY_Z", "*DATABASE_GLSTAT"):
            self.assertIn(keyword + "\n", deck)
        self.assertIn("*MAT_ELASTIC\n1, 7.9e-09, 210000, 0.3\n", deck)
        self.assertIn("*ELEMENT_SOLID\n1, 1\n1, 2, 7, 6, 11, 12, 17, 16\n", deck)  # two-card format
        self.assertIn("*LOAD_BODY_Z\n1, 9806.65\n", deck)  # gravity in -z is a positive body load
        self.assertNotIn("*CONTROL_TIMESTEP", deck)

    def test_ramp_and_constant_curves(self):
        ramp = deck_writer.write_deck(block_model()[0])
        self.assertIn("0.0, 0.0\n0.002, 1.0", ramp)
        constant = deck_writer.write_deck(block_model(load_curve="constant")[0])
        self.assertIn("0.0, 1.0\n0.002, 1.0", constant)

    def test_mass_scaling(self):
        deck = deck_writer.write_deck(block_model(mass_scaling_dt=1e-6)[0])
        self.assertIn("*CONTROL_TIMESTEP\n$  dtinit    tssfac      isdo    tslimt     dt2ms\n0.0, 0.9, 0, 0.0, -1e-06", deck)

    def test_shells_and_triangles(self):
        nodes = {1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0)}
        model = {"end_time": 0.001, "nodes": nodes, "parts": [
            {"pid": 1, "kind": "shell", "elform": 2, "thickness": 2.0,
             "material": {"rho": 1e-9, "E": 1000.0, "nu": 0.3}, "elements": [(1, [1, 2, 3]), (2, [1, 3, 4])]}],
            "pressures": [{"pressure": 0.5, "segments": [[1, 2, 3]]}]}
        deck = deck_writer.write_deck(model)
        self.assertIn("*SECTION_SHELL\n1, 2\n2, 2, 2, 2\n", deck)
        self.assertIn("*ELEMENT_SHELL\n1, 1, 1, 2, 3, 3\n2, 1, 1, 3, 4, 4\n", deck)
        self.assertIn("*LOAD_SEGMENT\n1, 0.5, 0.0, 1, 2, 3, 3\n", deck)

    def test_only_used_nodes_are_written(self):
        model, _tip = block_model()
        model["nodes"][999] = (5.0, 5.0, 5.0)  # e.g. a node of a face element
        model["fixed"][0]["nodes"].append(999)
        deck = deck_writer.write_deck(model)
        self.assertNotIn("\n999, ", deck)


@unittest.skipIf(radioss_runner.Installation().problems(), "OpenCourant/OpenRadioss not installed (~/OpenCourant, ~/OpenRadioss, ...)")
class FemDeckIntegrationTest(unittest.TestCase):
    """The deck writer output runs in OpenRadioss and bends the block the right way."""

    def test_block_bends_like_a_beam(self):
        import xml.etree.ElementTree as ET
        # 2 elements through the thickness: a single hexahedron layer is too coarse for bending
        model, tip = block_model(nx=8, ny=2, nz=2, size=5.0, extra="", gravity=None, pressures=[])
        with tempfile.TemporaryDirectory() as tmp:
            deck = os.path.join(tmp, "block.k")
            with open(deck, "w") as f:
                f.write(deck_writer.write_deck(model))
            result = radioss_runner.run_job(deck, threads=1, log=lambda _line: None)
            self.assertEqual(radioss_runner.listing_summary(result["starter_out"])[0], 0)
            arrays = {a.get("Name"): a.text.split() for a in ET.parse(result["vtk_files"][-1]).getroot().iter("DataArray")
                      if a.text}
            ids = [int(v) for v in arrays["NODE_ID"]]
            disp = [float(v) for v in arrays["Displacement"]]
            tip_uz = [disp[3 * i + 2] for i, n in enumerate(ids) if n in set(tip)]
            beam = 100.0 * 40.0 ** 3 / (3 * 210000.0 * 10.0 * 10.0 ** 3 / 12)  # F L^3 / 3EI = 0.0122 mm
            self.assertAlmostEqual(sum(tip_uz) / len(tip_uz), beam, delta=0.05 * beam)


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



def fake_installation(root, executable=True, cfg=True):
    """A directory tree that looks like an unpacked release (empty executables)."""
    inst = radioss_runner.Installation(root)
    os.makedirs(os.path.join(root, "exec"), exist_ok=True)
    for tool in ("starter", "engine", "anim_to_vtk"):
        path = inst.executable(tool)
        with open(path, "w") as f:
            f.write("")
        os.chmod(path, 0o755 if executable else 0o644)
    if cfg:
        os.makedirs(os.path.join(root, "hm_cfg_files", "config", "CFG"), exist_ok=True)
    os.makedirs(os.path.join(root, "extlib", "hm_reader", inst.libdir), exist_ok=True)
    os.makedirs(os.path.join(root, "extlib", "h3d", "lib", inst.libdir), exist_ok=True)
    return inst


class InstallationSetupTest(unittest.TestCase):
    """Finding, checking and downloading a solver installation (preference page backend)."""

    def test_candidate_order(self):
        paths = radioss_runner.candidate_paths(environ={"OPENRADIOSS_PATH": "/x/or", "OPENCOURANT_PATH": "/x/oc"},
                                               home="/h")
        self.assertEqual(paths[:4], ["/x/oc", "/x/or", "/h/OpenCourant", "/h/OpenRadioss"])

    def test_detect_prefers_first_usable(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "OpenCourant"))  # empty: not usable
            fake_installation(os.path.join(home, "OpenRadioss"))
            found = radioss_runner.detect_installation(environ={}, home=home)
            self.assertEqual(found.path, os.path.join(home, "OpenRadioss"))
            self.assertIsNone(radioss_runner.detect_installation(environ={}, home=os.path.join(home, "none")))

    def test_requisites(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = fake_installation(tmp, cfg=False)
            items = {name: ok for name, ok, _detail in inst.requisites()}
            self.assertTrue(items["Solver folder"])
            self.assertTrue(items["starter executable"])
            self.assertFalse(items["Reader configuration"])
            inst = fake_installation(tmp, executable=False)
            items = {name: ok for name, ok, _detail in inst.requisites()}
            self.assertTrue(items["Reader configuration"])
            self.assertEqual(items["engine executable"], inst.ext == ".exe")

    def test_release_asset_name(self):
        self.assertEqual(radioss_runner.release_asset_name("Linux", "x86_64"), "OpenCourant_linux64.zip")
        self.assertEqual(radioss_runner.release_asset_name("Linux", "aarch64"), "OpenCourant_linuxa64.zip")
        self.assertEqual(radioss_runner.release_asset_name("Windows", "AMD64"), "OpenCourant_win64.zip")
        with self.assertRaises(radioss_runner.OpenRadiossError):
            radioss_runner.release_asset_name("Darwin", "arm64")

    def test_latest_release_skips_prereleases(self):
        import json
        releases = [
            {"tag_name": "rc", "prerelease": True, "assets": [{"name": "OpenCourant_linux64.zip",
                                                               "browser_download_url": "u0", "size": 1}]},
            {"tag_name": "latest-20261011", "assets": [
                {"name": "OpenCourant_win64.zip", "browser_download_url": "w", "size": 2},
                {"name": "OpenCourant_linux64.zip", "browser_download_url": "u1", "size": 83933903}]},
        ]
        tag, url, size = radioss_runner.latest_release("OpenCourant_linux64.zip", fetch=lambda _u: json.dumps(releases))
        self.assertEqual((tag, url, size), ("latest-20261011", "u1", 83933903))
        with self.assertRaises(radioss_runner.OpenRadiossError):
            radioss_runner.latest_release("OpenCourant_other.zip", fetch=lambda _u: json.dumps(releases))

    def make_release_zip(self, path, extra=None):
        import zipfile
        with zipfile.ZipFile(path, "w") as z:
            info = zipfile.ZipInfo("OpenCourant/exec/starter_linux64_gf")
            info.external_attr = (0o100755 << 16)
            z.writestr(info, "#!/bin/sh\n")
            z.writestr("OpenCourant/hm_cfg_files/config/CFG/README", "cfg")
            for name in extra or []:
                z.writestr(name, "x")

    def test_extract_release_keeps_executable_bit(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = os.path.join(tmp, "release.zip")
            self.make_release_zip(archive)
            path = radioss_runner.extract_release(archive, os.path.join(tmp, "OpenCourant_latest"))
            self.assertEqual(path, os.path.join(tmp, "OpenCourant_latest", "OpenCourant"))
            if os.name == "posix":
                self.assertTrue(os.access(os.path.join(path, "exec", "starter_linux64_gf"), os.X_OK))

    def test_extract_release_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = os.path.join(tmp, "evil.zip")
            self.make_release_zip(archive, extra=["../outside.txt"])
            with self.assertRaises(radioss_runner.OpenRadiossError):
                radioss_runner.extract_release(archive, os.path.join(tmp, "target"))
            self.assertFalse(os.path.exists(os.path.join(tmp, "outside.txt")))

    def test_download_and_cancel(self):
        import pathlib
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source.bin")
            with open(source, "wb") as f:
                f.write(os.urandom(3 * 1024))
            url = pathlib.Path(source).as_uri()
            seen = []
            target = radioss_runner.download(url, os.path.join(tmp, "copy.bin"),
                                             lambda done, total: seen.append((done, total)), chunk_size=1024)
            with open(target, "rb") as a, open(source, "rb") as b:
                self.assertEqual(a.read(), b.read())
            self.assertEqual(seen[-1], (3072, 3072))
            with self.assertRaises(radioss_runner.OpenRadiossError):
                radioss_runner.download(url, os.path.join(tmp, "cancelled.bin"), lambda d, t: False, chunk_size=1024)
            self.assertFalse(os.path.exists(os.path.join(tmp, "cancelled.bin")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "cancelled.bin.part")))

    def test_test_run_reports_missing_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, message = radioss_runner.Installation(os.path.join(tmp, "nothing")).test_run(kfile_format.BASIC_K_FILE)
            self.assertFalse(ok)
            self.assertIn("not found", message)

    @unittest.skipIf(radioss_runner.Installation().problems(), "OpenCourant/OpenRadioss not installed")
    def test_test_run_with_real_solver(self):
        ok, message = radioss_runner.Installation().test_run(kfile_format.BASIC_K_FILE)
        self.assertTrue(ok, message)
        self.assertIn("0 errors", message)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False, verbosity=2).result.wasSuccessful() else 1)
