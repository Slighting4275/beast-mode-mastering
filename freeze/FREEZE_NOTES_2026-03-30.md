# Freeze notes — 2026-03-30

This freeze captures the current known-good direction of the application.

## Included behavior
- Stable GUI playback path
- Offline mastered render cache for preview/export
- Gentler DSP preview/export path to avoid clipping and UI instability
- Background-thread GUI export path
- CLI exporter for reliable non-GUI mastering export
- Heuristic analysis / auto-set path

## Not yet included
- True learned end-to-end mastering checkpoint
- User preference learning
- Reference-track style transfer
- Robust album-level consistency handling

## Freeze intent
Treat this snapshot as the baseline before future architecture changes toward a trained mastering assistant or checkpoint-driven system.
