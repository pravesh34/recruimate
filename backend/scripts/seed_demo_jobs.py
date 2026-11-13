"""Seed demo job postings so the job-search + compatibility ranking can be tested.

Run from the backend directory:

    python scripts/seed_demo_jobs.py [--reset]

The postings are written to ``job_postings`` with a ``parsed`` JSON payload so
the compatibility engine has structured skills to score against. Existing
rows are updated in place (matched on title + company) so the script is safe
to re-run. ``--reset`` deletes previously seeded demo postings first.

Seeding lives in ``app/database/seed.py`` so ``init_db()`` can reuse it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on sys.path

from app.database.models import SessionLocal  # noqa: E402
from app.database.seed import dump_state, reset_demo_data, seed_demo_jobs  # noqa: E402


def main() -> int:
    reset = "--reset" in sys.argv[1:]
    db = SessionLocal()
    try:
        if reset:
            reset_demo_data(db)
            print("Removed previously seeded demo data.")
        created = seed_demo_jobs(db)
        total = dump_state(db)["jobs"]
        print(f"Seeded {created} new demo job(s). {total} job postings total.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
