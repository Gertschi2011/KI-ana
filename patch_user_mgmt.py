import os, re, time, secrets

p = "/home/kiana/ki_ana/netapi/user_mgmt.py"
src = open(p,"r",encoding="utf-8").read()

def ensure(pattern, block):
    global src
    if not re.search(pattern, src):
        src = src.rstrip()+"\n\n"+block.strip()+"\n"

# itsdangerous-Import
if "URLSafeTimedSerializer" not in src:
    src = src.replace("\nfrom sqlalchemy",
        "\nfrom itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired\nfrom sqlalchemy")

# Secret-Key Loader
ensure(r"def _load_secret_key\(", r'''
def _load_secret_key():
    import pathlib
    env = os.getenv("KI_SECRET")
    if env:
        return env
    cfg_dir = os.path.expanduser("~/.config/ki_ana")
    os.makedirs(cfg_dir, exist_ok=True)
    key_path = os.path.join(cfg_dir, "secret.key")
    if os.path.exists(key_path):
        return open(key_path).read().strip()
    key = secrets.token_urlsafe(48)
    with open(key_path,"w") as f: f.write(key)
    return key
''')

# Serializer
ensure(r"def _serializer\(", r'''
def _serializer():
    return URLSafeTimedSerializer(_load_secret_key(), salt="ki_ana.session.v1")
''')

# Token ausstellen
ensure(r"def issue_session_token\(", r'''
def issue_session_token(user_id:int)->str:
    s = _serializer()
    return s.dumps({"uid":int(user_id),"ts":int(time.time())})
''')

# Token prüfen
ensure(r"def verify_session_token\(", r'''
def verify_session_token(token:str, max_age:int=60*60*24*7)->int|None:
    if not token: return None
    s=_serializer()
    try:
        data=s.loads(token,max_age=max_age)
        return int(data.get("uid"))
    except Exception: return None
''')

# SessionLocal fallback
if "SessionLocal" not in src and "engine" in src:
    ensure("SessionLocal", r'''
try:
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
except Exception: pass
''')

# get_user_by_id fallback
ensure(r"def get_user_by_id\(", r'''
def get_user_by_id(user_id:int):
    try:
        from sqlalchemy import select
        with SessionLocal() as s:
            return s.scalar(select(User).where(User.id==int(user_id)))
    except Exception: return None
''')

open(p,"w",encoding="utf-8").write(src)
print("Patched:", p)
