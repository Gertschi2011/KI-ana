# /home/kiana/ki_ana/netapi/init_db.py
# Erstellt alle SQL-Tabellen laut netapi.models (idempotent)

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from netapi.db import engine, Base
# Wichtig: Modelle importieren, damit sie bei Base bekannt sind
import netapi.models  # noqa: F401

def main():
    Base.metadata.create_all(bind=engine)
    print("OK: Tabellen (falls fehlend) erstellt.")

if __name__ == "__main__":
    main()
