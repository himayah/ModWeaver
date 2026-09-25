# ModWeaver

[日本語](README.md) | **English**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Format](https://img.shields.io/badge/Format-MOD%20%7C%20XM%20%7C%20S3M%20%7C%20IT%20%7C%20MIDI%20%7C%20MP3-green.svg)](https://openmpt.org/)

**ModWeaver** generates tracker music files entirely automatically, from waveform synthesis to sequencing, using **only the Python standard library** (no third-party packages). With `--format` you can choose ProTracker `.mod` (default), FastTracker II `.xm`, Scream Tracker 3 `.s3m`, Impulse Tracker `.it`, General MIDI `.mid` or `.mp3` (only `.mp3` needs the external program ffmpeg). Besides the nostalgic genre (`nostalgic`), `--genre` switches between 51 genres in three groups: **moods** (9, e.g. `calm`, `melancholic`, `focus`, `uplifting`), **genres** (27, e.g. `rock`, `pop`, `jazz`, `bossa-nova`, `city-pop`, `house`, `classical`, `cinematic`, `gamelan`, `industrial`, `trap`, `orchestral`) and **styles** (14, e.g. 80s J-pop `jpop-80s`, JRPG game music `jrpg`, cinematic trailer `trailer`, 8-bit chiptune `chiptune`, late-90s racing game `racing-breaks`, suspense `suspense-slow`). `--genre random` picks one for you. Each genre uses 4, 6 or 8 channels as its arrangement needs, and most genres also vary the arrangement from song to song (from a small 4-channel combo to a fuller 8-channel one; `--channels` picks one). (Formerly known as TwilightPad MOD Generator. See `--list-genres` for the current list of genres.)

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
  The default is Amiga ProTracker 4-channel MOD (`M.K.`). 6- and 8-channel songs (e.g. `pop` in its standard 6 channels, 8-channel `orchestral`) become FastTracker-style multichannel MOD (`6CHN` / `8CHN`). You can also choose `.xm` / `.s3m` / `.it` (tracker formats), General MIDI `.mid` (playable in DAWs and GM synths) and `.mp3` (rendered with ffmpeg). Automated tests play every tracker format with OpenMPT's playback engine (libopenmpt) and check that it sounds at the same pitch and length as the MOD.
- **Tempo control (`--tempo`)**:
  Fix the BPM with `--tempo 120`, or give a range such as `--tempo 80-100` to pick one at random within it. With the same seed you get "the same song" at a different tempo.

---

## Requirements

- **Python 3.10 or later** (no extra `pip install` needed)
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

**The usage, genre list and results are shown in Japanese by default. Add `-e` (`--english`) to get them in English**, as the examples below do.

#### Generate a new random song (different every run):
```bash
python modweaver.py -e --genre nostalgic
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
Output File : output/nostalgic_732501.mod
Success! To reproduce this exact song, run:
  python modweaver.py --genre nostalgic --seed 732501
==================================================
```

If you omit the output path, the file is written to the `output` folder in the current directory as `<genre>_<seed>.mod` (e.g. `output/nostalgic_732501.mod`); the folder is created if needed.

#### Regenerate a favourite song from its seed (`--genre` defaults to `nostalgic`):
```bash
python modweaver.py -e --seed 732501
```

#### Choose the output file name (with `--output` the file is written to that exact path instead of the `output` folder):
```bash
python modweaver.py -e --output MyTwilightSong.mod
```

#### Generate other genres (`--genre` / `-g`):
```bash
python modweaver.py -e --genre suspense-chase
python modweaver.py -e --genre suspense-slow --seed 1
python modweaver.py -e --genre march
python modweaver.py -e --genre swing-jazz
python modweaver.py -e --genre prog-rock
python modweaver.py -e --genre trap
python modweaver.py -e --genre future-bass
python modweaver.py -e --genre maqam
python modweaver.py -e --genre free-jazz
python modweaver.py -e --genre minimalism
python modweaver.py -e --genre orchestral   # 8 channels; 8CHN format with the default mod
python modweaver.py -e --genre calm         # mood: calm (4 channels)
python modweaver.py -e --genre city-pop     # genre: city pop (6 channels)
python modweaver.py -e --genre classical    # genre: string-quartet minuet (3/4)
python modweaver.py -e --genre jrpg         # style: JRPG field theme
python modweaver.py -e --genre gamelan      # genre: gamelan (slendro / pelog tuning)
python modweaver.py -e --genre chiptune     # style: 8-bit game music (pulse, triangle, noise)
python modweaver.py -e --genre industrial   # genre: industrial (distortion and metal)
python modweaver.py -e --genre racing-breaks  # style: late-90s racing game (drum'n'bass / breakbeat)
```

#### Pick a genre at random (`--genre random` / `-g r`):
```bash
python modweaver.py -e --genre random
python modweaver.py -e -g r --tempo 120     # picks among genres that can play at 120 BPM
```
The chosen genre is shown in the banner as `Genre       : trap (random)` (with `-e`), and the reproduce command names it (e.g. `--genre trap`). The genre choice does not depend on `--seed` and is random every time (use the reproduce command to make the same song again).

#### Choose the output format (`--format` / `-f`; defaults to `mod`):
```bash
python modweaver.py -e --format xm          # FastTracker II
python modweaver.py -e --format s3m         # Scream Tracker 3
python modweaver.py -e --format it          # Impulse Tracker
python modweaver.py -e --format midi        # General MIDI (extension .mid)
python modweaver.py -e --format mp3         # MP3 (needs ffmpeg; see Requirements)
```
When the output path is omitted, the extension follows the format (e.g. `output/nostalgic_732501.it`).

#### Set the tempo (`--tempo` / `-t`; chosen per genre if omitted):
```bash
python modweaver.py -e --tempo 120          # generate at 120 BPM
python modweaver.py -e --tempo 80-100       # pick a random BPM from 80 to 100
```
With a range, the BPM actually chosen is shown on the banner's `Tempo` line, and the reproduce command contains the resolved value (e.g. `--tempo 92`).

#### Set the number of channels (`--channels` / `-c`; chosen by the genre for each song if omitted):
```bash
python modweaver.py -e --genre pop --channels 4   # small 4-channel combo, Amiga-compatible (M.K.)
python modweaver.py -e --genre pop --channels 8   # 8 channels with a counter-melody and echo added
```
For genres with several numbers in the ch column (e.g. `4/6/8`), the same seed gives the same melody and chords in every arrangement; only the thickness and the number of channels change.

#### List the available genres:
```bash
python modweaver.py -e --list-genres
```

#### Show everything in English (`-e` / `--english`):
```bash
python modweaver.py -e                   # English usage
python modweaver.py -e --list-genres     # genre descriptions in English
python modweaver.py -e --genre trap      # English result banner
```
The usage, the genre descriptions and the result banner switch to English. `-e` does not change the generated song. The summary lines a genre adds to the banner (chord progression names etc.) and error/warning messages (stderr) are in English either way.

#### Show the version:
```bash
python modweaver.py -e --version
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
| `--output` | `-o` | `output/<genre>_<seed>.<ext>` (e.g. `output/nostalgic_732501.mod`); the folder is created if needed | Output path. When given, the file is written to exactly that path (a missing parent folder is an error) |
| `--channels` | `-c` | chosen by the genre for each song | Number of channels: `4` / `6` / `8`. Which numbers are available depends on the genre (the ch column of the genre list); an unavailable number is an error (exit code 2). With `--genre random`, only genres that can use that number are picked |
| `--list-genres` | – | – | Print the id, aliases and description of every available genre, grouped into moods, genres and styles, then exit (code 0). Nothing is generated |
| `--english` | `-e` | – | Show the usage, genre descriptions and results in English (Japanese by default) |
| `--version` | `-v` | – | Print the version and the GitHub repository URL, then exit (code 0) |
| `--help` | `-h` | – | Print the usage and the option list (ending with the genre ids per group), then exit (code 0) |

#### Output formats

| `--format` | Extension | Channels | Notes |
|:---|:---|:---|:---|
| `mod` (default) | `.mod` | 4 (`M.K.`) / otherwise `xCHN` | Genres with other than 4 channels (6 or 8) use FastTracker-style multichannel MOD. Plays in OpenMPT, MilkyTracker, libxmp and others, but not in the original ProTracker or on a real Amiga. The genre's stereo placement is lost and the player's default L R R L panning is used |
| `xm` | `.xm` | 1–32 | 4-channel genres use Amiga-style L R R L (with a narrower stereo width); 6- and 8-channel genres use the per-instrument panning the genre declares |
| `s3m` | `.s3m` | 1–16 | Same as above (expressed as channel panning) |
| `it` | `.it` | 1–64 | Same as above |
| `midi` | `.mid` | unlimited | General MIDI (SMF format 1). Instruments are the GM programs each genre assigns to its parts, not the synthesized samples themselves. Glides (portamento) jump straight to the target note; vibrato is approximated with modulation (CC1) |
| `mp3` | `.mp3` | 1–32 | 44.1 kHz stereo, 192 kbps. **Needs ffmpeg** (see Requirements) |

#### What the tempo (BPM) means

`--tempo` and the banner's `Tempo` are **quarter-note BPM** (the same as the tracker's `Fxx` value). The exception is `trap`, a half-time genre written on a fine 32nd-note grid, whose BPM is counted the way trap usually is (e.g. 150 feels like 75 in half time). `free-jazz` is a genre whose tempo drifts continuously; `--tempo` sets the starting BPM (later tempo changes are scaled by the same ratio; allowed range 44–163).

#### Available genres

**Moods (mood)** — 9

| Genre id | Aliases | ch | Description |
|:---|:---|:---|:---|
| `calm` | – | 4 | Calm and relaxed: soft pads and slow piano arpeggios |
| `cool` | – | 4/6/8 | Cool: glassy synths over a light two-step beat |
| `dark-tense` | – | 4/6/8 | Dark and tense: low ostinato, ticking pulse and heavy hits |
| `dreamy` | – | 4/6/8 | Dreamy: echoing arpeggios over lush pads |
| `energetic` | – | 4/6/8 | Energetic: fast, drum-driven rock with driving guitars and bass |
| `focus` | – | 4 | Focus: minimal lo-fi loop with a steady, unchanging groove |
| `melancholic` | – | 4 | Melancholic piano ballad in a minor key over soft strings |
| `uplifting` | – | 4/6/8 | Uplifting anthem: four-on-the-floor, bright arpeggios and supersaw chords |
| `warm` | – | 4/6 | Warm: acoustic guitar and piano in a gentle major key |

**Genres (genre)** — 27

| Genre id | Aliases | ch | Description |
|:---|:---|:---|:---|
| `ambient` | – | 4 | Ambient: layered pads and sparse bells with little or no beat |
| `bossa-nova` | – | 4/6 | Bossa nova: soft nylon guitar and light percussion in 2/4 |
| `cinematic` | – | 6/8 | Cinematic: piano ostinato building to soaring strings and horns |
| `city-pop` | – | 4/6/8 | City pop: jazzy electric piano, bouncy bass and funky guitar cutting |
| `classical` | – | 4 | Classical: a Classical-era minuet for string quartet with clear cadences |
| `edm` | – | 4/6/8 | EDM: synth-driven builds that explode into the drop |
| `folk` | – | 4/6 | Folk: strummed acoustic guitar and fiddle over simple progressions |
| `free-jazz` | – | 4 | Free jazz: tone clusters, probabilistic density textures, rubato (continuous tempo changes) |
| `future-bass` | – | 4 | Future bass: kick-triggered sidechain, vocal chops, Eb I-V-vi-IV |
| `gamelan` | – | 6 | Gamelan style: interlocking bronze metallophones and gongs in slendro or pelog tuning |
| `hiphop` | – | 4/6 | Hip hop: boom-bap beats and sample-style loops that leave room for rap |
| `house` | – | 4/6/8 | House: steady four-on-the-floor groove with offbeat organ stabs |
| `industrial` | – | 6 | Industrial: distorted beats and metal clangs, a roaring distorted bass and factory noise |
| `jazz` | – | 4 | Modal jazz: dorian vamps, quartal piano voicings and muted trumpet |
| `lofi-hiphop` | – | 4/6/8 | Lo-fi hip hop: swung beats, jazzy electric piano and vinyl noise |
| `maqam` | – | 4 | Middle Eastern maqam (Rast on G): oud taqsim and maqsum usul with neutral intervals |
| `march` | – | 4 | Military march: oom-pah and snare rolls, fanfares, modulation into the trio |
| `minimalism` | – | 4 | Minimal / phase music: four parts with 16/12/8/6-row cycles drift apart and realign |
| `orchestral` | – | 8 | Full orchestra / film score: 8 channels, six-voice strings + woodwinds + brass + timpani |
| `pop` | – | 4/6/8 | Pop: bright major-key melodies, piano and a catchy chorus |
| `prog-rock` | – | 4 | Odd-meter prog / math rock: a 7/8+7/8+5/8 riff contrasted with a 4/4 chorus |
| `rnb-soul` | – | 4/6/8 | R&B / soul: smooth extended chords and a singing melody in a slow jam |
| `rock` | – | 4/6/8 | Rock: guitar riffs over a straight eight-beat |
| `swing-jazz` | – | 4 | Swing jazz: ride cymbal, walking bass and piano comping over Bb rhythm changes (AABA) |
| `synthwave` | – | 4/6/8 | Synthwave: 80s synths, gated snare and a pulsing eighth-note bass |
| `techno` | – | 4 | Minimal techno: a hypnotic four-on-the-floor with slowly mutating sequences |
| `trap` | – | 4 | Trap / drill: 32nd-note hi-hat rolls and 808 glides over a two-chord Cm-Ab loop |

**Styles (style)** — 15

| Genre id | Aliases | ch | Description |
|:---|:---|:---|:---|
| `acoustic-ssw` | – | 4/6 | Acoustic singer-songwriter style: fingerpicked guitar, light percussion and a vocal-like melody |
| `ambient-drone` | – | 4 | Ambient drone: long sustained tones that shift very slowly |
| `anime-ost` | – | 4/6/8 | Anime soundtrack style: driving strings with jazz harmony and brass hits |
| `chiptune` | – | 4 | 8-bit chiptune style: pulse-wave melody and arpeggios, triangle bass, noise drums and jump sounds |
| `indie-rock` | – | 4/6/8 | Indie rock style: live-sounding drums, ringing guitar arpeggios and light overdrive |
| `jpop-80s` | – | 4/6/8 | 80s J-pop style: bright chords, city brass, a light beat and a final key change |
| `jrock-90s` | – | 4/6/8 | 90s J-rock style: loud guitars over a fast beat, a guitar solo and a final key change |
| `jrpg` | – | 4/6/8 | JRPG game music style: melodic adventure theme with harp, strings and horn |
| `lofi-chill` | – | 4/6/8 | Lo-fi chill: soft guitar and flute, pumping sidechain and rain ambience |
| `neo-soul` | – | 4/6/8 | Neo soul style: laid-back off-grid beats and lush electric piano chords |
| `nostalgic` | – | 4 | Lo-fi beat and music box evoking nostalgia at dusk (the original TwilightPad) |
| `racing-breaks` | – | 4/6/8 | Late-90s racing game style: drum'n'bass / breakbeat with 9th-chord e.piano and deep sub bass |
| `suspense-chase` | – | 4 | Emergency escape / pursuit: heartbeat on every beat, driving eighth notes, impacts out of silence |
| `suspense-slow` | `suspense` | 4 | Slow, heavy tension: heartbeat and silence, sudden metallic hits |
| `trailer` | – | 6/8 | Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts |

You can also check the current list with `python modweaver.py -e --list-genres` or `python modweaver.py -e --help` (if genres are added, that output is always authoritative). Without `-e` the descriptions are printed in Japanese.

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

## Tracks and parts

The number of channels (4, 6 or 8), their roles and instruments differ per genre and are defined in `mod_weaver/genres/*.py`
(see the ch column of the genre list). Below is the layout of the default `nostalgic` genre (a balanced stereo image
following the Amiga's fixed panning: 1: left, 2: right, 3: right, 4: left). For other genres, see each `genres/*.py`
(the 35 stage-3 genres declare them in `CHANNELS`), or the per-genre sections in §6 of [DESIGN.md](DESIGN.md)
(§6.16 for the stage-3 genres; in Japanese).

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
├── listen_samples.bat # Windows batch that renders listening samples (3 per item of DESIGN.md §11) into output\listen\
├── mod_weaver/        # The package. Also runnable as `python -m mod_weaver`
│   ├── core/          # Stable layer: data model, DSP, sample synthesis (Patch system), harmony, groove (EXT-1),
│   │                   #   variable measures (EXT-2), writer/verify, output formats (formats / s3m / it / midi /
│   │                   #   timeline / render (mp3))
│   ├── profiles/      # Genre machinery: GenreProfile base, registry (auto-discovers genres/), shared helpers
│   │                   #   (band_common: BandProfile, the skeleton shared by the 35 stage-3 genres)
│   └── genres/        # Variable layer: genre modules (one file = one genre; registered just by being there; 51 genres)
├── output/            # Generated music files (default output folder, e.g. nostalgic_732501.mod)
├── DESIGN.md          # Design document (the current specification; Japanese)
├── DESIGN_HISTORY.md  # Design history (reasons for decisions, corrections, dropped ideas; Japanese)
├── README.md          # README (Japanese; shown first on GitHub)
└── README.en.md       # This document (English)
```

The design documents are written in Japanese: [DESIGN.md](DESIGN.md) describes the current specification, and [DESIGN_HISTORY.md](DESIGN_HISTORY.md) records why things are the way they are, earlier plans and corrections.

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
