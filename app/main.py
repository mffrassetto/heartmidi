import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
import mido
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import aiofiles

app = FastAPI(title="Heartopia MIDI Converter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

class JobManager:
    def __init__(self):
        self.jobs = {}
    
    def create_job(self, source: str, url: Optional[str] = None, file_name: Optional[str] = None, 
                 instrument: str = "piano", apply_filters: bool = True) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "stage": "Iniciando...",
            "source": source,
            "url": url,
            "file_name": file_name,
            "instrument": instrument,
            "apply_filters": apply_filters,
            "output_file": None,
            "error": None,
            "note_count": 0,
            "duration": "00:00"
        }
        return job_id
    
    def update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
    
    def get_job(self, job_id: str):
        return self.jobs.get(job_id)
    
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
    return FileResponse("app/static/index.html")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/convert")
async def convert_audio(
    source: str = Form(...),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = Form(None),
    instrument: str = Form("piano"),
    apply_filters: bool = Form(True)
):
    try:
        file_name = "uploaded_file"
        
        if source == "url" and not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória quando source=url")
        
        if source == "file" and file:
            content = await file.read()
            file_name = file.filename or "uploaded_file"
            job_id = job_manager.create_job(source, file_name=file_name, 
                                        instrument=instrument, apply_filters=apply_filters)
            
            file_path = DATA_DIR / f"{job_id}.wav"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
        else:
            job_id = job_manager.create_job(source, url=url, file_name=url,
                                         instrument=instrument, apply_filters=apply_filters)

        asyncio.create_task(process_audio(job_id))
        
        return {"status": "processing", "job_id": job_id, "message": "Processamento iniciado"}
        
    except Exception as e:
        import traceback
        print(f"[ERRO] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def process_audio(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        print(f"[ERRO] Job {job_id} não encontrado")
        return
    
    try:
        job_manager.update_job(job_id, progress=10, stage="Baixando áudio...")
        
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
        else:
            normalized = DATA_DIR / f"{job_id}.wav"
        
        job_manager.update_job(job_id, progress=40, stage="Processando transcrição neural...")
        
        if job["source"] == "file" and job.get("file_name"):
            normalized = DATA_DIR / f"{job_id}.wav"
        
        from app.processor import transcribe_audio
        output_dir = DATA_DIR / f"{job_id}"
        output_dir.mkdir(exist_ok=True)
        midi_path = transcribe_audio(normalized, output_dir)
        
        job_manager.update_job(job_id, progress=70, stage="Aplicando filtros...")
        
        from app.formatter import clean_short_notes, transpose_to_range, apply_heartopia_filters
        
        filtered_midi = DATA_DIR / f"{job_id}.mid"
        
        if job.get("apply_filters", True):
            apply_heartopia_filters(midi_path, filtered_midi)
            clean_short_notes(filtered_midi, filtered_midi, min_duration_ms=50)
            transpose_to_range(filtered_midi, filtered_midi, min_note=36, max_note=84)
        else:
            import shutil
            shutil.copy(midi_path, filtered_midi)
        
        job_manager.update_job(job_id, progress=100, stage="Concluído!", 
                     status="completed", output_file=str(filtered_midi.resolve()),
                     note_count=job_manager.get_note_count(filtered_midi), 
                     duration=job_manager.get_duration(filtered_midi))
        
    except Exception as e:
        import traceback
        print(f"[ERRO no job {job_id}] {str(e)}")
        traceback.print_exc()
        job_manager.update_job(job_id, status="error", error=str(e))

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return job

@app.get("/download/{job_id}")
async def download_midi(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
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
        filename=f"heartopia_{job_id}.mid"
    )