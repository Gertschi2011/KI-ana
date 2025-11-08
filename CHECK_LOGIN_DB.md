# 🔍 Login Problem - DB-Analyse

## Problem:
Login funktioniert nicht - vermutlich DB-Inkonsistenz

## Gefundene DB-Dateien:
```
/home/kiana/ki_ana/kiana.db
/home/kiana/ki_ana/data/kiana.db  
/home/kiana/ki_ana/users.db
/home/kiana/ki_ana/netapi/users.db  ← 76KB, letzte Änderung Sept 13
```

## Zwei DB-Module gefunden:

### 1. `/netapi/db.py` (AKTUELL - wird vom Backend verwendet)
```python
DB_URL = os.getenv("DATABASE_URL", _default_sqlite_url()).strip()
# Default: sqlite:////home/kiana/ki_ana/netapi/users.db
```

### 2. `/ki_ana/db.py` (ALT - sollte nicht mehr verwendet werden)
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kiana.db")
```

## .env.production Konfiguration:
```
DATABASE_URL=postgresql+psycopg2://kiana:CHANGE_THIS_SECURE_PASSWORD@localhost:5432/kiana
```

## Problem:
1. `.env.production` definiert PostgreSQL
2. Backend nutzt vermutlich SQLite (`/netapi/users.db`) weil `.env` nicht geladen wird
3. User "gerald" ist in PostgreSQL angelegt
4. Login sucht in SQLite → findet gerald nicht!

## Lösung:
**Option 1: SQLite verwenden (einfacher)**
- Alle User nach `/netapi/users.db` migrieren
- `.env` entfernen oder DATABASE_URL auf SQLite setzen

**Option 2: PostgreSQL verwenden (production-ready)**
- Sicherstellen dass `.env.production` geladen wird
- DATABASE_URL korrekt setzen beim Start
- Alle User sind bereits in PostgreSQL

## Nächste Schritte:
1. Prüfen welche DB gerade aktiv ist
2. User "gerald" finden
3. Entscheiden: SQLite ODER PostgreSQL
4. Alles auf eine DB migrieren
