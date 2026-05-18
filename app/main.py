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
from app.auth import get_current_user, get_current_admin, get_supabase_client, get_supabase_admin_client, SUPABASE_URL, SUPABASE_ANON_KEY
from supabase import acreate_client

import random
import string
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

app = FastAPI(title="heartmid", version="1.0.0")

class InviteCreateReq(BaseModel):
    max_uses: Optional[int] = 1
    expires_in_days: Optional[int] = None
    custom_code: Optional[str] = None

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
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY"),
        "turnstile_site_key": os.getenv("TURNSTILE_SITE_KEY"),
        "google_analytics_id": os.getenv("GOOGLE_ANALYTICS_ID")
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
        
        mp3_path = await asyncio.to_thread(download_youtube_mp3, job["url"], output_dir, bitrate=bitrate)
        
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
    normalize: bool = Form(True),
    user = Depends(get_current_user)
):
    try:
        if not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória")

        job_id = str(uuid.uuid4())
        source_dir = DATA_DIR / f"{job_id}_source"
        source_dir.mkdir(exist_ok=True)

        from app.downloader import download_audio, normalize_audio
        downloaded = await asyncio.to_thread(download_audio, url, source_dir)

        normalized_path = None
        if normalize:
            normalized_path = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                await asyncio.to_thread(normalize_audio, downloaded, normalized_path)
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
            
            downloaded = await asyncio.to_thread(download_audio, job["url"], audio_path)
            
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                await asyncio.to_thread(normalize_audio, downloaded, normalized)
            except Exception as e:
                print(f"[AVISO] FFmpeg não disponível, usando arquivo original: {e}")
                import shutil
                await asyncio.to_thread(shutil.copy, downloaded, normalized)
        elif job["source"] == "file" and job.get("file_name"):
            from app.downloader import normalize_audio
            from pathlib import Path as _Path
            orig_ext = _Path(job.get("file_name") or "").suffix or ""
            uploaded_path = DATA_DIR / f"{job_id}_uploaded{orig_ext}"
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
            try:
                await asyncio.to_thread(normalize_audio, uploaded_path, normalized)
            except Exception as e:
                print(f"[AVISO] FFmpeg não disponível, usando arquivo original: {e}")
                import shutil
                await asyncio.to_thread(shutil.copy, uploaded_path, normalized)
        else:
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
        
        await job_manager.update_job(job_id, token, progress=40, stage="Transcrevendo com piano-transcription (Kong 2020)...")
        
        from app.processor import transcribe_audio
        output_dir = DATA_DIR / f"{job_id}"
        output_dir.mkdir(exist_ok=True)
        
        midi_path = await asyncio.to_thread(
            transcribe_audio,
            normalized,
            output_dir
        )
        
        await job_manager.update_job(job_id, token, progress=70, stage="Processando MIDI...")
        
        filtered_midi = DATA_DIR / f"{job_id}.mid"
        
        import shutil
        await asyncio.to_thread(shutil.copy, midi_path, filtered_midi)
        
        metadata = job.get("metadata", {})
        quantize_str = metadata.get('quantize', 'none')
        if quantize_str and quantize_str != 'none':
            from app.formatter import quantize_timing, detect_bpm
            bpm = await asyncio.to_thread(detect_bpm, normalized)
            print(f"[PROCESS] BPM: {bpm:.2f}. Quantizing to {quantize_str} (strength=0.5)...")
            await asyncio.to_thread(quantize_timing, filtered_midi, filtered_midi, grid=quantize_str,
                            strength=0.5, bpm=bpm, latency_offset_ms=0)
        
        new_note_count = await asyncio.to_thread(job_manager.get_note_count, filtered_midi)
        new_duration = await asyncio.to_thread(job_manager.get_duration, filtered_midi)

        await job_manager.update_job(job_id, token, progress=100, stage="Concluído!", 
                     status="completed", output_file=str(filtered_midi.resolve()),
                     note_count=new_note_count, 
                     duration=new_duration)
        
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

@app.post("/save-midi/{job_id}")
async def save_midi(
    job_id: str,
    payload: dict,
    user = Depends(get_current_user)
):
    """
    Recebe a lista de notas editadas pelo usuário no frontend, reconstrói o arquivo
    MIDI usando pretty_midi e atualiza o Job no Supabase.
    """
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if str(job.get("user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    if job.get("job_type") != "midi":
        raise HTTPException(status_code=400, detail="Job não é do tipo MIDI")
    
    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="Arquivo de saída não definido para este job")
    
    file_path = Path(output_file)
    
    notes = payload.get("notes", [])
    if not isinstance(notes, list):
        raise HTTPException(status_code=400, detail="A lista de notas deve ser fornecida no campo 'notes'")
        
    try:
        import pretty_midi
        
        # 1. Reconstrói o MIDI básico usando pretty_midi
        pm = pretty_midi.PrettyMIDI()
        piano = pretty_midi.Instrument(program=0) # Piano padrão
        
        for n_data in notes:
            pitch = int(n_data["midi"])
            start = float(n_data["time"])
            end = start + float(n_data["duration"])
            
            # Normalização de velocity
            vel = n_data.get("velocity", 0.8)
            if isinstance(vel, float) and vel <= 1.0:
                velocity = int(vel * 127)
            else:
                velocity = int(vel)
            velocity = max(1, min(127, velocity))
            
            # Cria a nota e adiciona ao instrumento
            note = pretty_midi.Note(
                velocity=velocity,
                pitch=pitch,
                start=start,
                end=end
            )
            piano.notes.append(note)
            
        pm.instruments.append(piano)
        
        # Grava diretamente no disco
        await asyncio.to_thread(pm.write, str(file_path))
        
        # 3. Recalcula estatísticas finais
        new_note_count = await asyncio.to_thread(job_manager.get_note_count, file_path)
        new_duration = await asyncio.to_thread(job_manager.get_duration, file_path)
        
        # 4. Atualiza banco de dados Supabase via JobManager
        await job_manager.update_job(
            job_id,
            progress=100,
            stage="Concluído (Editado)",
            status="completed",
            note_count=new_note_count,
            duration=new_duration
        )
        
        return JSONResponse(
            content={
                "status": "completed",
                "message": "MIDI salvo e otimizado com sucesso!",
                "note_count": new_note_count,
                "duration": new_duration
            }
        )
        
    except Exception as e:
        import traceback
        print(f"[ERRO AO SALVAR MIDI {job_id}] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao salvar arquivo MIDI: {str(e)}")

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

# --- ADMIN AND INVITE ROUTES ---

@app.get("/admin/stats")
async def get_admin_stats(admin_user=Depends(get_current_admin)):
    try:
        client = await get_supabase_admin_client()
        
        # 1. Total users
        res_users = await client.table("profiles").select("id", count="exact").execute()
        total_users = res_users.count if hasattr(res_users, 'count') else len(res_users.data)
        
        # 2. Total active jobs (processing or pending)
        res_jobs = await client.table("jobs").select("id").in_("status", ["processing", "pending"]).execute()
        active_jobs = len(res_jobs.data)
        
        # 3. Total jobs
        res_all_jobs = await client.table("jobs").select("id", count="exact").execute()
        total_jobs = res_all_jobs.count if hasattr(res_all_jobs, 'count') else len(res_all_jobs.data)
        
        return {
            "total_users": total_users,
            "active_jobs": active_jobs,
            "total_jobs": total_jobs
        }
    except Exception as e:
        print(f"[ADMIN STATS ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao buscar estatísticas")

@app.get("/admin/invites")
async def list_invites(admin_user=Depends(get_current_admin)):
    try:
        client = await get_supabase_admin_client()
        
        # Get invites
        res_invites = await client.table("invite_codes").select("*").order("created_at", desc=True).execute()
        invites = res_invites.data
        
        # Get usages
        res_usages = await client.table("invited_users").select("*").order("created_at", desc=True).execute()
        usages = res_usages.data
        
        # Group usages by invite code
        usages_map = {}
        for usage in usages:
            code_id = usage.get("invite_code_id")
            if code_id not in usages_map:
                usages_map[code_id] = []
            usages_map[code_id].append({
                "email": usage.get("registered_email"),
                "date": usage.get("created_at")
            })
            
        for inv in invites:
            inv["used_by"] = usages_map.get(inv["id"], [])
            
        return invites
    except Exception as e:
        print(f"[ADMIN INVITES ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao buscar convites")

@app.post("/admin/invites")
async def create_invite(req: InviteCreateReq, admin_user=Depends(get_current_admin)):
    try:
        client = await get_supabase_admin_client()
        
        code = req.custom_code
        if not code:
            part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            code = f"HM-{part1}-{part2}"
            
        expires_at = None
        if req.expires_in_days:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)).isoformat()
            
        data = {
            "code": code,
            "created_by": admin_user.id,
            "max_uses": req.max_uses,
            "expires_at": expires_at
        }
        
        res = await client.table("invite_codes").insert(data).execute()
        return res.data[0]
    except Exception as e:
        print(f"[ADMIN CREATE INVITE ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao criar convite")

@app.post("/admin/invites/{invite_id}/deactivate")
async def deactivate_invite(invite_id: str, admin_user=Depends(get_current_admin)):
    try:
        client = await get_supabase_admin_client()
        res = await client.table("invite_codes").update({"is_active": False}).eq("id", invite_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Convite não encontrado")
        return {"success": True, "message": "Convite desativado"}
    except Exception as e:
        print(f"[ADMIN DEACTIVATE ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao desativar convite")

@app.get("/invites/validate/{code}")
async def validate_invite(code: str):
    try:
        client = await get_supabase_admin_client()
        res = await client.table("invite_codes").select("*").eq("code", code).execute()
        
        if not res.data:
            return {"valid": False, "reason": "Código não encontrado"}
            
        invite = res.data[0]
        
        if not invite["is_active"]:
            return {"valid": False, "reason": "Código inativo"}
            
        if invite["expires_at"]:
            from datetime import datetime, timezone
            expires = datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                return {"valid": False, "reason": "Código expirado"}
                
        if invite["max_uses"] is not None and invite["uses_count"] >= invite["max_uses"]:
            return {"valid": False, "reason": "Limite de usos atingido"}
            
        return {"valid": True, "code": invite["code"]}
    except Exception as e:
        print(f"[VALIDATE INVITE ERROR] {str(e)}")
        return {"valid": False, "reason": "Erro interno ao validar"}