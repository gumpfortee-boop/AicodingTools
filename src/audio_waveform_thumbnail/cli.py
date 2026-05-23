"""Command-line interface for waveform thumbnail generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .waveform import WaveformError, WaveformOptions, generate_waveform_thumbnail


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audiowave-thumb",
        description="Generate a PNG waveform thumbnail from an .mp4 or .wav file.",
    )
    parser.add_argument("input", help="Input .mp4, .wav, or any media file ffmpeg can decode.")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output PNG path. Defaults to '<input-stem>.waveform.png'.",
    )
    parser.add_argument("--width", type=int, default=1280, help="Thumbnail width in pixels.")
    parser.add_argument("--height", type=int, default=720, help="Thumbnail height in pixels.")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Audio decode sample rate.")
    parser.add_argument("--padding", type=int, default=48, help="Inner waveform padding in pixels.")
    parser.add_argument("--background", default="#101827", help="Background color, e.g. #101827.")
    parser.add_argument("--wave", default="#38bdf8", help="Waveform color, e.g. #38bdf8.")
    parser.add_argument("--center-line", default="#334155", help="Center line color, e.g. #334155.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".waveform.png")

    options = WaveformOptions(
        width=args.width,
        height=args.height,
        sample_rate=args.sample_rate,
        padding=args.padding,
        background=args.background,
        waveform=args.wave,
        center_line=args.center_line,
    )

    try:
        generated = generate_waveform_thumbnail(input_path, output_path, options)
    except WaveformError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

