import yt_dlp
import subprocess
from pathlib import Path
import os

COOKIES_FILE = os.environ.get("COOKIES_FILE", "/data/cookies.txt")

def download_audio(url: str, output_path: Path) -> Path:
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / "audio"
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': str(output_file) + '.%(ext)s',
        'nocheckcertificate': True,
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
    }
    
    if Path(COOKIES_FILE).exists():
        ydl_opts['cookiefile'] = COOKIES_FILE
        print(f"[INFO] Using cookies from {COOKIES_FILE}")
    else:
        print(f"[INFO] Cookies file not found at {COOKIES_FILE}, trying without authentication")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    audio_file = output_path / "audio.mp4"
    if not audio_file.exists():
        audio_file = output_path / "audio.webm"
    
    if not audio_file.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado em {output_path}")
    
    return audio_file

def normalize_audio(input_path: Path, output_path: Path, sample_rate: int = 22050, channels: int = 1):
    """
    Advanced Pre-processing:
    - EBU R128 Loudness Normalization
    - FFT Denoiser (afftdn) to remove background noise
    - Brickwall filters (100Hz - 8kHz) to isolate the piano range
    - Resampling to 22050Hz Mono
    """
    filters = [
        "loudnorm",
        "afftdn",      # Advanced Noise Reduction
        "highpass=f=100", 
        "lowpass=f=8000"
    ]
    
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-af', ",".join(filters),
        '-ar', str(sample_rate),
        '-ac', str(channels),
        str(output_path)
    ]
    
    print(f"[PRE-PROCESS] Running advanced audio isolation for {input_path}")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"[AVISO] Pré-processamento avançado falhou. Usando fallback.")
        cmd_simple = ['ffmpeg', '-y', '-i', str(input_path), '-ar', str(sample_rate), '-ac', str(channels), str(output_path)]
        subprocess.run(cmd_simple, check=True)
    
    return output_path