#!/usr/bin/env python3
"""Synchronizes identical parts of task.ipynb and solution.ipynb.

Jupyter Notebook cells are assigned a UUID as a tag (Function 1) and can be synchronized
between the notebooks using this UUID (Function 2: individual cell;
additionally: all Markdown cells at once).

# generated with mistral Vibe Code

Usage:
python3 notebook_sync.py init <notebook>                       # add UUID-Tags to all cells
python3 notebook_sync.py clear <notebook>                      # remove UUID-Tags for all cells
python3 notebook_sync.py sync-markdown <source> <target>       # syncs markdown cells
python3 notebook_sync.py sync-cell <UUID> <source> <target>    # syncs one cell


ChangeLog:
- using UUIDs with 4 characters to simplify manual sync of single cells
"""


from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

UUID_PREFIX = "id-"
MARKDOWN = "markdown"


def load_notebook(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        nb = json.load(fh)
    if "cells" not in nb:
        nb["cells"] = []
    if "metadata" not in nb:
        nb["metadata"] = {}
    nb.setdefault("nbformat", 4)
    nb.setdefault("nbformat_minor", 5)
    return nb


def save_notebook(path: Path, nb: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(nb, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def get_cell_id(cell: dict) -> str | None:
    for tag in cell.get("metadata", {}).get("tags", []):
        if isinstance(tag, str) and tag.startswith(UUID_PREFIX):
            return tag[len(UUID_PREFIX):]
    return None


def set_cell_id(cell: dict, cell_id: str) -> None:
    meta = cell.setdefault("metadata", {})
    tags = meta.setdefault("tags", [])
    tags = [t for t in tags if not (isinstance(t, str) and t.startswith(UUID_PREFIX))]
    tags.append(UUID_PREFIX + cell_id)
    meta["tags"] = tags


def exist_cell_id(nb: dict, cell_id:str) -> bool:
    for cell in nb.get("cells", []):
        c_id = get_cell_id(cell)
        if c_id is not None and c_id == cell_id:
            return True
    return False


def ensure_ids(nb: dict) -> bool:
    changed = False
    for cell in nb.get("cells", []):
        if get_cell_id(cell) is None:
            id = str(uuid.uuid4())[0:4]
            while exist_cell_id(nb, id):
                id = str(uuid.uuid4())[0:4]
            set_cell_id(cell, id)
            changed = True
    return changed


def find_cell_index(nb: dict, cell_id: str) -> int | None:
    for i, cell in enumerate(nb.get("cells", [])):
        if get_cell_id(cell) == cell_id:
            return i
    return None


def remove_ids(nb: dict) -> int:
    removed = 0
    for cell in nb.get("cells", []):
        tags = cell.get("metadata", {}).get("tags", [])
        kept = [t for t in tags if not (isinstance(t, str) and t.startswith(UUID_PREFIX))]
        if len(kept) != len(tags):
            cell["metadata"]["tags"] = kept
            removed += len(tags) - len(kept)
    return removed


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.notebook)
    if not path.exists():
        print(f"Fehler: Notebook nicht gefunden: {path}", file=sys.stderr)
        return 1
    nb = load_notebook(path)
    changed = ensure_ids(nb)
    if changed:
        save_notebook(path, nb)
        n = len(nb.get("cells", []))
        print(f"{path}: UUID-Tags gesetzt, {n} Zellen. Datei gespeichert.")
    else:
        print(f"{path}: alle Zellen haben bereits einen UUID-Tag. Keine Aenderung.")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    path = Path(args.notebook)
    if not path.exists():
        print(f"Fehler: Notebook nicht gefunden: {path}", file=sys.stderr)
        return 1
    nb = load_notebook(path)
    removed = remove_ids(nb)
    if removed:
        save_notebook(path, nb)
        print(f"{path}: {removed} UUID-Tag(s) entfernt. Datei gespeichert.")
    else:
        print(f"{path}: keine UUID-Tags gefunden. Keine Aenderung.")
    return 0


def sync_cell_by_id(from_nb: dict, to_nb: dict, cell_id: str) -> tuple[bool, str]:
    src_idx = find_cell_index(from_nb, cell_id)
    if src_idx is None:
        return False, f"UUID {cell_id} nicht in Quelle gefunden."
    dst_idx = find_cell_index(to_nb, cell_id)
    if dst_idx is None:
        return False, f"UUID {cell_id} nicht in Ziel gefunden."
    src = from_nb["cells"][src_idx]
    dst = to_nb["cells"][dst_idx]
    if src.get("cell_type") != dst.get("cell_type"):
        return False, (
            f"Zelltypen unterscheiden sich "
            f"(Quelle: {src.get('cell_type')}, Ziel: {dst.get('cell_type')})."
        )
    dst["source"] = src["source"]
    for key in ("outputs", "execution_count"):
        if key in src:
            dst[key] = src[key]
    return True, "aktualisiert."


def cmd_sync_cell(args: argparse.Namespace) -> int:
    from_path = Path(args.source)
    to_path = Path(args.target)
    for p in (from_path, to_path):
        if not p.exists():
            print(f"Fehler: Notebook nicht gefunden: {p}", file=sys.stderr)
            return 1
    from_nb = load_notebook(from_path)
    to_nb = load_notebook(to_path)
    ok, msg = sync_cell_by_id(from_nb, to_nb, args.cell_id)
    print(f"{args.cell_id}: {msg}")
    if not ok:
        return 1
    save_notebook(to_path, to_nb)
    print(f"Ziel gespeichert: {to_path}")
    return 0


def cmd_sync_markdown(args: argparse.Namespace) -> int:
    from_path = Path(args.source)
    to_path = Path(args.target)
    for p in (from_path, to_path):
        if not p.exists():
            print(f"Fehler: Notebook nicht gefunden: {p}", file=sys.stderr)
            return 1
    from_nb = load_notebook(from_path)
    to_nb = load_notebook(to_path)
    updated = 0
    skipped = 0
    for cell in from_nb.get("cells", []):
        if cell.get("cell_type") != MARKDOWN:
            continue
        cell_id = get_cell_id(cell)
        if cell_id is None:
            continue
        dst_idx = find_cell_index(to_nb, cell_id)
        if dst_idx is None:
            skipped += 1
            print(f"  uebersprungen: {cell_id} (nicht im Ziel)")
            continue
        to_nb["cells"][dst_idx]["source"] = cell["source"]
        updated += 1
    if updated:
        save_notebook(to_path, to_nb)
    print(f"Markdown synchronisiert: {updated} aktualisiert, {skipped} uebersprungen.")
    if updated:
        print(f"Ziel gespeichert: {to_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UUID-Tags und Synchronisation fuer aufgabe.ipynb / loesung.ipynb."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init",
        help="Jeder Zelle eine UUID als Tag vergeben, falls noch keiner vorhanden.",
    )
    p_init.add_argument("notebook", help="Pfad zur .ipynb-Datei")
    p_init.set_defaults(func=cmd_init)

    p_clear = sub.add_parser(
        "clear",
        help="Alle UUID-Tags aus dem Notebook entfernen.",
    )
    p_clear.add_argument("notebook", help="Pfad zur .ipynb-Datei")
    p_clear.set_defaults(func=cmd_clear)

    p_cell = sub.add_parser(
        "sync-cell",
        help="Inhalt einer Zelle (anhand UUID) von Quelle nach Ziel kopieren.",
    )
    p_cell.add_argument("cell_id", help="UUID der zu synchronisierenden Zelle")
    p_cell.add_argument("source", help="Quell-Notebook (z. B. loesung.ipynb)")
    p_cell.add_argument("target", help="Ziel-Notebook (z. B. aufgabe.ipynb)")
    p_cell.set_defaults(func=cmd_sync_cell)

    p_md = sub.add_parser(
        "sync-markdown",
        help="Alle Markdown-Zellen anhand UUID von Quelle nach Ziel abgleichen.",
    )
    p_md.add_argument("source", help="Quell-Notebook (z. B. loesung.ipynb)")
    p_md.add_argument("target", help="Ziel-Notebook (z. B. aufgabe.ipynb)")
    p_md.set_defaults(func=cmd_sync_markdown)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())