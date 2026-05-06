import os
import uuid
import asyncio
import json
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

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

class JobManager:
    def __init__(self):
        self.jobs = {}
        self._load_persisted_jobs()
    
    def _job_file(self, job_id: str) -> Path:
        return DATA_DIR / f"{job_id}.job.json"
    
    def _load_persisted_jobs(self):
        """Load all persisted job states from disk on startup."""
        for f in DATA_DIR.glob("*.job.json"):
            try:
                with open(f, "r") as fh:
                    data = json.load(fh)
                    self.jobs[data["job_id"]] = data
            except Exception:
                pass
    
    def _persist(self, job_id: str):
        """Write current job state to disk."""
        try:
            data = {"job_id": job_id, **self.jobs[job_id]}
            with open(self._job_file(job_id), "w") as fh:
                json.dump(data, fh)
        except Exception as e:
            print(f"[AVISO] Não foi possível persistir job {job_id}: {e}")

    def create_job(self, source: str, url: Optional[str] = None, file_name: Optional[str] = None, 
                 instrument: str = "piano", apply_filters: bool = True, quantize: str = "1/16") -> str:
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
            "quantize": quantize,
            "output_file": None,
            "error": None,
            "note_count": 0,
            "duration": "00:00"
        }
        self._persist(job_id)
        return job_id
    
    def update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
            self._persist(job_id)
    
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
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/convert")
async def convert_audio(
    source: str = Form(...),
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    instrument: str = Form("piano"),
    apply_filters: bool = Form(True),
    quantize: str = Form("1/16")
):
    try:
        file_name = "uploaded_file"
        
        if source == "url" and not url:
            raise HTTPException(status_code=400, detail="URL é obrigatória quando source=url")
        
        if source == "file" and file:
            content = await file.read()
            file_name = file.filename or "uploaded_file"
            job_id = job_manager.create_job(source, file_name=file_name, 
                                         instrument=instrument, apply_filters=apply_filters, quantize=quantize)
            # Preserve original extension and save as uploaded source
            from pathlib import Path as _Path
            ext = _Path(file_name).suffix or ""
            uploaded_path = DATA_DIR / f"{job_id}_uploaded{ext}"
            async with aiofiles.open(uploaded_path, 'wb') as f:
                await f.write(content)
        else:
            job_id = job_manager.create_job(source, url=url, file_name=url,
                                          instrument=instrument, apply_filters=apply_filters, quantize=quantize)

        asyncio.create_task(process_audio(job_id))
        
        return {"status": "processing", "job_id": job_id, "message": "Processamento iniciado"}
        
    except Exception as e:
        import traceback
        print(f"[ERRO] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
        elif job["source"] == "file" and job.get("file_name"):
            # Normalize uploaded file to consistent WAV
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
            # Fallback: expect a pre-saved normalized wav
            normalized = DATA_DIR / f"{job_id}_normalized.wav"
        
        job_manager.update_job(job_id, progress=40, stage="Processando transcrição neural...")
        
        # normalized already computed above for both URL and file
        
        from app.processor import transcribe_audio
        output_dir = DATA_DIR / f"{job_id}"
        output_dir.mkdir(exist_ok=True)
        midi_path = transcribe_audio(
            normalized, 
            output_dir,
            onset_threshold=0.4, # More sensitive
            frame_threshold=0.3,
            use_dynamic_threshold=True
        )
        
        job_manager.update_job(job_id, progress=70, stage="Aplicando filtros...")
        
        from app.formatter import clamp_to_heartopia_scale, limit_polyphony, clean_short_notes, deduplicate_notes
        
        filtered_midi = DATA_DIR / f"{job_id}.mid"
        
        if job.get("apply_filters", True):
            # Apply essential game-engine filters
            print("[PROCESS] Applying game-engine filters: Noise Removal, Dedup, Polyphony(4), Quantization, Scale Clamping.")
            
            # Step 1: Remove artifacts and noise
            clean_short_notes(midi_path, midi_path, min_duration_ms=50)
            
            # Step 2: Align chords and merge same-pitch overlaps
            deduplicate_notes(midi_path, midi_path)
            
            # Step 3: Limit polyphony BEFORE quantization.
            # Quantize can snap staggered notes onto the same grid point, artificially
            # inflating simultaneous note count and causing limit_polyphony to discard
            # more notes than intended. Applying it first ensures we only drop notes
            # that were genuinely simultaneous in the original transcription.
            limit_polyphony(midi_path, midi_path, max_simultaneous=4)
            
            # Step 4: Quantize timing with auto-detected BPM and latency compensation
            from app.formatter import quantize_timing, detect_bpm
            bpm = detect_bpm(normalized)
            print(f"[PROCESS] Auto-detected BPM: {bpm:.2f}. Applying quantize ({job.get('quantize', '1/16')}) + latency compensation (-25ms)...")
            quantize_timing(midi_path, midi_path, grid=job.get('quantize', '1/16'), strength=0.7, bpm=bpm, latency_offset_ms=-25)
            
            # Step 5: Clamp to Heartopia scale (Final step)
            clamp_to_heartopia_scale(midi_path, filtered_midi)
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

@app.get("/source/{job_id}")
async def get_source_audio(job_id: str):
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