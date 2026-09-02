
"""Lab 34 stage 3 — run fastmcp's OWN verifier, in-process, and print why it says no.
Run from inside mcp_server/ with the SAME venv and SAME env vars you start the server with:
 
    cd mcp_server
    OAUTH_JWKS_URI=http://localhost:9100/.well-known/jwks.json \
    OAUTH_ISSUER=http://localhost:9100 \
    OAUTH_AUDIENCE=https://mcp.internal/payments \
    python checks3.py
"""
import asyncio, json, logging, os, subprocess, sys
 
logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)s: %(message)s")
for noisy in ("httpx", "httpcore", "asyncio", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
sys.path.insert(0, os.getcwd())
 
print("python      :", sys.version.split()[0], "at", sys.executable)
try:
    import fastmcp
    print("fastmcp     :", fastmcp.__version__)
except Exception as e:
    print("fastmcp import FAILED:", e); sys.exit(1)
 
print("env OAUTH_JWKS_URI:", os.getenv("OAUTH_JWKS_URI"))
print("env OAUTH_ISSUER  :", os.getenv("OAUTH_ISSUER"))
print("env OAUTH_AUDIENCE:", os.getenv("OAUTH_AUDIENCE"))
 
print("\n=== 0. what is actually running on port 9000 ===")
pid = subprocess.run(["lsof", "-nP", "-iTCP:9000", "-sTCP:LISTEN", "-t"],
                     capture_output=True, text=True).stdout.split()
if not pid:
    print("  NOTHING listening on 9000")
else:
    pid = pid[0]
    cmd = subprocess.run(["ps", "-o", "command=", "-p", pid],
                         capture_output=True, text=True).stdout.strip()
    print("  pid    :", pid)
    print("  command:", cmd)
    cwd = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                         capture_output=True, text=True).stdout
    for line in cwd.splitlines():
        if line.startswith("n"):
            print("  cwd    :", line[1:])
 
tok = subprocess.run(
    ["curl", "-s", "-X", "POST", "http://localhost:9100/token",
     "-d", "grant_type=client_credentials", "-d", "client_id=payments-app",
     "-d", "client_secret=lab-secret-not-real", "-d", "scope=mcp:invoke",
     "-d", "resource=https://mcp.internal/payments"],
    capture_output=True, text=True).stdout
tok = json.loads(tok)["access_token"]
print("token minted, length", len(tok))
 
print("\n=== A. your own main.py's verifier ===")
try:
    import main                      # safe: mcp.run() is behind __main__
    v = main.auth
    for f in ("jwks_uri", "issuer", "audience", "required_scopes", "algorithm"):
        print(f"  {f:16} = {getattr(v, f, '<absent>')!r}")
    r = asyncio.run(v.verify_token(tok))
    print("  RESULT:", "ACCEPTED" if r else "REJECTED  <-- reason is in the DEBUG/WARNING lines above")
except Exception as e:
    print("  could not use main.py's verifier:", type(e).__name__, e)
 
print("\n=== B. a verifier built from explicit known-good values ===")
from fastmcp.server.auth.providers.jwt import JWTVerifier
v2 = JWTVerifier(
    jwks_uri="http://localhost:9100/.well-known/jwks.json",
    issuer="http://localhost:9100",
    audience="https://mcp.internal/payments",
    required_scopes=["mcp:invoke"],
    algorithm="RS256",
)
r2 = asyncio.run(v2.verify_token(tok))
print("  RESULT:", "ACCEPTED" if r2 else "REJECTED  <-- fastmcp itself rejects a token PyJWT accepts")
 

