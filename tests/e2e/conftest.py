import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx
import pytest

DEFAULT_BASE_URL = "http://localhost:28000"


@dataclass(frozen=True)
class E2EUser:
    username: str
    email: str
    password: str
    email_verification_token: str


def _safe_suffix(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s or "x")[:28]


@pytest.fixture(scope="session")
def base_url() -> str:
    return (os.getenv("STAGING_BASE_URL") or os.getenv("E2E_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def run_id() -> str:
    env = (os.getenv("RUN_ID") or os.getenv("E2E_RUN_ID") or "").strip()
    if env:
        return env
    return f"{int(time.time())}-{secrets.token_hex(4)}"


@pytest.fixture()
def http(base_url: str) -> httpx.Client:
    timeout = float(os.getenv("E2E_HTTP_TIMEOUT", "20") or "20")
    return httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)


def _register_payload(username: str, email: str, password: str) -> Dict[str, Any]:
    return {
        "username": username,
        "email": email,
        "password": password,
        "birthdate": None,
        "address": None,
        "billing": None,
    }


def register_user(client: httpx.Client, *, username: str, email: str, password: str) -> Dict[str, Any]:
    resp = client.post("/api/register", json=_register_payload(username, email, password))
    assert resp.status_code in {200, 409}, resp.text
    if resp.status_code == 409:
        raise AssertionError(f"User collision for {username}/{email}; RUN_ID must be unique")
    data = resp.json()
    assert data.get("ok") is True, data
    return data


def verify_email(client: httpx.Client, token: str) -> Dict[str, Any]:
    resp = client.post("/api/verify-email", json={"token": token})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("ok") is True, data
    return data


def login(client: httpx.Client, *, username_or_email: str, password: str, remember: bool = False) -> Dict[str, Any]:
    resp = client.post(
        "/api/login",
        json={"username": username_or_email, "password": password, "remember": bool(remember)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("ok") is True, data
    return data


def logout(client: httpx.Client) -> None:
    try:
        client.post("/api/logout")
    except Exception:
        return


def create_verified_user_session(
    client: httpx.Client,
    *,
    run_id: str,
    suffix: str,
) -> Tuple[E2EUser, httpx.Client]:
    # Keep these short: RegisterIn enforces username <= 50 chars.
    rid = _safe_suffix(run_id)[-10:]
    sfx = _safe_suffix(suffix)[:12]
    rnd = secrets.token_hex(3)
    uniq = f"{rid}_{sfx}_{rnd}".strip("_")

    username = (f"e2e_{uniq}")[:50]
    email = f"e2e_{uniq}@example.com"
    password = f"pw-{uniq}-A1!"

    reg = register_user(client, username=username, email=email, password=password)
    token = reg.get("email_verification_token")
    if not token:
        pytest.skip("Server did not return email_verification_token; enable TEST_MODE=1 for E2E runs.")

    verify_email(client, str(token))

    # Exercise /api/login cookie logic (not only register auto-cookie).
    logout(client)
    login(client, username_or_email=username, password=password)

    return E2EUser(username=username, email=email, password=password, email_verification_token=str(token)), client


@pytest.fixture()
def verified_user_session(http: httpx.Client, run_id: str, request: pytest.FixtureRequest):
    try:
        user, client = create_verified_user_session(http, run_id=run_id, suffix=request.node.name)
        yield user, client
    finally:
        http.close()


@pytest.fixture()
def maybe_admin_client(base_url: str) -> Optional[httpx.Client]:
    """Return an authenticated admin/creator client when configured.

    Priority:
    1) Token-mode: ADMIN_API_TOKEN or E2E_ADMIN_API_TOKEN
    2) User-mode: E2E_ADMIN_USER/E2E_ADMIN_PASS via /api/login

    If nothing is configured, returns None.
    """

    admin_token = (os.getenv("E2E_ADMIN_API_TOKEN") or os.getenv("ADMIN_API_TOKEN") or "").strip()
    admin_user = (os.getenv("E2E_ADMIN_USER") or "").strip()
    admin_pass = (os.getenv("E2E_ADMIN_PASS") or "").strip()

    timeout = float(os.getenv("E2E_HTTP_TIMEOUT", "20") or "20")
    client = httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)

    if admin_token:
        client.headers["Authorization"] = f"Bearer {admin_token}"
        return client

    if admin_user and admin_pass:
        resp = client.post("/api/login", json={"username": admin_user, "password": admin_pass, "remember": False})
        if resp.status_code != 200:
            client.close()
            raise AssertionError(f"Admin login failed: {resp.status_code} {resp.text}")
        return client

    client.close()
    return None
