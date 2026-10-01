"""
annotate.py
===========

Interactive annotation tool for the Trilingual Readability Assessment System
(English / Russian / Kazakh).

Loads sentences from ``data/raw/{lang}/sample_sentences.txt``, prompts two
human raters to independently rate each on a 1–5 scale (decimals allowed),
and writes results to
``data/processed/annotations.csv``.

Usage
-----
    python annotate.py

Python: 3.9+
"""

from __future__ import annotations

import csv
import os
import statistics
import sys
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LANGUAGES: List[Tuple[str, str]] = [
    ("en", "English"),
    ("ru", "Russian"),
    ("kk", "Kazakh"),
]

RAW_DATA_DIR: str = "data/raw/test/"
OUTPUT_PATH: str = "data/processed/test_annotations.csv"
CSV_FIELDNAMES: List[str] = [
    "sentence_id",
    "lang",
    "sentence_text",
    "rater_1",
    "rater_2",
    "mean_rating",
    "notes",
]

RATING_MIN: float = 1.0
RATING_MAX: float = 5.0

RATING_SCALE: List[Tuple[float, str, str]] = [
    (5, "Very Easy",      "child's book level"),
    (4, "Easy",           "news headline"),
    (3, "Moderate",       "textbook article"),
    (2, "Difficult",      "academic paper"),
    (1, "Very Difficult", "legal jargon"),
]

BORDER: str = "═" * 64


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------

def load_sentences(lang: str) -> List[str]:
    """Load and return non-empty sentences for one language.

    Reads ``data/raw/{lang}/sample_sentences.txt``, strips whitespace from
    each line, and drops blank lines. If the file is missing or unreadable,
    a warning is printed to stderr and an empty list is returned so the other
    languages can still be processed.

    Parameters
    ----------
    lang : str
        Language code (``"en"``, ``"ru"``, or ``"kk"``).

    Returns
    -------
    List[str]
        Stripped, non-empty sentence strings in file order.
    """
    path = os.path.join(RAW_DATA_DIR, lang, "sample_sentences.txt")
    if not os.path.isfile(path):
        print(f"[WARN] File not found: {path} — skipping {lang}.", file=sys.stderr)
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        return [line.strip() for line in lines if line.strip()]
    except OSError as exc:
        print(f"[WARN] Could not read {path}: {exc} — skipping {lang}.", file=sys.stderr)
        return []


def build_sentence_list() -> List[Dict]:
    """Build the flat list of sentences to annotate across all languages.

    Returns
    -------
    List[Dict]
        Each dict has keys: ``sentence_id`` (str), ``lang`` (str),
        ``lang_name`` (str), ``sentence_text`` (str), ``lang_index`` (int).
        Languages appear in the order defined by ``LANGUAGES``.
    """
    items: List[Dict] = []
    for lang, lang_name in LANGUAGES:
        sentences = load_sentences(lang)
        for i, text in enumerate(sentences, start=1):
            items.append(
                {
                    "sentence_id": f"{lang}_{i:03d}",
                    "lang": lang,
                    "lang_name": lang_name,
                    "sentence_text": text,
                    "lang_index": i,
                }
            )
    return items


# ---------------------------------------------------------------------------
# 2. User interaction helpers
# ---------------------------------------------------------------------------

def print_header(total: int) -> None:
    """Print the welcome banner and rating-scale legend.

    Parameters
    ----------
    total : int
        Total number of sentences to annotate (shown in the preamble).
    """
    print(f"\n{BORDER}")
    print("TRILINGUAL READABILITY ANNOTATION TOOL")
    print(BORDER)
    print("\nRate each sentence on a 1–5 scale:\n")
    for value, label, description in RATING_SCALE:
        print(f"  {value} = {label:<15} ({description})")
    print(f"\nTwo raters will each rate {total} sentences independently.")
    print("Rater 2 will not be shown Rater 1's scores.\n")
    input("Press Enter to start...")
    print()


def prompt_rating(rater_label: str) -> Optional[float]:
    """Prompt the user for a rating and validate the input.

    Parameters
    ----------
    rater_label : str
        Label shown in the prompt, e.g. ``"Rater 1"``.

    Returns
    -------
    float
        A validated rating in [``RATING_MIN``, ``RATING_MAX``].
    None
        If the user chose to skip (entered ``'s'``).
    """
    while True:
        raw = input(
            f"  {rater_label} rating ({RATING_MIN:.0f}–{RATING_MAX:.0f}, decimals OK, 's' to skip): "
        ).strip()
        if raw.lower() == "s":
            return None
        try:
            value = float(raw)
        except ValueError:
            print("  ❌  Not a number. Try again (e.g. 3, 3.5, 4.2).")
            continue
        if not (RATING_MIN <= value <= RATING_MAX):
            print(
                f"  ❌  Out of range. Enter a value between "
                f"{RATING_MIN} and {RATING_MAX}."
            )
            continue
        return value


def prompt_notes() -> str:
    """Prompt the user for optional notes.

    Returns
    -------
    str
        The note text, or an empty string if the user pressed Enter without
        typing anything.
    """
    return input("  Notes (optional, press Enter to skip): ").strip()


def clear_screen() -> None:
    """Clear the console before handing the tool to the next rater."""
    os.system("cls" if os.name == "nt" else "clear")


def collect_ratings_for_rater(
    items: List[Dict],
    rater_label: str,
    total_raters: int,
) -> Dict[str, float]:
    """Collect one independent pass of ratings.

    Scores from earlier raters are not printed here, so the next rater sees
    only the sentence text and rating scale.
    """
    total = len(items)
    ratings: Dict[str, float] = {}

    print(f"\n{BORDER}")
    print(f"{rater_label.upper()} ANNOTATION PASS ({total_raters} total raters)")
    print(BORDER)
    print("Use 's' to skip a sentence. A sentence is saved only if both raters rate it.\n")

    for global_idx, item in enumerate(items, start=1):
        lang_name = item["lang_name"]
        lang_index = item["lang_index"]

        print(f"[{global_idx}/{total}] {lang_name} (#{lang_index})\n")
        print(f"  {item['sentence_text']}\n")

        rating = prompt_rating(rater_label)
        if rating is None:
            print("  ⊘  Skipped by this rater.\n")
            continue

        ratings[item["sentence_id"]] = rating
        print("\n  ✓  Recorded.\n")

    return ratings


# ---------------------------------------------------------------------------
# 3. Annotation loop
# ---------------------------------------------------------------------------

def annotate(items: List[Dict]) -> List[Dict]:
    """Run the interactive annotation loop over all sentences.

    Parameters
    ----------
    items : List[Dict]
        Sentence records from ``build_sentence_list()``.

    Returns
    -------
    List[Dict]
        Completed annotation records with keys matching ``CSV_FIELDNAMES``.
        Sentences skipped by either rater are omitted from the result.
    """
    annotations: List[Dict] = []

    rater_1 = collect_ratings_for_rater(items, "Rater 1", total_raters=2)

    input(
        "Rater 1 pass complete. Press Enter, then hand the keyboard to Rater 2..."
    )
    clear_screen()

    rater_2 = collect_ratings_for_rater(items, "Rater 2", total_raters=2)

    print(f"\n{BORDER}")
    print("OPTIONAL NOTES")
    print(BORDER)
    print("Notes are collected only for sentences rated by both raters.\n")

    for item in items:
        sentence_id = item["sentence_id"]
        if sentence_id not in rater_1 or sentence_id not in rater_2:
            continue

        print(f"{item['lang_name']} (#{item['lang_index']})\n")
        print(f"  {item['sentence_text']}\n")
        notes = prompt_notes()
        mean_rating = (rater_1[sentence_id] + rater_2[sentence_id]) / 2.0
        print()

        annotations.append(
            {
                "sentence_id": sentence_id,
                "lang": item["lang"],
                "sentence_text": item["sentence_text"],
                "rater_1": rater_1[sentence_id],
                "rater_2": rater_2[sentence_id],
                "mean_rating": mean_rating,
                "notes": notes,
            }
        )

    return annotations


# ---------------------------------------------------------------------------
# 4. Summary printing
# ---------------------------------------------------------------------------

def print_summary(annotations: List[Dict], total: int) -> None:
    """Print a per-language summary of collected ratings.

    Parameters
    ----------
    annotations : List[Dict]
        Completed annotation records.
    total : int
        Total sentences offered for annotation (for the header count).
    """
    print(f"\n{BORDER}")
    print("ANNOTATION SUMMARY")
    print(BORDER)
    print(f"\nTotal annotated: {len(annotations)}/{total}\n")

    by_lang: Dict[str, List[float]] = {lang: [] for lang, _ in LANGUAGES}
    for ann in annotations:
        by_lang[ann["lang"]].append(float(ann["mean_rating"]))

    all_ratings: List[float] = []
    for lang, lang_name in LANGUAGES:
        ratings = by_lang[lang]
        if not ratings:
            continue
        avg = statistics.mean(ratings)
        all_ratings.extend(ratings)
        count = len(ratings)
        print(f"  {lang_name} ({count} sentence{'s' if count != 1 else ''})")
        print(f"    Mean ratings : {[round(r, 2) for r in ratings]}")
        print(f"    Average mean : {avg:.2f}\n")

    if all_ratings:
        print(f"  Overall average: {statistics.mean(all_ratings):.2f}")

    print(f"\n{BORDER}\n")


# ---------------------------------------------------------------------------
# 5. CSV output
# ---------------------------------------------------------------------------

def save_annotations(
    annotations: List[Dict],
    output_path: str = OUTPUT_PATH,
) -> None:
    """Write annotation records to a UTF-8 CSV file.

    Creates the output directory if it does not already exist. Uses Unix
    line endings (``newline=""`` + ``lineterminator="\\n"``).

    Parameters
    ----------
    annotations : List[Dict]
        Records to write; each must contain the keys in ``CSV_FIELDNAMES``.
    output_path : str
        Destination file path. Defaults to ``OUTPUT_PATH``.

    Raises
    ------
    OSError
        If the file cannot be opened for writing (permission error, disk
        full, etc.). The caller handles this.
    """
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=CSV_FIELDNAMES,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(annotations)

    count = len(annotations)
    print(
        f"✅  Saved {count} annotation{'s' if count != 1 else ''} to {output_path}"
    )


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point: load sentences, annotate, summarise, save."""
    items = build_sentence_list()

    if not items:
        print(
            "[ERROR] No sentences found. "
            f"Check that {RAW_DATA_DIR}/{{en,ru,kk}}/sample_sentences.txt exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    print_header(total=len(items))

    try:
        annotations = annotate(items)
    except KeyboardInterrupt:
        print("\n\n⚠️   Interrupted — no annotations saved.")
        sys.exit(0)

    if not annotations:
        print("No annotations to save.")
        return

    print_summary(annotations, total=len(items))

    try:
        save_annotations(annotations)
    except OSError as exc:
        print(f"[ERROR] Could not write to {OUTPUT_PATH}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
