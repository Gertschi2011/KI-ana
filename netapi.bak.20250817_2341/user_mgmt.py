import os, time, bcrypt
from typing import Optional
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, Column, Integer, String

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")          # user | creator | admin
    plan = Column(String, default="free")          # free | pro
    plan_until = Column(Integer, default=0)        # unix ts (0 = kein Ablauf)
    birthdate = Column(String, default="")
    address = Column(String, default="")

def init_db():
    Base.metadata.create_all(engine)

def get_user_by_username(s, username:str) -> Optional[User]:
    return s.query(User).filter(User.username==username).first()

def get_user_by_id(s, uid:int) -> Optional[User]:
    return s.query(User).filter(User.id==uid).first()

def create_user(username:str, email:str, password:str, role:str="user", birthdate:str="", address:str="") -> User:
    with SessionLocal() as s:
        if get_user_by_username(s, username):
            return get_user_by_username(s, username)
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        u = User(username=username, email=email, password_hash=pw_hash, role=role, birthdate=birthdate, address=address, plan="free", plan_until=0)
        s.add(u); s.commit(); s.refresh(u)
        return u

def set_password(s, user:User, new_password:str):
    user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    s.commit()

def authenticate(username:str, password:str) -> Optional[User]:
    with SessionLocal() as s:
        u = get_user_by_username(s, username)
        if not u: return None
        ok = bcrypt.checkpw(password.encode(), u.password_hash.encode())
        return u if ok else None

# --- Sessions (signierte Cookies) ---
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired
SECRET = os.environ.get("KIANA_SECRET", "dev-secret-change-me")
signer = TimestampSigner(SECRET)

def issue_session_token(user_id:int, max_age_days:int=30) -> str:
    val = f"{user_id}"
    return signer.sign(val.encode()).decode()

def verify_session_token(token:str, max_age_days:int=30) -> Optional[int]:
    try:
        raw = signer.unsign(token, max_age=max_age_days*24*3600)
        return int(raw.decode())
    except (BadSignature, SignatureExpired, ValueError):
        return None
