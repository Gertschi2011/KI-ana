import io, os, json, requests, hashlib
from typing import Dict
from PIL import Image

try:
    import whisper  # optional
except Exception:
    whisper = None

from storage_minio import presign_put

def sha256_hex(b: bytes) -> str:
    import hashlib
    h = hashlib.sha256(); h.update(b); return h.hexdigest()


def crawl_image(url: str) -> Dict:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    img_bytes = r.content
    # validate image
    Image.open(io.BytesIO(img_bytes)).verify()
    cid = sha256_hex(img_bytes)
    put = presign_put(cid)
    up = requests.put(put, data=img_bytes, timeout=60); up.raise_for_status()
    return {"cid": cid, "kind": "image"}


def crawl_audio(url: str) -> Dict:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    audio_bytes = r.content
    cid = sha256_hex(audio_bytes)
    text = ""
    if whisper:
        model = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            f.write(audio_bytes); f.flush()
            res = model.transcribe(f.name)
            text = res.get("text", "")
    meta = {"audio_cid": cid, "text": text}
    # upload audio
    put = presign_put(cid)
    up = requests.put(put, data=audio_bytes, timeout=60); up.raise_for_status()
    # upload transcript
    tbytes = json.dumps(meta, ensure_ascii=False).encode()
    t_cid = sha256_hex(tbytes)
    put2 = presign_put(t_cid)
    up2 = requests.put(put2, data=tbytes, timeout=60); up2.raise_for_status()
    return {"cid": cid, "transcript_cid": t_cid, "kind": "audio"}
