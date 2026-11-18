# Lecture de PDF par PaddleOCR-VL (essai). Version processeur : paquets pris sur PyPI, modeles pris sur Hugging Face.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir paddlepaddle==3.2.1 "paddleocr[doc-parser]" pymupdf
ENV PADDLE_PDX_MODEL_SOURCE=huggingface
WORKDIR /v2
