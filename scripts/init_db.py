#!/usr/bin/env python
"""Initialise the database schema and seed an admin user."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import init_db


def main() -> None:
    print("Initialising database schema ...")
    init_db(seed_admin=True)
    print("Database ready.")


if __name__ == "__main__":
    main()
