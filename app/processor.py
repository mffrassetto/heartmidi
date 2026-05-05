import numpy as np
from pathlib import Path
import basic_pitch.inference as inference_module
import basic_pitch
import pretty_midi
import os

def transcribe_audio(audio_path: Path, output_dir: Path) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
    
    model_path = basic_pitch.ICASSP_2022_MODEL_PATH
    model_loaded = inference_module.Model(model_path)
    
    result = inference_module.run_inference(
        audio_path=str(audio_path),
        model_or_model_path=model_loaded,
        debug_file=None
    )
    
    output_midi = output_dir / "output.mid"
    if result and 'midi' in result:
        with open(output_midi, 'wb') as f:
            f.write(result['midi'])
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao gerar arquivo MIDI")
    
    return output_midi