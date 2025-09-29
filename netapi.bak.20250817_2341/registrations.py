# registrations.py — registration + simple login APIs
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from .user_mgmt import (init_db, create_user, authenticate, issue_session_token, verify_session_token, get_user)

router = APIRouter(prefix="/api", tags=["auth"])

class RegisterIn(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=6)
    birthdate: str # YYYY-MM-DD
    address: str

class LoginIn(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(inp: RegisterIn):
    init_db()
    try:
        uid = create_user(inp.username.strip(), inp.email.strip(), inp.password, inp.birthdate.strip(), inp.address.strip(), role="family")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"registration failed: {e}")
    return {"ok": True, "user_id": uid}

@router.post("/login")
def login(inp: LoginIn):
    u = authenticate(inp.username.strip(), inp.password)
    if not u:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_session_token(u)
    return {"ok": True, "token": token, "user": {"id": u["id"], "username": u["username"], "role": u["role"], "plan": u["plan"], "plan_until": u["plan_until"]}}
