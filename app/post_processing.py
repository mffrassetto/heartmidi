import mido
from mido import Message, MidiFile
import pretty_midi
from pathlib import Path
import numpy as np
from app.formatter import (
    HEARTOPIA_ALLOWED_NOTES,
    clamp_to_heartopia_scale,
    quantize_timing,
    clean_short_notes,
    deduplicate_notes,
    limit_polyphony,
    shift_pitch,
    apply_heartopia_filters,
    convert_zero_velocity_to_note_off,
    enforce_channel_and_program
)

def merge_consecutive_notes(midi_path: Path, output_path: Path, max_gap_s: float = 0.05) -> Path:
    """Merge consecutive notes of same pitch if the gap between them is very small (jitter)."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    for inst in pm.instruments:
        if not inst.notes: continue
        
        inst.notes.sort(key=lambda x: x.start)
        merged = []
        current = inst.notes[0]
        
        for i in range(1, len(inst.notes)):
            next_note = inst.notes[i]
            # If same pitch and gap is small, merge
            if next_note.pitch == current.pitch and (next_note.start - current.end) <= max_gap_s:
                current.end = max(current.end, next_note.end)
            else:
                merged.append(current)
                current = next_note
        merged.append(current)
        inst.notes = merged
        
    pm.write(str(output_path))
    return output_path

def run_post_processing_pipeline(midi_path: Path, output_path: Path, bpm: float = 120.0):
    """
    Main entry point for the post-processing logic as requested.
    - Removes notes < 60ms
    - Merges consecutive notes (jitter)
    - Quantizes to BPM grid
    - Clamps to Heartopia 22-key scale
    """
    temp_path = output_path
    
    print(f"[POST-PROCESS] Starting pipeline for {midi_path}")
    
    # 1. Essential cleanup first
    apply_heartopia_filters(midi_path, temp_path)
    
    # 2. Shift pitch (0 offset as per last user request)
    shift_pitch(temp_path, temp_path, semitones=0)
    
    # 3. Merge jitter (consecutive notes) - reduced to 20ms to avoid losing fast repeats
    merge_consecutive_notes(temp_path, temp_path, max_gap_s=0.02)
    
    # 4. Remove short notes (< 40ms) - lowered from 60ms to preserve fast melodies
    clean_short_notes(temp_path, temp_path, min_duration_ms=40)
    
    # 5. Quantize to BPM grid (Subtle Quantize) - reduced strength to 0.8 to avoid merging notes
    quantize_timing(temp_path, temp_path, grid="1/16", strength=0.8, bpm=bpm)
    
    # 6. Clamp to Heartopia Scale (22 keys, C4-C7)
    clamp_to_heartopia_scale(temp_path, temp_path)
    
    # 7. Final Polish
    deduplicate_notes(temp_path, temp_path, overlap_threshold=0.8)
    limit_polyphony(temp_path, temp_path, max_simultaneous=16)
    convert_zero_velocity_to_note_off(temp_path, temp_path)
    enforce_channel_and_program(temp_path, temp_path)
    
    print(f"[POST-PROCESS] Pipeline complete: {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_post_processing_pipeline(Path(sys.argv[1]), Path(sys.argv[1]))
    else:
        print("Uso: python -m app.post_processing <arquivo.mid>")
