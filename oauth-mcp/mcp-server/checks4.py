
"""Lab 34 stage 4 — inspect mcp_server/main.py WITHOUT importing it (no server start),
then run fastmcp's verifier on a fresh token.
 
    cd mcp_server && python checks4.py
"""
import ast, asyncio, json, logging, os, subprocess, sys
 
logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)s: %(message)s")
for noisy in ("httpx", "httpcore", "asyncio", "urllib3", "mcp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
 
print("python  :", sys.version.split()[0], "at", sys.executable)
import fastmcp
print("fastmcp :", fastmcp.__version__)
 
print("\n=== 0. process on port 9000 ===")
pids = subprocess.run(["lsof", "-nP", "-iTCP:9000", "-sTCP:LISTEN", "-t"],
                      capture_output=True, text=True).stdout.split()
if not pids:
    print("  NOTHING listening on 9000")
for pid in pids[:3]:
    cmd = subprocess.run(["ps", "-o", "command=", "-p", pid],
                         capture_output=True, text=True).stdout.strip()
    print(f"  pid {pid}: {cmd}")
    for line in subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                               capture_output=True, text=True).stdout.splitlines():
        if line.startswith("n"):
            print(f"           cwd {line[1:]}")
 
print("\n=== 1. JWTVerifier(...) as written in main.py  (parsed, not executed) ===")
path = sys.argv[1] if len(sys.argv) > 1 else "main.py"
try:
    tree = ast.parse(open(path).read(), filename=path)
except OSError as e:
    print("  cannot read", path, e); sys.exit(1)
 
def render(node):
    """Show the literal, and resolve os.getenv(NAME, default) against this env."""
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, (ast.List, ast.Tuple)):
        return "[" + ", ".join(render(e) for e in node.elts) + "]"
    if isinstance(node, ast.Call):
        fn = ast.unparse(node.func)
        if fn in ("os.getenv", "os.environ.get", "getenv"):
            name = render(node.args[0]).strip("'\"")
            dflt = render(node.args[1]) if len(node.args) > 1 else "None"
            live = os.getenv(name)
            got = repr(live) if live is not None else f"{dflt}  (env unset -> DEFAULT)"
            return f"{fn}({name!r}, {dflt}) -> {got}"
    return ast.unparse(node)
 
found = False
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "JWTVerifier":
        found = True
        for kw in node.keywords:
            print(f"  {kw.arg:16} = {render(kw.value)}")
if not found:
    print("  NO JWTVerifier(...) call found in", path, " <-- this file does not verify tokens")
 
guarded = any(isinstance(n, ast.If) and ast.unparse(n.test).replace(" ", "") == "__name__=='__main__'"
              for n in tree.body)
print(f"\n  has `if __name__ == '__main__':` guard : {guarded}")
 
print("\n=== 2. fastmcp's verifier, explicit known-good values, fresh token ===")
tok = json.loads(subprocess.run(
    ["curl", "-s", "-X", "POST", "http://localhost:9100/token",
     "-d", "grant_type=client_credentials", "-d", "client_id=payments-app",
     "-d", "client_secret=lab-secret-not-real", "-d", "scope=mcp:invoke",
     "-d", "resource=https://mcp.internal/payments"],
    capture_output=True, text=True).stdout)["access_token"]
from fastmcp.server.auth.providers.jwt import JWTVerifier
v = JWTVerifier(jwks_uri="http://localhost:9100/.well-known/jwks.json",
                issuer="http://localhost:9100",
                audience="https://mcp.internal/payments",
                required_scopes=["mcp:invoke"], algorithm="RS256")
print("  RESULT:", "ACCEPTED" if asyncio.run(v.verify_token(tok)) else "REJECTED")
 

