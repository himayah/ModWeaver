# ModWeaver

[日本語](README.md) | **English**

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Format](https://img.shields.io/badge/Format-MOD%20%7C%20XM%20%7C%20S3M%20%7C%20IT%20%7C%20MIDI%20%7C%20MP3-green.svg)](https://openmpt.org/)

**ModWeaver** generates tracker music files entirely automatically, from waveform synthesis to sequencing, using **only the Python standard library** (no third-party packages). With `--format` you can choose ProTracker `.mod` (default), FastTracker II `.xm`, Scream Tracker 3 `.s3m`, Impulse Tracker `.it`, General MIDI `.mid` or `.mp3` (only `.mp3` needs the external program ffmpeg). Besides the nostalgic genre (`nostalgic`), `--genre` switches between 12 genres in total, including suspense (`suspense-slow` / `suspense-chase`), military march (`march`), swing jazz (`swing-jazz`), odd-meter prog rock (`prog-rock`), trap (`trap`), future bass (`future-bass`), Middle Eastern maqam (`maqam`), free jazz (`free-jazz`), minimalism (`minimalism`) and full orchestra (`orchestral`, 8-channel). `--genre random` picks one for you. (Formerly known as TwilightPad MOD Generator. See `--list-genres` for the current list of genres.)

The default `nostalgic` genre produces bittersweet, wistful pieces: emotional chord progressions that evoke a city at dusk or the walk home, woven from a music box, an enveloping analog pad and a lo-fi beat.

---

## Features

- **An endless supply of different songs (procedural composition engine)**:
  Rather than rolling dice at random, it generates chord progressions, motifs, melodies and rhythms under the constraints of each genre's music theory. Every run yields a different, expressive and hummable piece.
- **Full reproducibility with seeds**:
  When you get a song you like, pass the seed shown in the console as `--seed <number>` to regenerate exactly the same song at any time.
- **Fully standalone synthesis**:
  Instead of loading external audio files (WAV or MP3), it synthesizes 8-bit PCM samples directly with digital signal processing (DSP): sine waves, harmonics and filtered noise.
- **Nostalgic sound design**:
  - **Music Box / Chime**: a music-box tone modelling the resonance of clear metal tines (inharmonic partials) with a smooth exponential decay.
  - **Twilight Ambient Pad**: warm analog synth strings with integer-period design, so they loop seamlessly with no clicks.
  - **Warm Mellow Bass**: a round, deep acoustic / lo-fi sub bass.
  - **Vintage Lo-Fi Drums**: a pitch-dropping kick, a warm retro snare and a delicate closed hi-hat.
- **Six output formats (`--format`)**:
  The default is Amiga ProTracker 4-channel MOD (`M.K.`). Genres with other than 4 channels (the 8-channel `orchestral`) become FastTracker-style multichannel MOD (`8CHN`). You can also choose `.xm` / `.s3m` / `.it` (tracker formats), General MIDI `.mid` (playable in DAWs and GM synths) and `.mp3` (rendered with ffmpeg). Automated tests play every tracker format with OpenMPT's playback engine (libopenmpt) and check that it sounds at the same pitch and length as the MOD.
- **Tempo control (`--tempo`)**:
  Fix the BPM with `--tempo 120`, or give a range such as `--tempo 80-100` to pick one at random within it. With the same seed you get "the same song" at a different tempo.

---

## Requirements

- **Python 3.7 or later** (no extra `pip install` needed)
- **Only for `--format mp3`: ffmpeg** (built with **libopenmpt** and **libmp3lame**)
  - The MP3 is made by writing the song as `.xm`, playing it with ffmpeg's built-in libopenmpt (OpenMPT's playback engine) and encoding it to MP3. ModWeaver itself has no audio playback engine.
  - Put `ffmpeg` on your PATH, or set the environment variable `MODWEAVER_FFMPEG` to the path of the executable.
  - On Windows, builds such as the **full** build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) include libopenmpt (the essentials build may not). To check, make sure `ffmpeg -hide_banner -demuxers` lists `libopenmpt` and `ffmpeg -hide_banner -encoders` lists `libmp3lame`.
  - If ffmpeg is not found or lacks a required feature, ModWeaver says what is missing and exits with code `5` (no file is written).
  - Formats other than `.mp3` do not need ffmpeg.

---

## Usage

### 1. Running

Running `python modweaver.py` with no arguments prints the usage (the same as `--help`) and exits. To make a song, give options as shown below.

#### Generate a new random song (different every run):
```bash
python modweaver.py --genre nostalgic
```
Example output:
```text
==================================================
  ModWeaver: TwilightPad Procedural
==================================================
Genre       : nostalgic
Format      : mod
Seed        : 732501
Tempo       : BPM 90
Theme A     : Step-Down (Nostalgic Descent) -> Fmaj7 - Em7 - Dm7 - Cmaj7
Theme B     : Journey (Memories & Depart) -> Am7 - Fmaj7 - Cmaj7 - G7
--------------------------------------------------
Output File : nostalgic/nostalgic_732501.mod
Success! To reproduce this exact song, run:
  python modweaver.py --genre nostalgic --seed 732501
==================================================
```

If you omit the output path, files are sorted into a subfolder per genre as `<genre>/<genre>_<seed>.mod` (e.g. `nostalgic/nostalgic_732501.mod`); the folder is created if needed.

#### Regenerate a favourite song from its seed (`--genre` defaults to `nostalgic`):
```bash
python modweaver.py --seed 732501
```

#### Choose the output file name (with `--output` the file is written to that exact path, without the per-genre folder):
```bash
python modweaver.py --output MyTwilightSong.mod
```

#### Generate other genres (`--genre` / `-g`):
```bash
python modweaver.py --genre suspense-chase
python modweaver.py --genre suspense-slow --seed 1
python modweaver.py --genre march
python modweaver.py --genre swing-jazz
python modweaver.py --genre prog-rock
python modweaver.py --genre trap
python modweaver.py --genre future-bass
python modweaver.py --genre maqam
python modweaver.py --genre free-jazz
python modweaver.py --genre minimalism
python modweaver.py --genre orchestral   # 8 channels; 8CHN format with the default mod
```

#### Pick a genre at random (`--genre random` / `-g r`):
```bash
python modweaver.py --genre random
python modweaver.py -g r --tempo 120     # picks among genres that can play at 120 BPM
```
The chosen genre is shown in the banner as `Genre       : trap (random)`, and the reproduce command names it (e.g. `--genre trap`). The genre choice does not depend on `--seed` and is random every time (use the reproduce command to make the same song again).

#### Choose the output format (`--format` / `-f`; defaults to `mod`):
```bash
python modweaver.py --format xm          # FastTracker II
python modweaver.py --format s3m         # Scream Tracker 3
python modweaver.py --format it          # Impulse Tracker
python modweaver.py --format midi        # General MIDI (extension .mid)
python modweaver.py --format mp3         # MP3 (needs ffmpeg; see Requirements)
```
When the output path is omitted, the extension follows the format (e.g. `nostalgic/nostalgic_732501.it`).

#### Set the tempo (`--tempo` / `-t`; chosen per genre if omitted):
```bash
python modweaver.py --tempo 120          # generate at 120 BPM
python modweaver.py --tempo 80-100       # pick a random BPM from 80 to 100
```
With a range, the BPM actually chosen is shown on the banner's `Tempo` line, and the reproduce command contains the resolved value (e.g. `--tempo 92`).

#### List the available genres:
```bash
python modweaver.py --list-genres
```

#### Show the version:
```bash
python modweaver.py --version
```
```text
ModWeaver 1.1.0
https://github.com/himayah/ModWeaver
```

### 2. Command-line options

`python modweaver.py` and `python -m mod_weaver` accept the same options. Started with no options at all, it prints the same usage as `--help` and exits (code 0).

| Option | Short | Default | Description |
|:---|:---|:---|:---|
| `--genre` | `-g` | `nostalgic` | Genre id to generate (see the table below). `random` / `r` picks one of the available genres at random (with `--tempo`, among the genres that support that tempo). An unknown id is an error (exit code 2) |
| `--seed` | `-s` | random (100000–999999) | Seed for reproducibility (any integer, negative values allowed). The same genre + seed (+ format + tempo) always produces an identical file |
| `--format` | `-f` | `mod` | Output format: `mod` / `xm` / `s3m` / `it` / `midi` / `mp3` (see the table below) |
| `--tempo` | `-t` | chosen per genre | A BPM (`120`) or a range (`80-100`, random within it), 32–255. A range the genre cannot play is an error (exit code 2); a range only partly outside is clipped to the supported range with a warning |
| `--output` | `-o` | `<genre>/<genre>_<seed>.<ext>` (e.g. `nostalgic/nostalgic_732501.mod`); the folder is created if needed | Output path. When given, the file is written to exactly that path without per-genre folders (a missing parent folder is an error) |
| `--list-genres` | – | – | Print the id, aliases and description of every available genre, then exit (code 0). Nothing is generated |
| `--version` | `-v` | – | Print the version and the GitHub repository URL, then exit (code 0) |
| `--help` | `-h` | – | Print the usage and the option list (including the genre list), then exit (code 0) |

#### Output formats

| `--format` | Extension | Channels | Notes |
|:---|:---|:---|:---|
| `mod` (default) | `.mod` | 4 (`M.K.`) / otherwise `xCHN` | Genres with other than 4 channels (the 8-channel `orchestral`) use FastTracker-style multichannel MOD. Plays in OpenMPT, MilkyTracker, libxmp and others, but not in the original ProTracker or on a real Amiga. Per-sample stereo placement (orchestral) is lost and the player's default L R R L panning is used |
| `xm` | `.xm` | 1–32 | 4-channel genres use Amiga-style L R R L (with a narrower stereo width); orchestral pans each instrument |
| `s3m` | `.s3m` | 1–16 | Same as above (expressed as channel panning) |
| `it` | `.it` | 1–64 | Same as above |
| `midi` | `.mid` | unlimited | General MIDI (SMF format 1). Instruments are the GM programs each genre assigns to its parts, not the synthesized samples themselves. Glides (portamento) jump straight to the target note; vibrato is approximated with modulation (CC1) |
| `mp3` | `.mp3` | 1–32 | 44.1 kHz stereo, 192 kbps. **Needs ffmpeg** (see Requirements) |

#### What the tempo (BPM) means

`--tempo` and the banner's `Tempo` are **quarter-note BPM** (the same as the tracker's `Fxx` value). The exception is `trap`, a half-time genre written on a fine 32nd-note grid, whose BPM is counted the way trap usually is (e.g. 150 feels like 75 in half time). `free-jazz` is a genre whose tempo drifts continuously; `--tempo` sets the starting BPM (later tempo changes are scaled by the same ratio; allowed range 44–163).

#### Available genres

| Genre id | Alias | Description |
|:---|:---|:---|
| `nostalgic` | – | Lo-fi beat and music box evoking nostalgia at dusk (the original TwilightPad) |
| `suspense-slow` | `suspense` | Slow, heavy tension: heartbeat and silence, sudden metallic hits |
| `suspense-chase` | – | Emergency escape / pursuit: heartbeat on every beat, driving eighth notes, impacts out of silence |
| `march` | – | Military march: oom-pah and snare rolls, fanfares, modulation into the trio |
| `swing-jazz` | – | Swing jazz: ride cymbal, walking bass and piano comping over Bb rhythm changes (AABA) |
| `prog-rock` | – | Odd-meter prog / math rock: a 7/8+7/8+5/8 riff contrasted with a 4/4 chorus |
| `trap` | – | Trap / drill: 32nd-note hi-hat rolls and 808 glides over a two-chord Cm–Ab loop |
| `future-bass` | – | Future bass: kick-triggered sidechain, vocal chops, Eb I–V–vi–IV |
| `maqam` | – | Middle Eastern maqam (Rast on G): oud taqsim and maqsum usul with neutral intervals |
| `free-jazz` | – | Free jazz: tone clusters, probabilistic density textures, rubato (continuous tempo changes) |
| `minimalism` | – | Minimal / phase music: four parts with 16/12/8/6-row cycles drift apart and realign |
| `orchestral` | – | Full orchestra / film score: 8-channel, six-voice strings + woodwinds + brass + timpani |

You can also check the current list with `python modweaver.py --list-genres` or `python modweaver.py --help` (if genres are added, that output is always authoritative). The descriptions printed by the program are in Japanese.

Genres are loaded automatically on every start from the modules in `mod_weaver/genres/` (one file = one genre). To add a genre, just put a `.py` file in that directory defining a `GenreProfile` subclass decorated with `@register_profile` (with an `id` and a one-line `description`). See [CLI_STAGE2_DESIGN.md](CLI_STAGE2_DESIGN.md) §3 (in Japanese) for details.

#### Exit codes

| Code | Meaning |
|:---|:---|
| `0` | Success (including running with no arguments, `--help`, `--list-genres` and `--version`) |
| `2` | Argument error, unknown genre, or a tempo the genre cannot play (including `--genre random` when no genre supports the tempo) |
| `3` | Generation or structure-check error |
| `4` | Output error (e.g. the file cannot be written) |
| `5` | `--format mp3` and ffmpeg is not found, or lacks libopenmpt / libmp3lame |
| `1` | Unexpected exception (a stack trace is printed) |

### 3. Playing the results

The generated `.mod` / `.xm` / `.s3m` / `.it` files play right away in the trackers and players below (`.mid` plays in GM synths, DAWs and media players; `.mp3` in any music player):

- **Recommended trackers (for editing and inspection)**:
  - [OpenMPT (Open ModPlug Tracker)](https://openmpt.org/) (Windows)
  - [MilkyTracker](https://milkytracker.org/) (Windows / macOS / Linux)
  - [Schism Tracker](http://schismtracker.org/) (cross-platform)
- **Media players**:
  - [XMPlay](https://www.un4seen.com/xmplay.html) (Windows / high-quality tracker playback)
  - [VLC media player](https://www.videolan.org/vlc/)
  - [Audacious](https://audacious-media-player.org/)

> **Tip (playing in OpenMPT)**:
> Opened in OpenMPT, you can watch and edit each pattern's note data, the samples used (headers and loop points), the tempo (BPM) setting and what each channel is playing, in real time.

---

## Tracks and parts (4 channels)

Channel roles and instruments differ per genre and are defined as a `ChannelPlan` in `mod_weaver/genres/*.py`.
Below is the layout of the default `nostalgic` genre (a balanced stereo image following the Amiga's fixed panning:
1: left, 2: right, 3: right, 4: left). For other genres, see `CHANNEL_PLAN` in each `genres/*.py`, or the per-genre
sections (ChannelPlan / instrument kit) of [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) (in Japanese).

| Channel | Pan | Part | Instruments | Role |
|:---|:---|:---|:---|:---|
| **Channel 1** | Left | Drums | LoFiKick, SoftSnare, ClosedHH | A laid-back chill-hop / lo-fi beat |
| **Channel 2** | Right | Bass | WarmBass | A singing bass line supporting the chord roots |
| **Channel 3** | Right | Pad | TwilightPad | Sustained analog chords filling the background with dusk colours |
| **Channel 4** | Left | Melody | MusicBox | A poignant lead melody (music box) |

---

## Project layout

```text
.
├── modweaver.py       # Top-level launcher (prints the usage when run with no arguments)
├── mod_weaver/        # The package. Also runnable as `python -m mod_weaver`
│   ├── core/          # Stable layer: data model, DSP, sample synthesis (Patch system), harmony, groove (EXT-1),
│   │                   #   variable measures (EXT-2), writer/verify, output formats (formats / s3m / it / midi /
│   │                   #   timeline / render (mp3))
│   ├── profiles/      # Genre machinery: GenreProfile base, registry (auto-discovers genres/), shared helpers
│   └── genres/        # Variable layer: genre modules (one file = one genre; registered just by being there)
│                       #   (nostalgic / suspense-* / march / swing-jazz / prog-rock /
│                       #   trap / future-bass / maqam / free-jazz / minimalism / orchestral)
├── nostalgic/         # Generated MOD files (default output folder, e.g. nostalgic_732501.mod)
├── DESIGN.md               # Original detailed design of the nostalgic genre: rework points, acoustics, music theory
├── EXTENSION_SPEC.md       # Earliest multi-genre concept (superseded by EXTENSION_DESIGN.md)
├── EXTENSION_DESIGN.md     # Multi-genre engine, first stage (Phases 1–3, four genres; implemented)
├── CORE_EXTENSION_DESIGN.md # Second-stage core extensions (EXT-1–6); Phases 4a–4e all implemented
├── GENRE_DESIGN_V2.md      # Detailed design of the eight second-stage genres; all implemented
├── FORMAT_TEMPO_DESIGN.md  # Output format (--format) and tempo (--tempo) design; implemented
├── CLI_STAGE2_DESIGN.md    # Genre auto-discovery, --genre random, --version etc.; implemented
├── README.md          # README (Japanese; shown first on GitHub)
└── README.en.md       # This document (English)
```

The design documents are written in Japanese. For the acoustic analysis and the rework of the original issues (problems in the Copilot-generated code), see [DESIGN.md](DESIGN.md). The first-stage implementation design (nostalgic/suspense/march) is in [EXTENSION_DESIGN.md](EXTENSION_DESIGN.md); sample synthesis (`core/synth.py`) is in [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md) §8, and the second-stage core extensions (EXT-1–6, all implemented) in [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md); the genres (swing-jazz, prog-rock, orchestral and the rest of the eight, all implemented) are in [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md); output formats and tempo in [FORMAT_TEMPO_DESIGN.md](FORMAT_TEMPO_DESIGN.md); genre auto-discovery and the CLI improvements in [CLI_STAGE2_DESIGN.md](CLI_STAGE2_DESIGN.md).

---

## License

This project is released under the [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0).

```
Copyright 2026

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
