from __future__ import annotations

import math
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf
import librosa

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

try:
    import tensorflow as tf
except Exception:  # pragma: no cover
    tf = None

try:
    import ddsp  # noqa: F401
except Exception:  # pragma: no cover
    ddsp = None

APP_NAME = "Beast Mode Neural Mastering Elite"
TARGET_SR = 48000
DEFAULT_BLOCKSIZE = 1024
DEFAULT_CHUNK = 16384
DEFAULT_CONTEXT = 4096
DEFAULT_LATENCY = "low"


# ------------------------------- Utilities ------------------------------- #

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio[:, :2]


def linear_to_db(value: float, floor: float = 1e-12) -> float:
    return 20.0 * math.log10(max(abs(value), floor))


def db_to_linear(db: float) -> float:
    return float(10.0 ** (db / 20.0))


@dataclass
class MasterParams:
    warmth: float = 50.0
    brightness: float = 50.0
    clarity: float = 50.0
    punch: float = 50.0
    width: float = 50.0
    depth: float = 20.0
    loudness: float = 50.0
    dynamic_range: float = 65.0
    harmonics: float = 30.0
    vocal_presence: float = 50.0

    def vector(self) -> np.ndarray:
        return np.array(list(asdict(self).values()), dtype=np.float32)[None, :]

    def normalized(self) -> Dict[str, float]:
        return {k: getattr(self, k) / 100.0 for k in self.__annotations__.keys()}


# -------------------------- Classic fallback engine -------------------------- #

class ClassicFallbackProcessor:
    def __init__(self, sr: int):
        self.sr = sr
        self.last_lufs = -70.0
        self.last_peak = -70.0

    def process_block(self, x: np.ndarray, params: MasterParams) -> np.ndarray:
        p = params.normalized()
        y = x.astype(np.float32).copy()

        # Simple multiband tone shaping in FFT domain.
        n = max(512, int(2 ** math.ceil(math.log2(len(y)))))
        spec_l = np.fft.rfft(y[:, 0], n=n)
        spec_r = np.fft.rfft(y[:, 1], n=n)
        freqs = np.fft.rfftfreq(n, 1.0 / self.sr)
        low = np.exp(-0.5 * ((freqs - 120.0) / 120.0) ** 2)
        air = np.exp(-0.5 * ((freqs - 9000.0) / 3000.0) ** 2)
        presence = np.exp(-0.5 * ((freqs - 3000.0) / 1300.0) ** 2)
        clarity = np.exp(-0.5 * ((freqs - 1800.0) / 1000.0) ** 2)
        mask = (
            1.0
            + (p["warmth"] - 0.5) * 1.0 * low
            + (p["brightness"] - 0.5) * 1.2 * air
            + (p["vocal_presence"] - 0.5) * 1.0 * presence
            + (p["clarity"] - 0.5) * 0.9 * clarity
        )
        mask = np.clip(mask, 0.3, 3.0)
        y[:, 0] = np.fft.irfft(spec_l * mask, n=n)[: len(y)].astype(np.float32)
        y[:, 1] = np.fft.irfft(spec_r * mask, n=n)[: len(y)].astype(np.float32)

        # Punch via HP transient emphasis.
        if p["punch"] > 0.001:
            alpha = 0.92
            hp = np.zeros_like(y)
            prev_x = np.zeros(2, dtype=np.float32)
            prev_y = np.zeros(2, dtype=np.float32)
            for i in range(len(y)):
                cur = y[i]
                hp[i] = cur - prev_x + alpha * prev_y
                prev_x = cur
                prev_y = hp[i]
            y = y + hp * (0.4 * p["punch"])

        # Width in mid/side.
        mid = 0.5 * (y[:, 0] + y[:, 1])
        side = 0.5 * (y[:, 0] - y[:, 1])
        side *= 0.4 + 1.4 * p["width"]
        y = np.stack([mid + side, mid - side], axis=1).astype(np.float32)

        # Ambience with a tiny short reverb.
        if p["depth"] > 0.001:
            wet = np.zeros_like(y)
            for delay, gain in [(int(self.sr * 0.021), 0.24), (int(self.sr * 0.039), 0.18), (int(self.sr * 0.053), 0.12)]:
                if delay < len(y):
                    wet[delay:] += y[:-delay] * gain
            y = y * (1.0 - 0.25 * p["depth"]) + wet * (0.35 * p["depth"])

        # Harmonics and loudness.
        drive = 1.0 + 1.2 * p["harmonics"] + 0.5 * p["loudness"]
        y = np.tanh(y * drive).astype(np.float32)

        # Dynamic range: higher value preserves more dynamics.
        dyn_keep = p["dynamic_range"]
        thresh = 0.25 + 0.35 * dyn_keep
        over = np.maximum(np.abs(y) - thresh, 0.0)
        y = np.sign(y) * (np.minimum(np.abs(y), thresh) + over * (0.15 + 0.5 * dyn_keep))

        # Output gain.
        y *= (0.8 + 0.8 * p["loudness"])
        y = np.tanh(y)

        peak = float(np.max(np.abs(y)) + 1e-12)
        rms = float(np.sqrt(np.mean(y ** 2)) + 1e-12)
        self.last_peak = linear_to_db(peak)
        self.last_lufs = -0.691 + 10.0 * math.log10(max(rms * rms, 1e-12))
        return y.astype(np.float32)


# -------------------------- Neural mastering pipeline -------------------------- #

class NeuralMasteringPipeline:
    def __init__(self, sr: int):
        self.sr = sr
        self.external_model = None
        self.model_path: Optional[str] = None
        self.model_name = "Internal TF spectral master"
        self.available = tf is not None
        self._graph_lock = threading.Lock()
        self._build_graphs()

    def _build_graphs(self) -> None:
        if tf is None:
            self._infer_graph = None
            return

        @tf.function(reduce_retracing=True)
        def default_graph(audio, controls):
            # audio: [1, N, 2], controls: [1, 10]
            x = tf.cast(audio, tf.float32)
            c = tf.cast(controls, tf.float32)[0]

            def channel_process(sig):
                stft = tf.signal.stft(sig, frame_length=512, frame_step=128, fft_length=512, window_fn=tf.signal.hann_window)
                mag = tf.abs(stft)
                phase = tf.math.angle(stft)
                bins = tf.shape(mag)[-1]
                f = tf.linspace(0.0, 1.0, bins)

                warmth = (c[0] / 100.0 - 0.5)
                brightness = (c[1] / 100.0 - 0.5)
                clarity = (c[2] / 100.0 - 0.5)
                vocal = (c[9] / 100.0 - 0.5)

                low = tf.exp(-0.5 * tf.square((f - 0.025) / 0.035))
                air = tf.exp(-0.5 * tf.square((f - 0.38) / 0.15))
                clarity_band = tf.exp(-0.5 * tf.square((f - 0.16) / 0.07))
                vocal_band = tf.exp(-0.5 * tf.square((f - 0.20) / 0.06))
                mask = 1.0 + warmth * 1.0 * low + brightness * 1.2 * air + clarity * 0.9 * clarity_band + vocal * 1.1 * vocal_band
                mask = tf.clip_by_value(mask, 0.35, 3.0)
                mag2 = mag * mask[tf.newaxis, :]
                comp = tf.complex(tf.cos(phase), tf.sin(phase)) * tf.cast(mag2, tf.complex64)
                y = tf.signal.inverse_stft(
                    comp,
                    frame_length=512,
                    frame_step=128,
                    fft_length=512,
                    window_fn=tf.signal.hann_window,
                )
                target_len = tf.shape(sig)[0]
                y = y[:target_len]
                pad = tf.maximum(0, target_len - tf.shape(y)[0])
                y = tf.pad(y, [[0, pad]])
                return y

            left = channel_process(x[0, :, 0])
            right = channel_process(x[0, :, 1])
            y = tf.stack([left, right], axis=-1)

            # Mid/side width.
            width = c[4] / 100.0
            mid = 0.5 * (y[:, 0] + y[:, 1])
            side = 0.5 * (y[:, 0] - y[:, 1]) * (0.35 + 1.55 * width)
            y = tf.stack([mid + side, mid - side], axis=-1)

            # Depth / ambience.
            depth = c[5] / 100.0
            if True:
                def add_delay(sig, delay, gain):
                    shifted = tf.pad(sig[:-delay], [[delay, 0]]) if delay > 0 else sig
                    return sig + shifted * gain
                y = tf.stack([
                    add_delay(y[:, 0], 1000, 0.18 * depth) + add_delay(y[:, 0], 1800, 0.12 * depth),
                    add_delay(y[:, 1], 1200, 0.18 * depth) + add_delay(y[:, 1], 2100, 0.12 * depth),
                ], axis=-1)

            # Punch / harmonic excitation / macro compression.
            punch = c[3] / 100.0
            harm = c[8] / 100.0
            loud = c[6] / 100.0
            dyn = c[7] / 100.0
            alpha = 0.94
            hp0 = tf.concat([[y[0, 0]], y[1:, 0] - y[:-1, 0] + alpha * y[:-1, 0]], axis=0)
            hp1 = tf.concat([[y[0, 1]], y[1:, 1] - y[:-1, 1] + alpha * y[:-1, 1]], axis=0)
            y = y + tf.stack([hp0, hp1], axis=-1) * (0.18 * punch)
            y = tf.math.tanh(y * (1.0 + 1.6 * harm + 0.8 * loud))

            # Soft dynamic-range shaping.
            dyn_keep = dyn
            thresh = 0.22 + 0.40 * dyn_keep
            ay = tf.abs(y)
            over = tf.nn.relu(ay - thresh)
            y = tf.sign(y) * (tf.minimum(ay, thresh) + over * (0.12 + 0.55 * dyn_keep))
            y = tf.math.tanh(y * (0.9 + 1.2 * loud))
            return y[tf.newaxis, ...]

        self._infer_graph = default_graph

    def load_external_model(self, path: str) -> None:
        if tf is None:
            raise RuntimeError("TensorFlow is not installed.")
        with self._graph_lock:
            model = tf.keras.models.load_model(path, compile=False)
            self.external_model = model
            self.model_path = path
            self.model_name = f"External model: {os.path.basename(path)}"
            # Prewarm once.
            audio = np.zeros((1, DEFAULT_CHUNK + 2 * DEFAULT_CONTEXT, 2), dtype=np.float32)
            controls = np.zeros((1, 10), dtype=np.float32)
            _ = self._run_model(audio, controls)

    def _run_model(self, audio: np.ndarray, controls: np.ndarray) -> np.ndarray:
        if tf is None:
            return audio
        if self.external_model is not None:
            out = None
            try:
                out = self.external_model([audio, controls], training=False)
            except Exception:
                try:
                    out = self.external_model({"audio": audio, "controls": controls}, training=False)
                except Exception:
                    out = self.external_model(audio, training=False)
            if isinstance(out, (list, tuple)):
                out = out[0]
            return np.asarray(out.numpy() if hasattr(out, "numpy") else out, dtype=np.float32)
        out = self._infer_graph(tf.convert_to_tensor(audio), tf.convert_to_tensor(controls))
        return np.asarray(out.numpy(), dtype=np.float32)

    def process_segment(self, segment: np.ndarray, params: MasterParams) -> np.ndarray:
        if tf is None:
            return segment.astype(np.float32)
        audio = segment[None, :, :].astype(np.float32)
        controls = params.vector()
        with self._graph_lock:
            y = self._run_model(audio, controls)
        if y.ndim == 3:
            y = y[0]
        return np.asarray(y, dtype=np.float32)


class NeuralChunkWorker:
    def __init__(self, pipeline: NeuralMasteringPipeline, fallback: ClassicFallbackProcessor):
        self.pipeline = pipeline
        self.fallback = fallback
        self.audio: Optional[np.ndarray] = None
        self.sr = TARGET_SR
        self.params = MasterParams()
        self.chunk_size = DEFAULT_CHUNK
        self.context = DEFAULT_CONTEXT
        self.cache: Dict[Tuple[int, int], np.ndarray] = {}
        self.generation = 0
        self._queue: "queue.PriorityQueue[Tuple[int, int]]" = queue.PriorityQueue()
        self._pending = set()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def configure(self, audio: np.ndarray, sr: int, params: MasterParams) -> None:
        with self._lock:
            self.audio = audio
            self.sr = sr
            self.params = params
            self.cache.clear()
            self.generation += 1
            self._pending.clear()
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Exception:
                    break

    def set_params(self, params: MasterParams) -> None:
        with self._lock:
            self.params = params
            self.cache.clear()
            self.generation += 1
            self._pending.clear()
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Exception:
                    break

    def request(self, chunk_idx: int, priority: int = 50) -> None:
        with self._lock:
            if self.audio is None:
                return
            key = (chunk_idx, self.generation)
            if key in self.cache or key in self._pending:
                return
            self._pending.add(key)
            self._queue.put((priority, chunk_idx))

    def get_cached(self, chunk_idx: int) -> Optional[np.ndarray]:
        with self._lock:
            return self.cache.get((chunk_idx, self.generation))

    def ensure_ready(self, chunk_idx: int) -> Optional[np.ndarray]:
        cached = self.get_cached(chunk_idx)
        if cached is not None:
            return cached
        return self._process_one(chunk_idx)

    def _loop(self) -> None:
        while True:
            try:
                _, idx = self._queue.get(timeout=0.1)
            except Exception:
                continue
            self._process_one(idx)

    def _segment_for_chunk(self, idx: int) -> Tuple[np.ndarray, int, int, int, int]:
        assert self.audio is not None
        chunk_start = idx * self.chunk_size
        chunk_end = min(chunk_start + self.chunk_size, len(self.audio))
        seg_start = max(0, chunk_start - self.context)
        seg_end = min(len(self.audio), chunk_end + self.context)
        left_pad = chunk_start - seg_start
        right_pad = seg_end - chunk_end
        segment = self.audio[seg_start:seg_end]
        if left_pad < self.context:
            segment = np.pad(segment, ((self.context - left_pad, 0), (0, 0)))
            left_pad = self.context
        if right_pad < self.context:
            segment = np.pad(segment, ((0, self.context - right_pad), (0, 0)))
            right_pad = self.context
        return segment.astype(np.float32), chunk_start, chunk_end, left_pad, right_pad

    def _process_one(self, idx: int) -> Optional[np.ndarray]:
        with self._lock:
            audio = self.audio
            params = self.params
            gen = self.generation
        if audio is None:
            return None
        key = (idx, gen)
        try:
            segment, chunk_start, chunk_end, left_pad, right_pad = self._segment_for_chunk(idx)
            processed = self.pipeline.process_segment(segment, params)
            start = left_pad
            stop = start + (chunk_end - chunk_start)
            trimmed = processed[start:stop]
            with self._lock:
                self.cache[key] = trimmed.astype(np.float32)
        finally:
            with self._lock:
                self._pending.discard(key)
        return self.get_cached(idx)


# ------------------------------ AI Analyzer ------------------------------ #

class AIAnalyzer(QObject):
    analysis_ready = pyqtSignal(dict, object)
    analysis_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._thread: Optional[threading.Thread] = None

    def analyze_async(self, audio: np.ndarray, sr: int) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker, args=(audio.copy(), sr), daemon=True)
        self._thread.start()

    def _worker(self, audio: np.ndarray, sr: int) -> None:
        try:
            mono = np.mean(audio, axis=1).astype(np.float32)
            if sr != TARGET_SR:
                mono = librosa.resample(mono, orig_sr=sr, target_sr=TARGET_SR)
                stereo = np.stack([
                    librosa.resample(audio[:, 0], orig_sr=sr, target_sr=TARGET_SR),
                    librosa.resample(audio[:, 1], orig_sr=sr, target_sr=TARGET_SR),
                ], axis=1)
                sr = TARGET_SR
            else:
                stereo = audio

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

            genre = self._predict_genre(centroid, dyn_range, transients, stereo_width, harmonic_ratio, air / total)
            params = self._infer_controls(
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
            result = {
                "genre_prediction": genre,
                "frequency_profile": {
                    "centroid_hz": round(centroid, 1),
                    "bandwidth_hz": round(bandwidth, 1),
                    "rolloff_hz": round(rolloff, 1),
                },
                "dynamic_range_score": round(dyn_range, 2),
                "transient_score": round(transients, 4),
                "stereo_width_score": round(stereo_width, 4),
                "vocal_presence_score": round(vocal / total, 4),
            }
            self.analysis_ready.emit(result, params)
        except Exception as exc:
            self.analysis_failed.emit(str(exc))

    def _predict_genre(self, centroid, dyn_range, transients, stereo_width, harmonic_ratio, air_ratio):
        if transients > 2.8 and centroid > 2100 and dyn_range < 14:
            return "Modern Metal / Hard Rock"
        if harmonic_ratio > 1.7 and dyn_range > 16:
            return "Acoustic / Singer-Songwriter"
        if stereo_width > 0.55 and centroid > 2300:
            return "Pop / EDM"
        if dyn_range > 18 and centroid < 1700:
            return "Cinematic / Orchestral"
        return "Balanced Contemporary Mix"

    def _infer_controls(self, **f):
        genre = f["genre"]
        warmth = 48 + (0.28 - f["low_ratio"]) * -120
        brightness = 48 + (f["air_ratio"] - 0.16) * 220
        clarity = 50 + (0.22 - f["mid_ratio"]) * -120
        punch = 45 + (f["transients"] - 1.5) * 12 + (f["crest_factor"] - 4.0) * 6
        width = 45 + (f["stereo_width"] - 0.30) * 120
        depth = 18 + (12.0 - f["dyn_range"]) * 1.8
        loudness = 55 + (12.0 - f["dyn_range"]) * 1.6
        dynamic_range = 72 - (12.0 - f["dyn_range"]) * 2.5
        harmonics = 28 + (1800.0 - f["centroid"]) * 0.01 + ("Metal" in genre) * 10
        vocal_presence = 50 + (f["vocal_ratio"] - 0.24) * 170
        if "Metal" in genre:
            punch += 8
            clarity += 6
            harmonics += 8
            width += 5
            depth -= 6
        elif "Acoustic" in genre:
            depth += 8
            dynamic_range += 8
            loudness -= 8
            punch -= 8
        elif "EDM" in genre:
            loudness += 10
            width += 10
            brightness += 8
            dynamic_range -= 10
        return MasterParams(
            warmth=clamp(warmth, 0, 100),
            brightness=clamp(brightness, 0, 100),
            clarity=clamp(clarity, 0, 100),
            punch=clamp(punch, 0, 100),
            width=clamp(width, 0, 100),
            depth=clamp(depth, 0, 100),
            loudness=clamp(loudness, 0, 100),
            dynamic_range=clamp(dynamic_range, 0, 100),
            harmonics=clamp(harmonics, 0, 100),
            vocal_presence=clamp(vocal_presence, 0, 100),
        )


# ------------------------------ Audio engine ------------------------------ #

class AudioEngine(QObject):
    position_changed = pyqtSignal(float)
    meters_changed = pyqtSignal(float, float)
    file_loaded = pyqtSignal(str)
    model_state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio: Optional[np.ndarray] = None
        self.sr = TARGET_SR
        self.position = 0
        self.is_playing = False
        self.use_mastered = True
        self.stream: Optional[sd.OutputStream] = None
        self.params = MasterParams()
        self.fallback = ClassicFallbackProcessor(self.sr)
        self.pipeline = NeuralMasteringPipeline(self.sr)
        self.worker = NeuralChunkWorker(self.pipeline, self.fallback)
        self._meter_lufs = -70.0
        self._meter_peak = -70.0

    def load_file(self, path: str) -> None:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        data = ensure_stereo(data)
        if sr != TARGET_SR:
            left = librosa.resample(data[:, 0], orig_sr=sr, target_sr=TARGET_SR)
            right = librosa.resample(data[:, 1], orig_sr=sr, target_sr=TARGET_SR)
            data = np.stack([left, right], axis=1).astype(np.float32)
            sr = TARGET_SR
        self.audio = np.ascontiguousarray(data, dtype=np.float32)
        self.sr = sr
        self.position = 0
        self.fallback = ClassicFallbackProcessor(self.sr)
        self.pipeline = NeuralMasteringPipeline(self.sr)
        self.worker = NeuralChunkWorker(self.pipeline, self.fallback)
        self.worker.configure(self.audio, self.sr, self.params)
        self.file_loaded.emit(path)
        self.position_changed.emit(0.0)
        self.model_state_changed.emit(self.pipeline.model_name if self.pipeline.available else "TensorFlow not installed; neural path unavailable")

    def load_model(self, path: str) -> None:
        self.pipeline.load_external_model(path)
        if self.audio is not None:
            self.worker.pipeline = self.pipeline
            self.worker.set_params(self.params)
        self.model_state_changed.emit(self.pipeline.model_name)

    def duration_seconds(self) -> float:
        return 0.0 if self.audio is None else len(self.audio) / float(self.sr)

    def current_time_seconds(self) -> float:
        return 0.0 if self.audio is None else self.position / float(self.sr)

    def set_master_params(self, params: MasterParams) -> None:
        self.params = params
        self.worker.set_params(params)
        self._prefetch_around_position()

    def set_ab_mode(self, mastered: bool) -> None:
        self.use_mastered = mastered
        self._prefetch_around_position()

    def seek_ratio(self, ratio: float) -> None:
        if self.audio is None:
            return
        self.position = int(clamp(ratio, 0.0, 1.0) * max(len(self.audio) - 1, 0))
        self.position_changed.emit(self.position / float(max(len(self.audio), 1)))
        self._prefetch_around_position(force_first=True)

    def play(self) -> None:
        if self.audio is None:
            return
        self._prefetch_around_position(force_first=True)
        if self.stream is None:
            self.stream = sd.OutputStream(
                samplerate=self.sr,
                channels=2,
                dtype="float32",
                blocksize=DEFAULT_BLOCKSIZE,
                latency=DEFAULT_LATENCY,
                callback=self._callback,
            )
            self.stream.start()
        elif not self.stream.active:
            self.stream.start()
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def stop(self) -> None:
        self.is_playing = False
        self.position = 0
        self.position_changed.emit(0.0)

    def close(self) -> None:
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        finally:
            self.stream = None
            self.is_playing = False

    def _prefetch_around_position(self, force_first: bool = False) -> None:
        if self.audio is None or not self.use_mastered:
            return
        current_chunk = self.position // DEFAULT_CHUNK
        if force_first:
            self.worker.ensure_ready(current_chunk)
        for offset, prio in zip(range(0, 6), [0, 5, 10, 15, 20, 25]):
            self.worker.request(current_chunk + offset, priority=prio)
        for offset, prio in zip(range(1, 3), [30, 35]):
            prev_idx = current_chunk - offset
            if prev_idx >= 0:
                self.worker.request(prev_idx, priority=prio)

    def _get_mastered_range(self, start: int, stop: int) -> np.ndarray:
        assert self.audio is not None
        out = np.zeros((stop - start, 2), dtype=np.float32)
        write_pos = 0
        cursor = start
        while cursor < stop:
            chunk_idx = cursor // DEFAULT_CHUNK
            chunk_start = chunk_idx * DEFAULT_CHUNK
            chunk_end = min(chunk_start + DEFAULT_CHUNK, len(self.audio))
            take_start = cursor - chunk_start
            take_stop = min(chunk_end, stop) - chunk_start
            cached = self.worker.get_cached(chunk_idx)
            if cached is None:
                raw = self.audio[cursor:min(stop, chunk_end)]
                piece = self.fallback.process_block(raw, self.params)
            else:
                piece = cached[take_start:take_stop]
            out[write_pos:write_pos + len(piece)] = piece
            write_pos += len(piece)
            cursor += len(piece)
            if len(piece) == 0:
                break
        if write_pos < len(out):
            out[write_pos:] = 0.0
        return out

    def _callback(self, outdata, frames, time_info, status):
        if self.audio is None or not self.is_playing:
            outdata[:] = np.zeros((frames, 2), dtype=np.float32)
            return
        start = self.position
        stop = min(start + frames, len(self.audio))
        remaining = stop - start
        if remaining <= 0:
            outdata[:] = 0.0
            self.is_playing = False
            return

        if self.use_mastered:
            block = self._get_mastered_range(start, stop)
        else:
            block = self.audio[start:stop]

        if remaining < frames:
            outdata[:] = 0.0
            outdata[:remaining] = block
            self.position = len(self.audio)
            self.is_playing = False
        else:
            outdata[:] = block
            self.position = stop
            self.position_changed.emit(self.position / float(len(self.audio)))

        self._prefetch_around_position()
        peak = float(np.max(np.abs(block)) + 1e-12)
        rms = float(np.sqrt(np.mean(block ** 2)) + 1e-12)
        self._meter_peak = linear_to_db(peak)
        self._meter_lufs = -0.691 + 10.0 * math.log10(max(rms * rms, 1e-12))
        self.meters_changed.emit(self._meter_lufs, self._meter_peak)


# ------------------------------ GUI widgets ------------------------------ #

class WaveformWidget(QWidget):
    seek_requested = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(220)
        self.audio: Optional[np.ndarray] = None
        self.playhead = 0.0

    def set_audio(self, audio: Optional[np.ndarray]) -> None:
        self.audio = audio
        self.update()

    def set_playhead(self, ratio: float) -> None:
        self.playhead = clamp(ratio, 0.0, 1.0)
        self.update()

    def mousePressEvent(self, event):
        if self.audio is not None:
            self.seek_requested.emit(clamp(event.position().x() / max(self.width(), 1), 0.0, 1.0))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#10131b"))
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#232942"), 1))
        for i in range(1, 6):
            y = int(h * i / 6)
            p.drawLine(0, y, w, y)
        if self.audio is None or len(self.audio) == 0:
            p.setPen(QPen(QColor("#808080"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load audio to view waveform")
            return
        mono = np.mean(self.audio, axis=1)
        step = max(1, len(mono) // max(w, 1))
        env = mono[: step * (len(mono) // step)].reshape(-1, step)
        mins = env.min(axis=1)
        maxs = env.max(axis=1)
        path = QPainterPath()
        mid = h / 2.0
        sx = max(1, len(mins)) / max(w, 1)
        for px in range(w):
            idx = min(int(px * sx), len(mins) - 1)
            y1 = mid - maxs[idx] * h * 0.42
            y2 = mid - mins[idx] * h * 0.42
            path.moveTo(float(px), float(y1))
            path.lineTo(float(px), float(y2))
        p.setPen(QPen(QColor("#00f0ff"), 1.2))
        p.drawPath(path)
        x = int(self.playhead * w)
        p.setPen(QPen(QColor("#ff2bd6"), 2))
        p.drawLine(x, 0, x, h)


class MeterBar(QProgressBar):
    def __init__(self, title: str, minimum: int, maximum: int):
        super().__init__()
        self.title = title
        self.setRange(minimum, maximum)
        self.setValue(minimum)
        self.setFormat(f"{title}: %v")
        self.setTextVisible(True)
        self.setFixedHeight(22)


class ControlSlider(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, name: str, default: float):
        super().__init__()
        self.label = QLabel(name)
        self.value_label = QLabel(str(int(default)))
        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(default))
        self.slider.valueChanged.connect(self._changed)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def _changed(self, value: int) -> None:
        self.value_label.setText(str(value))
        self.value_changed.emit(float(value))

    def set_value(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(value)))
        self.slider.blockSignals(False)
        self.value_label.setText(str(int(round(value))))

    def value(self) -> float:
        return float(self.slider.value())


# ------------------------------ Main window ------------------------------ #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = AudioEngine()
        self.analyzer = AIAnalyzer()
        self.controls: Dict[str, ControlSlider] = {}
        self._build_ui()
        self._connect()
        self._theme()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_transport)
        self._timer.start(80)

    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        self.resize(1560, 980)
        central = QWidget()
        main = QVBoxLayout(central)
        main.setContentsMargins(18, 18, 18, 18)
        main.setSpacing(14)

        title = QLabel("BEAST MODE ELITE NEURAL MASTERING")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 900; letter-spacing: 2px;")
        main.addWidget(title)

        self.waveform = WaveformWidget()
        main.addWidget(self.waveform)

        info = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        self.transport_label = QLabel("00:00 / 00:00")
        self.transport_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info.addWidget(self.file_label, 1)
        info.addWidget(self.transport_label)
        main.addLayout(info)

        meters = QHBoxLayout()
        self.lufs_meter = MeterBar("LUFS", -70, 6)
        self.peak_meter = MeterBar("Peak", -70, 3)
        meters.addWidget(self.lufs_meter)
        meters.addWidget(self.peak_meter)
        main.addLayout(meters)

        body = QHBoxLayout()
        main.addLayout(body, 1)

        left = QVBoxLayout()
        body.addLayout(left, 4)

        controls_group = QGroupBox("Master Controls")
        cgl = QHBoxLayout(controls_group)
        for name, default in [
            ("warmth", 50), ("brightness", 50), ("clarity", 50), ("punch", 50),
            ("width", 50), ("depth", 20), ("loudness", 50), ("dynamic_range", 65),
            ("harmonics", 30), ("vocal_presence", 50),
        ]:
            w = ControlSlider(name.replace("_", " ").title(), default)
            self.controls[name] = w
            cgl.addWidget(w)
        left.addWidget(controls_group, 1)

        transport_group = QGroupBox("Transport / Neural Engine")
        tgl = QHBoxLayout(transport_group)
        self.load_btn = QPushButton("Load Audio")
        self.load_model_btn = QPushButton("Load Neural Model")
        self.analyze_btn = QPushButton("ANALYZE & AUTO-SET")
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.original_btn = QPushButton("ORIGINAL")
        self.original_btn.setCheckable(True)
        self.mastered_btn = QPushButton("MASTERED")
        self.mastered_btn.setCheckable(True)
        self.mastered_btn.setChecked(True)
        for b in [self.load_btn, self.load_model_btn, self.analyze_btn, self.play_btn, self.pause_btn, self.stop_btn, self.original_btn, self.mastered_btn]:
            tgl.addWidget(b)
        left.addWidget(transport_group)

        right = QVBoxLayout()
        body.addLayout(right, 2)

        analysis_group = QGroupBox("AI Analysis")
        agl = QVBoxLayout(analysis_group)
        self.analysis_status = QLabel("Ready. Load a file and run analysis.")
        self.analysis_status.setWordWrap(True)
        self.analysis_details = QLabel("Genre: —\nFrequency profile: —\nDynamic range: —\nTransients: —\nStereo width: —\nVocal presence: —")
        self.analysis_details.setWordWrap(True)
        agl.addWidget(self.analysis_status)
        agl.addWidget(self.analysis_details)
        right.addWidget(analysis_group)

        model_group = QGroupBox("Neural Model State")
        mgl = QVBoxLayout(model_group)
        self.model_status = QLabel("No external model loaded. Using internal TF spectral master.")
        self.model_status.setWordWrap(True)
        self.model_hint = QLabel(
            "Expected external model interface: ([audio, controls]) -> audio, where audio is [1, N, 2] and controls is [1, 10]."
        )
        self.model_hint.setWordWrap(True)
        mgl.addWidget(self.model_status)
        mgl.addWidget(self.model_hint)
        right.addWidget(model_group)
        right.addStretch(1)

        self.setCentralWidget(central)
        QShortcut(QKeySequence("O"), self, activated=self._switch_original)
        QShortcut(QKeySequence("M"), self, activated=self._switch_mastered)
        QShortcut(QKeySequence("Space"), self, activated=self._toggle_play)

    def _connect(self):
        self.load_btn.clicked.connect(self.load_audio)
        self.load_model_btn.clicked.connect(self.load_model)
        self.analyze_btn.clicked.connect(self.run_analysis)
        self.play_btn.clicked.connect(self.engine.play)
        self.pause_btn.clicked.connect(self.engine.pause)
        self.stop_btn.clicked.connect(self.engine.stop)
        self.original_btn.clicked.connect(self._switch_original)
        self.mastered_btn.clicked.connect(self._switch_mastered)
        self.waveform.seek_requested.connect(self.engine.seek_ratio)
        for _, control in self.controls.items():
            control.value_changed.connect(self._controls_changed)
        self.engine.position_changed.connect(self.waveform.set_playhead)
        self.engine.meters_changed.connect(self._update_meters)
        self.engine.file_loaded.connect(self._file_loaded)
        self.engine.model_state_changed.connect(self.model_status.setText)
        self.analyzer.analysis_ready.connect(self._analysis_ready)
        self.analyzer.analysis_failed.connect(lambda msg: self.analysis_status.setText(f"Analysis failed: {msg}"))

    def _theme(self):
        self.setStyleSheet(
            """
            QWidget { background: #0b0e14; color: #f2f4ff; font-family: Inter, Segoe UI, Arial, sans-serif; }
            QGroupBox { border: 1px solid #2e3550; border-radius: 12px; margin-top: 10px; padding-top: 12px; font-weight: 700; }
            QGroupBox::title { left: 12px; padding: 0 8px; color: #00f0ff; }
            QPushButton { background: #171c28; border: 1px solid #39415d; border-radius: 10px; padding: 10px 16px; font-weight: 800; }
            QPushButton:hover { border-color: #00f0ff; }
            QPushButton:checked { background: #00f0ff; color: #0a0d12; border-color: #ff2bd6; }
            QSlider::groove:vertical { background: #151a24; width: 10px; border-radius: 5px; }
            QSlider::handle:vertical { background: #00f0ff; border: 1px solid #ff2bd6; height: 24px; margin: -2px -7px; border-radius: 12px; }
            QProgressBar { border: 1px solid #39415d; border-radius: 8px; background: #141923; text-align: center; }
            QProgressBar::chunk { background-color: #00f0ff; border-radius: 8px; }
            """
        )

    def _gather_params(self) -> MasterParams:
        return MasterParams(**{name: control.value() for name, control in self.controls.items()})

    def _controls_changed(self, *_):
        self.engine.set_master_params(self._gather_params())

    def load_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open audio", str(Path.home()), "Audio Files (*.wav *.flac *.aif *.aiff *.mp3 *.ogg *.m4a);;All Files (*)")
        if not path:
            return
        try:
            self.engine.load_file(path)
            self.waveform.set_audio(self.engine.audio)
            self.engine.set_master_params(self._gather_params())
            self.analysis_status.setText("File loaded. Ready for elite analysis and neural mastering.")
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def load_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Keras model", str(Path.home()), "Keras Model (*.keras *.h5 *.hdf5);;All Files (*)")
        if not path:
            return
        try:
            self.engine.load_model(path)
        except Exception as exc:
            QMessageBox.critical(self, "Model load failed", str(exc))

    def run_analysis(self):
        if self.engine.audio is None:
            QMessageBox.information(self, "No audio", "Load an audio file first.")
            return
        self.analysis_status.setText("Analyzing spectrum, dynamics, stereo field, transients, and vocal band…")
        self.analyzer.analyze_async(self.engine.audio, self.engine.sr)

    def _analysis_ready(self, result: dict, params: MasterParams):
        for name, value in asdict(params).items():
            self.controls[name].set_value(value)
        self.engine.set_master_params(params)
        self.analysis_status.setText("Analysis complete. Controls were auto-set for the elite neural chain.")
        self.analysis_details.setText(
            f"Genre: {result['genre_prediction']}\n"
            f"Frequency profile: centroid {result['frequency_profile']['centroid_hz']} Hz, rolloff {result['frequency_profile']['rolloff_hz']} Hz\n"
            f"Dynamic range: {result['dynamic_range_score']} dB\n"
            f"Transients: {result['transient_score']}\n"
            f"Stereo width: {result['stereo_width_score']}\n"
            f"Vocal presence: {result['vocal_presence_score']}"
        )

    def _file_loaded(self, path: str):
        self.file_label.setText(os.path.basename(path))
        self.transport_label.setText(f"00:00 / {self._fmt(self.engine.duration_seconds())}")

    def _switch_original(self):
        self.original_btn.setChecked(True)
        self.mastered_btn.setChecked(False)
        self.engine.set_ab_mode(False)

    def _switch_mastered(self):
        self.mastered_btn.setChecked(True)
        self.original_btn.setChecked(False)
        self.engine.set_ab_mode(True)

    def _toggle_play(self):
        if self.engine.is_playing:
            self.engine.pause()
        else:
            self.engine.play()

    def _update_meters(self, lufs: float, peak: float):
        self.lufs_meter.setValue(int(clamp(round(lufs), self.lufs_meter.minimum(), self.lufs_meter.maximum())))
        self.peak_meter.setValue(int(clamp(round(peak), self.peak_meter.minimum(), self.peak_meter.maximum())))
        self.lufs_meter.setFormat(f"LUFS: {lufs:.1f}")
        self.peak_meter.setFormat(f"Peak: {peak:.1f} dBFS")

    def _refresh_transport(self):
        self.transport_label.setText(f"{self._fmt(self.engine.current_time_seconds())} / {self._fmt(self.engine.duration_seconds())}")

    @staticmethod
    def _fmt(sec: float) -> str:
        s = int(max(sec, 0))
        return f"{s // 60:02d}:{s % 60:02d}"

    def closeEvent(self, event):
        self.engine.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
