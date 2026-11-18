# Image d'execution des scripts HANNIBAL X (RAG + Whisper GPU)
FROM python:3.12-slim
RUN pip install --no-cache-dir "psycopg[binary]" requests numpy scipy openpyxl faster-whisper \
    nvidia-cublas-cu12 nvidia-cudnn-cu12
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib
WORKDIR /hx
