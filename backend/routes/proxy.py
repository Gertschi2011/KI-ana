"""
Proxy routes to forward requests to the FastAPI backend running on host.
This is a temporary solution until we fully migrate to FastAPI.
"""
from flask import Blueprint, request, Response
import requests

bp = Blueprint("proxy", __name__)

# FastAPI server URL (host machine from Docker container)
# Use host.docker.internal or the gateway IP
import os
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://172.19.0.1:8000")

@bp.route("/api/goals/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_goals(subpath):
    """Proxy goals requests to FastAPI."""
    url = f"{FASTAPI_URL}/api/goals/{subpath}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        params=request.args,
    )
    return Response(resp.content, resp.status_code, resp.headers.items())


@bp.route("/api/personality/<path:subpath>", methods=["GET", "POST"])
def proxy_personality(subpath):
    """Proxy personality requests to FastAPI."""
    url = f"{FASTAPI_URL}/api/personality/{subpath}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        params=request.args,
    )
    return Response(resp.content, resp.status_code, resp.headers.items())


@bp.route("/api/conflicts/<path:subpath>", methods=["GET", "POST"])
def proxy_conflicts(subpath):
    """Proxy conflicts requests to FastAPI."""
    url = f"{FASTAPI_URL}/api/conflicts/{subpath}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        params=request.args,
    )
    return Response(resp.content, resp.status_code, resp.headers.items())


@bp.route("/api/reflection/<path:subpath>", methods=["GET", "POST"])
def proxy_reflection(subpath):
    """Proxy reflection requests to FastAPI."""
    url = f"{FASTAPI_URL}/api/reflection/{subpath}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        params=request.args,
    )
    return Response(resp.content, resp.status_code, resp.headers.items())
