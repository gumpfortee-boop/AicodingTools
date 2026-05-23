# AicodingTools

Small standalone tools for AI coding workflows.

## Audio waveform thumbnail

`audio-waveform-thumbnail` creates a PNG waveform thumbnail from a `.mp4`, `.wav`,
or any local media file that `ffmpeg` can decode.

### Requirements

- Python 3.9+
- `ffmpeg` and `ffprobe` available in `PATH`

### Install locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

### Usage

```bash
audiowave-thumb input.wav output.png
audiowave-thumb input.mp4 output.png --width 1280 --height 720
```

If `output.png` is omitted, the tool writes `<input-stem>.waveform.png`.

Useful options:

```bash
audiowave-thumb input.mp4 \
  --width 1280 \
  --height 720 \
  --padding 48 \
  --background '#101827' \
  --wave '#38bdf8' \
  --center-line '#334155'
```

### Python API

```python
from audio_waveform_thumbnail import WaveformOptions, generate_waveform_thumbnail

generate_waveform_thumbnail(
    "input.mp4",
    "output.png",
    WaveformOptions(width=1280, height=720),
)
```
