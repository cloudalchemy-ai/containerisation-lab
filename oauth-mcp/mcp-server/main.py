from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
import os

auth = JWTVerifier(
    # WHERE to get the public keys. Fetched and cached — not called per request.
    jwks_uri=os.getenv("OAUTH_JWKS_URI", "http://idp:9100/.well-known/jwks.json"),
    # WHO must have signed it. Stops a token from any other IdP being accepted.
    issuer=os.getenv("OAUTH_ISSUER", "http://idp:9100"),
    # WHO it was minted for. THIS IS THE ONE PEOPLE OMIT.
    # Without it, a token the app legitimately holds for ANY other API is
    # accepted here — the confused deputy problem. MCP calls this out explicitly.
    audience=os.getenv("OAUTH_AUDIENCE", "https://mcp.internal/payments"),
    # WHAT it is allowed to do. Authentication is not authorisation.
    required_scopes=["mcp:invoke"],
    # HOW it must have been signed. Pinned, so the token's own header cannot
    # choose — that is what closes alg:none and RS256->HS256 confusion.
    # Lab 31b demonstrates both attacks against a verifier that omits this.
    algorithm="RS256",
)

mcp = FastMCP("payments-mcp", auth=auth)


@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


mcp.run(
    transport="http",
    host="0.0.0.0",
    port=9000
)