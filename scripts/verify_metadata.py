#!/usr/bin/env python3
"""
NAME
===============================
Verify Metadata (verify_metadata.py)


BY
===============================
Mark Gotham


LICENCE:
===============================
Code = MIT. See [README](https://github.com/MarkGotham/Hauptstimme/tree/main#licence).


ABOUT:
===============================
Verify the dataset's YAML metadata at the level of `sets`.

For each entry in sets.yaml, fetch the corresponding Wikidata entity and check:

  - Composer:  `composer_id` matches the work's P86 (composer) claim,
               and the `composer` name approximately matches the entity label.
  - Title:     `name` approximately matches the Wikidata entity's English label
               (or aliases). No dedicated property — the label itself is compared.
  - Date:      `date` is checked against Wikidata date properties in order:
               P577 (publication date),
               P1191 (date of first performance),
               P571 (inception).
               The first property with claims that overlaps
               the YAML year(s) counts as a pass.
               Clearly, this date data is indicative only.

Usage:
    python verify_sets.py [--yaml path/to/sets.yaml] [--ids 1 2 3] [--verbose]

Requirements:
    pip install requests pyyaml
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests
import yaml


# ---------------------------------------------------------------------------

# Config


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Hauptstimme dataset (local verification script)"
RATE_LIMIT_SECONDS = 1.5   # minimum gap between requests (Wikidata asks for ≥1 s)
RETRY_ATTEMPTS    = 4      # max retries on 429 / 5xx
RETRY_BACKOFF     = 5.0    # initial back-off on 429 (doubles each retry)

# Wikidata property IDs
P_COMPOSER          = "P86"
P_PUBLICATION       = "P577"
P_FIRST_PERFORMANCE = "P1191"
P_INCEPTION         = "P571"

# Approximate name-match threshold (0–1); lower = more lenient
NAME_MATCH_THRESHOLD = 0.6


# ---------------------------------------------------------------------------

# Helpers

def fetch_entity(qid: str, props: str = "claims|labels|aliases") -> dict:
    """
    Fetch a single Wikidata entity via the "wbgetentities" API.

    Sleeps `RATE_LIMIT_SECONDS` *before* every request, and retries up to
    `RETRY_ATTEMPTS` times with exponential back-off on HTTP 429 / 5xx.
    """
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "props": props,
        "languages": "en",
        "format": "json",
    }
    backoff = RETRY_BACKOFF
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        time.sleep(RATE_LIMIT_SECONDS)   # always wait before hitting the API
        try:
            resp = requests.get(
                WIKIDATA_API,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
        except requests.RequestException as exc:
            if attempt == RETRY_ATTEMPTS:
                raise
            print(f" [network error, retrying in {backoff:.0f}s: {exc}]")
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == RETRY_ATTEMPTS:
                resp.raise_for_status()
            retry_after = int(resp.headers.get("Retry-After", backoff))
            wait = max(retry_after, backoff)
            print(f"      [HTTP {resp.status_code} — waiting {wait:.0f}s before retry {attempt}/{RETRY_ATTEMPTS}]")
            time.sleep(wait)
            backoff *= 2
            continue

        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Wikidata API error for {qid}: {data['error']}")
        entities = data.get("entities", {})
        if qid not in entities:
            raise RuntimeError(f"Entity {qid} not found in API response")
        return entities[qid]

    raise RuntimeError(f"Failed to fetch {qid} after {RETRY_ATTEMPTS} attempts")


def en_label(entity: dict) -> str:
    """Return the English label of a Wikidata entity, or its QID."""
    return (
        entity.get("labels", {}).get("en", {}).get("value")
        or entity.get("id", "?")
    )


def en_names(entity: dict) -> list[str]:
    """
    Return all English name candidates for an entity: label + aliases.
    All returned strings are lower-cased and stripped.
    """
    candidates = []
    label = entity.get("labels", {}).get("en", {}).get("value")
    if label:
        candidates.append(label.lower().strip())
    for alias in entity.get("aliases", {}).get("en", []):
        v = alias.get("value", "")
        if v:
            candidates.append(v.lower().strip())
    return candidates


def claim_qids(entity: dict, prop: str) -> list[str]:
    """Return all Q-IDs from an entity's property claims (item-valued only)."""
    result = []
    for snak_container in entity.get("claims", {}).get(prop, []):
        snak = snak_container.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            val = snak.get("datavalue", {}).get("value", {})
            if isinstance(val, dict) and "id" in val:
                result.append(val["id"])
    return result


def claim_years(entity: dict, prop: str) -> list[int]:
    """Return all years from an entity's time-valued property claims."""
    result = []
    for snak_container in entity.get("claims", {}).get(prop, []):
        snak = snak_container.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            val = snak.get("datavalue", {}).get("value", {})
            if isinstance(val, dict) and "time" in val:
                # time is like "+1733-00-00T00:00:00Z"
                m = re.search(r"[+-](\d{4})", val["time"])
                if m:
                    result.append(int(m.group(1)))
    return result


def parse_yaml_years(composed: str) -> list[int]:
    """
    Parse a date string from the YAML into a list of years.
    Handles: "1877", "1801–1802", "1733/1748–1749", "c.1718–1721"
    Returns every distinct year mentioned.
    """
    if not composed:
        return []
    composed = str(composed)
    years = [int(y) for y in re.findall(r"\d{4}", composed)]
    return years


def years_overlap(yaml_years: list[int], wd_years: list[int]) -> bool:
    """True if any year from Wikidata falls within the YAML year range."""
    if not yaml_years or not wd_years:
        return False
    lo, hi = min(yaml_years), max(yaml_years)
    return any(lo <= y <= hi for y in wd_years)


# ---------------------------------------------------------------------------

# Approximate string matching (no external deps)


def _normalise(s: str) -> str:
    """
    Lower-case and drop both punctuation and articles for a fuzzy text comparison.
    """
    s = s.lower()
    s = re.sub(r"^(the|a|an|le|la|les|l'|der|die|das|il|lo|gli|i)\s+", "", s)
    # drop punctuation
    s = re.sub(r"[^\w\s]", " ", s)
    return s.strip()


def _token_set_ratio(a: str, b: str) -> float:
    """
    Jaccard similarity on word tokens (after normalisation).
    Returns a value in [0, 1].
    """
    ta = set(_normalise(a).split())
    tb = set(_normalise(b).split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def best_name_score(yaml_name: str, wd_candidates: list[str]) -> tuple[float, str]:
    """
    Return (best_score, best_candidate) comparing `yaml_name` against all
    Wikidata name candidates (label + aliases).
    """
    best_score = 0.0
    best_cand  = wd_candidates[0] if wd_candidates else ""
    for cand in wd_candidates:
        score = _token_set_ratio(yaml_name, cand)
        if score > best_score:
            best_score = score
            best_cand  = cand
    return best_score, best_cand


# ---------------------------------------------------------------------------

# Result helpers

PASS  = "✓ PASS"
FAIL  = "✗ FAIL"
WARN  = "⚠ WARN"
SKIP  = "– SKIP"


class Result:
    def __init__(self, label: str, status: str, detail: str = ""):
        self.label  = label
        self.status = status
        self.detail = detail

    def __str__(self):
        line = f"  {self.status}  {self.label}"
        if self.detail:
            line += f"\n         {self.detail}"
        return line


# ---------------------------------------------------------------------------

# Main verification logic


def verify_entry(entry: dict, verbose: bool) -> tuple[list[Result], bool]:
    """
    Verify a single YAML entry. Returns (results, all_passed).

    Checks:
    1. work title,
    2. composer matches (Q-ID + name),
    3. Date (P577, P1191, P571)
    """
    results = []
    all_ok  = True

    work_qid     = entry["wikidata"]
    composer_qid = f"Q{entry['composer_id']}"

    # --- fetch work entity ---
    try:
        work_entity = fetch_entity(work_qid)
    except Exception as e:
        results.append(Result("Wikidata fetch", FAIL, str(e)))
        return results, False

    # Check 1
    yaml_title  = entry.get("name", "")
    wd_titles   = en_names(work_entity)

    if not wd_titles:
        results.append(Result(
            "Work title",
            WARN,
            f"No English label/aliases on {work_qid}; cannot verify title",
        ))
    else:
        score, best = best_name_score(yaml_title, wd_titles)
        if score >= NAME_MATCH_THRESHOLD:
            results.append(Result(
                "Work title",
                PASS,
                f"'{yaml_title}' ≈ '{best}' (score={score:.2f})" if verbose else "",
            ))
        else:
            all_ok = False
            results.append(Result(
                "Work title",
                FAIL,
                f"YAML title '{yaml_title}' vs best Wikidata match '{best}' "
                f"(score={score:.2f} < threshold {NAME_MATCH_THRESHOLD})",
            ))

    # Check 2
    wd_composer_qids = claim_qids(work_entity, P_COMPOSER)

    if not wd_composer_qids:
        results.append(Result(
            "Composer (P86)",
            WARN,
            f"No P86 claim found on {work_qid}; cannot verify composer_id={composer_qid}",
        ))
    elif composer_qid in wd_composer_qids:
        # Also do a name sanity check on the composer entity
        yaml_composer_name = entry.get("composer", "")
        if yaml_composer_name:
            try:
                composer_entity = fetch_entity(composer_qid)
                wd_comp_names   = en_names(composer_entity)
                c_score, c_best = best_name_score(yaml_composer_name, wd_comp_names)
                if c_score >= NAME_MATCH_THRESHOLD:
                    results.append(Result(
                        "Composer (P86 + name)",
                        PASS,
                        f"ID {composer_qid} confirmed; "
                        f"'{yaml_composer_name}' ≈ '{c_best}' (score={c_score:.2f})"
                        if verbose else "",
                    ))
                else:
                    all_ok = False
                    results.append(Result(
                        "Composer (P86 + name)",
                        FAIL,
                        f"ID {composer_qid} matched P86, but name mismatch: "
                        f"YAML '{yaml_composer_name}' vs best Wikidata name '{c_best}' "
                        f"(score={c_score:.2f})",
                    ))
            except Exception as e:
                results.append(Result(
                    "Composer (P86 + name)",
                    WARN,
                    f"ID {composer_qid} matched P86; could not fetch composer entity: {e}",
                ))
        else:
            results.append(Result(
                "Composer (P86)",
                PASS,
                f"composer_id {composer_qid} confirmed (no composer name in YAML to check)"
                if verbose else "",
            ))
    else:
        all_ok = False
        results.append(Result(
            "Composer (P86)",
            FAIL,
            f"YAML composer_id={composer_qid}, "
            f"Wikidata says: {', '.join(wd_composer_qids)}",
        ))

    # Check 3:

    DATE_CHAIN = [
        (P_PUBLICATION,       "publication date (P577)"),
        (P_FIRST_PERFORMANCE, "first performance (P1191)"),
        (P_INCEPTION,         "inception (P571)"),
    ]

    raw_date = entry.get("date")
    if raw_date is None:
        results.append(Result("Date", SKIP, "No 'date' field in YAML"))
    else:
        yaml_years = parse_yaml_years(str(raw_date))

        first_mismatch_label = None   # label of highest-priority property that had
        first_mismatch_years = []     # claims but didn't match (fallback fail target)
        no_claims_at_all     = True

        found = False
        for prop, label in DATE_CHAIN:
            wd_years = claim_years(work_entity, prop)
            if not wd_years:
                continue
            no_claims_at_all = False
            if years_overlap(yaml_years, wd_years):
                results.append(Result(
                    "Date",
                    PASS,
                    f"'{raw_date}' matched via {label} (Wikidata: {wd_years})"
                    if verbose else f"matched via {label}",
                ))
                found = True
                break
            # mismatch — remember the first one, keep trying
            if first_mismatch_label is None:
                first_mismatch_label = label
                first_mismatch_years = wd_years

        if not found:
            if no_claims_at_all:
                results.append(Result(
                    "Date",
                    PASS,
                    f"No P577/P1191/P571 claims on {work_qid}; "
                    f"YAML '{raw_date}' unverifiable — skipping date check",
                ))
            else:
                all_ok = False
                results.append(Result(
                    "Date",
                    FAIL,
                    f"YAML '{raw_date}' (years {yaml_years}) did not match any "
                    f"date property tried; first mismatch: "
                    f"{first_mismatch_label} = {first_mismatch_years}",
                ))

    return results, all_ok


# ---------------------------------------------------------------------------

# Entry point


def main():

    global RATE_LIMIT_SECONDS
    global NAME_MATCH_THRESHOLD

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yaml", default="../data/sets.yaml",
        help="Path to sets.yaml (default: sets.yaml)",
    )
    parser.add_argument(
        "--delay", type=float, default=None, metavar="SECS",
        help=f"Seconds to wait between Wikidata requests (default: {RATE_LIMIT_SECONDS})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print extra detail on passing checks",
    )
    parser.add_argument(
        "--ids", nargs="*", type=int, metavar="ID",
        help="Only verify entries with these IDs (default: all)",
    )
    parser.add_argument(
        "--threshold", type=float, default=NAME_MATCH_THRESHOLD, metavar="FLOAT",
        help=f"Name-match threshold 0–1 (default: {NAME_MATCH_THRESHOLD})",
    )

    args = parser.parse_args()

    if args.delay is not None:
        RATE_LIMIT_SECONDS = args.delay

    NAME_MATCH_THRESHOLD = args.threshold

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        sys.exit(f"ERROR: file not found: {yaml_path}")

    with yaml_path.open() as f:
        entries = yaml.safe_load(f)

    if args.ids:
        entries = [e for e in entries if e["id"] in args.ids]
        if not entries:
            sys.exit(f"ERROR: no entries found with ids={args.ids}")

    total   = len(entries)
    passed  = 0
    failed  = 0
    warned  = 0

    print(f"\n{'='*60}")
    print(f"  sets.yaml Wikidata Verification")
    print(f"  File : {yaml_path.resolve()}")
    print(f"  Entries: {total}  |  Name threshold: {NAME_MATCH_THRESHOLD}")
    print(f"{'='*60}\n")

    for entry in entries:
        eid      = entry["id"]
        name     = entry["name"]
        work_qid = entry["wikidata"]

        date_str = entry.get("date", "")
        print(f"[{eid:02d}] {name}")
        print(f"      Work : {work_qid}  |  Composer : Q{entry['composer_id']}"
              + (f"  |  date={date_str}" if date_str else ""))

        try:
            results, all_ok = verify_entry(entry, args.verbose)
        except Exception as e:
            print(f"  {FAIL}  Unexpected error: {e}\n")
            failed += 1
            continue

        entry_failed = False
        entry_warned = False
        for r in results:
            if args.verbose or r.status != PASS:
                print(str(r))
            if r.status == FAIL:
                entry_failed = True
            if r.status == WARN:
                entry_warned = True

        if entry_failed:
            failed += 1
        elif entry_warned:
            warned += 1
            passed += 1
        else:
            passed += 1

        print()

    print(f"{'='*60}")
    print(f"  Results : {passed} passed, {failed} failed, {warned} with warnings")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
