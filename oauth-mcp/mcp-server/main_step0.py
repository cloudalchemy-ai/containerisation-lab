import os

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier

auth = JWTVerifier(
    jwks_uri=os.getenv("OAUTH_JWKS_URI", "http://idp:9100/.well-known/jwks.json"),
    issuer=os.getenv("OAUTH_ISSUER", "http://idp:9100"),
    audience=os.getenv("OAUTH_AUDIENCE", "https://mcp.internal/payments"),
    required_scopes=["mcp:invoke"],
    algorithm="RS256",
)
mcp = FastMCP("payments-mcp", auth=auth)

@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@mcp.tool
def refund_payment(payment_id: str, amount_minor: int) -> dict:
    """Refund a payment."""
    return {"payment_id": payment_id, "refunded_minor": amount_minor}

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",  # noqa: S104 — mandatory in a container; see Lab 2
        port=int(os.getenv("PORT", "9001")),
    )