import os, json, requests, pyttsx3

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

def tts(text: str, out_path: str = "tts_out.mp3"):
    if ELEVEN_API_KEY:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
        headers = {"xi-api-key": ELEVEN_API_KEY, "accept": "audio/mpeg", "content-type": "application/json"}
        data = {"text": text, "model_id": "eleven_multilingual_v2"}
        r = requests.post(url, headers=headers, data=json.dumps(data), timeout=30); r.raise_for_status()
        open(out_path, "wb").write(r.content); return out_path
    eng = pyttsx3.init(); eng.save_to_file(text, out_path); eng.runAndWait(); return out_path


def stt_wav(path: str) -> str:
    try:
        import whisper
        model = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))
        res = model.transcribe(path); return res.get("text","")
    except Exception:
        try:
            import vosk  # optional placeholder
            return "(vosk transcript placeholder)"
        except Exception:
            return ""
