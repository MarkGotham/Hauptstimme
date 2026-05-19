"""
NAME
===============================
Build pitch db (build_pitch_db.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Crawl the corpus and write a SQLite database of pitch events
flexible enough to be suitable for various aggregation tasks downstream.

Corpus structure assumed:
    <CORPUS_ROOT>/<Composer>/<Set>/<Movement>/<score_file>.mxl

e.g.
    .../Beethoven,_Ludwig_van/Symphony_No.1,_Op.21/1/Beethoven_Op.21_1.mxl


DESIGN:
===============================

Keep raw events canonical; treat aggregations as reproducible derivatives.

... and the inevitable case of what might be considered an exception:
 Although pitch class is a simplest derivative,
 it's not really an aggregation so much as a re-encoding of a single field.
 Unlike a count or a mean, it doesn't collapse rows (still one value per note).
 The cost of computing `midi_pitch % 12` is negligible at insert time,
 and having it as an indexed column makes GROUP BY pitch_class and WHERE pitch_class = ? queries
 both faster and more readable than computing `midi_pitch % 12` everywhere in the notebook SQL.


USAGE:
===============================
    python build_pitch_db.py [options]

Options:
    --corpus
    --db
    --rebuild

Dependencies:
    pip install amads

"""

import argparse
import logging
import sqlite3
from pathlib import Path

# AMADS imports 
from amads.core.basics import Note, Score, Part
from amads.instruments import instrument_classification
from amads.io.readscore import read_score, set_reader_warning_level

set_reader_warning_level("none")


# Defaults
DEFAULT_CORPUS = Path("../data/")
DEFAULT_DB     = Path("../data/pitch_events.db")


# Database setup 
DDL = """
CREATE TABLE IF NOT EXISTS pitch_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    composer       TEXT    NOT NULL,
    work_set       TEXT    NOT NULL,   -- e.g. "Symphony_No.1,_Op.21"
    movement       TEXT    NOT NULL,   -- e.g. "1"
    work_id        TEXT    NOT NULL,   -- composer|work_set|movement
    canonical_name TEXT    NOT NULL,   -- e.g. "Flute"
    part_number    INTEGER NOT NULL DEFAULT 1,
    family         TEXT,               -- e.g. "Woodwind"
    midi_pitch     INTEGER NOT NULL,   -- 0-127
    pitch_class    INTEGER NOT NULL,   -- 0-11  (midi_pitch % 12)
    duration       REAL                -- in quarter-note beats
);

CREATE INDEX IF NOT EXISTS idx_work      ON pitch_events (work_id);
CREATE INDEX IF NOT EXISTS idx_instr     ON pitch_events (canonical_name, part_number);
CREATE INDEX IF NOT EXISTS idx_pitch     ON pitch_events (midi_pitch);
CREATE INDEX IF NOT EXISTS idx_pc        ON pitch_events (pitch_class);
CREATE INDEX IF NOT EXISTS idx_family    ON pitch_events (family);
"""


def init_db(db_path: Path, rebuild: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    if rebuild:
        conn.execute("DROP TABLE IF EXISTS pitch_events")
        logging.info("Dropped existing pitch_events table.")
    conn.executescript(DDL)
    conn.commit()
    return conn


def extract_events_from_score(score_path: Path) -> list[dict]:
    """
    Parse one .mxl file and return a list of event dicts.

    Iterates over parts,
    normalises a canonical form of that instrument name with AMADS,
    then iterates over notes.
    """
    try:
        score: Score = read_score(str(score_path))
    except Exception as exc:
        logging.error(f"Failed to parse {score_path.name}: {exc}")
        return []

    events = []

    parts = score.find_all(Part)

    reg = instrument_classification.InstrumentRegistry()

    for part in parts:

        # Normalise instrument name once per part
        raw_part_name: str = part.instrument
        if raw_part_name is None:
            logging.error(f"... Failed to parse a part name in {score_path.name}")
            continue

        i = reg.parse(raw_part_name)
        family = i.family
        if family not in ["Woodwind", "Strings", "Brass"]:
            continue

        # Iterate notes in this part
        notes: list[Note] = part.list_all(Note)

        for note in notes:
            try:
                midi_pitch = note.pitch.key_num
            except AttributeError:
                logging.warning(f"Note missing `key_num` in {raw_part_name}, skipping.")
                continue

            part_num = 1
            if i.index:
                part_num = i.index

            events.append(
                {
                    "canonical_name": i.canonical,
                    "part_number":    part_num,
                    "family":         i.family,
                    "midi_pitch":     midi_pitch,
                    "pitch_class":    midi_pitch % 12,
                    "duration":       note.duration,
                }
            )

    return events


def iter_scores(corpus_root: Path):
    """
    Find all .mxl files under corpus_root via rglob
    (exclude melody scores ending `_melody`),
    deduce structure from the number of path parts relative to corpus_root:

    Depth is
    either 3 (movement = None): composer / work / score.mxl
    or 4 (with movement given): composer / work / movement / score.mxl

    Create (composer, work_set, movement, score_path) tuples from this information,
    with movement (correctly) assigned as `None` in the few cases of single-movement works.
    """
    for score_path in sorted(corpus_root.rglob("*.mxl")):
        if score_path.stem.endswith("_melody"):
            continue

        # Parts of the path relative to corpus_root, excluding the filename itself
        rel_parts = score_path.relative_to(corpus_root).parts[:-1]
        depth = len(rel_parts)

        if depth < 2:
            logging.warning(f"An .mxl file found at too shallow a level: {score_path}")
            continue

        composer = rel_parts[0]
        work_set = rel_parts[1]
        movement = rel_parts[2] if depth >= 3 else None

        yield composer, work_set, movement, score_path


def main():

    parser = argparse.ArgumentParser(description="Build pitch events SQLite DB from corpus.")
    parser.add_argument("--corpus",  type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--db",      type=Path, default=DEFAULT_DB)
    parser.add_argument("--rebuild", action="store_true",
                        help="Drop and recreate the pitch_events table before processing.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    INSERT_SQL = """
        INSERT INTO pitch_events
            (composer, work_set, movement, work_id,
             canonical_name, part_number, family,
             midi_pitch, pitch_class, duration)
        VALUES
            (:composer, :work_set, :movement, :work_id,
             :canonical_name, :part_number, :family,
             :midi_pitch, :pitch_class, :duration)
    """

    with sqlite3.connect(args.db) as conn:
        if args.rebuild:
            conn.execute("DROP TABLE IF EXISTS pitch_events")
        conn.executescript(DDL)

        cursor = conn.cursor()

        total_events = 0

        for composer, work_set, movement, score_path in iter_scores(args.corpus):

            work_id = f"{composer}|{work_set}|{movement}"
            logging.info(f"Processing: {work_id}  [{score_path.name}]")

            events = extract_events_from_score(score_path)

            if not events:
                logging.warning(f"  No events extracted from {score_path} — skipping.")
                continue

            # Attach provenance to each event
            for ev in events:
                ev.update({
                    "composer": composer,
                    "work_set": work_set,
                    "movement": movement,
                    "work_id":  work_id,
                })

            cursor.executemany(INSERT_SQL, events)
            conn.commit()

            logging.info(f"  → {len(events)} events written.")
            total_events += len(events)

    logging.info(f"\nDone. Total events: {total_events:,}  →  {args.db}")


if __name__ == "__main__":
    main()
