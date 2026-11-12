"""
common.py: tiny helpers shared by the numbered scripts.

Why it exists: CLAUDE.md requires every headline figure to be written to
outputs/key_numbers.csv by the script that computed it, so slides never contain
a hand-typed number. This file holds that one writer, plus a markdown-table
helper so reports need no extra dependency.
"""
import pandas as pd

import config

KEY_COLUMNS = ["name", "value", "unit", "script", "note"]


def record_key_numbers(rows, script):
    """Insert-or-replace rows in outputs/key_numbers.csv.

    rows: list of (name, value, unit, note).
    Replacing by `name` (instead of appending) keeps the file idempotent:
    re-running a script updates its numbers rather than duplicating them.
    """
    new = pd.DataFrame(rows, columns=["name", "value", "unit", "note"])
    new["script"] = script
    new = new[KEY_COLUMNS]
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    if config.KEY_NUMBERS.exists():
        old = pd.read_csv(config.KEY_NUMBERS, dtype=str)
        old = old[~old["name"].isin(new["name"])]
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    new.to_csv(config.KEY_NUMBERS, index=False)


def md_table(df, index=False):
    """Render a small DataFrame as a GitHub-markdown table (no tabulate needed)."""
    if index:
        df = df.reset_index()
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
            for row in df.itertuples(index=False, name=None)]
    return "\n".join([header, sep, *body])
