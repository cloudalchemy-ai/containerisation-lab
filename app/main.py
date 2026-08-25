# The if condition checks if the script is being run directly (not imported as a module).
# **Why that guard matters:** it means "only run `main() / myfn() ` if I am the entry point, not if someone imports me."
# __init__.py tells Python to treat a folder as a package and can optionally define what gets loaded when that package is imported.

# Lab-01

#def myfn():

#    print("Welcome to Deep Dive Containerization!")
#if __name__ == "__main__":
#    myfn()

#Lab02- I am creating a FastAPI application that will serve as the backend for my containerization lab. 
# This application will have several endpoints to demonstrate basic functionality, 
# including health checks and readiness probes.
# response: Response Give this function an HTTP Response object
# For development, /docs is one of the easiest ways to test your API 
# without needing curl or Postman.

# 0.0.0.0 means:
# “Listen on port 8080 on all network interfaces available to this machine/container.”
# Because Uvicorn is listening on all interfaces, a request sent to 127.0.0.1:8080 is accepted.




#    app.main:app
#    │   │     │
#    │   │     └── variable: app = FastAPI()
#    └──────────── folder/package: app
#    │   └──────── file: main.py

#    │
#Uvicorn server
#    ▼
#    │ listens on
# 0.0.0.0:8080
#    │
#    ├── accepts 127.0.0.1:8080
#    ├── accepts localhost:8080
#    ├── accepts 192.168.x.x:8080
#    └── accepts other interfaces

import os
import socket
import time

from fastapi import FastAPI

APP_MESSAGE = os.getenv("APP_MESSAGE", "Hello, Welcome to my Containerisation Lab!!")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
PORT     = int(os.getenv("PORT", "8080"))     # platform-agnostic contract
INSTANCE = socket.gethostname()               # in a Pod, this is the Pod name
STARTED  = time.monotonic()

app = FastAPI()

@app.get("/")
def root():
    return {"message": APP_MESSAGE, "instance": INSTANCE}

@app.get("/hello")
def hello(name: str = "world"):
    return {"greeting": f"Hello, {name}!", "instance": INSTANCE}

@app.get("/info")
def info():
    return {"version": APP_VERSION, "instance": INSTANCE,
            "uptime_seconds": round(time.monotonic() - STARTED, 3)}

@app.get("/health")          # LIVENESS — am I wedged?
def health():
    return {"status": "ok"}
