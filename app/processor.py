import librosa
import numpy as np
from pathlib import Path
from basic_pitch.inference import predict
import pretty_midi
import os
import traceback

def filter_notes_by_onsets(midi_data: pretty_midi.PrettyMIDI, onset_times: np.ndarray, window_ms: float = 350):
    """
    Keep only notes that start near a detected physical onset (attack).
    This helps remove 'tail' notes and artifacts.
    """
    window_s = window_ms / 1000.0
    for inst in midi_data.instruments:
        filtered_notes = []
        for note in inst.notes:
            # Check if any detected onset is within the window of the note start
            dist = np.min(np.abs(onset_times - note.start))
            if dist <= window_s:
                filtered_notes.append(note)
        inst.notes = filtered_notes
    return midi_data

def transcribe_audio(
    audio_path: Path, 
    output_dir: Path, 
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 100, # ms
    minimum_frequency: float = None,
    maximum_frequency: float = None,
    use_dynamic_threshold: bool = True
) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
    
    print(f"[PROCESSOR] Transcribing audio with basic-pitch...")
    print(f"[PROCESSOR] Parameters: onset={onset_threshold}, frame={frame_threshold}, dynamic_filter={use_dynamic_threshold}")
    
    try:
        # predict returns (model_output, midi_data, note_events)
        _, midi_data, _ = predict(
            audio_path=str(audio_path),
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length,
            minimum_frequency=minimum_frequency,
            maximum_frequency=maximum_frequency
        )
        
        if use_dynamic_threshold:
            print("[PROCESSOR] Applying Dynamic Threshold (Onset Attack Detection)...")
            # Load audio for librosa onset detection
            y, sr = librosa.load(str(audio_path), sr=22050)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')
            
            # Filter notes
            midi_data = filter_notes_by_onsets(midi_data, onsets)
            
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