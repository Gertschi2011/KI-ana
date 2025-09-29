from fastapi import FastAPI, Body
from fastapi.responses import FileResponse
import os, json

APP_DIR = os.path.dirname(__file__)
SETTINGS_PATH = os.getenv("SETTINGS_JSON", os.path.join(APP_DIR, "settings.json"))

app = FastAPI(title="Settings UI")

@app.get("/")
def idx():
    return FileResponse(os.path.join(APP_DIR, "index.html"))

@app.get("/manifest.json")
def man():
    return FileResponse(os.path.join(APP_DIR, "manifest.json"))

@app.get("/sw.js")

def sw():
    return FileResponse(os.path.join(APP_DIR, "sw.js"))

@app.get("/api/settings")
def get_settings():
    if not os.path.exists(SETTINGS_PATH):
        return {"language":"de","ethics":"strict","subkis":"crawler"}
    return json.load(open(SETTINGS_PATH))

@app.post("/api/settings")

def set_settings(body: dict = Body(...)):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    json.dump(body, open(SETTINGS_PATH,"w"))
    return {"ok": True}
