#!/usr/bin/env python3
"""Transcrit les audios de test avec Whisper (faster-whisper), en local.

Usage :
    python transcribe.py audio/manifest.csv audio transcripts.csv
           [--set vhf] [--model small] [--device cpu] [--no-vocab] [--limit 150]

Sur le serveur (GPU) :  --model large-v3-turbo --device cuda
Necessite : pip install faster-whisper

--no-vocab desactive le vocabulaire OTAN fourni a Whisper (pour comparer).
Le fichier de sortie (id, transcript, confiance) se donne ensuite a evaluate.py :
    python evaluate.py kb/signals.json tests/testset.jsonl --transcripts transcripts.csv
"""
import argparse
import csv
import math
import wave
from pathlib import Path

import numpy as np

VOCAB = ("NATO maritime tactical signals. This is, over, out, execute to follow, immediate "
         "execute, I say again, standby, execute. Corpen, turn, speed, station, screen, "
         "formation, emergency, interrogative, desig, negat, tack, answer, port, starboard. "
         "Alfa, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel, India, Juliett, Kilo, Lima, "
         "Mike, November, Oscar, Papa, Quebec, Romeo, Sierra, Tango, Uniform, Victor, Whiskey, "
         "Xray, Yankee, Zulu. Zero, one, two, three, four, five, six, seven, eight, niner. "
         "Hannibal, all ships.")


def load_wav(path):
    """Lit un WAV 16 kHz mono 16 bits (format ecrit par generate_audio.py)."""
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "attendu : 16 kHz mono"
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest"); ap.add_argument("audio_dir"); ap.add_argument("out")
    ap.add_argument("--set", default="vhf", choices=["vhf", "clean"])
    ap.add_argument("--model", default="small")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--no-vocab", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device=a.device,
                         compute_type="float16" if a.device == "cuda" else "int8")
    with open(a.manifest, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[:: max(1, len(rows) // a.limit)][: a.limit]
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "transcript", "avg_confidence", "min_word_confidence", "reference"])
        for n, r in enumerate(rows, start=1):
            path = Path(a.audio_dir) / r[f"{a.set}_wav"]
            segs, _ = model.transcribe(load_wav(path), language="en", beam_size=5, word_timestamps=True,
                                       initial_prompt=None if a.no_vocab else VOCAB,
                                       condition_on_previous_text=False, vad_filter=False)
            segs = list(segs)
            text = " ".join(s.text.strip() for s in segs)
            words = [x for s in segs for x in (s.words or [])]
            probs = [x.probability for x in words] or [0.0]
            avg = math.exp(sum(s.avg_logprob for s in segs) / max(len(segs), 1)) if segs else 0.0
            w.writerow([r["id"], text, round(avg, 3), round(min(probs), 3), r["spoken_text"]])
            if n % 25 == 0:
                print(f"{n}/{len(rows)}", flush=True)
    print(f"{len(rows)} fichiers -> {a.out}")


if __name__ == "__main__":
    main()
