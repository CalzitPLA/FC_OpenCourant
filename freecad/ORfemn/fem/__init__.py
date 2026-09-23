"""
OpenRadioss as a solver of the FreeCAD FEM workbench.

- deck_writer: FreeCAD-independent writer of an LS-DYNA format deck from a
  neutral model (nodes, parts, constraints, loads)
- model: builds that model from a FEM analysis (mesh, materials, constraints)
- solver / tasks: the FEM solver object and its Check/Prepare/Solve/Results tasks
- commands: the "Solver OpenRadioss" command, also added to the FEM workbench
"""
