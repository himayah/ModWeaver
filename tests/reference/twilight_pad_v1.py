import struct
import math
import random
import sys
import argparse

# ============================================================
# ProTracker Constants & Utilities
# ============================================================

PAL_AMIGA_CLOCK = 3546895.0
SR = PAL_AMIGA_CLOCK / (214.0 * 2.0)  # ~8287.1378 Hz (C-3 再生レート基準)

def clamp(x):
    return max(-128, min(127, int(round(x))))

def pad_even(b):
    return b if len(b) % 2 == 0 else b + b"\x00"

# ProTracker Standard PAL Period Table (3 Octaves, 36 Notes)
PERIODS = {
    # Octave 1 (Low)
    "C-1": 856, "C#1": 808, "D-1": 762, "D#1": 720,
    "E-1": 678, "F-1": 640, "F#1": 604, "G-1": 570,
    "G#1": 538, "A-1": 508, "A#1": 480, "B-1": 453,
    # Octave 2 (Mid)
    "C-2": 428, "C#2": 404, "D-2": 381, "D#2": 360,
    "E-2": 339, "F-2": 320, "F#2": 302, "G-2": 285,
    "G#2": 269, "A-2": 254, "A#2": 240, "B-2": 226,
    # Octave 3 (High)
    "C-3": 214, "C#3": 202, "D-3": 190, "D#3": 180,
    "E-3": 170, "F-3": 160, "F#3": 151, "G-3": 143,
    "G#3": 135, "A-3": 127, "A#3": 120, "B-3": 113,
}

SCALE_NOTES = [
    "C-2", "D-2", "E-2", "F-2", "G-2", "A-2", "B-2",
    "C-3", "D-3", "E-3", "F-3", "G-3", "A-3", "B-3"
]

def make_cell(note="---", sample=0, effect=0, effect_param=0):
    """ProTracker 4byte ノートセルを生成"""
    period = 0 if note == "---" or note is None else PERIODS[note]
    hi_smp = (sample >> 4) & 0x0F
    lo_smp = sample & 0x0F
    b0 = (hi_smp << 4) | ((period >> 8) & 0x0F)
    b1 = period & 0xFF
    b2 = (lo_smp << 4) | (effect & 0x0F)
    b3 = effect_param & 0xFF
    return bytes([b0, b1, b2, b3])

def cell(note="---", sample=0, vol=None, effect=0, effect_param=0):
    """ベロシティ(0x0C)またはエフェクト付きでセルを生成"""
    if vol is not None:
        v = max(0, min(64, int(vol)))
        return make_cell(note, sample, 0x0C, v)
    return make_cell(note, sample, effect, effect_param)

# ============================================================
# サンプル音源生成 (ノスタルジック・高音質設計)
# ============================================================

def gen_kick():
    """Lo-Fi Warm Kick: 深く温かみのある丸いキック"""
    length = int(0.20 * SR)
    data = []
    for i in range(length):
        t = i / SR
        phase = 2 * math.pi * (46 * t + (64.0 / 30.0) * (1.0 - math.exp(-30.0 * t)))
        env = math.exp(-11.5 * t)
        v = math.sin(phase) * env
        v = math.tanh(v * 1.3)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_snare():
    """Nostalgic Soft Snare: 乾いたレトロな質感の柔らかいスネア"""
    r = random.Random(42)  # サンプル波形は常に安定した高品質
    length = int(0.18 * SR)
    data = []
    lp = 0.0
    for i in range(length):
        t = i / SR
        tone = math.sin(2 * math.pi * 175 * t) * math.exp(-22.0 * t)
        raw_noise = r.uniform(-1.0, 1.0)
        lp = lp * 0.35 + raw_noise * 0.65
        noise = lp * math.exp(-14.0 * t)
        v = tone * 0.45 + noise * 0.55
        v = math.tanh(v * 1.25)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_hihat():
    """Closed Hi-Hat: 繊細で小気味よいLo-Fiクローズドハット"""
    r = random.Random(123)
    length = int(0.045 * SR)
    data = []
    prev = 0.0
    for i in range(length):
        t = i / SR
        raw = r.uniform(-1.0, 1.0)
        ring = (math.sin(2 * math.pi * 3200 * t) + math.sin(2 * math.pi * 4400 * t)) * 0.25
        hp = (raw + ring) - prev
        prev = raw + ring
        env = math.exp(-65.0 * t)
        v = hp * env * 0.85
        v = math.tanh(v * 1.4)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_bass():
    """Warm Mellow Bass: 豊かで丸みのあるアコースティック風ベース (実音 C4基準)"""
    length = int(0.72 * SR)
    f0 = 261.63
    data = []
    for i in range(length):
        t = i / SR
        v1 = math.sin(2 * math.pi * f0 * t) * 0.80
        v2 = math.sin(2 * math.pi * 2 * f0 * t) * 0.20
        attack = min(1.0, t / 0.005)
        env = attack * math.exp(-3.2 * t)
        v = math.tanh((v1 + v2) * env * 1.25)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_musicbox():
    """Nostalgic Music Box / Chime: 郷愁を誘う澄んだオルゴール/トイチャイム音"""
    length = int(1.15 * SR)
    f0 = 261.63
    data = []
    for i in range(length):
        t = i / SR
        v1 = math.sin(2 * math.pi * f0 * t) * math.exp(-2.0 * t) * 0.55
        v2 = math.sin(2 * math.pi * 2 * f0 * t) * math.exp(-3.5 * t) * 0.25
        v3 = math.sin(2 * math.pi * 3 * f0 * t) * math.exp(-5.0 * t) * 0.12
        v4 = math.sin(2 * math.pi * 5.4 * f0 * t) * math.exp(-12.0 * t) * 0.08
        attack = min(1.0, t / 0.0015)
        v = (v1 + v2 + v3 + v4) * attack
        v = math.tanh(v * 1.1)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_pad():
    """Twilight Ambient Pad: 完全ループ対応の温かいアナログ・ストリングスパッド"""
    length = 1024
    K = 32
    data = []
    for i in range(length):
        phase = 2 * math.pi * K * i / length
        h1 = math.sin(phase) * 0.55
        h2 = math.sin(2 * phase) * 0.22
        h3 = math.sin(3 * phase) * 0.08
        sub = math.sin(0.5 * phase) * 0.30
        v = h1 + h2 + h3 + sub
        v = math.tanh(v * 0.95)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_flute():
    """Mellow Flute / Lead: 哀愁漂う素朴な木管風リード (完全ループ)"""
    length = 1024
    K = 32
    data = []
    for i in range(length):
        phase = 2 * math.pi * K * i / length
        s1 = math.sin(phase) * 0.72
        s3 = math.sin(3 * phase) * 0.16
        s5 = math.sin(5 * phase) * 0.06
        v = s1 + s3 + s5
        v = math.tanh(v * 1.05)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

# ============================================================
# 音楽理論・コード・スケール情報プール
# ============================================================

CHORD_DEFS = {
    "Fmaj7": {
        "root": "F-2", "pad": "C-3",
        "chord_tones": ["A-2", "C-3", "E-3", "A-3"],
        "scale_tones": ["A-2", "C-3", "D-3", "E-3", "G-3", "A-3"],
    },
    "Em7": {
        "root": "E-2", "pad": "B-2",
        "chord_tones": ["G-2", "B-2", "D-3", "G-3"],
        "scale_tones": ["B-2", "C-3", "D-3", "E-3", "G-3", "A-3"],
    },
    "Dm7": {
        "root": "D-2", "pad": "A-2",
        "chord_tones": ["F-2", "A-2", "C-3", "F-3"],
        "scale_tones": ["A-2", "C-3", "D-3", "E-3", "F-3", "A-3"],
    },
    "Cmaj7": {
        "root": "C-2", "pad": "G-2",
        "chord_tones": ["E-2", "G-2", "B-2", "C-3", "E-3"],
        "scale_tones": ["G-2", "A-2", "B-2", "C-3", "D-3", "E-3", "G-3"],
    },
    "G7": {
        "root": "G-2", "pad": "D-3",
        "chord_tones": ["B-2", "D-3", "F-3", "G-3"],
        "scale_tones": ["B-2", "C-3", "D-3", "E-3", "F-3", "G-3"],
    },
    "Am7": {
        "root": "A-2", "pad": "E-3",
        "chord_tones": ["C-3", "E-3", "G-3", "A-3"],
        "scale_tones": ["A-2", "B-2", "C-3", "D-3", "E-3", "G-3", "A-3"],
    },
}

# ノスタルジックさを担保するコード進行プール
PROGRESSION_PRESETS = [
    ("Step-Down (Nostalgic Descent)", ["Fmaj7", "Em7", "Dm7", "Cmaj7"]),
    ("Royal Road (Classic Emotion)",  ["Fmaj7", "G7", "Em7", "Am7"]),
    ("Saudade (Sentimental Sunset)",  ["Dm7", "G7", "Cmaj7", "Am7"]),
    ("Journey (Memories & Depart)",   ["Am7", "Fmaj7", "Cmaj7", "G7"]),
    ("Canon Sunset (Warm Twilight)",  ["Cmaj7", "G7", "Am7", "Em7"]),
]

RHYTHM_MOTIFS = [
    [0, 4, 6, 10, 12],
    [0, 6, 10, 14],
    [0, 4, 8, 12],
    [0, 3, 6, 10, 12],
    [0, 6, 8, 12],
]

# ============================================================
# 手続き型メロディ＆バッキング生成エンジン
# ============================================================

def make_empty_row():
    return [make_cell("---") for _ in range(4)]

def generate_melody_bar(rng, chord_name, rhythm, prev_note=None, octave_shift=0, is_cadence=False):
    """コードトーンと対位法ルールに基づき、1小節分の歌心あるメロディを生成"""
    info = CHORD_DEFS[chord_name]
    chord_tones = info["chord_tones"]
    scale_tones = info["scale_tones"]

    # オクターブシフト（サビ用）
    if octave_shift > 0:
        shifted_chord = []
        for n in chord_tones:
            name, octv = n.split("-")
            new_oct = min(3, int(octv) + octave_shift)
            shifted_chord.append(f"{name}-{new_oct}")
        chord_tones = shifted_chord

        shifted_scale = []
        for n in scale_tones:
            name, octv = n.split("-")
            new_oct = min(3, int(octv) + octave_shift)
            shifted_scale.append(f"{name}-{new_oct}")
        scale_tones = shifted_scale

    notes = []
    current_note = prev_note

    for idx, row in enumerate(rhythm):
        if idx == 0:
            # 強拍はコードトーンから選択（切ない長7度や3度、5度）
            if current_note is None:
                note = rng.choice(chord_tones)
            else:
                # 前の音から近いコードトーン（滑らかな接続）
                sorted_tones = sorted(
                    chord_tones,
                    key=lambda n: abs(SCALE_NOTES.index(n) - SCALE_NOTES.index(current_note))
                )
                note = sorted_tones[0] if rng.random() < 0.75 else sorted_tones[min(1, len(sorted_tones)-1)]
        elif idx == len(rhythm) - 1 and is_cadence:
            # フレーズ末尾の終止（解決音）
            note = chord_tones[0] if chord_tones else "C-3"
        else:
            # 経過音: 75%で順次進行、25%で跳躍進行
            curr_idx = SCALE_NOTES.index(current_note)
            if rng.random() < 0.75:
                step = rng.choice([-1, 1, -2, 2])
                target_idx = max(0, min(len(SCALE_NOTES) - 1, curr_idx + step))
                cand = SCALE_NOTES[target_idx]
                note = cand if cand in scale_tones else min(
                    scale_tones, key=lambda s: abs(SCALE_NOTES.index(s) - target_idx)
                )
            else:
                note = rng.choice(chord_tones)

        current_note = note
        # ベロシティの人間味（拍頭は強く、経過拍は柔らかく）
        vol = 60 if idx == 0 else rng.randint(48, 56)
        notes.append((row, note, vol))

    return notes, current_note

def build_procedural_pattern(rng, progression, bpm, is_intro=False, is_outro=False, is_chorus=False):
    """1パターン（64行・4小節）を手続き型生成"""
    rows = [make_empty_row() for _ in range(64)]

    # テンポ指定 (BPM 88〜96)
    rows[0][0] = make_cell("---" if is_intro else "C-3", 0 if is_intro else 1, 0x0F, bpm)

    # 動機（Motif）の選択（反復性を生み出す）
    motif_a = rng.choice(RHYTHM_MOTIFS)
    motif_b = rng.choice(RHYTHM_MOTIFS)
    rhythms = [motif_a, motif_a, motif_b, [0, 6, 10, 14] if not is_outro else [0, 8]]

    # ドラムスタイルの決定
    has_ghost = rng.random() < 0.5

    melody_prev = None

    for bar_idx, chord_name in enumerate(progression):
        base_row = bar_idx * 16
        cinfo = CHORD_DEFS[chord_name]
        rhythm = rhythms[bar_idx]

        # --------------------------------------------------------
        # Ch1: Drums
        # --------------------------------------------------------
        if not is_intro:
            if is_outro:
                # アウトロは静かなキックのみ
                if bar_idx < 2:
                    rows[base_row + 0][0] = cell("C-3", 1, 46 - bar_idx * 10)
                    rows[base_row + 8][0] = cell("C-3", 1, 40 - bar_idx * 10)
            else:
                for step in range(0, 16, 2):
                    r_idx = base_row + step
                    if step in [0, 8]:
                        # Kick
                        if step == 0 and bar_idx == 0:
                            pass  # Row 0 はテンポエフェクトで処理済み
                        else:
                            rows[r_idx][0] = cell("C-3", 1, 56)
                    elif step in [4, 12]:
                        # Snare
                        rows[r_idx][0] = cell("C-3", 2, 50)
                    else:
                        # Hi-Hat (表)
                        rows[r_idx][0] = cell("C-3", 3, 40)

                    # Hi-Hat (裏拍)
                    if step + 1 < 16:
                        rows[r_idx + 1][0] = cell("C-3", 3, 30)

                # ゴーストノート
                if has_ghost and is_chorus:
                    rows[base_row + 15][0] = cell("C-3", 3, 24)

                # 小節末フィル（第4小節末）
                if bar_idx == 3:
                    rows[base_row + 14][0] = cell("C-3", 3, 34)
                    rows[base_row + 15][0] = cell("C-3", 2, 46)

        # --------------------------------------------------------
        # Ch2: Warm Bass
        # --------------------------------------------------------
        if not is_intro:
            root = cinfo["root"]
            rows[base_row + 0][1] = cell(root, 4, 60 if not is_outro else 50 - bar_idx * 8)
            if not is_outro:
                # 8拍目や12拍目にルート・パッシングノート
                rows[base_row + 8][1] = cell(root, 4, 54)
                if rng.random() < 0.6:
                    pass_note = cinfo["chord_tones"][0]
                    rows[base_row + 12][1] = cell(pass_note, 4, 50)

        # --------------------------------------------------------
        # Ch3: Twilight Pad (持続和音)
        # --------------------------------------------------------
        pad_note = cinfo["pad"]
        pad_vol = 46 if not is_outro else max(10, 42 - bar_idx * 8)
        rows[base_row + 0][2] = cell(pad_note, 6, pad_vol)

        # --------------------------------------------------------
        # Ch4: Melody (Music Box)
        # --------------------------------------------------------
        oct_shift = 1 if is_chorus else 0
        is_cadence = (bar_idx == 3)
        bar_melody, melody_prev = generate_melody_bar(
            rng, chord_name, rhythm, melody_prev, octave_shift=oct_shift, is_cadence=is_cadence
        )

        for m_row, m_note, m_vol in bar_melody:
            if is_intro:
                m_vol = max(38, m_vol - 6)
            elif is_outro:
                m_vol = max(30, m_vol - bar_idx * 5)
            rows[base_row + m_row][3] = cell(m_note, 5, m_vol)

    # アウトロのフェードアウト処理
    if is_outro:
        rows[56][2] = cell("---", 0, 18)
        rows[60][2] = cell("---", 0, 8)
        rows[63][2] = cell("---", 0, 0)

    return b"".join(b"".join(r) for r in rows)

# ============================================================
# MODファイル構築メイン処理
# ============================================================

def build_procedural_mod(path="TwilightPad.mod", seed=None):
    if seed is None:
        seed = random.randint(100000, 999999)

    rng = random.Random(seed)

    # 進行プリセットのプロシージャル選択
    idx_a = rng.randrange(len(PROGRESSION_PRESETS))
    idx_b = (idx_a + rng.randint(1, len(PROGRESSION_PRESETS) - 1)) % len(PROGRESSION_PRESETS)

    name_a, prog_a = PROGRESSION_PRESETS[idx_a]
    name_b, prog_b = PROGRESSION_PRESETS[idx_b]

    # テンポのプロシージャル決定 (BPM 88〜96)
    bpm = rng.choice([88, 90, 92, 94, 96])

    print("==================================================")
    print("  TwilightPad Procedural MOD Generator")
    print("==================================================")
    print(f"Seed        : {seed}")
    print(f"Tempo       : BPM {bpm}")
    print(f"Theme A     : {name_a} -> {' - '.join(prog_a)}")
    print(f"Theme B     : {name_b} -> {' - '.join(prog_b)}")
    print("--------------------------------------------------")
    print("Synthesizing nostalgic samples...")

    kick = gen_kick()
    snare = gen_snare()
    hihat = gen_hihat()
    bass = gen_bass()
    musicbox = gen_musicbox()
    pad = gen_pad()
    flute = gen_flute()

    samples_info = [
        (kick,     "LoFiKick",    56, 0, 1),
        (snare,    "SoftSnare",   50, 0, 1),
        (hihat,    "ClosedHH",    42, 0, 1),
        (bass,     "WarmBass",    60, 0, 1),
        (musicbox, "MusicBox",    60, 0, 1),
        (pad,      "TwilightPad", 46, 0, len(pad) // 2),
        (flute,    "MellowFlute", 52, 0, len(flute) // 2),
    ]

    print("Composing patterns and melodies...")
    # 4つのパターンを生成
    pat_intro   = build_procedural_pattern(rng, prog_a, bpm, is_intro=True)
    pat_theme_a = build_procedural_pattern(rng, prog_a, bpm, is_intro=False, is_chorus=False)
    pat_theme_b = build_procedural_pattern(rng, prog_b, bpm, is_intro=False, is_chorus=True)
    pat_outro   = build_procedural_pattern(rng, prog_a, bpm, is_outro=True)

    patterns = [pat_intro, pat_theme_a, pat_theme_b, pat_outro]
    song_order = [0, 1, 2, 1, 3]

    with open(path, "wb") as f:
        # Title
        f.write(b"Twilight Pad".ljust(20, b"\x00"))

        # Sample Headers (31 samples × 30 bytes)
        for i in range(31):
            if i < len(samples_info):
                data, name, vol, loop_start, loop_len = samples_info[i]
                name_bytes = name.encode("ascii")
                f.write(name_bytes.ljust(22, b"\x00"))
                lw = len(data) // 2
                f.write(struct.pack(">H", lw))
                f.write(b"\x00")
                f.write(bytes([vol & 0xFF]))
                f.write(struct.pack(">H", loop_start))
                f.write(struct.pack(">H", loop_len))
            else:
                f.write(b"\x00" * 30)

        # Song Length & Restart
        f.write(struct.pack(">B", len(song_order)))
        f.write(struct.pack(">B", 0x7F))

        # Pattern Order Table (128 bytes)
        f.write(bytes(song_order + [0] * (128 - len(song_order))))

        # Magic "M.K."
        f.write(b"M.K.")

        # Patterns
        for pat in patterns:
            f.write(pat)

        # Sample Data
        for info in samples_info:
            f.write(info[0])

    print(f"Output File : {path}")
    print("Success! To reproduce this exact song, run:")
    print(f"  python twilight_pad.py --seed {seed}")
    print("==================================================")
    return seed

# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Procedural Nostalgic MOD Generator")
    parser.add_argument("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output", "-o", type=str, default="TwilightPad.mod", help="Output .mod file path")
    args = parser.parse_args()

    build_procedural_mod(path=args.output, seed=args.seed)

if __name__ == "__main__":
    main()
