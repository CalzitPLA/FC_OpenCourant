# ORfe – OpenRadioss Workbench for FreeCAD

Create and edit LS-DYNA format input decks (`.k` files, as read by OpenRadioss) inside FreeCAD.

## Dependencies

- FreeCAD >= 1.0 (Python 3, PySide provided by FreeCAD)
- For running simulations: [OpenRadioss](https://github.com/OpenRadioss/OpenRadioss/releases)
  (unpack the release, e.g. to `~/OpenRadioss`; the path can be changed in the run dialog)

## Quick Start

1. Link or copy this repository into your FreeCAD `Mod` directory, e.g.
   `ln -s "$PWD" ~/.local/share/FreeCAD/Mod/ORfe`
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
| `data/` | Scraped documentation, keyword database archives and examples (`data/examples/` is not tracked by git) |
| `docs/` | Workflow documentation (LaTeX/PDF) |

## Tests

```shell
python tests/tests.py   # or: pixi run test
```

The tests cover the FreeCAD-independent `.k` formatting code and templates.

## Maintainer

Nicholas Herrmann
nicholas.herrmann@proton.me
