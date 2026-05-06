import yt_dlp
import subprocess
from pathlib import Path
import os

COOKIES_FILE = os.environ.get("COOKIES_FILE", "/data/cookies.txt")

def download_audio(url: str, output_path: Path) -> Path:
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / "audio"
    
    ydl_opts = {
        'format': '18',
        'outtmpl': str(output_file) + '.%(ext)s',
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {'player_client': ['android']},
        },
    }
    
    if Path(COOKIES_FILE).exists():
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    audio_file = output_path / "audio.mp4"
    if not audio_file.exists():
        audio_file = output_path / "audio.webm"
    
    if not audio_file.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado em {output_path}")
    
    return audio_file

def normalize_audio(input_path: Path, output_path: Path, sample_rate: int = 22050, channels: int = 1):
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-y', str(output_path)
    ]
    
    result = subprocess.run(cmd, check=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr.decode()}")
    
    return output_path