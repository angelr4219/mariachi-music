# MuseScore Gap Analysis — Mariachi Music Project

**Date:** 2026-05-11  
**Project:** mariachi_music  
**Purpose:** Compare current feature set against MuseScore 4 to identify build priorities.

---

## Features We Already Have

### Core Data Model
- **Score container** — `Score` dataclass with title, composer, tempo, key/time signature, parts list
- **Part model** — `Part` with instrument metadata, ordered list of measures, auto-measure overflow
- **Measure model** — `Measure` with beat accounting, overflow detection, strict/non-strict add
- **Note model** — `Note` with `Pitch`, `Duration`, velocity, tie start/end, optional lyrics
- **Rest model** — `Rest` with duration; treated uniformly with notes via `NoteOrRest` union
- **Pitch model** — `Pitch` with letter name, accidental, octave; MIDI number, enharmonic, transpose helpers
- **Duration model** — `Duration` covering whole/half/quarter/eighth/sixteenth/thirty-second + dotted variants; beat and MusicXML division values
- **Key signature** — `KeySignature` with root+mode, fifths computation for all standard major/minor keys
- **Time signature** — `TimeSignature` with numerator/denominator, beats-per-measure calculation
- **Tempo** — `Tempo` with BPM

### Instrument Library
- 10 preset instruments: Violin, Trumpet, Guitarrón, Vihuela, Guitar, Voice, Harp, Piano, Generic Treble, Generic Bass
- Per-instrument: clef, MIDI program, range (midi_min/midi_max), transposition (Bb trumpet), abbreviation

### Generation
- **Scale generator** — generates ascending/descending scales for any key/mode/octave/duration/instrument
- **Chord generator** — basic chord-building utilities

### Export
- **MusicXML export** — full `export_musicxml()` on Score
- **MIDI export** — `export_midi()` on Score
- **LilyPond export** — `export_lilypond()` on Score

### GUI
- **Main window** — `MainWindow` with QSplitter layout; menu bar (File/Tools/Help); status bar
- **Controls panel** — `ControlsPanel` for key, mode, octave, duration, time sig, tempo, instrument, title, composer inputs; "Generate Scale" button emitting `generate_requested` signal
- **Score view (table)** — `ScoreView` table displaying Measure / Beat / Instrument / Type / Pitch / Duration columns
- **Export panel** — `ExportPanel` wiring MusicXML and MIDI export with file dialogs

### Tests
- 62 tests passing across core, theory, generation, export, CLI modules

---

## Critical Missing Features — Priority 1 (needed to be viable)

| Feature | MuseScore has | We have | Gap |
|---|---|---|---|
| **Staff notation renderer** | Full engraving engine | Table view only | No visual notation at all |
| **Interactive note entry** | Click staff / MIDI keyboard input | Not started | Can't enter music by hand |
| **Playback engine** | Built-in FluidSynth + SoundFont | Not started | Can't hear the music |
| **Chord/harmony entry** | Click or keyboard shortcut per chord | Not started | Notes only added by code |
| **Multi-measure selection** | Full selection model | Not started | Can't copy/paste regions |
| **Undo/redo** | Unlimited history stack | Not started | Destructive edits |
| **File open/save (native format)** | `.mscz` / `.mscx` | Only export, no round-trip | Can't save work in progress |
| **Dotted note rendering** | Visual dot after notehead | Duration object supports it | Renderer doesn't draw the dot |
| **Accidental rendering** | Automatic placement, courtesy accidentals | Not started in renderer | No sharps/flats on noteheads |
| **Rest symbols** | Standard glyph per duration type | Data model only | Not rendered |
| **Beam groups** | Auto-beaming per time sig | Not started | Eighth/sixteenth notes unbeamed |

---

## Important Missing Features — Priority 2

| Feature | Description |
|---|---|
| **Dynamics (p, mf, f, ff…)** | Per-note or per-measure dynamic markings |
| **Articulations** | Staccato, tenuto, accent, marcato, fermata |
| **Slurs and ties (visual)** | Data model has tie_start/end; renderer needs curves |
| **Lyrics** | Data model has lyric field; no rendering or entry UI |
| **Repeat signs** | First/second endings, D.C. al Coda, D.S. |
| **Volta brackets** | 1st/2nd ending brackets |
| **Multiple voices per staff** | Voice 1/2/3/4 with independent stems |
| **Chord input mode** | Stack multiple noteheads on one stem |
| **Transposition UI** | Shift selected region by interval |
| **Score mixer** | Per-part volume, mute, solo |
| **Multi-staff instruments** | Grand staff (piano, harp) — two staves bracket together |
| **Crescendo/decrescendo hairpins** | Wedge notation |
| **Tuplets (triplets)** | 3 notes in the time of 2, etc. |
| **8va / 8vb ottava lines** | Octave transposition brackets |
| **Rehearsal marks** | Letter/number boxes for ensemble navigation |

---

## Nice-to-Have — Priority 3

| Feature | Description |
|---|---|
| **MIDI import** | Parse .mid → Score (transcription module stub exists) |
| **Audio import + transcription** | Record or import audio, auto-detect pitches |
| **Print/PDF export** | Send rendered notation to printer or PDF |
| **Plugin/extension API** | User-written scripts to manipulate scores |
| **Style editor** | Font sizes, staff spacing, engraving rules |
| **Continuous view** | Horizontal scroll instead of line-wrapped systems |
| **Concert pitch toggle** | Show/hide transpositions for transposing instruments |
| **Score comparison / diff** | Show differences between two versions |
| **Cloud sync** | Save/load from cloud storage |
| **Accessibility (screen reader)** | Announce pitch/duration on focus |

---

## Mariachi-Specific Features (unique to our project)

| Feature | Description | Priority |
|---|---|---|
| **Son / Bolero / Waltz rhythm templates** | Pre-built rhythmic accompaniment patterns for the most common mariachi styles | P1 |
| **Guitarrón tab notation** | 6-string fretboard diagram overlay or dedicated tab staff for the guitarrón | P1 |
| **Vihuela chord grid** | Box-diagram chord chart mode (like guitar chord diagrams) | P1 |
| **Ensemble arrangement templates** | One-click scaffold for full mariachi ensemble (2 trumpets, 2 violins, vihuela, guitarrón, guitar, voice) | P1 |
| **Mariachi-style ornaments** | Glissandos, bends, vibrato markings common in mariachi performance | P2 |
| **Grito marker** | Notation glyph to cue a "¡Ay!" or gritar (crowd/performer shout) at specific measures | P2 |
| **Rasgueo notation** | Strum-pattern notation for vihuela and guitar (rhythmic slash notation) | P2 |
| **Golpe marking** | Tap/percussion hit on guitar body notation | P2 |
| **Regional style tags** | Metadata tags for jaliscience vs. veracruzano vs. norteño style | P3 |
| **Mariachi song database** | Built-in library of traditional son, bolero, polka, ranchera titles with chords | P3 |
| **Trumpet duo voicing assistant** | Auto-harmonize a melody into two-trumpet thirds/sixths (classic mariachi texture) | P2 |
| **Violin section auto-divisi** | Spread melody across violin 1 / violin 2 with idiomatic mariachi figurations | P2 |

---

## Recommended Build Order

### Phase 1 — Visual Foundation (current sprint)
1. **Staff notation renderer** (`notation_view.py`) — read-only QPainter widget, 5-line staff, clef, time sig, key sig, noteheads, stems, barlines, ledger lines, multi-part stacking ✅ **(this deliverable)**
2. **Dotted note dot** and **accidental glyphs** on noteheads in the renderer
3. **Rest symbols** in the renderer (whole, half, quarter, eighth glyphs)

### Phase 2 — Sound and Interaction
4. **Playback engine** — integrate `fluidsynth` Python bindings or `pygame.midi`; play current score from the notation view
5. **Interactive note entry** — click on staff to place a note; duration selected from toolbar
6. **Undo/redo** — `QUndoStack` wrapping all Score mutations

### Phase 3 — Notation Completeness
7. **Beam groups** — auto-beam eighth and sixteenth note runs per time signature
8. **Chord input** — stack noteheads; add `Chord` container alongside `Note`/`Rest`
9. **Slur/tie curves** — QPainter bezier arcs
10. **Dynamics and articulations** — text/glyph rendering below/above staff
11. **Lyrics** — render `note.lyrics` below staff in italic

### Phase 4 — Mariachi Core Features
12. **Son/Bolero/Waltz rhythm templates** — generator functions producing standard accompaniment patterns
13. **Ensemble arrangement scaffold** — `create_mariachi_ensemble(style)` returning a pre-populated Score
14. **Trumpet duo harmonizer** — interval-based voice duplication
15. **Guitarrón bass-line generator** — root + fifth pattern following chord symbols
16. **Rasgueo / vihuela chord grid** — slash notation on a dedicated rhythm staff

### Phase 5 — Production Polish
17. **Native file format** (JSON or SQLite serialization of Score for round-trip save/load)
18. **PDF/Print export** — render each system to a QPrinter
19. **MIDI import** — finish transcription module
20. **Mariachi song database** — curated chord-chart library
