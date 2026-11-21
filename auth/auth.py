import json
import os
import time
from functools import wraps
from urllib.request import urlopen

from flask import request
from jose import jwt


AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN')
API_AUDIENCE = os.environ.get('API_AUDIENCE')
ALGORITHMS = os.environ.get('ALGORITHMS', 'RS256').split(',')


class AuthError(Exception):
    """A standardized way to communicate auth failure modes."""

    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


def get_token_auth_header():
    """Get the bearer token from the Authorization header.

    Raises an AuthError if the header is missing or malformed.
    """
    auth = request.headers.get('Authorization', None)
    if not auth:
        raise AuthError({
            'code': 'authorization_header_missing',
            'description': 'Authorization header is expected.'
        }, 401)

    parts = auth.split()
    if parts[0].lower() != 'bearer':
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Authorization header must start with "Bearer".'
        }, 401)
    elif len(parts) == 1:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Token not found.'
        }, 401)
    elif len(parts) > 2:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Authorization header must be bearer token.'
        }, 401)

    return parts[1]


def check_permissions(permission, payload):
    """Check that the decoded JWT grants the requested permission.

    Raises an AuthError if the payload has no permissions claim (check that
    RBAC and "Add Permissions in the Access Token" are enabled in Auth0),
    or if the permission is not in it.
    """
    if 'permissions' not in payload:
        raise AuthError({
            'code': 'invalid_claims',
            'description': 'Permissions not included in JWT.'
        }, 400)

    if permission not in payload['permissions']:
        raise AuthError({
            'code': 'unauthorized',
            'description': 'Permission not found.'
        }, 403)

    return True


# Auth0's public signing keys, cached so each request doesn't fetch them.
_jwks = {'keys': None, 'fetched_at': 0.0}
JWKS_REFRESH_SECONDS = 60


def _fetch_jwks():
    url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    with urlopen(url, timeout=5) as response:
        _jwks['keys'] = json.loads(response.read())['keys']
    _jwks['fetched_at'] = time.monotonic()


def _key_for(kid):
    for key in _jwks['keys'] or []:
        if key['kid'] == kid:
            return {
                'kty': key['kty'],
                'kid': key['kid'],
                'use': key['use'],
                'n': key['n'],
                'e': key['e']
            }
    return None


def find_rsa_key(kid):
    """Return the Auth0 public key matching the token's key id (kid).

    Keys are cached. An unknown kid triggers a refetch, in case Auth0
    rotated its keys, but at most once every JWKS_REFRESH_SECONDS so
    tokens with made-up kids can't make every request call Auth0.
    """
    if _jwks['keys'] is None:
        _fetch_jwks()

    key = _key_for(kid)
    if key is None:
        elapsed = time.monotonic() - _jwks['fetched_at']
        if elapsed >= JWKS_REFRESH_SECONDS:
            _fetch_jwks()
            key = _key_for(kid)
    return key


def verify_decode_jwt(token):
    """Verify the token's signature and claims, and return its payload.

    The signature is checked against Auth0's public keys from
    /.well-known/jwks.json, then the audience, issuer and expiry are
    validated.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Unable to parse authentication token.'
        }, 401)

    if 'kid' not in unverified_header:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Authorization malformed.'
        }, 401)

    rsa_key = find_rsa_key(unverified_header['kid'])
    if not rsa_key:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Unable to find the appropriate key.'
        }, 401)

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=API_AUDIENCE,
            issuer=f'https://{AUTH0_DOMAIN}/'
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise AuthError({
            'code': 'token_expired',
            'description': 'Token expired.'
        }, 401)

    except jwt.JWTClaimsError:
        raise AuthError({
            'code': 'invalid_claims',
            'description': ('Incorrect claims. '
                            'Please, check the audience and issuer.')
        }, 401)

    except Exception:
        raise AuthError({
            'code': 'invalid_header',
            'description': 'Unable to parse authentication token.'
        }, 401)


def requires_auth(permission=''):
    """Decorator that protects an endpoint with an Auth0 permission.

    Gets the token, decodes and verifies it, checks the requested
    permission (e.g. 'post:recipes'), and passes the decoded payload to
    the decorated function as its first argument.
    """
    def requires_auth_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = get_token_auth_header()
            payload = verify_decode_jwt(token)
            check_permissions(permission, payload)
            return f(payload, *args, **kwargs)

        return wrapper
    return requires_auth_decorator
