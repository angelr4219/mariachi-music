from pathlib import Path

from mariachi_music.mariachi import (
    MariachiSongRequest,
    classify_features,
    generate_mariachi_arrangement,
)


def test_ranchera_restaurant_full_generates_section_map_and_score():
    result = generate_mariachi_arrangement(MariachiSongRequest(
        genre="ranchera",
        context="restaurant",
        key="G",
        tempo=132,
        length="full",
    ))

    assert result.score.key_signature.root == "G"
    assert str(result.score.time_signature) == "3/4"
    assert [part.instrument.name for part in result.score.parts][:3] == ["Guitarrón", "Vihuela", "Guitar"]
    assert result.sections[0].label == "A"
    assert result.sections[-1].label == "C''"
    assert result.section_map()["template"]["intro_rule"].startswith("intro often states")


def test_cantina_son_auto_uses_short_context_form():
    result = generate_mariachi_arrangement(MariachiSongRequest(
        genre="son",
        context="cantina",
        key="D",
        length="auto",
    ))

    assert result.template.genre == "son"
    assert str(result.score.time_signature) == "6/8"
    assert [section.label for section in result.sections] == ["A", "A'", "B", "A''"]
    assert len(result.score.parts) == 4


def test_bolero_intro_rule_and_exports(tmp_path: Path):
    result = generate_mariachi_arrangement(MariachiSongRequest(
        genre="bolero",
        context="restaurant",
        key="C",
        length="short",
        ensemble=("Guitarrón", "Vihuela", "Violin"),
    ))

    xml_path = result.score.export_musicxml(tmp_path / "bolero.musicxml")
    mid_path = result.score.export_midi(tmp_path / "bolero.mid")
    map_path = result.write_section_map(tmp_path / "bolero.sections.json")

    assert "independent" in result.template.intro_rule
    assert xml_path.exists()
    assert mid_path.exists()
    assert '"genre": "bolero"' in map_path.read_text()


def test_classifier_feature_rules():
    son = classify_features(tempo_bpm=140, meter_hint="6/8")
    bolero = classify_features(tempo_bpm=72, meter_hint="4/4")
    ranchera = classify_features(tempo_bpm=128, meter_hint="3/4")

    assert son.genre == "son"
    assert bolero.genre == "bolero"
    assert ranchera.genre == "ranchera"
    assert son.confidence > 0.5
