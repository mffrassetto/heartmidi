import numpy as np
from pathlib import Path
import basic_pitch.inference as inference_module
import basic_pitch
import pretty_midi
import os
import traceback
import librosa

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
        print(f"[PROCESSOR] Traceback: {traceback.format_exc()}")
        raise
    
    print(f"[PROCESSOR] Result keys: {result.keys() if result else 'None'}")
    
    if not result:
        raise RuntimeError("Falha ao gerar arquivo MIDI: resultado vazio")
    
    output_midi = output_dir / "output.mid"
    
    if 'midi' in result:
        with open(output_midi, 'wb') as f:
            f.write(result['midi'])
    elif 'note' in result:
        print(f"[PROCESSOR] Generating MIDI from note events...")
        note_array = result['note']
        
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(0)
        
        for note in note_array:
            if len(note) >= 3:
                start = float(note[0])
                end = float(note[1])
                pitch = int(note[2])
                velocity = note[3] if len(note) > 3 else 100
                
                if end > start and start >= 0:
                    midi_note = pretty_midi.Note(
                        velocity=velocity,
                        pitch=pitch,
                        start=start,
                        end=end
                    )
                    instrument.notes.append(midi_note)
        
        pm.instruments.append(instrument)
        pm.write(str(output_midi))
    else:
        raise RuntimeError(f"Falha ao gerar arquivo MIDI: nenhuma chave compatível. chaves: {result.keys()}")
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao gerar arquivo MIDI")
    
    print(f"[PROCESSOR] MIDI generated: {output_midi}")
    return output_midi