"""Audio format bridging between WebRTC (48 kHz) and the OpenAI Realtime API (24 kHz PCM16).

The browser sends/receives Opus audio decoded by aiortc into 48 kHz signed-16-bit
frames. The OpenAI Realtime API speaks raw, mono, 16-bit little-endian PCM at
24 kHz (base64'd over the socket). These helpers convert between the two.
"""

from __future__ import annotations

from fractions import Fraction

import av
import numpy as np

OPENAI_SAMPLE_RATE = 24000
WEBRTC_SAMPLE_RATE = 48000

# 20 ms of mono s16 PCM at 24 kHz: 24000 * 0.02 * 2 bytes.
CHUNK_BYTES = 960
CHUNK_SECONDS = 0.02


def make_mic_resampler() -> av.AudioResampler:
    """Resampler for microphone audio: WebRTC (48 kHz) -> PCM16 mono @ 24 kHz."""
    return av.AudioResampler(
        format="s16", layout="mono", rate=OPENAI_SAMPLE_RATE
    )


def make_playback_resampler() -> av.AudioResampler:
    """Resampler for model audio: PCM16 mono @ 24 kHz -> WebRTC stereo @ 48 kHz."""
    return av.AudioResampler(
        format="s16", layout="stereo", rate=WEBRTC_SAMPLE_RATE
    )


def resample_to_pcm24(frame: av.AudioFrame, resampler: av.AudioResampler) -> bytes:
    """Downmix + resample an incoming WebRTC frame to raw PCM16 mono @ 24 kHz."""
    frames = resampler.resample(frame)
    return b"".join(f.to_ndarray().tobytes() for f in frames)


def pcm24_to_frame(
    data: bytes, resampler: av.AudioResampler, pts: int
) -> av.AudioFrame | None:
    """Convert raw PCM16 mono @ 24 kHz back into a WebRTC-ready 48 kHz frame."""
    array = np.frombuffer(data, dtype=np.int16).copy().reshape(1, -1)
    frame = av.AudioFrame.from_ndarray(array, format="s16", layout="mono")
    frame.sample_rate = OPENAI_SAMPLE_RATE
    frame.pts = 0
    frame.time_base = Fraction(1, OPENAI_SAMPLE_RATE)

    frames = resampler.resample(frame)
    if not frames:
        return None

    out = frames[0]
    out.pts = pts
    out.time_base = Fraction(1, WEBRTC_SAMPLE_RATE)
    return out
