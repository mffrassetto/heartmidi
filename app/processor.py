import numpy as np
from pathlib import Path
import basic_pitch.inference as inference_module
import basic_pitch
import pretty_midi
import os

def transcribe_audio(audio_path: Path, output_dir: Path) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
    
    print(f"[PROCESSOR] Loading basic-pitch model...")
    model_path = basic_pitch.ICASSP_2022_MODEL_PATH
    print(f"[PROCESSOR] Model path: {model_path}")
    model_loaded = inference_module.Model(model_path)
    print(f"[PROCESSOR] Running inference on {audio_path}...")
    
    try:
        result = inference_module.run_inference(
            audio_path=str(audio_path),
            model_or_model_path=model_loaded,
            debug_file=None
        )
    except Exception as e:
        print(f"[PROCESSOR] Inference error: {e}")
        raise
    
    output_midi = output_dir / "output.mid"
    print(f"[PROCESSOR] Result keys: {result.keys() if result else 'None'}")
    
    if result and 'midi' in result:
        with open(output_midi, 'wb') as f:
            f.write(result['midi'])
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao gerar arquivo MIDI")
    
    print(f"[PROCESSOR] MIDI generated: {output_midi}")
    return output_midi