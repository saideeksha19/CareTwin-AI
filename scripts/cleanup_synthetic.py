"""Remove medical documents created by CareTwin's own verification scripts.

The document-intelligence scripts upload synthetic PDFs on every run, so repeated
verification leaves a large tail of documents and unverified extractions in the
demo database. This tool removes only documents whose *filename* carries an
explicit test marker. It never matches on patient, date, size or content, so a real
upload cannot be selected by accident.

Safety rules
------------
* Dry run by default. Nothing is deleted without ``--confirm``.
* Only ``original_filename`` values starting with a marker (default ``SYNTHETIC-``).
* The audit trail (``audit_events``) is never deleted or modified.
* The original stored files are removed only when they live inside the configured
  document storage directory.
* After deletion the script re-counts rows and runs ``PRAGMA foreign_key_check``.

Usage
-----
    python scripts/cleanup_synthetic.py                 # dry run
    python scripts/cleanup_synthetic.py --confirm       # actually delete
    python scripts/cleanup_synthetic.py --db data/demo/caretwin.db --marker SYNTHETIC- --confirm
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

CONFIRM_FLAG = "--confirm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete only test-marked synthetic documents (dry run by default).",
    )
    parser.add_argument("--db", help="Path to the SQLite database. Defaults to the app setting.")
    parser.add_argument(
        "--marker",
        action="append",
        default=None,
        help="Filename prefix that identifies test uploads (repeatable). Default: SYNTHETIC-",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Perform the deletion. Without this flag the script only reports what it would do.",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Delete database rows but leave the stored file bytes on disk.",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable summary.")
    return parser.parse_args()


def resolve_paths(db_override: str | None) -> tuple[Path, Path]:
    if db_override:
        db_path = Path(db_override).expanduser().resolve()
        storage = db_path.parent.parent / "documents"
    else:
        from app.config import Settings

        settings = Settings.from_env()
        db_path = settings.db_path
        storage = settings.document_storage_path
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    return db_path, storage


def select_targets(conn: sqlite3.Connection, markers: list[str]) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, patient_id, original_filename, document_type, storage_path, "
        "file_size_bytes, uploaded_at FROM medical_documents ORDER BY uploaded_at"
    ).fetchall()
    targets: list[dict] = []
    for row in rows:
        record = dict(row)
        name = (record["original_filename"] or "").lower()
        if any(name.startswith(marker.lower()) for marker in markers):
            targets.append(record)
    conn.row_factory = None
    return targets


def dependent_counts(conn: sqlite3.Connection, ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("document_pages", "document_extractions", "document_extraction_reviews"):
        if not ids:
            counts[table] = 0
            continue
        placeholders = ",".join("?" for _ in ids)
        counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE document_id IN ({placeholders})", ids
        ).fetchone()[0]
    counts["unverified_extractions"] = 0
    if ids:
        placeholders = ",".join("?" for _ in ids)
        counts["unverified_extractions"] = conn.execute(
            "SELECT COUNT(*) FROM document_extractions "
            f"WHERE verification_status = 'unverified' AND document_id IN ({placeholders})",
            ids,
        ).fetchone()[0]
    return counts


def integrity_report(conn: sqlite3.Connection) -> dict:
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    orphans = {
        "pages_without_document": conn.execute(
            "SELECT COUNT(*) FROM document_pages p "
            "LEFT JOIN medical_documents d ON d.id = p.document_id WHERE d.id IS NULL"
        ).fetchone()[0],
        "extractions_without_document": conn.execute(
            "SELECT COUNT(*) FROM document_extractions e "
            "LEFT JOIN medical_documents d ON d.id = e.document_id WHERE d.id IS NULL"
        ).fetchone()[0],
        "reviews_without_extraction": conn.execute(
            "SELECT COUNT(*) FROM document_extraction_reviews r "
            "LEFT JOIN document_extractions e ON e.id = r.extraction_id WHERE e.id IS NULL"
        ).fetchone()[0],
    }
    return {"foreignKeyViolations": [list(row) for row in fk], "orphans": orphans}


def main() -> int:
    args = parse_args()
    markers = [m for m in (args.marker or ["SYNTHETIC-"]) if len(m) >= 4]
    if not markers:
        raise SystemExit("Refusing to run: every marker must be at least 4 characters long.")

    db_path, storage = resolve_paths(args.db)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        targets = select_targets(conn, markers)
        ids = [doc["id"] for doc in targets]
        counts = dependent_counts(conn, ids)
        totals = {
            "documentsInDatabase": conn.execute("SELECT COUNT(*) FROM medical_documents").fetchone()[0],
            "pendingExtractionsInDatabase": conn.execute(
                "SELECT COUNT(*) FROM document_extractions WHERE verification_status = 'unverified'"
            ).fetchone()[0],
            "auditEventsInDatabase": conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        }
        summary = {
            "database": str(db_path),
            "storage": str(storage),
            "markers": markers,
            "dryRun": not args.confirm,
            "matchedDocuments": len(targets),
            "matchedDocumentIds": ids,
            "cascadingRows": counts,
            "totals": totals,
        }

        if not args.json:
            print(f"Database: {db_path}")
            print(f"Storage:  {storage}")
            print(f"Markers:  {', '.join(markers)}")
            print()
            if targets:
                print(f"{'document id':<22} {'filename':<42} {'uploaded':<26} type")
                for doc in targets:
                    print(
                        f"{doc['id']:<22} {doc['original_filename'][:40]:<42} "
                        f"{doc['uploaded_at'][:24]:<26} {doc['document_type']}"
                    )
            else:
                print("No document matched the test markers.")
            print()
            print(f"Matched documents:         {len(targets)}")
            print(f"Document pages:            {counts['document_pages']}")
            print(f"Extractions:               {counts['document_extractions']} "
                  f"({counts['unverified_extractions']} unverified)")
            print(f"Extraction reviews:        {counts['document_extraction_reviews']}")
            print(f"Database before:           {totals['documentsInDatabase']} documents, "
                  f"{totals['pendingExtractionsInDatabase']} unverified extractions, "
                  f"{totals['auditEventsInDatabase']} audit events")
            print("Audit events are never modified.")

        if not args.confirm:
            if not args.json:
                print()
                print("DRY RUN — nothing was deleted. Re-run with --confirm to delete these rows.")
            else:
                print(json.dumps(summary, indent=2))
            return 0

        deleted_files: list[str] = []
        missing_files: list[str] = []
        root = storage.resolve()
        with conn:  # single transaction for every row deletion
            for doc in targets:
                rel = doc.get("storage_path") or ""
                if rel and not args.keep_files:
                    candidate = (root / rel).resolve()
                    if root in candidate.parents and candidate.exists():
                        try:
                            candidate.unlink()
                            deleted_files.append(rel)
                        except OSError as exc:  # pragma: no cover - filesystem dependent
                            print(f"warning: could not delete {candidate}: {exc}", file=sys.stderr)
                    elif root in candidate.parents:
                        missing_files.append(rel)
            conn.executemany(
                "DELETE FROM document_extraction_reviews WHERE document_id = ?",
                [(i,) for i in ids],
            )
            conn.executemany(
                "DELETE FROM document_extractions WHERE document_id = ?",
                [(i,) for i in ids],
            )
            conn.executemany("DELETE FROM document_pages WHERE document_id = ?", [(i,) for i in ids])
            conn.executemany("DELETE FROM medical_documents WHERE id = ?", [(i,) for i in ids])

        after = {
            "documents": conn.execute("SELECT COUNT(*) FROM medical_documents").fetchone()[0],
            "unverifiedExtractions": conn.execute(
                "SELECT COUNT(*) FROM document_extractions WHERE verification_status = 'unverified'"
            ).fetchone()[0],
            "auditEvents": conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        }
        report = {
            **summary,
            "dryRun": False,
            "deleted": {
                "documents": len(ids),
                "pages": counts["document_pages"],
                "extractions": counts["document_extractions"],
                "reviews": counts["document_extraction_reviews"],
                "files": deleted_files,
                "missingFiles": missing_files,
            },
            "after": after,
            "integrity": integrity_report(conn),
        }
        if not conn.execute("PRAGMA foreign_keys").fetchone()[0]:
            raise SystemExit("Foreign keys were not enabled; no deletion should have happened.")
        conn.commit()

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print()
            print(f"Deleted {len(ids)} documents, {counts['document_pages']} pages, "
                  f"{counts['document_extractions']} extractions, "
                  f"{counts['document_extraction_reviews']} reviews.")
            print(f"Removed {len(deleted_files)} stored files "
                  f"({len(missing_files)} were already missing on disk).")
            print(f"Database after: {after['documents']} documents, "
                  f"{after['unverifiedExtractions']} unverified extractions, "
                  f"{after['auditEvents']} audit events.")
            print(f"Integrity: {json.dumps(report['integrity'])}")
        violations = report["integrity"]["foreignKeyViolations"]
        orphans = report["integrity"]["orphans"]
        if violations or any(orphans.values()):
            print("Consistency check FAILED — inspect the report above.", file=sys.stderr)
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
