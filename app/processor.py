import librosa
import numpy as np
from pathlib import Path
from basic_pitch.inference import predict
import pretty_midi
import os
import traceback

def filter_notes_by_onsets(midi_data: pretty_midi.PrettyMIDI, onset_times: np.ndarray, window_ms: float = 600):
    """
    DEPRECATED — no longer called in the main pipeline.

    This filter was causing inner voices and legato notes to be silently dropped:
    notes that start during the sustain of another note have no detectable onset
    transient in librosa, so their distance to the nearest onset often exceeds
    any reasonable window. basic-pitch's own onset_threshold already handles
    artifact suppression, making this filter redundant and destructive.

    Kept for reference / manual debugging only.
    """
    window_s = window_ms / 1000.0
    for inst in midi_data.instruments:
        filtered_notes = []
        for note in inst.notes:
            if len(onset_times) == 0:
                filtered_notes.append(note)  # No onsets detected: keep all notes
                continue
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
            # Onset-based filtering has been disabled: it caused inner voices and
            # legato notes to be dropped because they lack a strong attack transient.
            # basic-pitch's onset_threshold=0.4 is already sufficient for noise control.
            print("[PROCESSOR] Dynamic onset filter skipped — relying on basic-pitch onset_threshold.")
            
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