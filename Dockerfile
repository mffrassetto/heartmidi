FROM python:3.11-slim

WORKDIR /app

# Instalar Node.js para yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    wget \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Pin numpy<2 BEFORE installing torch/piano-transcription-inference to avoid
# the NumPy 2.x ABI incompatibility with torch binaries compiled for NumPy 1.x.
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0"
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the piano-transcription model checkpoint at build time (~100 MB)
# so the first conversion request is not blocked by a large download.
RUN python -c "from piano_transcription_inference import PianoTranscription; PianoTranscription(device='cpu')"

COPY app/ ./app/
COPY .gitignore .
COPY README.md .

RUN mkdir -p /data

ENV PORT=3000
ENV COOKIES_FILE=/data/cookies.txt

EXPOSE 3000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT