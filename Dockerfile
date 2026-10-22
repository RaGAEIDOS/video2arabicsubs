# Video2ArabicSubs — web app image (desktop Tkinter app not included at runtime)
FROM python:3.11-slim

# FFmpeg: audio extraction fallback + subtitle burn-in (libass)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Whisper models + job data live on a volume so they survive restarts
ENV V2A_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
