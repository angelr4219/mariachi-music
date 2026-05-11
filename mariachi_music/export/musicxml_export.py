"""MusicXML 3.1 exporter for Score objects.

Produces score-partwise XML compatible with MuseScore, Finale, Sibelius,
and any MusicXML-compliant application.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from mariachi_music.core.duration import DIVISIONS_PER_QUARTER
from mariachi_music.core.instrument import Instrument
from mariachi_music.core.measure import Measure
from mariachi_music.core.note import Note, Rest
from mariachi_music.core.score import Score


# MusicXML clef parameters
_CLEF_PARAMS: dict[str, tuple[str, str]] = {
    "treble": ("G", "2"),
    "bass":   ("F", "4"),
    "alto":   ("C", "3"),
    "tenor":  ("C", "4"),
}


def _sub(parent: ET.Element, tag: str, text: str = "", **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, attrib=attrs)
    if text:
        el.text = text
    return el


def _instrument_xml_id(instrument: Instrument, index: int) -> str:
    return f"P{index + 1}"


def _build_part_list(root: ET.Element, score: Score) -> None:
    part_list = _sub(root, "part-list")
    for i, part in enumerate(score.parts):
        pid = _instrument_xml_id(part.instrument, i)
        sp = _sub(part_list, "score-part", id=pid)
        _sub(sp, "part-name", part.instrument.name)
        _sub(sp, "part-abbreviation", part.instrument.abbreviation or part.instrument.name[:4])
        si = _sub(sp, "score-instrument", id=f"{pid}-I1")
        _sub(si, "instrument-name", part.instrument.name)
        midi_inst = _sub(sp, "midi-instrument", id=f"{pid}-I1")
        _sub(midi_inst, "midi-channel", str(i + 1))
        _sub(midi_inst, "midi-program", str(part.instrument.midi_program + 1))
        _sub(midi_inst, "volume", "78.7402")
        _sub(midi_inst, "pan", "0")


def _build_note_element(parent: ET.Element, event: Note | Rest, divisions: int) -> None:
    note_el = _sub(parent, "note")
    if isinstance(event, Rest):
        _sub(note_el, "rest")
    else:
        pitch_el = _sub(note_el, "pitch")
        _sub(pitch_el, "step", event.pitch.name)
        if event.pitch.accidental in ("#", "##", "b", "bb"):
            semitones = {"#": 1, "##": 2, "b": -1, "bb": -2}[event.pitch.accidental]
            _sub(pitch_el, "alter", str(semitones))
        _sub(pitch_el, "octave", str(event.pitch.octave))
    _sub(note_el, "duration", str(event.duration.divisions))
    if isinstance(event, Note):
        _sub(note_el, "voice", "1")
    _sub(note_el, "type", event.duration.xml_type)
    if event.duration.is_dotted:
        _sub(note_el, "dot")
    if isinstance(event, Note) and event.tie_start:
        _sub(note_el, "tie", type="start")
    if isinstance(event, Note) and event.tie_end:
        _sub(note_el, "tie", type="stop")
    if isinstance(event, Note):
        notations = None
        if event.tie_start or event.tie_end:
            notations = _sub(note_el, "notations")
            if event.tie_end:
                _sub(notations, "tied", type="stop")
            if event.tie_start:
                _sub(notations, "tied", type="start")


def _build_measure(
    part_el: ET.Element,
    measure: Measure,
    score: Score,
    instrument: Instrument,
    is_first: bool,
) -> None:
    m_el = _sub(part_el, "measure", number=str(measure.number))

    # Attributes block (printed on first measure, or when they change)
    if is_first:
        attrs = _sub(m_el, "attributes")
        _sub(attrs, "divisions", str(DIVISIONS_PER_QUARTER))

        ks = _sub(attrs, "key")
        _sub(ks, "fifths", str(score.key_signature.fifths))
        _sub(ks, "mode", score.key_signature.xml_mode)

        ts = _sub(attrs, "time")
        _sub(ts, "beats", str(measure.time_signature.beats_per_measure))
        _sub(ts, "beat-type", str(measure.time_signature.beat_unit))

        clef_sign, clef_line = _CLEF_PARAMS.get(instrument.clef, ("G", "2"))
        clef = _sub(attrs, "clef")
        _sub(clef, "sign", clef_sign)
        _sub(clef, "line", clef_line)

        # Tempo direction
        direction = _sub(m_el, "direction", placement="above")
        dt = _sub(direction, "direction-type")
        mm = _sub(dt, "metronome", parentheses="no")
        _sub(mm, "beat-unit", "quarter")
        _sub(mm, "per-minute", str(int(score.tempo.bpm)))
        _sub(direction, "sound", tempo=str(int(score.tempo.bpm)))

    for event in measure.events:
        _build_note_element(m_el, event, DIVISIONS_PER_QUARTER)


def export_score_musicxml(score: Score, path: Path) -> Path:
    """Export a Score to a MusicXML file.

    Args:
        score: The Score to export.
        path:  Output file path (should end in .musicxml or .xml).

    Returns:
        The path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element(
        "score-partwise",
        attrib={"version": "3.1"},
    )

    # Score-level metadata
    work = _sub(root, "work")
    _sub(work, "work-title", score.title)

    identification = _sub(root, "identification")
    encoding = _sub(identification, "encoding")
    _sub(encoding, "software", "Mariachi Music v0.1")
    _sub(encoding, "supports", element="accidental", type="yes")
    _sub(encoding, "supports", element="beam", type="yes")
    _sub(encoding, "supports", element="print", attribute="new-system", type="yes", value="yes")
    _sub(encoding, "supports", element="print", attribute="new-page", type="yes", value="yes")

    if score.composer:
        credit = _sub(root, "credit", page="1")
        _sub(credit, "credit-words", score.composer,
             attrib={"default-x": "595", "default-y": "45",
                     "justify": "center", "valign": "bottom"})

    _build_part_list(root, score)

    for i, part in enumerate(score.parts):
        pid = _instrument_xml_id(part.instrument, i)
        part_el = _sub(root, "part", id=pid)
        measures = part.measures
        for j, measure in enumerate(measures):
            _build_measure(part_el, measure, score, part.instrument, is_first=(j == 0))

    # Pretty-print with minidom
    rough = ET.tostring(root, encoding="unicode")
    reparsed = minidom.parseString(rough)
    pretty = reparsed.toprettyxml(indent="  ", encoding="UTF-8")

    # Insert DOCTYPE declaration after the XML declaration
    declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    doctype = b'<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"\n  "http://www.musicxml.org/dtds/partwise.dtd">\n'
    body = b"\n".join(pretty.split(b"\n")[1:])  # strip minidom's own declaration
    output = declaration + doctype + body

    path.write_bytes(output)
    return path
