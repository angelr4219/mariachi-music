# Mariachi Music

Music transcription and sheet music generation software — built Python-first, designed for mariachi and beyond.

## What it does

- **Generates sheet music programmatically** — scales, exercises, multi-instrument scores
- **Exports MusicXML** — open in MuseScore to view, edit, and print
- **Exports MIDI** — play back generated scores
- **PyQt5 GUI** — visual score creation without touching the CLI
- **Audio transcription pipeline** — convert audio → Score → sheet music (in progress)

## Architecture

```
mariachi_music/
├── core/           # Score, Part, Measure, Note, Rest, Pitch, Duration, Instrument
├── theory/         # Scales, intervals, keys (major, minor, chromatic, modes)
├── generation/     # Scale generator, exercise generator (planned)
├── export/         # MusicXML 3.1, MIDI (pretty_midi)
├── cli/            # Command-line tools
├── gui/            # PyQt5 GUI
├── transcription/  # Audio → Score pipeline, stem separation
└── cpp/            # C++ acceleration (future)
```

**Design rule:** The `Score` object is the center of everything. The CLI, GUI, and transcription pipeline all use the same `Score → Part → Measure → Note` classes. Nothing writes MusicXML directly from raw audio data.

## Quick start

```bash
git clone https://github.com/angelr4219/mariachi-music
cd mariachi-music
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI examples

### Generate a C major scale

```bash
python -m mariachi_music.cli.create_scale \
  --key C --mode major --octave 4 --duration quarter \
  --time-signature 4/4 --tempo 120 --instrument Violin \
  --output outputs/c_major_scale
```

Produces `outputs/c_major_scale.musicxml` and `outputs/c_major_scale.mid`.

### Generate a G major scale for trumpet (descending, half notes, 3/4)

```bash
python -m mariachi_music.cli.create_scale \
  --key G --mode major --duration half \
  --time-signature 3/4 --tempo 90 --instrument Trumpet \
  --descending --output outputs/g_major_trumpet
```

### Generate a multi-instrument score

```bash
python -m mariachi_music.cli.create_score \
  --title "Mariachi Practice" --composer "Angel Ramirez" \
  --tempo 120 --key G --mode major --time-signature 4/4 \
  --instruments Violin Trumpet Guitarrón \
  --output outputs/mariachi_practice
```

### Launch the GUI

```bash
python -m mariachi_music.gui.app
```

## Python API

```python
from mariachi_music.core.score import Score
from mariachi_music.core.tempo import Tempo
from mariachi_music.generation.scale_generator import generate_scale_score

# Generate a scale
score = generate_scale_score(key="C", mode="major", duration="quarter",
                              instrument="Violin", tempo=120)
score.export_musicxml("outputs/c_major.musicxml")
score.export_midi("outputs/c_major.mid")

# Build a score manually
score = Score(title="My Score", composer="Angel Ramirez", tempo=Tempo(120))
violin = score.new_part("Violin")
violin.add_notes(["C4", "E4", "G4", "C5"], duration="quarter")
trumpet = score.new_part("Trumpet")
trumpet.add_notes(["G4", "B4", "D5", "G5"], duration="quarter")
score.export_musicxml("outputs/my_score.musicxml")
```

## Supported features

### Modes / scales
`major`, `minor`, `dorian`, `phrygian`, `lydian`, `mixolydian`, `locrian`, `chromatic`

### Instruments
Violin, Trumpet, Guitarrón, Vihuela, Guitar, Voice, Harp, Piano, Generic Treble, Generic Bass

### Durations
whole, half, quarter, eighth, sixteenth, dotted_half, dotted_quarter, dotted_eighth

### Time signatures
4/4, 3/4, 2/4, 6/8 (and others)

### Keys
All 15 major keys, natural minor keys

## Running tests

```bash
pytest
```

62 tests covering core engine, scale generation, MusicXML export, and MIDI export.

## Opening output in MuseScore

1. Open MuseScore
2. **File → Open** → select the `.musicxml` file
3. Review and edit notes
4. **File → Export → PDF** to print sheet music

Or via command line:

```bash
mscore -o outputs/score.pdf outputs/score.musicxml
```

## Roadmap

- [ ] Chord generation (`theory/chords.py`)
- [ ] Accompaniment generator (vihuela strumming patterns, guitarrón basslines)
- [ ] PDF export via MuseScore CLI
- [ ] Audio transcription → Score integration
- [ ] Onset-aware note segmentation
- [ ] Multi-stem transcription (Demucs → per-instrument Score)
- [ ] LilyPond export
- [ ] C++ acceleration for pitch detection / FFT
