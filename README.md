# Beast Mode Mastering — Freeze 2026-03-30

This repository is a frozen snapshot of the current working Linux desktop mastering assistant.

## Current status
- GUI loads audio, analyzes tracks, previews playback, and exports mastered WAVs.
- Current rendering path is the **stable DSP path**.
- The app still includes TensorFlow plumbing, but it is **not** a trained end-to-end commercial mastering model yet.
- DDSP is intentionally **not** a required runtime dependency in this freeze.

## Repo layout
- `src/beast_mode_mastering/app.py` — main GUI application
- `scripts/export_mastered_cli.py` — reliable non-GUI exporter
- `docs/BUILD_LINUX.md` — distro-specific dependency and build/run notes
- `freeze/FREEZE_NOTES_2026-03-30.md` — snapshot notes
- `freeze/SHA256SUMS.txt` — hash manifest for the freeze

## Quick start
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m beast_mode_mastering.app
```

## Packaging notes
This is a Python application. On Linux, the practical "compile" step is installing the required system libraries and then creating a Python environment for the Python packages.

## License

This project is licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later).

If you distribute modified versions of this project, you must also make the corresponding source code available under the GPL.
