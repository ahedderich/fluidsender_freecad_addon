# FluidSender FreeCAD Addon — Kickstart

> **Note:** This file lives temporarily inside the `fluidSender` monorepo at `freecad_addon/` for planning purposes. It is intended to be moved into its own dedicated repository once that repo is created, and to serve as that repo's initial `CLAUDE.md`. References to "this repo" below describe the *future* standalone addon repo, not `fluidSender` itself.

## Project Intention

FluidSender is a web-based GCode sender for FluidNC-based CNC machines (see the main [fluidSender](https://github.com/ahedderich/fluidSender) project). Today, getting a toolpath from FreeCAD's CAM workbench into FluidSender is a manual process: post-process to a local file, then upload it through the FluidSender web UI.

The goal of this addon is to close that loop from inside FreeCAD:

- Add a button to FreeCAD's **CAM workbench** toolbar.
- Let the user pick which CAM **operations** (from one or more Jobs) to include.
- Post-process the selection into a single combined GCode file, reusing FreeCAD's existing CAM post-processor pipeline (not reinventing GCode generation).
- Upload that file directly to a FluidSender server instance over HTTP, instead of (or in addition to) saving it locally.

This addon is **FreeCAD-side only**. The receiving HTTP API on the FluidSender server (a new Nuxt server route for third-party file uploads) is tracked separately as [fluidSender#63 — "Add API Endpoint for third party file upload options"](https://github.com/ahedderich/fluidSender/issues/63) and is being built on the `feat/third-party-file-upload-api` branch of the `fluidSender` repo. The two projects should agree on a small, versioned upload API contract (endpoint path, auth, payload shape, response) but otherwise release independently.

This document captures the research done to evaluate feasibility *before* any code was written. Treat it as background/context for kickstarting the addon repo, not as a finished design.

---

## Research Findings: FreeCAD Addon System

### Addon types & distribution

- FreeCAD's [Addon Manager](https://github.com/FreeCAD/AddonManager) recognizes five addon categories: **Workbench**, **Macro**, **Preference Pack**, **Bundle**, **Other**.
- The Addon Manager pulls from a community index at `addons.freecad.org`, regenerated every ~6 hours from a curated list of repos.
- Manual installation is also possible by dropping files into FreeCAD's `Mod/` folder (workbenches) or `Macro/` folder (macros), then restarting FreeCAD.
- **Macro** addons are a single `.FCMacro` Python file; auxiliary files can be declared via a `__Files__` global so the Addon Manager installs them alongside it. Fine for a quick script, but too limited for this project (we need multiple modules: HTTP client, preferences page, selection dialog, icons).
- **Workbench** addons are proper multi-file Python packages (an `InitGui.py` entry point plus supporting modules), installed into `Mod/`, with metadata in a `package.xml` (format documented on the FreeCAD wiki). This is the right category for us, even though we are not building a new modeling workbench — "Workbench" is simply the Addon Manager's bucket for anything beyond a single-file macro.

### Supported languages

- **Python is effectively the only language available to third-party addons.** FreeCAD's core is a C++/Python hybrid, but the Addon Manager has no mechanism for third-party addons to ship or hot-load compiled binary extensions into a running FreeCAD instance.
- UI dialogs are built with Qt (PySide2/PySide6, bundled with FreeCAD), but that's driven entirely from Python — not a separate implementation language.
- Conclusion: this addon will be 100% Python, which conveniently matches skills already in use on the FluidSender project.

### Adding a button to the CAM workbench toolbar

- FreeCAD does **not** offer a stable, officially documented API for a third-party addon to inject a toolbar button into another (built-in) workbench. The menus/toolbars that ship with a workbench "cannot be changed" through normal customization APIs.
- However, there is a known, precedented technique (used by addons such as Lattice2 injecting into PartDesign): from `InitGui.py`, hook into workbench activation and call:

  ```python
  Gui.activateWorkbench("CAMWorkbench")
  wb = Gui.getWorkbench("CAMWorkbench")
  wb.appendToolbar("FluidSender", ["FluidSender_PostAndSend"])
  ```

  This only works once the target workbench has been activated at least once in the session, and injected toolbars may need `wb.reloadActive()` (or a workbench switch) to become visible immediately.
- **This is not a stable contract.** It relies on internal `Gui.Workbench` methods and on CAM workbench internals that have already broken custom post-processor behavior once (see [FreeCAD#26006 — "Custom post processors fail in v1.2"](https://github.com/FreeCAD/FreeCAD/issues/26006)). The injection code must be defensive (try/except, graceful no-button fallback) and the addon must track/pin tested FreeCAD versions.

### CAM post-processor pipeline (reuse, don't reinvent)

- FreeCAD's Path/CAM workbench already has the exact extension point we need: post-processor scripts, conventionally named `..._post.py` (lowercase suffix), located either in the user's FreeCAD macro directory or bundled under `Mod/CAM/Path/Post/scripts/`.
- A post-processor exposes an `export(objectslist, filename, argstring)` function:
  - `objectslist` — a **collection** of post-processable objects (operations, tools, jobs). Combining multiple selected operations into one output file is already the default behavior of a Job's "Post Process" step — **we don't need to build this ourselves**.
  - `filename` — the output destination.
  - `argstring` — extra config passed through.
  - It returns/writes a GCode string built up incrementally (`export()` handles job-level concerns like comments/coolant; delegates per-operation GCode generation to a `parse()` function).
- A `grbl_post.py` post-processor is already bundled with CAM and is close to FluidNC's dialect. We should **reuse or lightly extend it**, not write GCode emission from scratch. Any FluidNC-specific formatting quirks belong in the post-processor's comment/header output only — the ack/planner-buffer timing behaviors documented in the main `fluidSender` repo's `CLAUDE.md` (Category A/B1/B2/C command classification) are a **sender/sim concern**, not something FreeCAD needs to model; the GCode text itself is unaffected by that classification.
- Because post-processor scripts are just Python, nothing stops `export()` (or a thin wrapper command around it) from making an HTTP call after generating the GCode string, instead of only writing to a local file.

### Network access from FreeCAD Python

- Standard library `urllib.request` is usable from FreeCAD's bundled Python for HTTP requests (including POST with a body), confirmed via FreeCAD's own Addon Manager source (which uses `urllib.request` internally).
- The third-party `requests` library is commonly recommended for ergonomics but is **not guaranteed to be bundled** with every FreeCAD Python distribution — should be treated as an optional dependency with a stdlib fallback, or vendored, if used.
- No FreeCAD-specific sandboxing prevents outbound network calls from addon code.

### Precedent check

- Searched for existing "FreeCAD → network CNC/3D-printer controller" addons (e.g. OctoPrint integration) as a sanity check for feasibility and prior art.
- **No such addon currently exists.** Native OctoPrint integration is an open FreeCAD feature request ([FreeCAD#27320](https://github.com/FreeCAD/FreeCAD/issues/27320)), not a shipped addon. The community workaround today is mapping a network drive to a watched folder, or shelling out to `curl` in a post-processing step.
- Takeaway: this addon would be genuinely novel rather than an adaptation of an established pattern. The individual building blocks (toolbar injection, post-processor reuse, Python HTTP calls) are all independently precedented and low-risk; the *combination* is new, so expect some trial and error, particularly around the toolbar injection point and CAM workbench version compatibility.

---

## Proposed Architecture (starting point, not final)

1. **Addon package** — Workbench-type Addon Manager package: `InitGui.py`, a preferences page (FluidSender host/port/token), an HTTP client module, an operation-selection dialog, and the post-processor integration.
2. **Toolbar button** — injected into the CAM workbench toolbar on activation, guarded so a failed injection doesn't break FreeCAD startup.
3. **Command flow**: user clicks button → dialog to select operations/Job(s) → call existing CAM post-processing (reusing/extending `grbl_post.py`) to produce a combined GCode string → HTTP POST the result to the configured FluidSender endpoint → show success/failure feedback in FreeCAD's report view.
4. **Config/credentials** — stored via FreeCAD's standard preferences (`ParameterGet`), which is **plaintext**, not a secrets vault. If the FluidSender instance has `auth.enabled`, decide whether the addon needs to hold a token at all, or whether this integration is scoped to local-network/no-auth deployments only.

## Open Questions / Long-Term Concerns

- **FreeCAD API stability**: CAM/Path internals have already had breaking changes across versions (see FreeCAD#26006). Need a tested-version matrix and defensive coding around the toolbar-injection and post-processor APIs.
- **Operation selection scope**: default CAM Job post-processing already combines *all* operations in a Job into one file. If we want an arbitrary subset (cross-job cherry-picking), that requires custom dialog UI beyond what CAM gives for free — decide if MVP needs this or if "one Job = one upload" is sufficient to start.
- **Credential storage**: FreeCAD preferences are not encrypted at rest; needs an explicit decision on whether/how auth tokens are handled.
- **Testability**: FreeCAD's `FreeCAD`/`FreeCADGui`/`Path` Python modules only exist inside FreeCAD's bundled interpreter. Unit testing requires either mocking those modules or running headless FreeCAD (`freecadcmd --console`) in CI — this will need its own CI setup distinct from the Bun/Vue or `uv`/pytest conventions used elsewhere in the FluidSender ecosystem.
- **API contract with FluidSender**: needs to be defined jointly with [fluidSender#63](https://github.com/ahedderich/fluidSender/issues/63) — endpoint path, auth mechanism, payload format (raw GCode body vs. multipart file upload), and response/error shape. Keep it small and versioned so the two repos can evolve independently.
- **Repo/release lifecycle**: this addon is Python/Qt/FreeCAD — none of the Bun/Vue/Nuxt/FastAPI stack conventions from the `fluidSender` monorepo apply here. It should have its own repo, its own `package.xml` versioning, and its own CI (general security practices — no hardcoded secrets, TLS for the upload call — still apply).
