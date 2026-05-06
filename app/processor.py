import numpy as np
from pathlib import Path
from basic_pitch.inference import predict
import pretty_midi
import os
import traceback

def transcribe_audio(
    audio_path: Path, 
    output_dir: Path, 
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 100, # ms
    minimum_frequency: float = None,
    maximum_frequency: float = None
) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
    
    print(f"[PROCESSOR] Transcribing audio with basic-pitch...")
    print(f"[PROCESSOR] Parameters: onset={onset_threshold}, frame={frame_threshold}")
    
    try:
        # predict returns (model_output, midi_data, note_events)
        # midi_data is a pretty_midi.PrettyMIDI object
        _, midi_data, _ = predict(
            audio_path=str(audio_path),
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length,
            minimum_frequency=minimum_frequency,
            maximum_frequency=maximum_frequency
        )
    except Exception as e:
        print(f"[PROCESSOR] Prediction error: {e}")
        print(f"[PROCESSOR] Traceback: {traceback.format_exc()}")
        raise
    
    if not midi_data:
        raise RuntimeError("Falha ao gerar arquivo MIDI: nenhum dado retornado")
    
    output_midi = output_dir / "output.mid"
    
    # Calculate note count for logging
    note_count = sum(len(inst.notes) for inst in midi_data.instruments)
    print(f"[PROCESSOR] Writing MIDI file with {note_count} notes...")
    midi_data.write(str(output_midi))
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao salvar arquivo MIDI")
    
    print(f"[PROCESSOR] MIDI generated successfully: {output_midi} ({output_midi.stat().st_size} bytes)")
    return output_midi