#!/usr/bin/env python3
"""Service HANNIBAL X : voix -> texte -> signal MTP, pour le simulateur.

Tourne sur le serveur, dans l'image hannibal-x, avec le GPU. Ecoute en local
seulement (127.0.0.1:8772). Whisper est charge une fois au demarrage.

    POST /voice       corps = fichier audio (WAV 16 kHz mono de preference)
                      -> {transcript, words, asr_seconds, interp}
    POST /interpret   {"text": "..."}            -> {interp}
    POST /explain     {"text": "..."}            -> explication EN/FR par le LLM (plus lent)
    GET  /health

Variables : HX_WHISPER (defaut small), HX_DEVICE (cuda), HX_PORT (8772),
HX_SHIPS (indicatifs ajoutes au vocabulaire).
"""
import io
import json
import os
import sys
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from interpret import KB, interpret          # noqa: E402
from transcribe import VOCAB                 # noqa: E402

KB_DIR = Path(os.environ.get("HX_KB", HERE.parent / "kb"))
MODEL = os.environ.get("HX_WHISPER", "small")
DEVICE = os.environ.get("HX_DEVICE", "cuda")
PORT = int(os.environ.get("HX_PORT", "8772"))
SHIPS = os.environ.get("HX_SHIPS", "Hannibal, Alfa, Charlie, Delta")

kb = KB(KB_DIR / "signals.json")
kb.by_id = {s["id"]: s for s in kb.signals}
asr_lock = Lock()
whisper = None


def load_whisper():
    global whisper
    from faster_whisper import WhisperModel
    try:
        whisper = WhisperModel(MODEL, device=DEVICE,
                               compute_type="float16" if DEVICE == "cuda" else "int8")
    except Exception as e:                       # pas de GPU disponible : repli sur le processeur
        print(f"GPU indisponible ({e}) : Whisper sur processeur", flush=True)
        whisper = WhisperModel(MODEL, device="cpu", compute_type="int8")


def read_audio(data):
    """Octets -> tableau float32 16 kHz mono."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getsampwidth() == 2:
                a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
                if w.getnchannels() > 1:
                    a = a.reshape(-1, w.getnchannels()).mean(axis=1)
                sr = w.getframerate()
                if sr != 16000:
                    n = int(len(a) * 16000 / sr)
                    a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
                return a
    except (wave.Error, EOFError):
        pass
    from faster_whisper.audio import decode_audio      # autres formats (webm, mp3...)
    return decode_audio(io.BytesIO(data), sampling_rate=16000)


def transcribe(data):
    t0 = time.time()
    audio = read_audio(data)
    with asr_lock:
        segs, _ = whisper.transcribe(audio, language="en", beam_size=5, word_timestamps=True,
                                     initial_prompt=VOCAB + " " + SHIPS + ".",
                                     condition_on_previous_text=False, vad_filter=False)
        segs = list(segs)
    words = [{"w": x.word.strip(), "p": round(float(x.probability), 3),
              "t0": round(float(x.start), 2), "t1": round(float(x.end), 2)}
             for s in segs for x in (s.words or [])]
    return {"transcript": " ".join(s.text.strip() for s in segs), "words": words,
            "duration_s": round(len(audio) / 16000, 2), "asr_seconds": round(time.time() - t0, 2),
            "asr_model": MODEL}


def public(res):
    """Resultat de l'interpreteur, sans les champs volumineux."""
    return {k: res.get(k) for k in ("status", "signal", "signal_id", "meaning", "reference", "params",
                                    "extra", "warnings", "to", "from", "method", "written_signal", "groups")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            return self._json({"ok": True, "whisper": MODEL, "signals": len(kb.signals)})
        self.send_error(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        data = self.rfile.read(n)
        try:
            if self.path == "/voice":
                out = transcribe(data)
                out["interp"] = public(interpret(out["transcript"], kb))
                return self._json(out)
            body = json.loads(data or b"{}")
            if self.path == "/interpret":
                return self._json({"interp": public(interpret(body.get("text", ""), kb))})
            if self.path == "/explain":
                import rag
                return self._json(rag.explain(body.get("text", ""), kb))
        except Exception as e:                    # l'appelant recoit l'erreur, le service reste debout
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        self.send_error(404)


if __name__ == "__main__":
    load_whisper()
    print(f"HANNIBAL X : service voix sur 127.0.0.1:{PORT} (Whisper {MODEL})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
