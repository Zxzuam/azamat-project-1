import csv

from src import annotate as annotate_module


def test_annotate_stores_two_raters_and_mean(monkeypatch):
    items = [
        {
            "sentence_id": "en_001",
            "lang": "en",
            "lang_name": "English",
            "sentence_text": "A short sentence.",
            "lang_index": 1,
        },
        {
            "sentence_id": "en_002",
            "lang": "en",
            "lang_name": "English",
            "sentence_text": "Another short sentence.",
            "lang_index": 2,
        },
    ]

    rating_passes = [
        {"en_001": 4.0, "en_002": 3.0},
        {"en_001": 5.0},
    ]

    def fake_collect_ratings_for_rater(items, rater_label, total_raters):
        return rating_passes.pop(0)

    monkeypatch.setattr(
        annotate_module,
        "collect_ratings_for_rater",
        fake_collect_ratings_for_rater,
    )
    monkeypatch.setattr(annotate_module, "clear_screen", lambda: None)
    monkeypatch.setattr(annotate_module, "prompt_notes", lambda: "")
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    annotations = annotate_module.annotate(items)

    assert annotations == [
        {
            "sentence_id": "en_001",
            "lang": "en",
            "sentence_text": "A short sentence.",
            "rater_1": 4.0,
            "rater_2": 5.0,
            "mean_rating": 4.5,
            "notes": "",
        }
    ]


def test_save_annotations_writes_new_columns(tmp_path):
    output_path = tmp_path / "annotations.csv"
    annotations = [
        {
            "sentence_id": "en_001",
            "lang": "en",
            "sentence_text": "A short sentence.",
            "rater_1": 4.0,
            "rater_2": 5.0,
            "mean_rating": 4.5,
            "notes": "",
        }
    ]

    annotate_module.save_annotations(annotations, str(output_path))

    with output_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows == [
        {
            "sentence_id": "en_001",
            "lang": "en",
            "sentence_text": "A short sentence.",
            "rater_1": "4.0",
            "rater_2": "5.0",
            "mean_rating": "4.5",
            "notes": "",
        }
    ]
