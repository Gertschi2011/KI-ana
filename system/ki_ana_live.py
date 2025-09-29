import os
import subprocess

print("🚀 KI_ana wird gestartet...")

BASE_DIR = os.path.expanduser("~/ki_ana")
LISTENER = os.path.join(BASE_DIR, "system", "conversation_listener.py")

if not os.path.exists(LISTENER):
    print("❌ Fehler: conversation_listener.py nicht gefunden.")
else:
    subprocess.run(["python3", LISTENER])
