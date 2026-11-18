#!/usr/bin/env python3
"""Entraine (ajuste) le modele de reclassement bge-reranker-v2-m3 sur les paires question/passage du domaine.
Entree : data_train/train_rerank.jsonl. Sortie : models/reranker-hannibal/. Une epoque, demi-precision, GPU.
Usage (image hannibal-v2g, --gpus all) : python3 scripts/train_reranker.py data_train models/reranker-hannibal [--epochs 1] [--bs 8]"""
import json, os, sys, random, time, torch
os.environ.setdefault("HF_HOME", "/v2/models")
from transformers import AutoTokenizer, AutoModelForSequenceClassification
src, dst = sys.argv[1], sys.argv[2]
EP = int(sys.argv[sys.argv.index("--epochs") + 1]) if "--epochs" in sys.argv else 1
BS = int(sys.argv[sys.argv.index("--bs") + 1]) if "--bs" in sys.argv else 2
ACC = int(sys.argv[sys.argv.index("--acc") + 1]) if "--acc" in sys.argv else 4     # accumulation : lot effectif = BS x ACC
tok = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-m3"); model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-m3").cuda()
data = [json.loads(l) for l in open(os.path.join(src, "train_rerank.jsonl"), encoding="utf-8")]
random.seed(3); random.shuffle(data)
opt = torch.optim.AdamW(model.parameters(), lr=6e-6, weight_decay=0.01); scaler = torch.amp.GradScaler("cuda")
steps = EP * (len(data) // BS); upd = max(1, steps // ACC); sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 100) * max(0.0, 1 - s / upd))
model.train(); t0 = time.time(); step = 0; run = 0.0; opt.zero_grad(set_to_none=True)
for ep in range(EP):
    for i in range(0, len(data) - BS + 1, BS):
        batch = data[i:i + BS]
        # chaque exemple : 1 positif + 3 negatifs -> le modele doit classer le positif en tete (perte par liste)
        pairs = [(d["q"], t) for d in batch for t in [d["pos"]] + d["negs"]]
        x = tok([p[0] for p in pairs], [p[1] for p in pairs], padding=True, truncation="only_second", max_length=384, return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.float16):
            logits = model(**x).logits.view(len(batch), 4)
            loss = torch.nn.functional.cross_entropy(logits.float(), torch.zeros(len(batch), dtype=torch.long, device="cuda"))
        scaler.scale(loss / ACC).backward(); step += 1; run = 0.98 * run + 0.02 * loss.item() if step > 1 else loss.item()
        if step % ACC == 0:
            scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); scaler.step(opt); scaler.update(); sched.step(); opt.zero_grad(set_to_none=True)
        if step % 200 == 0: print(f"pas {step}/{steps} perte moyenne {run:.4f} {round((time.time() - t0) / step, 2)} s/pas", flush=True)
model.save_pretrained(dst); tok.save_pretrained(dst); print("FIN enregistre", dst, flush=True)
