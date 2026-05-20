import yt_dlp
import subprocess
from pathlib import Path
import os

COOKIES_FILE = os.environ.get("COOKIES_FILE", "/data/cookies.txt")

def download_audio(url: str, output_path: Path, start_time: int = None, end_time: int = None) -> Path:
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
    
    # Use glob to find the downloaded file regardless of extension
    # (yt-dlp may use .mp4, .webm, .m4a, .opus, .ogg, etc.)
    candidates = sorted(output_path.glob("audio.*"))
    if not candidates:
        raise FileNotFoundError(f"Arquivo de áudio não encontrado em {output_path}")
    
    downloaded = candidates[0]

    # Trim to time range if requested
    if start_time is not None or end_time is not None:
        trimmed = output_path / f"audio_trimmed{downloaded.suffix}"
        cmd = ['ffmpeg', '-y']
        if start_time:
            cmd += ['-ss', str(start_time)]
        cmd += ['-i', str(downloaded)]
        if end_time is not None:
            duration = end_time - (start_time or 0)
            cmd += ['-t', str(duration)]
        cmd += ['-c', 'copy', str(trimmed)]
        print(f"[TRIM] Cortando áudio: início={start_time}s, fim={end_time}s")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and trimmed.exists():
            return trimmed
        else:
            print(f"[AVISO] Falha ao cortar áudio, usando arquivo completo.")

    return downloaded

def normalize_audio(input_path: Path, output_path: Path, sample_rate: int = 22050, channels: int = 1, apply_filters: bool = True):
    """
    Pre-processing:
    - When apply_filters=True: EBU R128 Loudness Normalization + FFT Denoiser (afftdn)
      + Brickwall filters (100Hz - 8kHz) to isolate the piano range
    - When apply_filters=False: Basic resampling only (preserves original audio character)
    - Resampling to 22050Hz Mono
    """
    if apply_filters:
        filters = [
            "loudnorm",
            "afftdn",      # Advanced Noise Reduction
            "highpass=f=100",
            "lowpass=f=8000"
        ]
        af_args = ['-af', ",".join(filters)]
        print(f"[PRE-PROCESS] Running advanced audio isolation (apply_filters=True) for {input_path}")
    else:
        af_args = []
        print(f"[PRE-PROCESS] Basic resampling only (apply_filters=False) for {input_path}")

    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        *af_args,
        '-ar', str(sample_rate),
        '-ac', str(channels),
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"[AVISO] Pré-processamento falhou. Usando fallback simples.")
        cmd_simple = ['ffmpeg', '-y', '-i', str(input_path), '-ar', str(sample_rate), '-ac', str(channels), str(output_path)]
        subprocess.run(cmd_simple, check=True)
    
    return output_path

def download_youtube_mp3(url: str, output_path: Path, bitrate: str = "320k", start_time: int = None, end_time: int = None) -> Path:
    """
    Downloads audio from YouTube and converts it to MP3 with the specified bitrate.
    Optionally trims to a time range (start_time/end_time in seconds).
    """
    output_path.mkdir(parents=True, exist_ok=True)
    temp_file = output_path / "temp_audio"
    final_file = output_path / "audio.mp3"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(temp_file) + '.%(ext)s',
        'nocheckcertificate': True,
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
        'noplaylist': True,
    }
    
    if Path(COOKIES_FILE).exists():
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # Find the downloaded file
    candidates = list(output_path.glob("temp_audio.*"))
    if not candidates:
        raise FileNotFoundError(f"Falha ao baixar áudio de {url}")
    
    downloaded_file = candidates[0]
    
    # Build ffmpeg command with optional time range
    cmd = ['ffmpeg', '-y']
    if start_time:
        cmd += ['-ss', str(start_time)]
    cmd += ['-i', str(downloaded_file)]
    if end_time is not None:
        duration = end_time - (start_time or 0)
        cmd += ['-t', str(duration)]
    cmd += ['-ab', bitrate, str(final_file)]
    
    print(f"[CONVERT] Converting to MP3 with bitrate {bitrate}, start={start_time}s, end={end_time}s")
    result = subprocess.run(cmd, capture_output=True)
    
    # Clean up temp file
    if downloaded_file.exists():
        downloaded_file.unlink()
        
    if result.returncode != 0:
        raise Exception(f"Erro na conversão para MP3: {result.stderr.decode()}")
        
    return final_file