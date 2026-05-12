# Mariachi Template Engine Use Cases

The mariachi template engine turns musical grammar into a structured score. It is not trying to fully compose like a human yet. Version 0.1 focuses on believable form, context, instrument roles, section maps, and exportable MusicXML/MIDI.

## What It Generates

The engine can create:

- A structured `Score`
- Multi-instrument mariachi arrangement skeletons
- MusicXML files
- MIDI files
- Section-map JSON files

It currently supports these genre templates:

- `son`
- `bolero`
- `ranchera`
- `polca_ranchera`

It currently supports these performance contexts:

- `cantina`
- `restaurant`
- `restaurant_or_private_party`
- `show`
- `show_or_concert`

## When To Use It

Use the template engine when you want to generate a whole mariachi-style arrangement from musical rules:

- Generate a ranchera form for practice or testing.
- Generate a son with a shortened cantina-style structure.
- Generate a bolero with a romantic 4/4 feel.
- Generate a multi-instrument MusicXML skeleton to open in the app or MuseScore.
- Create examples for testing staff view, piano roll, MIDI export, and MusicXML export.
- Create a section map that explains where A, B, C, intro, verse, chorus, and ending sections happen.

Use the scale/manual tools instead when you only want to add material to one selected instrument part.

## Current Generation Rule

The core idea is:

```text
Song = Genre + Context + Ensemble + SectionForm + RhythmicFeel + InstrumentRoles + Ending
```

Example:

```text
Generate a ranchera in 3/4,
restaurant context,
medium ensemble,
full-length standardized form,
with intro, verse, harmony chorus,
and traditional ending.
```

This produces a structured score before it tries to create fancy melody.

## CLI Examples

Generate a full restaurant ranchera:

```bash
python -m mariachi_music.cli.mariachi_template generate \
  --genre ranchera \
  --context restaurant \
  --key G \
  --tempo 132 \
  --length full \
  --output outputs/ranchera_demo
```

Generated files:

- `outputs/ranchera_demo.musicxml`
- `outputs/ranchera_demo.mid`
- `outputs/ranchera_demo.sections.json`

Generate a short/automatic cantina son:

```bash
python -m mariachi_music.cli.mariachi_template generate \
  --genre son \
  --context cantina \
  --key D \
  --length auto \
  --output outputs/son_cantina_demo
```

Generate a short bolero for a small ensemble:

```bash
python -m mariachi_music.cli.mariachi_template generate \
  --genre bolero \
  --context restaurant \
  --key C \
  --length short \
  --ensemble Guitarrón Vihuela Violin \
  --output outputs/bolero_short_demo
```

Classify an audio file:

```bash
python -m mariachi_music.cli.mariachi_template classify-audio path/to/song.wav
```

The classifier estimates tempo and a rough meter hint, then guesses:

- `son`
- `bolero`
- `ranchera`

It returns confidence and reasoning.

## GUI Use

Open the GUI:

```bash
python -m mariachi_music.gui.app
```

Use the left panel:

1. Set score title, composer, tempo, key, and mode.
2. Open the `Mariachi Template Engine` section.
3. Choose genre, context, length, and optional subtype.
4. Click `Generate Arrangement`.
5. Use `Score Table`, `Staff View`, and `Piano Roll` tabs to inspect the score.
6. Export MusicXML/MIDI or save the project.

The GUI also includes `Classify Audio...`, which asks for an audio file and displays the guessed genre, confidence, tempo, meter hint, and reasoning.

## Design Limits

Version 0.1 is intentionally grammar-first:

- Form correctness over fancy melody
- Instrument roles over perfect realism
- Reusable motifs over random note generation
- Context-aware shortening over fixed song length
- MusicXML/MIDI output over audio synthesis

Future versions should improve:

- Real motif generation and variation
- Harmony vocal writing
- Better endings and pickups
- Better genre recognition from audio
- Staff-view pagination and playback
- GUI control for section maps
