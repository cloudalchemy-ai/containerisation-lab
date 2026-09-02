import os

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.jwt import JWTVerifier

# TIER 1 — the door. Identical to main.py.
auth = JWTVerifier(
    jwks_uri=os.getenv("OAUTH_JWKS_URI", "http://idp:9100/.well-known/jwks.json"),
    issuer=os.getenv("OAUTH_ISSUER", "http://idp:9100"),
    audience=os.getenv("OAUTH_AUDIENCE", "https://mcp.internal/payments"),
    required_scopes=["mcp:invoke"],          # coarse: may you enter at all
    algorithm="RS256",
)

mcp = FastMCP("payments-mcp", auth=auth)

# TIER 2 — one lock per room.
@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.tool(auth=require_scopes("payments:read"))
def get_payment_status(payment_id: str) -> dict:
    """Look up the status of a payment. Read-only."""
    return {"payment_id": payment_id, "status": "settled", "amount_minor": 4999}


@mcp.tool(auth=require_scopes("payments:write"))
def refund_payment(payment_id: str, amount_minor: int, idempotency_key: str) -> dict:
    """Refund a payment. Requires payments:write."""
    # The key is accepted but not yet checked — Step 5 adds the policy.
    return {"payment_id": payment_id, "refunded_minor": amount_minor,
            "idempotency_key": idempotency_key}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "9100")))
