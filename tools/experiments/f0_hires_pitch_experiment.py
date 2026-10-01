"""F0 experiment (FRAMEWORK_REDESIGN.md §13.4, first two rows): does a 16-bit sample in XM/IT
play back at the requested rate, with the design's XM (relative_note + finetune/128) and
IT (C5Speed directly) formulas? Measured with a high-resolution FFT pitch estimate (not the
test suite's coarse zero-crossing helper), since the 7-cent tolerance (I4) needs sub-cent
measurement precision to be checked meaningfully.

Throwaway script. Not part of the package; not meant to be reused by F1/F4 (those build the
real 16-bit writer support properly, informed by what this finds).
"""
from __future__ import annotations

import math
import struct
import subprocess
import sys
import tempfile

import numpy as np

FFMPEG = "ffmpeg"
DECODE_RATE = 48000


def decode_f32(path: str, rate: int = DECODE_RATE) -> np.ndarray:
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "libopenmpt",
           "-i", path, "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    return np.frombuffer(proc.stdout, dtype="<f4")


def measure_freq(samples: np.ndarray, rate: int, start_s: float = 0.3, dur_s: float = 1.0) -> float:
    """FFT peak with parabolic (log-magnitude) interpolation. Good to a small fraction of a bin
    for a clean near-sinusoidal tone."""
    lo = int(start_s * rate)
    hi = lo + int(dur_s * rate)
    w = samples[lo:hi]
    if len(w) < rate * 0.2:
        raise RuntimeError(f"decoded audio too short: {len(samples)} samples at {rate} Hz")
    win = w * np.hanning(len(w))
    spec = np.fft.rfft(win)
    mag = np.abs(spec)
    mag[0] = 0  # ignore DC
    k = int(np.argmax(mag))
    if k <= 0 or k >= len(mag) - 1:
        return k * rate / len(win)
    # parabolic interpolation on log magnitude around the peak
    a, b, c = (math.log(max(mag[k - 1], 1e-12)), math.log(max(mag[k], 1e-12)), math.log(max(mag[k + 1], 1e-12)))
    p = 0.5 * (a - c) / (a - 2 * b + c)
    return (k + p) * rate / len(win)


def cents(f_measured: float, f_target: float) -> float:
    return 1200.0 * math.log2(f_measured / f_target)


# ============================================================
# A minimal 16-bit looped sine sample, shared by both formats.
# K samples/cycle at a comfortable amplitude; delta/plain encoding applied per format below.
# ============================================================

K = 256  # samples per cycle (arbitrary; only the ratio playback_rate/K matters for frequency)


def sine_cycle_i16() -> list[int]:
    amp = 30000
    return [round(amp * math.sin(2 * math.pi * i / K)) for i in range(K)]


# ============================================================
# Minimal XM file: 1 channel, 1 pattern (64 rows), 1 instrument/sample.
# Reuses core.model.Cell/Pattern + core.writer's pattern packer (format-neutral), writes its
# own 16-bit instrument block (writer._serialize_xm_instrument is 8-bit-only and doesn't expose
# an arbitrary finetune byte or nonzero relative_note).
# ============================================================

def build_xm(relative_note: int, finetune: int, *, xm_note: int = 49) -> bytes:
    """Raw construction, independent of core.model.Cell (which caps note at the current 36-note
    range) -- the whole point of this experiment is to check XM's own, much wider, note range."""
    XM_ID = b"Extended Module: "
    row0 = bytes([0x80 | 0x01 | 0x02, xm_note, 1])  # note + instrument, no vol/effect
    pattern_body = row0 + bytes([0x80]) * 63  # 63 empty rows (flags=0x80, no bits set)
    pattern_bytes = struct.pack("<IBHH", 9, 0, 64, len(pattern_body)) + pattern_body

    cyc = sine_cycle_i16()
    raw = b"".join(struct.pack("<h", v) for v in cyc)  # plain 16-bit signed, pre-delta
    # FT2 delta-encodes sample data regardless of bit depth; for 16-bit it's a 16-bit-word delta.
    delta = bytearray()
    prev = 0
    for i in range(0, len(raw), 2):
        cur = struct.unpack_from("<h", raw, i)[0]
        d = (cur - prev) & 0xFFFF
        delta += struct.pack("<H", d)
        prev = cur

    name = b"hires".ljust(22, b" ")
    inst_header = struct.pack("<I", 243) + name + bytes([0]) + struct.pack("<H", 1) + struct.pack("<I", 40)
    inst_header += bytes(96) + bytes(48) + bytes(48)
    inst_header += bytes([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    inst_header += struct.pack("<H", 0) + struct.pack("<H", 0)
    assert len(inst_header) == 243, len(inst_header)

    has_loop = True
    loop_type_and_bits = 1 | 0x10  # bit0-1=forward loop, bit4=16-bit
    sample_header = struct.pack("<III", len(raw), 0, len(raw))  # length/loop-start/loop-len, in BYTES
    sample_header += bytes([64])            # default volume
    sample_header += struct.pack("<b", finetune)
    sample_header += bytes([loop_type_and_bits])
    sample_header += bytes([128])           # pan (center)
    sample_header += struct.pack("<b", relative_note)
    sample_header += bytes([0])
    sample_header += name
    assert len(sample_header) == 40, len(sample_header)

    instrument = inst_header + sample_header + bytes(delta)

    out = bytearray()
    out += XM_ID
    out += b"hires".ljust(20, b" ")
    out += bytes([0x1A])
    out += b"exp".ljust(20, b" ")
    out += struct.pack("<H", 0x0104)
    out += struct.pack("<I", 276)
    out += struct.pack("<H", 1)   # song length
    out += struct.pack("<H", 0)   # restart pos
    out += struct.pack("<H", 1)   # n channels
    out += struct.pack("<H", 1)   # n patterns
    out += struct.pack("<H", 1)   # n instruments
    out += struct.pack("<H", 0)   # flags: Amiga freq table
    out += struct.pack("<H", 6)   # speed
    out += struct.pack("<H", 125)  # bpm
    out += bytes([0]) + bytes(255)  # order table (256 bytes)
    out += pattern_bytes
    out += instrument
    return bytes(out)


def xm_predicted_hz(relative_note: int, finetune: int, xm_note: int = 49) -> float:
    return 8363.0 * 2 ** ((xm_note + relative_note - 49 + finetune / 128.0) / 12.0)


# ============================================================
# Minimal IT file: 1 channel, 1 pattern (64 rows), 1 sample (sample mode, matching core/it.py).
# ============================================================

def build_it(it_note: int, c5speed_val: int) -> bytes:
    """Raw construction, independent of core.model.Cell -- same reason as build_xm: IT's own
    note range (0..119) is much wider than the current 36-note Cell model."""
    row0 = bytes([1 | 0x80, 0x01 | 0x02, it_note, 1])  # channel 1, mask=note|sample
    body = row0 + bytes(64 - 1)  # remaining 63 rows: terminator byte (0) each
    pattern_bytes = struct.pack("<HH4x", len(body), 64) + bytes(body)

    cyc = sine_cycle_i16()
    data = b"".join(struct.pack("<h", v) for v in cyc)  # plain 16-bit signed, no delta in IT

    HEADER_SIZE = 0xC0
    out = bytearray(b"IMPM")
    out += b"hires".ljust(26, b"\x00")
    out += bytes([4, 16])
    out += struct.pack("<HHHHHHHH", 1, 0, 1, 1, 0x0214, 0x0214, 0x01 | 0x10, 0)  # stereo|old effects
    out += bytes([128, 48, 6, 125, 128, 0])
    out += struct.pack("<HII", 0, 0, 0)
    out += bytes([32] + [32 | 0x80] * 63)
    out += bytes([64] * 64)
    assert len(out) == HEADER_SIZE, len(out)
    out += bytes([0])            # 1 order entry
    smp_ptr_pos = len(out)
    out += bytes(4)
    pat_ptr_pos = len(out)
    out += bytes(4)

    header_off = len(out)
    out += bytes(0x50)
    pattern_off = len(out)
    out += pattern_bytes
    data_off = len(out)
    out += data

    h = bytearray(b"IMPS")
    h += bytes(12)
    h += bytes([0, 64])
    h.append(0x01 | 0x02 | 0x10)   # has-data | 16-bit | loop
    h.append(64)                   # default volume
    h += b"hires".ljust(26, b"\x00")
    h.append(0x01)                 # Cvt: signed
    h.append(32)                   # default pan, center, DfP disabled
    h += struct.pack("<IIII", len(data), 0, len(cyc), c5speed_val)
    h += struct.pack("<III", 0, 0, data_off)
    h += bytes(4)
    assert len(h) == 0x50, len(h)
    out[header_off:header_off + 0x50] = bytes(h)

    struct.pack_into("<I", out, smp_ptr_pos, header_off)
    struct.pack_into("<I", out, pat_ptr_pos, pattern_off)
    return bytes(out)


def it_predicted_hz(it_note: int, c5speed_val: float) -> float:
    return c5speed_val * 2 ** ((it_note - 60) / 12.0)


# ============================================================
# Run
# ============================================================

def run_case(label: str, data: bytes, predicted_hz: float) -> None:
    with tempfile.NamedTemporaryFile(suffix=".xm" if "xm" in label else ".it", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        samples = decode_f32(path)
        measured = measure_freq(samples, DECODE_RATE) * K
        err = cents(measured, predicted_hz)
        print(f"{label:28s} predicted={predicted_hz:9.3f} Hz  measured={measured:9.3f} Hz  "
              f"error={err:+7.2f} cents  {'OK' if abs(err) <= 7 else 'FAIL'}")
    except Exception as e:  # noqa: BLE001
        print(f"{label:28s} EXCEPTION: {e}")


def main() -> None:
    print("=== XM: relative_note=0, finetune sweep (Amiga frequency table) ===")
    for ft in (-128, -96, -64, -32, -1, 0, 1, 32, 64, 96, 127):
        data = build_xm(0, ft)
        run_case(f"xm finetune={ft}", data, xm_predicted_hz(0, ft))

    print()
    print("=== XM: finetune=0, relative_note sweep ===")
    for rn in (-24, -12, -1, 0, 1, 12, 24):
        data = build_xm(rn, 0)
        run_case(f"xm relative_note={rn}", data, xm_predicted_hz(rn, 0))

    print()
    print("=== XM: combined (non-round target) ===")
    for rn, ft in ((3, 47), (-5, -83), (7, 113)):
        data = build_xm(rn, ft)
        run_case(f"xm rn={rn} ft={ft}", data, xm_predicted_hz(rn, ft))

    print()
    print("=== XM: wide note range (relative_note=finetune=0), xm_note across the full 1..96 ===")
    for xm_note in (1, 13, 25, 37, 49, 61, 73, 85, 96):
        data = build_xm(0, 0, xm_note=xm_note)
        run_case(f"xm xm_note={xm_note}", data, xm_predicted_hz(0, 0, xm_note))

    print()
    print("=== IT: C5Speed direct, at reference note C-5 (it_note=60) ===")
    for c5 in (8363, 4000, 12000, 20000, 65535, 100, 44100, 7919):
        data = build_it(60, c5)
        run_case(f"it C5Speed={c5}", data, it_predicted_hz(60, c5))

    print()
    print("=== IT: fixed C5Speed=8363, note sweep across IT's wider 0..119 range "
          "(checks 2^((note-60)/12) beyond the current 36-note model) ===")
    for it_note in (0, 24, 48, 60, 72, 96, 119):
        data = build_it(it_note, 8363)
        run_case(f"it note={it_note}", data, it_predicted_hz(it_note, 8363))


if __name__ == "__main__":
    main()


def recheck_long_window():
    """Confirm the two FAIL rows are a measurement artifact: at K=256 and a low read-rate, the
    output tone itself is sub-Hz (read_rate/256), so the 1s default window captures under one
    cycle. Retry with a window sized to the pattern's actual length (~7.68s at speed 6/bpm 125)."""
    print()
    print("=== recheck with a window long enough for the (sub-Hz) output tone ===")
    for label, data, predicted in (
        ("it C5Speed=100 (re-check)", build_it(60, 100), it_predicted_hz(60, 100)),
        ("it note=0 (re-check)", build_it(0, 8363), it_predicted_hz(0, 8363)),
    ):
        with tempfile.NamedTemporaryFile(suffix=".it", delete=False) as f:
            f.write(data)
            path = f.name
        samples = decode_f32(path)
        measured = measure_freq(samples, DECODE_RATE, start_s=0.3, dur_s=7.0) * K
        err = cents(measured, predicted)
        print(f"{label:28s} predicted={predicted:9.3f} Hz  measured={measured:9.3f} Hz  "
              f"error={err:+7.2f} cents  {'OK' if abs(err) <= 7 else 'FAIL'}  "
              f"(output tone ~{predicted/K:.3f} Hz, period ~{K/predicted:.2f} s)")


if __name__ == "__main__":
    recheck_long_window()
