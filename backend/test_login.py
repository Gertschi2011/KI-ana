#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from backend.auth.routes import _get_user

# Test with actual password
u = _get_user('gerald')
password_from_request = 'Jawohund2011!'

print('User password:', repr(u.get('password_plain')))
print('Request password:', repr(password_from_request))
print('Match:', u.get('password_plain') == password_from_request)
print('Lengths:', len(u.get('password_plain')), len(password_from_request))
