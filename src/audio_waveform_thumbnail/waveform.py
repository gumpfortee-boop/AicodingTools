"""Generate waveform thumbnail PNGs from audio or video inputs."""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import sys
import zlib
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class WaveformError(RuntimeError):
    """Raised when a waveform thumbnail cannot be generated."""


Color = tuple[int, int, int]


@dataclass(frozen=True)
class WaveformOptions:
    width: int = 1280
    height: int = 720
    sample_rate: int = 16000
    padding: int = 48
    background: str | Color = "#101827"
    waveform: str | Color = "#38bdf8"
    center_line: str | Color = "#334155"


def generate_waveform_thumbnail(
    input_path: str | Path,
    output_path: str | Path,
    options: WaveformOptions | None = None,
) -> Path:
    """Generate a PNG waveform thumbnail from an input media file.

    The input can be a .wav file, an .mp4 containing an audio stream, or any
    local media file supported by ffmpeg.
    """

    opts = options or WaveformOptions()
    _validate_options(opts)

    source = Path(input_path)
    target = Path(output_path)
    if not source.exists():
        raise WaveformError(f"input file does not exist: {source}")
    if not source.is_file():
        raise WaveformError(f"input path is not a file: {source}")
    if shutil.which("ffmpeg") is None:
        raise WaveformError("ffmpeg is required but was not found in PATH")

    peaks = _decode_peaks(source, opts.width, opts.sample_rate)
    pixels = _render_waveform(peaks, opts)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_png(target, opts.width, opts.height, pixels)
    return target


def _validate_options(options: WaveformOptions) -> None:
    if options.width < 16:
        raise WaveformError("width must be at least 16")
    if options.height < 16:
        raise WaveformError("height must be at least 16")
    if options.sample_rate < 1000:
        raise WaveformError("sample rate must be at least 1000")
    if options.padding < 0:
        raise WaveformError("padding cannot be negative")
    if options.padding * 2 >= options.height:
        raise WaveformError("padding leaves no vertical space for the waveform")
    parse_color(options.background)
    parse_color(options.waveform)
    parse_color(options.center_line)


def parse_color(value: str | Color) -> Color:
    if isinstance(value, tuple):
        if len(value) != 3 or any(channel < 0 or channel > 255 for channel in value):
            raise WaveformError("RGB color tuples must contain three values from 0 to 255")
        return value

    color = value.strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) != 6:
        raise WaveformError(f"expected a six-digit hex color, got: {value}")
    try:
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except ValueError as exc:
        raise WaveformError(f"invalid hex color: {value}") from exc


def _decode_peaks(source: Path, width: int, sample_rate: int) -> list[float]:
    duration = _probe_duration(source)
    samples_per_bucket = max(1, math.ceil(duration * sample_rate / width)) if duration else None

    if samples_per_bucket is None:
        samples = [abs(sample) / 32768.0 for chunk in _iter_pcm_chunks(source, sample_rate) for sample in chunk]
        if not samples:
            raise WaveformError("no audio samples could be decoded from input")
        return _resize_peaks(samples, width)

    peaks: list[float] = []
    bucket_peak = 0.0
    bucket_count = 0
    decoded_samples = 0

    for chunk in _iter_pcm_chunks(source, sample_rate):
        for sample in chunk:
            decoded_samples += 1
            bucket_peak = max(bucket_peak, min(1.0, abs(sample) / 32768.0))
            bucket_count += 1
            if bucket_count >= samples_per_bucket:
                peaks.append(bucket_peak)
                bucket_peak = 0.0
                bucket_count = 0

    if bucket_count:
        peaks.append(bucket_peak)
    if decoded_samples == 0:
        raise WaveformError("no audio samples could be decoded from input")
    return _resize_peaks(peaks, width)


def _probe_duration(source: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def _iter_pcm_chunks(source: Path, sample_rate: int) -> Iterable[array]:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        raise WaveformError("failed to start ffmpeg")

    leftover = b""
    try:
        while True:
            chunk = process.stdout.read(65536)
            if not chunk:
                break
            chunk = leftover + chunk
            if len(chunk) % 2:
                leftover = chunk[-1:]
                chunk = chunk[:-1]
            else:
                leftover = b""
            if chunk:
                samples = array("h")
                samples.frombytes(chunk)
                if sys.byteorder != "little":
                    samples.byteswap()
                yield samples

        stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
        return_code = process.wait()
        if return_code != 0:
            message = stderr or f"ffmpeg exited with status {return_code}"
            raise WaveformError(message)
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()


def _resize_peaks(peaks: list[float], width: int) -> list[float]:
    if len(peaks) == width:
        return peaks

    resized: list[float] = []
    source_count = len(peaks)
    for x in range(width):
        start = int(x * source_count / width)
        end = max(start + 1, int((x + 1) * source_count / width))
        resized.append(max(peaks[start:end]))
    return resized


def _render_waveform(peaks: list[float], options: WaveformOptions) -> bytearray:
    background = parse_color(options.background)
    waveform = parse_color(options.waveform)
    center_line = parse_color(options.center_line)

    width = options.width
    height = options.height
    pixels = bytearray(background * (width * height))

    center_y = height // 2
    available_half_height = max(1, (height - options.padding * 2) // 2)
    _draw_horizontal_line(pixels, width, height, center_y, center_line)

    for x, peak in enumerate(peaks):
        shaped_peak = math.sqrt(max(0.0, min(1.0, peak)))
        half_height = max(1, int(shaped_peak * available_half_height))
        y1 = max(options.padding, center_y - half_height)
        y2 = min(height - options.padding - 1, center_y + half_height)
        _draw_vertical_line(pixels, width, height, x, y1, y2, waveform)

    return pixels


def _draw_horizontal_line(pixels: bytearray, width: int, height: int, y: int, color: Color) -> None:
    if y < 0 or y >= height:
        return
    for x in range(width):
        _set_pixel(pixels, width, x, y, color)


def _draw_vertical_line(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y1: int,
    y2: int,
    color: Color,
) -> None:
    if x < 0 or x >= width:
        return
    for y in range(max(0, y1), min(height - 1, y2) + 1):
        _set_pixel(pixels, width, x, y, color)


def _set_pixel(pixels: bytearray, width: int, x: int, y: int, color: Color) -> None:
    offset = (y * width + x) * 3
    pixels[offset : offset + 3] = bytes(color)


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    if len(pixels) != width * height * 3:
        raise WaveformError("pixel buffer size does not match image dimensions")

    raw_rows = bytearray()
    stride = width * 3
    for y in range(height):
        raw_rows.append(0)
        start = y * stride
        raw_rows.extend(pixels[start : start + stride])

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(_png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(_png_chunk(b"IDAT", zlib.compress(bytes(raw_rows), level=9)))
    png.extend(_png_chunk(b"IEND", b""))
    path.write_bytes(png)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum & 0xFFFFFFFF)
