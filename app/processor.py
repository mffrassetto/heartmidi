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
        print(f"[PROCESSOR] Note array type: {type(note_array)}")
        
        if hasattr(note_array, 'shape'):
            print(f"[PROCESSOR] Note array shape: {note_array.shape}")
        
        notes_list = note_array if isinstance(note_array, list) else note_array.tolist() if hasattr(note_array, 'tolist') else []
        
        print(f"[PROCESSOR] Notes list length: {len(notes_list)}")
        
        if not notes_list or len(notes_list) == 0:
            raise RuntimeError("Nenhuma nota detectada pelo modelo")
        
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(0)
        
        notes_added = 0
        for i, note in enumerate(notes_list):
            print(f"[PROCESSOR] Processing note {i}: {note}, type: {type(note)}")
            if isinstance(note, (list, tuple)) and len(note) >= 3:
                start = float(note[0])
                end = float(note[1])
                pitch = int(note[2])
                velocity = int(note[3]) if len(note) > 3 else 100
                
                if end > start and start >= 0:
                    midi_note = pretty_midi.Note(
                        velocity=velocity,
                        pitch=pitch,
                        start=start,
                        end=end
                    )
                    instrument.notes.append(midi_note)
                    notes_added += 1
                    if notes_added <= 10:
                        print(f"[PROCESSOR] Added note: start={start}, end={end}, pitch={pitch}")
        
        print(f"[PROCESSOR] Total notes added: {notes_added}")
        
        pm.instruments.append(instrument)
        print(f"[PROCESSOR] Writing MIDI file...")
        pm.write(str(output_midi))
        print(f"[PROCESSOR] MIDI written, size={output_midi.stat().st_size}")
    else:
        raise RuntimeError(f"Falha ao gerar arquivo MIDI: nenhuma chave compatível. chaves: {result.keys()}")
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao gerar arquivo MIDI")
    
    print(f"[PROCESSOR] MIDI generated: {output_midi}")
    return output_midi