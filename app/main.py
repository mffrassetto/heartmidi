import os
import uuid
import asyncio
import json
from pathlib import Path
from typing import Optional, Annotated
import mido
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import aiofiles
from app.auth import get_current_user, get_supabase_client, get_supabase_admin_client, SUPABASE_URL, SUPABASE_ANON_KEY
from supabase import acreate_client

app = FastAPI(title="heartmid", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

class JobManager:
    def __init__(self):
        pass
    
    async def create_job(self, client, user_id: str, source: str, **kwargs) -> str:
        data = {
            "user_id": user_id,
            "source": source,
            "status": "processing",
            "progress": 0,
            "stage": "Iniciando...",
            "instrument": kwargs.get("instrument", "piano"),
            "job_type": kwargs.get("job_type", "midi"),
            "url": kwargs.get("url"),
            "file_name": kwargs.get("file_name"),
            "output_file": kwargs.get("output_file"),
            "metadata": {
                "apply_filters": kwargs.get("apply_filters", True),
                "quantize": kwargs.get("quantize", "none"),
                "bitrate": kwargs.get("bitrate", "320k"),
                "note_count": 0,
                "duration": "00:00"
            }
        }
        try:
            res = await client.table("jobs").insert(data).execute()
            if not res.data:
                raise Exception("Falha ao criar job no Supabase (RLS Negado?)")
            return res.data[0]["id"]
        except Exception as e:
            print(f"[ERRO] Falha ao criar job: {e}")
            raise

    async def update_job(self, job_id: str, user_token: Optional[str] = None, **kwargs):
        # Usamos o cliente admin para garantir que as atualizações de progresso
        # funcionem em segundo plano, independente de RLS ou expiração de token.
        client = await get_supabase_admin_client()
        
        update_data = {}
        metadata_update = {}
        
        for k, v in kwargs.items():
            if k in ["status", "progress", "stage", "output_file", "error", "url", "file_name", "instrument", "job_type"]:
                update_data[k] = v
            else:
                metadata_update[k] = v
        
        if metadata_update:
            current_job = await self.get_job(job_id)
            if current_job:
                new_metadata = current_job.get("metadata", {})
                if not isinstance(new_metadata, dict):
                    new_metadata = {}
                new_metadata.update(metadata_update)
                update_data["metadata"] = new_metadata

        try:
            await client.table("jobs").update(update_data).eq("id", job_id).execute()
        except Exception as e:
            print(f"[ERRO] Falha ao atualizar job {job_id}: {e}")

    async def get_job(self, job_id: str):
        try:
            client = await get_supabase_admin_client()
            res = await client.table("jobs").select("*").eq("id", job_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[ERRO] get_job: {e}")
            return None
    
    def get_note_count(self, midi_path: Path) -> int:
        try:
            mid = mido.MidiFile(str(midi_path))
            return sum(1 for track in mid.tracks for msg in track if msg.type == 'note_on' and msg.velocity > 0)
        except:
            return 0
    
    def get_duration(self, midi_path: Path) -> str:
        try:
            mid = mido.MidiFile(str(midi_path))
            seconds = mid.length
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins:02d}:{secs:02d}"
        except:
            return "00:00"

job_manager = JobManager()

@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/config")
async def get_config():
    return {
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY")
    }

@app.post("/convert")
async def convert_audio(
    source: str = Form(...),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    instrument: str = Form("piano"),
    apply_filters: bool = Form(True),
    quantize: str = Form("none"),
    user = Depends(get_current_user),
    authorization: str = Header(None)
):
    try:
        file_name = "uploaded_file"
        
        if source == "url" and not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória quando source=url")
        
        from app.auth import get_supabase_admin_client
        admin_client = await get_supabase_admin_client()

        if source == "file" and file:
            content = await file.read()
            file_name = file.filename or "uploaded_file"
            job_id = await job_manager.create_job(admin_client, user.id, source, file_name=file_name, 
                                          instrument=instrument, apply_filters=apply_filters, quantize=quantize)
            
            from pathlib import Path as _Path
            ext = _Path(file_name).suffix or ""
            uploaded_path = DATA_DIR / f"{job_id}_uploaded{ext}"
            async with aiofiles.open(uploaded_path, 'wb') as f:
                await f.write(content)
        else:
            job_id = await job_manager.create_job(admin_client, user.id, source, url=url, file_name=url,
                                          instrument=instrument, apply_filters=apply_filters, quantize=quantize)

        token = authorization.split(" ")[1] if authorization else None
        asyncio.create_task(process_audio(job_id, token))
        
        return {"status": "processing", "job_id": job_id, "message": "Processamento iniciado"}
        
    except Exception as e:
        import traceback
        print(f"[ERRO] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/youtube-to-mp3")
async def youtube_to_mp3(
    url: str = Form(...),
    bitrate: str = Form("320k"),
    user = Depends(get_current_user),
    authorization: str = Header(None)
):
    try:
        if not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória")
        
        from app.auth import get_supabase_admin_client
        admin_client = await get_supabase_admin_client()
        
        job_id = await job_manager.create_job(admin_client, user.id, source="url", url=url, file_name=url, job_type="mp3", bitrate=bitrate)
        
        token = authorization.split(" ")[1] if authorization else None
        asyncio.create_task(process_mp3_task(job_id, token))
        
        return {"status": "processing", "job_id": job_id, "message": "Conversão para MP3 iniciada"}
        
    except Exception as e:
        import traceback
        print(f"[ERRO] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def process_mp3_task(job_id: str, token: Optional[str] = None):
    job = await job_manager.get_job(job_id)
    if not job:
        return
    
    try:
        await job_manager.update_job(job_id, token, progress=20, stage="Baixando do YouTube...")
        from app.downloader import download_youtube_mp3
        
        output_dir = DATA_DIR / f"{job_id}_mp3"
        output_dir.mkdir(exist_ok=True)
        
        metadata = job.get("metadata", {})
        bitrate = metadata.get("bitrate", "320k")
        if bitrate.isdigit():
            bitrate = f"{bitrate}k"
            
        await job_manager.update_job(job_id, token, progress=50, stage=f"Convertendo para MP3 ({bitrate})...")
        
        mp3_path = download_youtube_mp3(job["url"], output_dir, bitrate=bitrate)
        
        await job_manager.update_job(job_id, token, progress=100, stage="Concluído!", 
                             status="completed", output_file=str(mp3_path.resolve()))
        
    except Exception as e:
        import traceback
        print(f"[ERRO no job MP3 {job_id}] {str(e)}")
        traceback.print_exc()
        await job_manager.update_job(job_id, token, status="error", error=str(e))

@app.post("/fetch-audio")
async def fetch_audio(
    url: str = Form(...),
    normalize: bool = Form(True)
):
    try:
        if not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória")

        job_id = str(uuid.uuid4())
        source_dir = DATA_DIR / f"{job_id}_source"
        source_dir.mkdir(exist_ok=True)

        from app.downloader import download_audio, normalize_audio
        downloaded = download_audio(url, source_dir)

        normalized_path = None
        if normalize:
            normalized_path = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                normalize_audio(downloaded, normalized_path)
            except Exception as e:
                print(f"[AVISO] FFmpeg não disponível, mantendo arquivo original: {e}")
                normalized_path = None

        response = {
            "status": "downloaded",
            "job_id": job_id,
            "url": url,
            "downloaded_file": str(downloaded.resolve()),
            "normalized_file": str(normalized_path.resolve()) if normalized_path and normalized_path.exists() else None
        }
        return JSONResponse(response)
    except Exception as e:
        import traceback
        print(f"[ERRO fetch-audio] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def process_audio(job_id: str, token: Optional[str] = None):
    job = await job_manager.get_job(job_id)
    if not job:
        print(f"[ERRO] Job {job_id} não encontrado")
        return
    
    try:
        await job_manager.update_job(job_id, token, progress=10, stage="Baixando áudio...")
        
        if job["source"] == "url" and job.get("url"):
            from app.downloader import download_audio, normalize_audio
            audio_path = DATA_DIR / f"{job_id}_source"
            audio_path.mkdir(exist_ok=True)
            
            downloaded = download_audio(job["url"], audio_path)
            
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                normalize_audio(downloaded, normalized)
            except Exception as e:
                print(f"[AVISO] FFmpeg não disponível, usando arquivo original: {e}")
                import shutil
                shutil.copy(downloaded, normalized)
        elif job["source"] == "file" and job.get("file_name"):
            from app.downloader import normalize_audio
            from pathlib import Path as _Path
            orig_ext = _Path(job.get("file_name") or "").suffix or ""
            uploaded_path = DATA_DIR / f"{job_id}_uploaded{orig_ext}"
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                normalize_audio(uploaded_path, normalized)
            except Exception as e:
                print(f"[AVISO] FFmpeg não disponível, usando arquivo original: {e}")
                import shutil
                shutil.copy(uploaded_path, normalized)
        else:
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
        
        await job_manager.update_job(job_id, token, progress=40, stage="Transcrevendo com piano-transcription (Kong 2020)...")
        
        from app.processor import transcribe_audio
        output_dir = DATA_DIR / f"{job_id}"
        output_dir.mkdir(exist_ok=True)
        
        midi_path = transcribe_audio(
            normalized,
            output_dir
        )
        
        await job_manager.update_job(job_id, token, progress=70, stage="Aplicando filtros...")
        
        from app.formatter import clamp_to_heartopia_scale, limit_polyphony, clean_short_notes
        
        filtered_midi = DATA_DIR / f"{job_id}.mid"
        
        metadata = job.get("metadata", {})
        if metadata.get("apply_filters", True):
            print("[PROCESS] Applying minimal game-engine filters: Short-note removal, Polyphony(6), Scale Clamping.")

            clean_short_notes(midi_path, midi_path, min_duration_ms=30)
            limit_polyphony(midi_path, midi_path, max_simultaneous=6)

            quantize_str = metadata.get('quantize', 'none')
            if quantize_str and quantize_str != 'none':
                from app.formatter import quantize_timing, detect_bpm
                bpm = detect_bpm(normalized)
                print(f"[PROCESS] BPM: {bpm:.2f}. Quantizing to {quantize_str} (strength=0.5)...")
                quantize_timing(midi_path, midi_path, grid=quantize_str,
                                strength=0.5, bpm=bpm, latency_offset_ms=0)

            clamp_to_heartopia_scale(midi_path, filtered_midi)
        else:
            import shutil
            shutil.copy(midi_path, filtered_midi)
        
        await job_manager.update_job(job_id, token, progress=100, stage="Concluído!", 
                     status="completed", output_file=str(filtered_midi.resolve()),
                     note_count=job_manager.get_note_count(filtered_midi), 
                     duration=job_manager.get_duration(filtered_midi))
        
    except Exception as e:
        import traceback
        print(f"[ERRO no job {job_id}] {str(e)}")
        traceback.print_exc()
        await job_manager.update_job(job_id, token, status="error", error=str(e))

@app.get("/status/{job_id}")
async def get_status(job_id: str, user = Depends(get_current_user)):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    # RLS no banco já cuida disso se usarmos o cliente do usuário, 
    # mas como JobManager usa anon, verificamos aqui se o job pertence ao usuário
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    return JSONResponse(
        content=job,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )

@app.get("/download/{job_id}")
async def download_midi(job_id: str, user = Depends(get_current_user)):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Processamento não concluído")
    
    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    file_path = Path(output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/midi",
        filename=f"heartmid_{job_id}.mid",
        headers={"Cache-Control": "no-store"}
    )

@app.get("/download-mp3/{job_id}")
async def download_mp3(job_id: str, user = Depends(get_current_user)):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Processamento não concluído")
    
    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    file_path = Path(output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=f"heartmid_audio_{job_id}.mp3",
        headers={"Cache-Control": "no-store"}
    )

@app.get("/midi-data/{job_id}")
async def get_midi_data(job_id: str, user = Depends(get_current_user)):
    """Retorna o arquivo .mid em base64 para o player MIDI no frontend."""
    import base64
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    if job.get("job_type") != "midi":
        raise HTTPException(status_code=400, detail="Job não é do tipo MIDI")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Processamento não concluído")
    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="Arquivo de saída não definido")
    file_path = Path(output_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo .mid não encontrado no disco")
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return JSONResponse(
        content={
            "data": data,
            "filename": f"heartmid_{job_id}.mid",
            "note_count": job_manager.get_note_count(file_path),
            "duration": job_manager.get_duration(file_path)
        },
        headers={"Cache-Control": "no-store"}
    )

@app.get("/source/{job_id}")
async def get_source_audio(job_id: str, user = Depends(get_current_user)):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Prefer normalized file if present
    normalized = DATA_DIR / f"{job_id}_normalized.wav"
    if normalized.exists():
        return FileResponse(
            path=str(normalized.resolve()),
            media_type="audio/wav",
            filename=f"{job_id}_normalized.wav"
        )

    # Fallback to raw downloaded container in source dir
    source_dir = DATA_DIR / f"{job_id}_source"
    cand = None
    for name in ["audio.mp4", "audio.webm", "audio.m4a", "audio"]:
        p = source_dir / name
        if p.exists():
            cand = p
            break
    if not cand:
        raise HTTPException(status_code=404, detail="Arquivo de origem não encontrado")

    # Guess media type
    mt = "video/mp4" if cand.suffix == ".mp4" else ("video/webm" if cand.suffix == ".webm" else "application/octet-stream")
    return FileResponse(
        path=str(cand.resolve()),
        media_type=mt,
        filename=cand.name
    )