# Video2ArabicSubs — web app image (desktop Tkinter app not included at runtime)
FROM python:3.11-slim

# FFmpeg: audio extraction fallback + subtitle burn-in (libass)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# CPU-only torch first — avoids multi-GB CUDA wheels on CPU Spaces
RUN pip install --no-cache-dir torch torchvision torchaudio \
      --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

# Whisper models + job data live on a volume so they survive restarts
ENV V2A_DATA_DIR=/data
VOLUME ["/data"]

# Hugging Face Spaces routes traffic to port 76 (override with -e PORT=…)
ENV PORT=76
EXPOSE 76

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','76')+'/api/health')" || exit 1

# shell form so ${PORT} expands
CMD uvicorn web.main:app --host 0.0.0.0 --port ${PORT}
