# Heartopia MIDI Converter

Converte áudio do YouTube ou arquivos locais para MIDI usando transcrição neural com Basic-Pitch.

## Preparação (Ubuntu/Linux)

```bash
# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar FFmpeg (necessário para áudio)
sudo apt install ffmpeg
```

## Ejecutar

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

- `POST /convert` - Converter áudio (source=url ou source=file)
- `GET /status/{job_id}` - Verificar progresso
- `GET /download/{job_id}` - Baixar arquivo MIDI

## Uso

```bash
# Via URL do YouTube
curl -X POST "http://localhost:8000/convert" \
  -F "source=url" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "instrument=piano"

# Via arquivo
curl -X POST "http://localhost:8000/convert" \
  -F "source=file" \
  -F "file=@audio.mp3"
```