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
# Pin numpy<2 BEFORE installing torch to avoid ABI incompatibility.
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0"

# Install torch CPU version first to avoid CUDA dependencies (~2GB savings)
RUN pip install --no-cache-dir torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu


RUN pip install --no-cache-dir -r requirements.txt

# Pre-download model commented out to save RAM during build. 
# It will download on the first run instead.
# RUN python -c "from piano_transcription_inference import PianoTranscription; PianoTranscription(device='cpu')"


COPY app/ ./app/
COPY .gitignore .
COPY README.md .

RUN mkdir -p /data

ENV PORT=3000
ENV COOKIES_FILE=/data/cookies.txt

EXPOSE 3000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT