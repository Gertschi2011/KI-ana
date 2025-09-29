import os
import requests
import uuid
from pathlib import Path

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Standard: Rachel

def synthesize(text: str, voice: str = ELEVEN_VOICE_ID, streaming: bool = False) -> str:
    """
    Wandelt Text mit ElevenLabs in Sprache um und speichert als MP3-Datei.
    """
    if not ELEVEN_API_KEY:
        raise ValueError("Fehlender ELEVEN_API_KEY in Umgebungsvariablen.")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"TTS-Fehler ({response.status_code}): {response.json().get('error', response.text)}")
    
    # Speichere Ausgabe als Audio-Datei
    output_dir = Path("tts_outputs")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"output_{uuid.uuid4().hex[:8]}.mp3"
    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"[🗣️ TTS gespeichert unter {filename}]")
    return str(filename)
