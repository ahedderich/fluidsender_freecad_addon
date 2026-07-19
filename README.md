# FluidSender Upload — FreeCAD CAM Addon

Post-process selected CAM operations and upload the resulting GCode directly to a
[FluidSender](https://github.com/ahedderich/fluidSender) server, without a manual
save/upload round trip. See `CLAUDE.md` for the background research this addon is
based on, and `external-api.md` for the FluidSender upload API it talks to.

## Status

Confirmed working end-to-end on FreeCAD 1.1.1 (macOS), as of 2026-07-19: addon
loads, preferences page and toolbar injection register, folder browsing works,
post-processing correctly restricts to the checked operations, and upload
(including overwrite-by-selecting-an-existing-file) succeeds. Originally built
in an environment without FreeCAD or a GUI, then hardened against a real
install — see "Known limitations" below for the two real FreeCAD bugs that
were found and worked around along the way, and for what's still unverified
(no CI, no packaging/release process yet).

## Install (manual, for development)

Clone/copy this folder into your FreeCAD `Mod/` directory, e.g.:

```
~/.local/share/FreeCAD/Mod/FluidSenderUpload/   (Linux)
%APPDATA%/FreeCAD/Mod/FluidSenderUpload/         (Windows)
~/Library/Application Support/FreeCAD/Mod/FluidSenderUpload/  (macOS)
```

so that `InitGui.py` sits directly inside that folder. Restart FreeCAD. On startup
you should see either a "FluidSender" button appear in the CAM workbench toolbar, or
(if that injection failed — see below) a separate selectable "FluidSender" workbench
in the workbench dropdown, which always has the command available.

## Usage

1. **Edit > Preferences > FluidSender**: add one or more FluidSender instances
   (label, URL, API token). Generate a token in the FluidSender UI under
   *Settings > Authentication > Generate API Token* — grant it "Allow Load" only if
   you want this addon to be able to start jobs remotely, not just upload them.
2. Select a CAM Job (or one of its operations) and run the FluidSender command
   (CAM toolbar button, or the FluidSender workbench's toolbar as a fallback).
3. In the dialog: pick the target instance, check which operations to include,
   browse/create the destination folder on the server, set a filename, and
   optionally "load as active job", then upload. Double-click an existing file
   in the folder listing to select it as the filename (for overwriting it).
   The destination folder, filename, and operation checkboxes are remembered
   for the rest of the FreeCAD session (not across restarts) so re-opening the
   dialog to re-upload the same thing is a single click away.

## Architecture

```
InitGui.py                          FreeCAD entry point: registers the command,
                                     the FluidSender workbench (fallback), and
                                     best-effort injects a CAM toolbar button.
fluidsender_addon/
  client.py, errors.py              FluidSenderClient: stdlib-only HTTP client for
                                     the external API (upload/list/create folder).
                                     No FreeCAD imports -- testable with pytest.
  sanitize.py                       Mirrors the server's filename/folder character
                                     rules, for client-side preview.
  config.py                         InstanceConfig + InstanceStore, storage
                                     abstracted behind a ParameterGroup Protocol so
                                     it's testable outside FreeCAD.
  session_state.py                  In-process (not persisted to disk) memory of
                                     the last folder/filename/operation-selection
                                     used in the dialog, current session only.
  freecad_prefs.py                  Wires InstanceStore to real FreeCAD preferences
                                     (FreeCAD-only, thin).
  commands.py                       The FluidSender_PostAndSend command.
  workbench.py                      Always-available fallback workbench.
  toolbar_injection.py              Best-effort CAM toolbar button injection.
  postprocessing.py                 Bridges checked operations to FreeCAD's CAM
                                     post-processor (Path.Post.Processor).
  gui/preferences.py                Preferences page: instance add/edit/remove.
  gui/post_process_dialog.py        Main upload dialog.
tests/                               pytest suite for the FreeCAD-free modules above.
```

## Development

FreeCAD/FreeCADGui/Path/PySide only exist inside FreeCAD's bundled interpreter, so
`client.py`, `errors.py`, `sanitize.py`, `config.py`, and `session_state.py` are
deliberately kept free of those imports and are the only modules covered by the
test suite here. Everything under `gui/`, plus `commands.py`, `postprocessing.py`,
`workbench.py`, `toolbar_injection.py`, and `freecad_prefs.py`, can only be
exercised by actually running inside FreeCAD (see "Known limitations").

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest
ruff check .
mypy fluidsender_addon tests
```

## Known limitations / things to verify against a real FreeCAD install

- **CAM post-processor API is a moving target — two approaches were tried and
  failed against a real FreeCAD 1.1.1 install before finding one that works.**
  `postprocessing.py` originally filtered to selected operations the way
  FreeCAD's own "Post Process Selected" command does on `main` — passing
  `{"job": job, "operations": operations}` into
  `PostProcessorFactory.get_post_processor()`. On 1.1.1 that hits an upstream
  ordering bug in `PostProcessor.__init__` (`self._machine` gets resolved from
  the dict *before* it's unwrapped into the real Job) and crashes with
  `AttributeError: 'dict' object has no attribute 'Fixtures'`. Switching to
  constructing with the plain Job and setting `postprocessor._operations`
  afterward avoided the crash, but turned out to be a silent no-op: 1.1.1's
  actual installed `PostProcessor._buildPostList()` (confirmed by reading the
  real installed source via FreeCAD's Python console) always iterates
  `self._job.Operations.Group` directly in every ordering mode and never reads
  `self._operations` — that filtering attribute is a `main`-branch-only
  mechanism (`Path.Post.PostList`, which doesn't exist on 1.1.1 at all). The
  fix that actually works on 1.1.1: wrap the real Job in a proxy
  (`_FilteredJobProxy` in `postprocessing.py`) that overrides just
  `.Operations.Group` to return the filtered list and forwards every other
  attribute through — since `_buildPostList()` only ever reads operations
  through that attribute chain, this works regardless of which `OrderOutputBy`
  mode the Job uses. FreeCAD has already broken custom post-processor behavior
  once before across a version bump
  ([FreeCAD#26006](https://github.com/FreeCAD/FreeCAD/issues/26006)), and the
  1.2+ "Machine-based" flow (`job.Machine`) is still not handled here —
  re-verify this module if you upgrade FreeCAD.
- **CAM toolbar injection is not a stable public API.** `toolbar_injection.py`
  writes into FreeCAD's toolbar-customization parameter tree (the same technique
  the Lattice2 addon uses to inject into PartDesign) rather than calling
  undocumented `Workbench.appendToolbar()` at runtime, but it still depends on the
  CAM workbench's internal name (`"CAMWorkbench"`) not changing. If it fails, the
  addon's own **FluidSender workbench is the always-available fallback** — that's
  why it exists.
- **Single-Job operation selection only**, by design — see the project CLAUDE.md's
  discussion of why cross-Job selection risks mismatched Tool Controllers/units/
  post-processor settings.
- **Preferences are plaintext.** FreeCAD's `ParamGet` preference storage is not
  encrypted at rest; API tokens are visible in `user.cfg`. The preferences page
  says so; there's no secrets-manager integration here.
- **License placeholder.** `package.xml` currently declares `LGPL-2.1-or-later`
  (the common choice across the FreeCAD addon ecosystem) as a placeholder — pick
  the actual license before publishing, and add a `LICENSE` file.
- **Icon is a placeholder** (`Resources/icons/fluidsender.svg`) — replace with real
  artwork.
- **No CI yet.** Per the project CLAUDE.md, this addon needs its own CI distinct
  from the Bun/Vue/`uv`+pytest conventions used elsewhere in the fluidSender
  monorepo — headless FreeCAD (`freecadcmd --console`) or mocked `FreeCAD`/
  `FreeCADGui`/`Path` modules would be needed to test `gui/`, `commands.py`,
  `workbench.py`, and `postprocessing.py` in CI; only the FreeCAD-free modules
  are covered today.
