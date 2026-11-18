#!/usr/bin/env python3
"""Genere les fichiers audio du jeu de test : voix de synthese + effet radio VHF.

Usage :
    python generate_audio.py tests/testset.jsonl audio --voices voices/ [--limit 300]
                             [--categories clean_param,clean_fixed] [--seed 5]

Necessite : pip install piper-tts numpy scipy   (tout tourne en local, sur CPU)
Voix Piper (.onnx + .onnx.json) a placer dans le dossier --voices, par exemple
en_GB-alan-medium et en_US-ryan-medium (https://huggingface.co/rhasspy/piper-voices).

Pour chaque message, le script ecrit :
    audio/clean/<id>.wav   voix seule, 16 kHz mono
    audio/vhf/<id>.wav     meme voix passee dans la chaine radio simulee
    audio/manifest.csv     id, fichiers, voix, debit, rapport signal/bruit, texte

La chaine radio simulee : filtre passe-bande 300-3000 Hz, compression et
ecretage, bruit de fond a un niveau tire au hasard, bruit seul avant et apres
la parole (ouverture et fermeture du squelch). C'est une approximation destinee
aux tests ; elle ne remplace pas de vrais enregistrements VHF.
"""
import argparse
import csv
import json
import random
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

SR = 16000


def to_tts_text(spoken):
    """'CHARLIE THIS IS ALFA TURN STARBOARD NINER OVER' -> phrase lisible par la synthese."""
    t = " " + spoken + " "
    for marker in (" THIS IS ", " EXECUTE TO FOLLOW ", " IMMEDIATE EXECUTE ", " I SAY AGAIN ",
                   " STANDBY EXECUTE ", " OVER "):
        t = t.replace(marker, "," + marker.rstrip() + ", " if marker != " THIS IS " else ", this is ")
    t = t.strip(" ,").lower().replace(" ,", ",")
    t = t.replace("x-ray", "x ray").replace("xray", "x ray").replace("juliett", "juliet")
    t = t.replace("alfa", "alpha")           # prononciation ; le texte de reference reste ALFA
    return t.capitalize() + "."


def synth(voice, text, length_scale):
    from piper import SynthesisConfig
    cfg = SynthesisConfig(length_scale=length_scale)
    chunks = list(voice.synthesize(text, syn_config=cfg))
    audio = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float32)
    src = chunks[0].sample_rate
    if src != SR:
        audio = resample_poly(audio, SR, src).astype(np.float32)
    return audio


def vhf(audio, rng, snr_db):
    """Simule une reception VHF en phonie."""
    sos = butter(4, [300, 3000], btype="bandpass", fs=SR, output="sos")
    x = sosfilt(sos, audio)
    x = x / (np.max(np.abs(x)) + 1e-9)
    x = np.tanh(2.5 * x)                               # compression + ecretage doux
    lead = int(SR * rng.uniform(0.15, 0.4)); tail = int(SR * rng.uniform(0.15, 0.35))
    x = np.concatenate([np.zeros(lead), x, np.zeros(tail)])
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, 1, len(x))
    noise = sosfilt(butter(2, [200, 3400], btype="bandpass", fs=SR, output="sos"), noise)
    p_sig = np.mean(x[lead:len(x) - tail] ** 2)
    noise *= np.sqrt(p_sig / (10 ** (snr_db / 10)) / (np.mean(noise ** 2) + 1e-12))
    y = x + noise
    return (y / (np.max(np.abs(y)) + 1e-9) * 0.9).astype(np.float32)


def write_wav(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("testset"); ap.add_argument("out_dir")
    ap.add_argument("--voices", required=True, help="dossier contenant les voix Piper (.onnx)")
    ap.add_argument("--limit", type=int, default=0, help="nombre maximum de messages (0 = tous)")
    ap.add_argument("--categories", default="", help="categories a garder, separees par des virgules")
    ap.add_argument("--ids", default="", help="fichier texte listant les ID a generer")
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()

    from piper import PiperVoice
    rng = random.Random(a.seed)
    voices = {p.stem: PiperVoice.load(str(p)) for p in sorted(Path(a.voices).glob("*.onnx"))}
    if not voices:
        raise SystemExit(f"Aucune voix .onnx dans {a.voices}")
    cases = [json.loads(l) for l in Path(a.testset).read_text("utf-8").splitlines() if l.strip()]
    if a.categories:
        keep = set(a.categories.split(","))
        cases = [c for c in cases if c["category"] in keep]
    if a.ids:
        ids = set(Path(a.ids).read_text("utf-8").split())
        cases = [c for c in cases if c["id"] in ids]
    if a.limit and len(cases) > a.limit:
        cases = rng.sample(cases, a.limit)
        cases.sort(key=lambda c: c["id"])

    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    with open(out / "manifest.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "clean_wav", "vhf_wav", "voice", "length_scale", "snr_db",
                    "duration_s", "spoken_text", "written_text", "expected_signal"])
        for n, c in enumerate(cases, start=1):
            name = rng.choice(sorted(voices))
            scale = round(rng.uniform(0.85, 1.1), 2)       # debit de parole
            snr = round(rng.uniform(6, 25), 1)
            audio = synth(voices[name], to_tts_text(c["spoken_text"]), scale)
            write_wav(out / "clean" / f"{c['id']}.wav", audio)
            write_wav(out / "vhf" / f"{c['id']}.wav", vhf(audio, rng, snr))
            e = c["expected"]
            w.writerow([c["id"], c["category"], f"clean/{c['id']}.wav", f"vhf/{c['id']}.wav", name,
                        scale, snr, round(len(audio) / SR, 2), c["spoken_text"], c["written_text"],
                        e.get("signal") or e.get("base_signal", "")])
            if n % 50 == 0:
                print(f"{n}/{len(cases)}")
    print(f"{len(cases)} messages -> {out}")


if __name__ == "__main__":
    main()
