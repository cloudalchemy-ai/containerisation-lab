"""Application container — a FastAPI service that is an OAuth CLIENT.

Flow, every time /add is called:

  1. get a token from the IdP  (cached until it is nearly expired)
  2. call the MCP server with  Authorization: Bearer <token>
  3. return the tool's result

The token is fetched by the APP, for the APP's own identity. No user is
involved and no user credential is ever forwarded.
"""

import os
import time

import httpx
from fastapi import FastAPI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

IDP_TOKEN_URL = os.getenv("IDP_TOKEN_URL", "http://idp:9100/token")
MCP_URL = os.getenv("MCP_URL", "http://mcp:9000/mcp")
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "payments-app")
# Injected from a Secret. Never hard-coded, never logged.
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
# The API we want a token FOR. Binds the token to this one audience.
MCP_AUDIENCE = os.getenv("OAUTH_AUDIENCE", "https://mcp.internal/payments")

app = FastAPI(title="payments-app")

_cache: dict = {"token": None, "expires_at": 0.0}


def get_token() -> str:
    """Fetch an access token, reusing the cached one until it is nearly expired.

    Caching matters: without it every request costs a round trip to the IdP,
    and under load you will rate-limit yourself against your own identity
    provider. Refresh EARLY (60s before expiry) so a token never expires
    mid-flight.
    """
    if _cache["token"] and time.time() < _cache["expires_at"]:
        return _cache["token"]

    r = httpx.post(
        IDP_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "mcp:invoke",
            "resource": MCP_AUDIENCE,
        },
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    _cache["token"] = body["access_token"]
    _cache["expires_at"] = time.time() + body["expires_in"] - 60
    return _cache["token"]


@app.get("/add")
async def add(a: int = 2, b: int = 3):
    """Call the MCP server's add_numbers tool, authenticated with our token."""
    token = get_token()
    transport = StreamableHttpTransport(
        url=MCP_URL, headers={"Authorization": f"Bearer {token}"}
    )
    async with Client(transport) as client:
        result = await client.call_tool("add_numbers", {"a": a, "b": b})
    return {"a": a, "b": b, "sum": result.data}


@app.get("/health")
def health():
    return {"status": "ok"}