#!/usr/bin/env python3
"""Smoke tests for Blockviewer APIs.
Usage:
  python3 netapi/tests/smoke_viewer.py --base http://localhost:8000
"""
import os
import sys
import argparse
import json

try:
    import requests
except Exception:
    print("Missing dependency: requests. Install with `pip install requests`.")
    sys.exit(2)


def call(base, path, method='GET', **kwargs):
    url = base.rstrip('/') + path
    try:
        if method == 'GET':
            r = requests.get(url, timeout=10, **kwargs)
        else:
            r = requests.post(url, timeout=30, **kwargs)
    except Exception as e:
        print(f"ERROR: {method} {url} -> Exception: {e}")
        return None, None
    try:
        j = r.json()
    except Exception:
        j = r.text
    return r, j


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default=os.getenv('BASE_URL', 'http://127.0.0.1:8000'), help='Base URL of the server')
    p.add_argument('--rebuild', action='store_true', help='Attempt rebuild-addressbook (requires auth)')
    p.add_argument('--cookie', default=None, help='Path to cookiejar file for authenticated requests')
    args = p.parse_args()

    base = args.base
    print(f"Running smoke tests against {base}")

    headers = {}
    cookies = None
    if args.cookie:
        try:
            # requests can accept a dict of cookies; support Netscape cookiejar parsing omitted
            # If user supplies a path, attempt to load JSON cookie dict
            cj = json.loads(open(args.cookie, 'r', encoding='utf-8').read())
            if isinstance(cj, dict):
                cookies = cj
        except Exception:
            cookies = None

    ok = True

    def expect_ok_or_403(resp, label: str) -> bool:
        nonlocal ok
        if resp is None:
            print(f'  -> FAILED no response ({label})')
            ok = False
            return False
        if resp.status_code == 403:
            print(f'  -> SKIP (auth required) ({label})')
            return False
        if resp.status_code != 200:
            print(f'  -> FAILED {resp.status_code} ({label})')
            ok = False
            return False
        return True

    print('\n1) GET /viewer/api/blocks?source=filesystem&limit=1')
    r, j = call(base, '/viewer/api/blocks?source=filesystem&limit=1', headers=headers, cookies=cookies)
    if expect_ok_or_403(r, 'blocks'):
        print('  -> OK', 'total=', j.get('total') if isinstance(j, dict) else 'n/a')

    print('\n2) GET /viewer/api/blocks/coverage')
    r, j = call(base, '/viewer/api/blocks/coverage', headers=headers, cookies=cookies)
    if expect_ok_or_403(r, 'coverage'):
        print('  -> OK', j)

    print('\n3) GET /viewer/api/blocks/health')
    r, j = call(base, '/viewer/api/blocks/health', headers=headers, cookies=cookies)
    if expect_ok_or_403(r, 'health'):
        print('  -> OK', j if isinstance(j, dict) else str(j)[:200])

    print('\n4) GET /viewer/api/addressbook/health')
    r, j = call(base, '/viewer/api/addressbook/health', headers=headers, cookies=cookies)
    if expect_ok_or_403(r, 'addressbook_health'):
        print('  -> OK', j if isinstance(j, dict) else str(j)[:200])

    print('\n5) GET /viewer/api/addressbook')
    r, j = call(base, '/viewer/api/addressbook', headers=headers, cookies=cookies)
    if expect_ok_or_403(r, 'addressbook') and isinstance(j, dict):
        tree = j.get('tree')
        cats = len(tree.keys()) if isinstance(tree, dict) else 0
        print('  -> OK', f'categories={cats}')

    if args.rebuild:
        print('\n6) POST /viewer/api/rebuild-addressbook (requires auth)')
        r, j = call(base, '/viewer/api/rebuild-addressbook', method='POST', headers=headers, cookies=cookies)
        if expect_ok_or_403(r, 'rebuild'):
            print('  -> OK', j)

    print('\nSmoke summary:')
    print('  OK' if ok else '  FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
