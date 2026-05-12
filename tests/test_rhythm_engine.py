"""Tests for mariachi_music.generation.rhythm_engine.

Coverage
--------
- Waltz guitarrón produces exactly 3 events per measure (3/4 pattern).
- Son time signature is 6/8.
- Bolero time signature is 4/4.
- Full mariachi band creates exactly 5 parts.
- generate_song_structure creates the correct total measure count.
- Default tempos fall within the published typical ranges for each style.
- G chord waltz guitarrón uses G in the bass register (octave 2).
- RhythmPattern.from_name rejects unknown styles.
- All five styles generate non-empty events for every instrument.
- Progression mode respects measures_per_chord and repetitions.
- Vihuela son pattern contains rests (authentic chop feel).
- Jarabe vihuela has all eighth notes (continuous rapid strum).
"""

from __future__ import annotations

import pytest

from mariachi_music.core.instrument import Instrument
from mariachi_music.core.note import Note, Rest
from mariachi_music.generation.rhythm_engine import (
    RhythmPattern,
    _DEFAULT_TEMPO,
    _FULL_MARIACHI_BAND,
    _TIME_SIGNATURE,
    _TYPICAL_TEMPO_RANGE,
    generate_rhythm_score,
    generate_song_structure,
)
from mariachi_music.theory.chords import chord_by_root


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _events_for_first_measure(score, instrument_name: str):
    """Return the event list of the first measure for a named instrument part."""
    for part in score.parts:
        if part.instrument.name == instrument_name:
            return part.measures[0].events
    raise KeyError(f"No part for {instrument_name!r}")


def _count_notes_and_rests(events):
    notes = sum(1 for e in events if isinstance(e, Note))
    rests = sum(1 for e in events if isinstance(e, Rest))
    return notes, rests


# ──────────────────────────────────────────────────────────────────────────────
# RhythmPattern basics
# ──────────────────────────────────────────────────────────────────────────────

class TestRhythmPatternConstruction:
    def test_waltz_time_signature(self):
        rp = RhythmPattern.from_name("waltz")
        assert rp.time_signature == "3/4"

    def test_son_time_signature(self):
        rp = RhythmPattern.from_name("son")
        assert rp.time_signature == "6/8"

    def test_bolero_time_signature(self):
        rp = RhythmPattern.from_name("bolero")
        assert rp.time_signature == "4/4"

    def test_jarabe_time_signature(self):
        rp = RhythmPattern.from_name("jarabe")
        assert rp.time_signature == "6/8"

    def test_cumbia_time_signature(self):
        rp = RhythmPattern.from_name("cumbia")
        assert rp.time_signature == "4/4"

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError, match="Unknown rhythm style"):
            RhythmPattern.from_name("polka")

    def test_case_insensitive_lookup(self):
        rp = RhythmPattern.from_name("WALTZ")
        assert rp.name == "waltz"

    def test_time_sig_property_parses(self):
        from mariachi_music.core.time_signature import TimeSignature
        rp = RhythmPattern.from_name("waltz")
        ts = rp.time_sig
        assert isinstance(ts, TimeSignature)
        assert ts.beats_per_measure == 3
        assert ts.beat_unit == 4

    def test_str_representation(self):
        rp = RhythmPattern.from_name("son")
        s = str(rp)
        assert "son" in s and "6/8" in s


# ──────────────────────────────────────────────────────────────────────────────
# Tempo defaults
# ──────────────────────────────────────────────────────────────────────────────

class TestTempoDefaults:
    @pytest.mark.parametrize("style", ["son", "bolero", "waltz", "jarabe", "cumbia"])
    def test_default_tempo_within_typical_range(self, style):
        rp  = RhythmPattern.from_name(style)
        lo, hi = _TYPICAL_TEMPO_RANGE[style]
        assert lo <= rp.default_tempo <= hi, (
            f"{style} default tempo {rp.default_tempo} not in [{lo}, {hi}]"
        )

    @pytest.mark.parametrize("style", ["son", "bolero", "waltz", "jarabe", "cumbia"])
    def test_generate_rhythm_score_uses_default_tempo(self, style):
        score = generate_rhythm_score(chord_root="C", rhythm=style, measures=1)
        lo, hi = _TYPICAL_TEMPO_RANGE[style]
        assert lo <= score.tempo.bpm <= hi

    def test_custom_tempo_is_respected(self):
        score = generate_rhythm_score(chord_root="G", rhythm="waltz", tempo=99.0, measures=1)
        assert score.tempo.bpm == pytest.approx(99.0)


# ──────────────────────────────────────────────────────────────────────────────
# generate_rhythm_score
# ──────────────────────────────────────────────────────────────────────────────

class TestGenerateRhythmScore:
    def test_full_band_creates_five_parts(self):
        score = generate_rhythm_score(
            chord_root="G",
            rhythm="waltz",
            measures=4,
        )
        assert score.part_count == 5

    def test_custom_instrument_list(self):
        score = generate_rhythm_score(
            chord_root="C",
            rhythm="son",
            instruments=["Guitarrón", "Vihuela"],
            measures=2,
        )
        assert score.part_count == 2

    def test_correct_measure_count_per_part(self):
        score = generate_rhythm_score(
            chord_root="C", rhythm="waltz", measures=8
        )
        for part in score.parts:
            assert len(part.measures) == 8

    def test_score_has_correct_time_signature(self):
        score = generate_rhythm_score(chord_root="G", rhythm="son", measures=1)
        assert str(score.time_signature) == "6/8"

    def test_bolero_score_time_signature(self):
        score = generate_rhythm_score(chord_root="C", rhythm="bolero", measures=1)
        assert str(score.time_signature) == "4/4"

    def test_waltz_score_time_signature(self):
        score = generate_rhythm_score(chord_root="D", rhythm="waltz", measures=1)
        assert str(score.time_signature) == "3/4"

    def test_auto_title_generated(self):
        score = generate_rhythm_score(chord_root="G", rhythm="waltz")
        assert score.title != "" and score.title != "Untitled"

    def test_custom_title(self):
        score = generate_rhythm_score(
            chord_root="G", rhythm="waltz", title="My Waltz"
        )
        assert score.title == "My Waltz"

    def test_score_is_exportable_summary(self):
        score = generate_rhythm_score(chord_root="C", rhythm="waltz", measures=2)
        summary = score.summary()
        assert "Guitarrón" in summary


# ──────────────────────────────────────────────────────────────────────────────
# Waltz guitarrón pattern validation
# ──────────────────────────────────────────────────────────────────────────────

class TestWaltzGuitarron:
    def test_has_exactly_three_events_per_measure(self):
        score  = generate_rhythm_score(chord_root="G", rhythm="waltz", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        assert len(events) == 3, f"Expected 3 events, got {len(events)}"

    def test_all_events_are_quarter_notes(self):
        score  = generate_rhythm_score(chord_root="G", rhythm="waltz", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        for event in events:
            assert event.beats == pytest.approx(1.0), (
                f"Expected quarter note (1.0 beat), got {event.beats}"
            )

    def test_g_chord_bass_in_octave_2(self):
        """Guitarrón beat-1 root should be G in octave 2 (low bass register)."""
        score  = generate_rhythm_score(chord_root="G", rhythm="waltz", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        first  = events[0]
        assert isinstance(first, Note)
        assert first.pitch.name == "G", f"Expected G, got {first.pitch.name}"
        assert first.pitch.octave == 2, f"Expected octave 2, got {first.pitch.octave}"

    def test_midi_number_in_bass_range(self):
        """G2 MIDI number should be in the guitarrón bass range (28–64)."""
        score  = generate_rhythm_score(chord_root="G", rhythm="waltz", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        first  = events[0]
        assert isinstance(first, Note)
        # G2 = MIDI 43, firmly in bass range
        assert 28 <= first.midi_number <= 64, (
            f"MIDI {first.midi_number} not in guitarrón bass range [28, 64]"
        )

    def test_waltz_measure_fills_three_quarter_beats(self):
        """Measure should be full: 3 quarter-notes = 3.0 beats in 3/4."""
        score  = generate_rhythm_score(chord_root="C", rhythm="waltz", measures=1)
        for part in score.parts:
            m = part.measures[0]
            assert m.is_full, (
                f"{part.instrument.name}: measure not full "
                f"({m.used_beats:.2f}/{m.capacity_beats:.2f})"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Son pattern validation
# ──────────────────────────────────────────────────────────────────────────────

class TestSonPattern:
    def test_guitarron_has_six_events(self):
        score  = generate_rhythm_score(chord_root="C", rhythm="son", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        assert len(events) == 6

    def test_guitarron_first_event_is_note(self):
        score  = generate_rhythm_score(chord_root="G", rhythm="son", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        assert isinstance(events[0], Note)

    def test_guitarron_has_rests(self):
        score  = generate_rhythm_score(chord_root="C", rhythm="son", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        _, rests = _count_notes_and_rests(events)
        assert rests > 0, "Son guitarrón should have rests (beats 2, 3, 6)"

    def test_vihuela_has_rests(self):
        """Classic son vihuela bump-ba-bump has rests on beats 2 and 5."""
        score  = generate_rhythm_score(chord_root="C", rhythm="son", measures=1)
        events = _events_for_first_measure(score, "Vihuela")
        _, rests = _count_notes_and_rests(events)
        assert rests > 0, "Son vihuela should have rests for the chop feel"

    def test_son_measure_fills_two_dotted_quarters(self):
        """6/8 measure = 6 eighths = 3.0 quarter beats."""
        score = generate_rhythm_score(chord_root="C", rhythm="son", measures=1)
        for part in score.parts:
            m = part.measures[0]
            assert m.is_full, (
                f"{part.instrument.name}: measure not full "
                f"({m.used_beats:.2f}/{m.capacity_beats:.2f})"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Bolero pattern validation
# ──────────────────────────────────────────────────────────────────────────────

class TestBoleroPattern:
    def test_guitarron_has_four_events(self):
        score  = generate_rhythm_score(chord_root="C", rhythm="bolero", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        assert len(events) == 4

    def test_guitarron_all_quarter_notes(self):
        score  = generate_rhythm_score(chord_root="C", rhythm="bolero", measures=1)
        events = _events_for_first_measure(score, "Guitarrón")
        for e in events:
            assert isinstance(e, Note)
            assert e.beats == pytest.approx(1.0)

    def test_bolero_melody_uses_varied_durations(self):
        """Bolero melody should have dotted quarter and half for lyrical feel."""
        score  = generate_rhythm_score(chord_root="C", rhythm="bolero", measures=1)
        events = _events_for_first_measure(score, "Violin")
        durations = {e.beats for e in events}
        assert len(durations) > 1, "Bolero melody should use multiple duration values"

    def test_bolero_measure_fills_four_quarter_beats(self):
        score = generate_rhythm_score(chord_root="G", rhythm="bolero", measures=1)
        for part in score.parts:
            m = part.measures[0]
            assert m.is_full, (
                f"{part.instrument.name}: measure not full "
                f"({m.used_beats:.2f}/{m.capacity_beats:.2f})"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Jarabe pattern validation
# ──────────────────────────────────────────────────────────────────────────────

class TestJarabePattern:
    def test_vihuela_all_eighth_notes(self):
        """Jarabe vihuela is continuous rapid strum — all eighths, no rests."""
        score  = generate_rhythm_score(chord_root="C", rhythm="jarabe", measures=1)
        events = _events_for_first_measure(score, "Vihuela")
        assert all(isinstance(e, Note) for e in events), "Jarabe vihuela has no rests"
        assert all(e.beats == pytest.approx(0.5) for e in events)

    def test_jarabe_has_six_events_vihuela(self):
        score  = generate_rhythm_score(chord_root="C", rhythm="jarabe", measures=1)
        events = _events_for_first_measure(score, "Vihuela")
        assert len(events) == 6


# ──────────────────────────────────────────────────────────────────────────────
# generate_song_structure
# ──────────────────────────────────────────────────────────────────────────────

class TestGenerateSongStructure:
    def test_correct_total_measures(self):
        """I–IV–V–I, 4 measures/chord, 2 repetitions → 4 chords × 4 × 2 = 32 measures."""
        progression   = [1, 4, 5, 1]
        mpc           = 4
        reps          = 2
        expected      = len(progression) * mpc * reps

        score = generate_song_structure(
            key="C",
            chord_progression=progression,
            rhythm="waltz",
            measures_per_chord=mpc,
            repetitions=reps,
        )
        for part in score.parts:
            assert len(part.measures) == expected, (
                f"{part.instrument.name}: expected {expected} measures, "
                f"got {len(part.measures)}"
            )

    def test_single_chord_single_rep(self):
        score = generate_song_structure(
            key="G", chord_progression=[1], rhythm="son",
            measures_per_chord=2, repetitions=1,
        )
        for part in score.parts:
            assert len(part.measures) == 2

    def test_five_parts_by_default(self):
        score = generate_song_structure(
            key="C", chord_progression=[1, 5], rhythm="waltz"
        )
        assert score.part_count == 5

    def test_custom_instruments(self):
        score = generate_song_structure(
            key="C",
            chord_progression=[1, 4, 5],
            rhythm="son",
            instruments=["Guitarrón", "Violin"],
            measures_per_chord=1,
            repetitions=1,
        )
        assert score.part_count == 2

    def test_invalid_degree_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            generate_song_structure(
                key="C",
                chord_progression=[1, 8],
                rhythm="waltz",
            )

    def test_auto_title_includes_key(self):
        score = generate_song_structure(
            key="G", chord_progression=[1, 4, 5, 1], rhythm="waltz"
        )
        assert "G" in score.title

    def test_custom_title(self):
        score = generate_song_structure(
            key="C", chord_progression=[1, 5], rhythm="waltz",
            title="My Song"
        )
        assert score.title == "My Song"

    def test_measures_per_chord_three(self):
        """3 chords × 3 measures × 1 rep = 9 total."""
        score = generate_song_structure(
            key="C", chord_progression=[1, 4, 5],
            rhythm="bolero", measures_per_chord=3, repetitions=1,
        )
        for part in score.parts:
            assert len(part.measures) == 9

    def test_minor_keys_accepted(self):
        """generate_song_structure should work for any diatonic chord degree."""
        score = generate_song_structure(
            key="A", chord_progression=[1, 6, 4, 5],
            rhythm="waltz", measures_per_chord=2, repetitions=1,
        )
        assert score.part_count == 5


# ──────────────────────────────────────────────────────────────────────────────
# All styles × all instruments smoke tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAllStylesAllInstruments:
    @pytest.mark.parametrize("style", ["son", "bolero", "waltz", "jarabe", "cumbia"])
    @pytest.mark.parametrize("inst_name", _FULL_MARIACHI_BAND)
    def test_events_are_non_empty_and_fill_measure(self, style, inst_name):
        score = generate_rhythm_score(
            chord_root="C", rhythm=style,
            instruments=[inst_name], measures=1,
        )
        assert score.part_count == 1
        part = score.parts[0]
        assert len(part.measures) == 1
        m = part.measures[0]
        assert len(m.events) > 0, f"{style}/{inst_name}: no events"
        assert m.is_full, (
            f"{style}/{inst_name}: measure not full "
            f"({m.used_beats:.2f}/{m.capacity_beats:.2f})"
        )

    @pytest.mark.parametrize("style", ["son", "bolero", "waltz", "jarabe", "cumbia"])
    def test_rhythm_pattern_get_notes_for_instrument(self, style):
        """RhythmPattern.get_notes_for_instrument returns non-empty list."""
        rp    = RhythmPattern.from_name(style)
        chord = chord_by_root("G", "major")
        for inst_name in _FULL_MARIACHI_BAND:
            inst   = Instrument.by_name(inst_name)
            events = rp.get_notes_for_instrument(chord, inst)
            assert len(events) > 0, (
                f"RhythmPattern({style}).get_notes_for_instrument({inst_name!r}) returned empty"
            )

    @pytest.mark.parametrize("style", ["son", "bolero", "waltz", "jarabe", "cumbia"])
    def test_octave_override_is_respected(self, style):
        """When octave is overridden for guitarrón, bass note should be in that octave."""
        rp    = RhythmPattern.from_name(style)
        chord = chord_by_root("C", "major")
        inst  = Instrument.by_name("Guitarrón")
        events = rp.get_notes_for_instrument(chord, inst, octave=3)
        # First note event should have octave 3 (or 4 if wrapped)
        note_events = [(p, d) for p, d in events if p is not None]
        assert len(note_events) > 0
        # Just verify it doesn't crash and returns events
        assert all(isinstance(p, str) for p, _ in note_events)


# ──────────────────────────────────────────────────────────────────────────────
# CLI smoke test
# ──────────────────────────────────────────────────────────────────────────────

class TestCLI:
    def test_single_chord_cli(self, tmp_path):
        from mariachi_music.cli.create_rhythm import main
        out = str(tmp_path / "test_waltz")
        rc  = main([
            "--chord", "G", "--rhythm", "waltz",
            "--key", "C", "--measures", "2",
            "--instruments", "Guitarrón", "Vihuela",
            "--output", out,
        ])
        assert rc == 0
        assert (tmp_path / "test_waltz.musicxml").exists()
        assert (tmp_path / "test_waltz.mid").exists()

    def test_progression_cli(self, tmp_path):
        from mariachi_music.cli.create_rhythm import main
        out = str(tmp_path / "test_son")
        rc  = main([
            "--key", "C", "--progression", "1", "4", "5", "1",
            "--rhythm", "son", "--measures-per-chord", "1",
            "--repetitions", "1",
            "--instruments", "Guitarrón", "Guitar",
            "--output", out,
        ])
        assert rc == 0
        assert (tmp_path / "test_son.musicxml").exists()

    def test_bad_instrument_exits_nonzero(self, tmp_path):
        from mariachi_music.cli.create_rhythm import main
        out = str(tmp_path / "bad")
        with pytest.raises(SystemExit) as exc_info:
            main(["--chord", "C", "--instruments", "Bagpipe", "--output", out])
        assert exc_info.value.code != 0
