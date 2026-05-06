FROM python:3.11-slim

WORKDIR /app

# Instalar Node.js para yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY .gitignore .
COPY README.md .

RUN mkdir -p /data

ENV PORT=3000
ENV COOKIES_FILE=/data/cookies.txt

EXPOSE 3000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT