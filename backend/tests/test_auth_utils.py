import pytest
import sys
import types
import asyncio
from fastapi import HTTPException
from starlette.requests import Request

# Create a lightweight JWT stub so auth_utils can be imported without the
# external PyJWT dependency.
def _encode(payload, key=None, algorithm=None):
    import base64, json
    header = base64.urlsafe_b64encode(b"{}").rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.signature"

def _decode(token, options=None):
    import base64, json
    parts = token.split('.')
    data = base64.urlsafe_b64decode(parts[1] + '===')
    return json.loads(data)

fake_jwt = types.SimpleNamespace(encode=_encode, decode=_decode, exceptions=types.SimpleNamespace(PyJWTError=Exception))
sys.modules.setdefault('jwt', fake_jwt)
sys.modules.setdefault('jwt.exceptions', fake_jwt.exceptions)
jwt = fake_jwt

from utils.auth_utils import get_current_user_id_from_jwt


def test_get_current_user_id_from_jwt_valid():
    token = jwt.encode({'sub': 'user123'}, 'secret', algorithm='HS256')
    scope = {'type': 'http', 'headers': [(b'authorization', f'Bearer {token}'.encode())]}
    request = Request(scope)
    user_id = asyncio.run(get_current_user_id_from_jwt(request))
    assert user_id == 'user123'


def test_get_current_user_id_from_jwt_missing_header():
    scope = {'type': 'http', 'headers': []}
    request = Request(scope)
    with pytest.raises(HTTPException):
        asyncio.run(get_current_user_id_from_jwt(request))
