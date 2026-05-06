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
    enforce_channel_and_program,
    detect_bpm
)

def limit_to_monophonic(midi_path: Path, output_path: Path, tolerance_s: float = 0.1) -> Path:
    """
    Ensure only one note plays at a time, but with a small tolerance 
    to avoid cutting off fast legato transitions.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    for inst in pm.instruments:
        if not inst.notes: continue
        
        inst.notes.sort(key=lambda x: x.start)
        clean_notes = []
        last_end = -1
        
        for n in inst.notes:
            # If the gap is negative (overlap), check the severity
            if n.start >= last_end - tolerance_s:
                # If there's a slight overlap, just trim the previous note
                if clean_notes and n.start < last_end:
                    clean_notes[-1].end = n.start
                clean_notes.append(n)
                last_end = n.end
            else:
                # Severe overlap: only keep the loudest
                if clean_notes and n.velocity > clean_notes[-1].velocity:
                    clean_notes[-1] = n
                    last_end = n.end
        inst.notes = clean_notes
        
    pm.write(str(output_path))
    return output_path

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

def run_post_processing_pipeline(midi_path: Path, output_path: Path, audio_path: Path = None, quantize_grid: str = "1/16", monophonic: bool = False):
    """
    Universal pipeline: Auto-detects BPM and applies smart quantization.
    Monophonic is now DISABLED by default to preserve richness.
    """
    temp_path = output_path
    
    # 1. Fully Dynamic BPM Detection
    bpm = 120.0
    if audio_path and audio_path.exists():
        print(f"[POST-PROCESS] Detecting BPM from {audio_path}...")
        bpm = detect_bpm(audio_path)
        print(f"[POST-PROCESS] Detected BPM: {bpm:.2f}")

    print(f"[POST-PROCESS] Starting universal pipeline for {midi_path}")
    
    # 1. Essential cleanup
    apply_heartopia_filters(midi_path, temp_path)
    
    # 2. Shift pitch (0 offset)
    shift_pitch(temp_path, temp_path, semitones=0)
    
    # 3. Smart Monophonic Filter (Now Optional)
    if monophonic:
        print("[POST-PROCESS] Applying Smart Monophonic filter...")
        limit_to_monophonic(temp_path, temp_path, tolerance_s=0.1)
    
    # 4. Light Quantize (0.7 strength) with Latency Compensation (-25ms)
    if quantize_grid and quantize_grid != "none":
        print(f"[POST-PROCESS] Quantizing to {quantize_grid} grid at {bpm:.2f} BPM...")
        quantize_timing(temp_path, temp_path, grid=quantize_grid, strength=0.7, bpm=bpm, latency_offset_ms=-25)
    
    # 5. Clamp to Heartopia Scale (ESSENTIAL)
    clamp_to_heartopia_scale(temp_path, temp_path)
    
    # 6. Final normalization
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
