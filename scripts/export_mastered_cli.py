# Copyright (C) 2026 Nick
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
from __future__ import annotations

import os
import sys
import numpy as np
import librosa
import soundfile as sf

from beast_mode_mastering.app import AudioEngine, AIAnalyzer, MasterParams, TARGET_SR


def auto_analyze_params(audio: np.ndarray, sr: int) -> MasterParams:
    analyzer = AIAnalyzer()
    mono = np.mean(audio, axis=1).astype(np.float32)
    stereo = audio
    if sr != TARGET_SR:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=TARGET_SR)
        stereo = np.stack([
            librosa.resample(audio[:, 0], orig_sr=sr, target_sr=TARGET_SR),
            librosa.resample(audio[:, 1], orig_sr=sr, target_sr=TARGET_SR),
        ], axis=1)
        sr = TARGET_SR

    S = np.abs(librosa.stft(mono, n_fft=2048, hop_length=512))
    centroid = float(np.mean(librosa.feature.spectral_centroid(S=S, sr=sr)))
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(S=S, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)))
    rms = librosa.feature.rms(y=mono, frame_length=2048, hop_length=512)[0]
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-9))
    dyn_range = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 10))
    onset_env = librosa.onset.onset_strength(y=mono, sr=sr)
    transients = float(np.mean(onset_env))
    harmonic, percussive = librosa.effects.hpss(mono)
    harmonic_ratio = float(np.mean(np.abs(harmonic)) / (np.mean(np.abs(percussive)) + 1e-6))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    spec_mean = np.mean(S, axis=1)
    low = float(np.sum(spec_mean[(freqs >= 20) & (freqs < 200)]))
    mid = float(np.sum(spec_mean[(freqs >= 800) & (freqs < 2500)]))
    presence = float(np.sum(spec_mean[(freqs >= 2500) & (freqs < 5000)]))
    air = float(np.sum(spec_mean[(freqs >= 5000) & (freqs < 12000)]))
    vocal = float(np.sum(spec_mean[(freqs >= 1000) & (freqs < 4000)]))
    total = low + mid + presence + air + 1e-9
    left, right = stereo[:, 0], stereo[:, 1]
    mid_sig = 0.5 * (left + right)
    side_sig = 0.5 * (left - right)
    stereo_width = float(np.sqrt(np.mean(side_sig ** 2)) / (np.sqrt(np.mean(mid_sig ** 2)) + 1e-9))
    crest = float(np.max(np.abs(mono)) / (np.sqrt(np.mean(mono ** 2)) + 1e-9))

    genre = analyzer._predict_genre(centroid, dyn_range, transients, stereo_width, harmonic_ratio, air / total)
    params = analyzer._infer_controls(
        centroid=centroid,
        rolloff=rolloff,
        bandwidth=bandwidth,
        dyn_range=dyn_range,
        transients=transients,
        stereo_width=stereo_width,
        low_ratio=low / total,
        mid_ratio=mid / total,
        presence_ratio=presence / total,
        air_ratio=air / total,
        vocal_ratio=vocal / total,
        crest_factor=crest,
        genre=genre,
    )
    return params


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python scripts/export_mastered_cli.py INPUT_AUDIO OUTPUT_WAV")
        return 1

    in_path = argv[1]
    out_path = argv[2]

    if not os.path.isfile(in_path):
        print(f"input not found: {in_path}")
        return 1

    engine = AudioEngine()
    engine.load_file(in_path)
    params = auto_analyze_params(engine.audio, engine.sr)
    params.loudness = min(params.loudness, 30.0)
    params.harmonics = min(params.harmonics, 15.0)
    params.punch = min(params.punch, 35.0)
    params.depth = min(params.depth, 15.0)
    params.dynamic_range = max(params.dynamic_range, 75.0)
    engine.set_master_params(params)
    mastered = engine.render_mastered_full()
    sf.write(out_path, mastered, engine.sr, subtype="PCM_24")
    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
