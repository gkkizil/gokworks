# Compact desktop UI: source research

Retrieved **20 October 2026, Europe/Istanbul**. This is a read-only review of real desktop applications' repository source and documentation, **not a live visual audit**. The upstream applications were not installed or run. Every raw source URL below returned HTTP 200 when retrieved. `main` and `master` are moving branches; the PrusaSlicer references are pinned to `version_2.9.2`.

## FreeCAD — task panels and reachable actions

- [Project README](https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/README.md) establishes the parametric CAD context.
- [TaskView.cpp](https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/src/Gui/TaskView/TaskView.cpp): `TaskBox` accepts an expandable flag (lines 84–95); `hideGroupBox` folds the content while keeping its header (124–160). `TaskPanel` uses resizable scroll content without a horizontal scrollbar (194–223). Standard task buttons are inserted into `dialogLayout` above or below the scroll area rather than inside its content (640–662).
- The same file documents a layout failure where collapsed groups squeeze other controls, and explicitly respects their layout minimum sizes (102–114). Compactness must preserve usable controls and scroll access.
- [LICENSE](https://raw.githubusercontent.com/FreeCAD/FreeCAD/main/LICENSE): LGPL 2.1; the reviewed UI file declares `LGPL-2.1-or-later`.

**GOKWORKS adaptation:** keep the current task's main action visible in the page header/command row; scroll parameters and results independently. Use named, keyboard-operable disclosure sections for long explanations and secondary parameters. Preserve technical text and diagram widgets inside these sections, including their minimum sizes; avoid placing an essential control below a large diagram or long form.

## Qt Creator — compact navigation and a consistent command area

- [Project README](https://raw.githubusercontent.com/qt-creator/qt-creator/master/README.md) documents the desktop IDE and its licensing.
- [modemanager.cpp](https://raw.githubusercontent.com/qt-creator/qt-creator/master/src/plugins/coreplugin/modemanager.cpp): the mode selector exposes Icons and Text, Icons Only, and Hidden styles (232–289). `setModeStyle` applies the chosen presentation to both navigation and its action bar (603–613). It also registers mode shortcuts (around 407). This is evidence for an explicit compact-navigation preference, not evidence that unlabeled navigation is best for every user.
- [fancyactionbar.cpp](https://raw.githubusercontent.com/qt-creator/qt-creator/master/src/plugins/coreplugin/fancyactionbar.cpp): command controls share one action layout (351–374), and `setIconsOnly` updates every tool button consistently (386–393).
- [LICENSE.GPL3-EXCEPT](https://raw.githubusercontent.com/qt-creator/qt-creator/master/LICENSES/LICENSE.GPL3-EXCEPT): GPL 3 with The Qt Company GPL Exception 1.0. Reviewed source headers also offer a Qt commercial-license alternative.

**GOKWORKS adaptation:** reduce sidebar branding/padding and keep familiar Turkish module names visible by default. A user-controlled collapsed state can preserve room for tables and diagrams; retain full tooltips and accessible names for collapsed buttons. Keep one consistent page action location, one emphasized primary action, and less prominent export/help commands. Do not infer arbitrary pixel dimensions from this source review.

## PrusaSlicer — progressive disclosure without losing technical options

- [Project README, v2.9.2](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/README.md) describes the desktop model-to-print workflow.
- [Config.hpp](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/src/libslic3r/Config.hpp) defines Simple, Advanced, and Expert option modes (236–241).
- [Tab.cpp](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/src/slic3r/GUI/Tab.cpp): changing mode updates page/group visibility and rebuilds the page tree (907–935); pages keep option groups and selectively reveal them (5248–5268). Description lines are refreshed as part of visibility updates (931–932).
- [Field.cpp](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/src/slic3r/GUI/Field.cpp): `get_tooltip_text` provides option explanations and defaults (197–212), and field controls use these tooltips (e.g. 515, 782, 928).
- [Plater.cpp](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/src/slic3r/GUI/Plater.cpp): the sidebar collapse state is restored (1124–1127); collapse/expand labels are updated (1189–1202); slice/export action visibility reflects workflow readiness (4062–4089).
- [LICENSE, v2.9.2](https://raw.githubusercontent.com/prusa3d/PrusaSlicer/version_2.9.2/LICENSE): GNU AGPL 3. Source file headers also identify AGPL-3.0-or-later.

**GOKWORKS adaptation:** use local sections such as “Gelişmiş seçenekler” and “Teknik açıklama” rather than adding an app-wide expertise mode. Keep common inputs and the result first; reveal detailed formulas, assumptions, standards and diagrams on demand. Disclosure must not recreate widgets, reset values, clear measurement inputs, rerun jobs or change calculation semantics. Safety-relevant scope and active validation errors remain visible beside the result.

## Application across the GOKWORKS screens

| Screens | Primary workspace | Secondary material to reveal on demand |
| --- | --- | --- |
| PDF; DXF / DWG | Source/output selection, file table, visible start/stop action | Export rules and advanced file options |
| BOM; İsimlendirme | Source selection, preview table/tree, main read/apply action | Mapping, format rules and explanatory help |
| K faktörü; ISO geçmeler; Cıvata; Hızlı tork; Ağırlık | Essential inputs, live result and relevant diagram | Formula/standard notes, detailed result table, secondary export commands |
| Geometrik toleranslar | Tolerance selection, measured comparison and diagram | Full reading/measurement/design guidance; keep comparison scope visible |
| Tolerans yığılması | Dimension stack, result and stack diagram | Advanced analysis/import/report options and calculation assumptions |
| Nesting | Parts table, sheet canvas, visible “Yerleştir” action | Sheet/stock/cost settings and detailed import reports |

These mappings are design recommendations based on the reviewed patterns and GOKWORKS' existing Qt pages, not claims that the upstream products implement GOKWORKS workflows. Native Qt widgets, existing GOKWORKS diagrams, existing engine calls and existing stored settings remain the implementation basis. **No third-party code, icons, screenshots, fonts or other assets were copied into the application.**
