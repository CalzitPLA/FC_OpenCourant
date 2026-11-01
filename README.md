# ORfe – OpenRadioss Workbench for FreeCAD

Explicit dynamics in FreeCAD: OpenRadioss as a solver of the FEM workbench, plus a workbench to create,
edit and run LS-DYNA format input decks (`.k` files, as read by OpenRadioss).

A short introduction (installation, workflows, testing, limitations) is in
[`docs/ORfe_Introduction.pdf`](docs/ORfe_Introduction.pdf).

## Dependencies

- FreeCAD >= 1.0 (Python 3, PySide provided by FreeCAD); tested with 1.0.0 and 1.1.4
- For running simulations: [OpenCourant](https://github.com/OpenCourant/OpenCourant/releases), the
  community continuation of OpenRadioss (unpack the release, e.g. to `~/OpenRadioss`; the path can be
  changed in the run dialog). The OpenRadioss project was discontinued in October 2026 and its GitHub
  repository removed; OpenCourant releases have the same layout and executable names, so older OpenRadioss
  releases and OpenCourant both work.

## Quick Start

1. Clone, link or copy this repository into your FreeCAD `Mod` directory, e.g.
   `git clone https://github.com/CalzitPLA/ORfe ~/.local/share/FreeCAD/Mod/ORfe`
   (Flatpak: `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/Mod/ORfe`), or install it with `pip install -e .`.
2. Restart FreeCAD and select the **OpenRadioss** workbench.
3. Use the toolbar:
   - **Create Radioss Model** – new document with groups for parts, materials, loads, ...
   - **Create Basic .k File** – adds a small, runnable single-shell deck as a text object
   - **Keyword Editor** – browse keywords, fill in card fields, cache generated keywords,
     or start from a template (*Templates* menu); **Update .k File** writes the cache into the document
   - **Template Editor** – create, edit, duplicate, delete and reorder the templates of the
     *Templates* menu, with a live preview (also under *Templates → Edit Templates...* in the Keyword Editor)
   - **Open Cache Viewer** – inspect/remove cached keywords of the open editor
   - **Export LS-DYNA .k File** – save a text object to a `.k` file
   - **Run OpenRadioss** – run starter, engine and the VTK conversion on a keyword text object in the
     background (live log, Stop), then load the result into FEM post-processing. All frames are written
     as `.vtu` plus a `.pvd` series for ParaView. Inside the FreeCAD Flatpak the two host libraries the
     solver needs (`libcrypt.so.1`, `libapr-1.so.0`) are copied to `<OpenRadioss>/extlib/flatpak_compat`.

### OpenRadioss in the FEM workbench

OpenRadioss is also available as a solver of FreeCAD's **FEM workbench** (*Solve* toolbar and menu:
**Solver OpenRadioss**, next to CalculiX, Elmer, Mystran and Z88). Set up an analysis as usual
(mesh, material, constraints), add the solver and run it with *Run solver calculations* or by
double-clicking the solver. The last frame appears as a FEM result (displacement, von Mises and
principal stresses, like CalculiX results) plus a post-processing pipeline in the analysis; all frames are in the working directory as `radioss.pvd` for ParaView.

OpenRadioss is an **explicit dynamic** solver. Solver properties:

| Property | Meaning |
|---|---|
| EndTime | simulated time (default 0.01 s); explicit time steps are tiny, so keep it short |
| LoadCurve | *Ramp* (loads grow from 0 over EndTime, quasi-static) or *Constant* (impact-like) |
| OutputFrames | number of result frames |
| MassScalingMicroseconds | 0 = off; otherwise mass is added so the time step stays at least this value in µs (much faster, e.g. 0.2) |
| Threads | threads for starter and engine |
| AdditionalKeywords | a text document whose keywords are appended to the deck (e.g. from the Keyword Editor) |

Supported: volume meshes (tetra4, tetra10 native, hexa8, penta6, pyra5; second-order hexa/penta/pyra
are reduced to corner nodes) and face meshes with a shell thickness; linear elastic materials (several
via references); fixed and displacement (fixed components) constraints, force, pressure and self weight.
Other constraints are reported and ignored. For bending with hexahedra use at least two elements
through the thickness.

**Known solver limitation (tetra10):** in a cantilever test with OpenCourant `latest-20261011` the
10-node tetrahedron deflected about 35 % more than CalculiX on the same mesh, and the starter reports
only 0.70 of the physical mass for tetra10 meshes. Hexahedra (+0.4 % vs. beam theory) and linear
tetrahedra (within 2–9 % of CalculiX) agree. The deck's tetra10 node order was checked against the
starter, so this comes from the solver element; use hexahedra or a fine tetra4 mesh for quantitative
results. Mass scaling can also add a lot of mass for tetra10 meshes: check *MASS ADDED* in
`radioss_0001.out`.

The default templates live in `freecad/ORfemn/templates.json` and use consistent mm / t / s / N / MPa units.
Templates edited in the Template Editor are saved per user to `<FreeCAD user data>/ORfemn/templates.json`
(e.g. `~/.local/share/FreeCAD/ORfemn/`), which then replaces the defaults; *Reset to Defaults* removes it.

## Repository layout

| Path | Contents |
|---|---|
| `freecad/ORfemn/` | The workbench package (the only part that gets installed) |
| `tests/` | Unit tests for the FreeCAD-independent code |
| `tools/keyword_db/` | Scripts that build `keywords_with_parameters.json`: `download_docs.py` (fetch the current Radioss LS-DYNA keyword docs into `data/docs/`), then `extract_cards.py` (card layouts, options, links; also runs `extract_field_info.py` for defaults and descriptions) |
| `tools/examples/` | Scripts that download dynaexamples.com and extract `.k` files into `data/examples/` |
| `tools/legacy/` | Old code kept for reference; not loaded by the workbench |
| `data/` | Keyword list. The scraped Altair Radioss documentation (`data/docs/`, `data/local_documentation/`, `data/Keyword documentation/`), keyword database archives (`data/archiv/`) and examples (`data/examples/`) are not tracked by git; the scripts in `tools/` download or rebuild them |
| `docs/` | Introduction (`ORfe_Introduction.tex/.pdf`) and older workflow documentation (LaTeX/PDF) |

## Tests

```shell
python tests/tests.py   # or: pixi run test
```

The tests cover the FreeCAD-independent `.k` formatting code, templates, deck writer and result
conversion. Two integration tests run the real solver; they are skipped unless OpenRadioss/OpenCourant
is installed in `~/OpenRadioss`.

## License

LGPL-2.1-or-later, like FreeCAD (see [LICENSE](LICENSE)). OpenRadioss and OpenCourant are separate
programs under the AGPL-3.0; the workbench only runs their executables.

## Maintainer

Nicholas Herrmann
nicholas.herrmann@proton.me
