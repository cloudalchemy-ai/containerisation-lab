"""Minimal OAuth 2.0 Authorization Server — the LAB stand-in for Entra ID / Keycloak.

You would never write this in production. It exists so the lab runs offline and
so you can see exactly what an authorisation server does, which is only:

  1. authenticate a CLIENT (here: client_id + client_secret)
  2. decide what that client is allowed to ask for (scopes, audiences)
  3. mint a short-lived, SIGNED JWT saying so
  4. publish the PUBLIC key so any resource server can verify it offline

In production you delete this file and change two URLs. Nothing else changes.
"""

import os
import time
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException

ISSUER = os.getenv("OAUTH_ISSUER", "http://localhost:9100")
# Short on purpose. A leaked token is only useful until it expires, so TTL is
# your blast-radius control. Minutes, not days.
TOKEN_TTL = int(os.getenv("TOKEN_TTL", "3600"))

# ---------------------------------------------------------------------------
# Signing key. Generated at startup for the lab; a real IdP keeps this in an
# HSM or key vault and rotates it on a schedule.
# ---------------------------------------------------------------------------
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_numbers = _key.public_key().public_numbers()


def _b64(n: int) -> str:
    """Encode an int as base64url, the format JWKS requires."""
    import base64

    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


# ---------------------------------------------------------------------------
# THE KEY ID IS DERIVED FROM THE KEY ITSELF — this is not cosmetic.
#
# A hard-coded kid like "lab-key-1" is an actual trap, and this lab hit it:
# restart the IdP, it generates NEW key material but reuses the SAME kid, and
# any resource server holding a cached JWKS keeps the OLD key under that id.
# Every token then fails signature verification with a completely unhelpful
# "invalid_token", while the JWKS endpoint appears to serve a matching kid.
#
# Deriving the kid from the public key (an RFC 7638-style thumbprint) makes a
# new key produce a NEW id, so caches miss, refetch, and self-heal.
#
# THE REAL LESSON: this is precisely why key rotation needs OVERLAP. A real IdP
# publishes the old and new keys in JWKS simultaneously, each with its own kid,
# so tokens signed before the rotation keep verifying until they expire. Cutting
# over instantly — or reusing a kid — breaks every token already in flight.
# ---------------------------------------------------------------------------
def _thumbprint() -> str:
    import hashlib
    import json as _json

    jwk = {"e": _b64(_public_numbers.e), "kty": "RSA", "n": _b64(_public_numbers.n)}
    canonical = _json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()
    import base64

    return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).decode().rstrip("=")


KEY_ID = _thumbprint()


PRIVATE_PEM = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

# ---------------------------------------------------------------------------
# The client registry. In production this lives in the IdP's directory and is
# managed by your identity team — not in code.
#
# NOTE: this secret is FAKE and exists only for the lab. Real machine-to-machine
# auth should prefer workload identity (federated, no stored secret) — the lab
# notes explain why.
# ---------------------------------------------------------------------------
CLIENTS = {
    # The real client used by the lab.
    "payments-app": {
        "secret": "lab-secret-not-real",
        # What this client is ALLOWED to request. The IdP enforces this — the
        # client cannot grant itself more by simply asking for more.
        "allowed_scopes": {"mcp:invoke"},
        "allowed_audiences": {"https://mcp.internal/payments"},
    },
    # Exists ONLY to demonstrate the confused-deputy attack. It gets a
    # perfectly valid, correctly signed, unexpired token — for a DIFFERENT API.
    # Presenting it to the MCP server must fail on the audience check.
    "reporting-app": {
        "secret": "lab-secret-not-real-2",
        "allowed_scopes": {"mcp:invoke"},
        "allowed_audiences": {"https://api.internal/reports"},
    },
    # Exists ONLY to demonstrate authentication != authorisation. Valid token,
    # right audience, but it lacks the mcp:invoke scope.
    "readonly-app": {
        "secret": "lab-secret-not-real-3",
        "allowed_scopes": {"mcp:read"},
        "allowed_audiences": {"https://mcp.internal/payments"},
    },
     "payments-reader": {
        "secret": "lab-secret-not-real-4",
        "allowed_scopes": {"mcp:invoke", "payments:read"},
        "allowed_audiences": {"https://mcp.internal/payments"},
    },
    "payments-operator": {
        "secret": "lab-secret-not-real-5",
        "allowed_scopes": {"mcp:invoke", "payments:read", "payments:write"},
        "allowed_audiences": {"https://mcp.internal/payments"},
    },
}

app = FastAPI(title="Lab Authorization Server")


@app.post("/token")
def token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form(""),
    resource: str = Form(...),
):
    """The client_credentials grant — machine-to-machine, no user involved.

    'resource' is RFC 8707 (Resource Indicators). The client states WHICH API
    the token is for, and the IdP binds that into the 'aud' claim. This is the
    control that stops a token issued for the MCP server being replayed against
    a different API. MCP requires it for exactly that reason.
    """
    if grant_type != "client_credentials":
        raise HTTPException(400, "unsupported_grant_type")

    client = CLIENTS.get(client_id)
    # Constant-time compare avoids leaking the secret through timing.
    import hmac

    if not client or not hmac.compare_digest(client_secret, client["secret"]):
        raise HTTPException(401, "invalid_client")

    if resource not in client["allowed_audiences"]:
        raise HTTPException(400, "invalid_target")

    # Intersect what was ASKED for with what is ALLOWED. Never grant more.
    granted = sorted(set(scope.split()) & client["allowed_scopes"])
    if not granted:
        raise HTTPException(400, "invalid_scope")

    now = int(time.time())
    claims = {
        "iss": ISSUER,           # who minted it
        "sub": client_id,        # WHICH WORKLOAD this is — the audit identity
        "aud": resource,         # WHO it is for  <- audience binding
        "scope": " ".join(granted),  # WHAT it may do
        "iat": now,
        "exp": now + TOKEN_TTL,  # WHEN it dies
        "jti": str(uuid.uuid4()),  # unique id, for replay detection / audit
    }
    access_token = jwt.encode(
        claims, PRIVATE_PEM, algorithm="RS256", headers={"kid": KEY_ID}
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "scope": " ".join(granted),
    }


@app.get("/.well-known/jwks.json")
def jwks():
    """The PUBLIC half of the signing key.

    This is why JWT validation needs no call back to the IdP on every request:
    the resource server fetches this once, caches it, and verifies signatures
    locally. That is what makes token validation cheap enough to do per-request.
    """
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KEY_ID,
                "n": _b64(_public_numbers.n),
                "e": _b64(_public_numbers.e),
            }
        ]
    }


@app.get("/.well-known/openid-configuration")
def discovery():
    """Discovery document — how clients and resource servers find the endpoints."""
    return {
        "issuer": ISSUER,
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
    }
