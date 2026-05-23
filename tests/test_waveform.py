from __future__ import annotations

import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from audio_waveform_thumbnail import WaveformOptions, generate_waveform_thumbnail
from audio_waveform_thumbnail.waveform import WaveformError, parse_color


def _write_sine_wav(path: Path, duration_seconds: float = 0.4, sample_rate: int = 8000) -> None:
    frames = bytearray()
    for index in range(int(duration_seconds * sample_rate)):
        sample = int(20000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


class WaveformThumbnailTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg is required")
    def test_generates_png_from_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "tone.wav"
            target = tmp / "tone.waveform.png"
            _write_sine_wav(source)

            generated = generate_waveform_thumbnail(
                source,
                target,
                WaveformOptions(width=320, height=180, sample_rate=8000, padding=16),
            )

            data = generated.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (320, 180))

    def test_rejects_invalid_color(self) -> None:
        with self.assertRaises(WaveformError):
            parse_color("#12xx34")


if __name__ == "__main__":
    unittest.main()

