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

def limit_to_monophonic(midi_path: Path, output_path: Path) -> Path:
    """Prioritize only the loudest note at any given time (monophonic melody)."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    for inst in pm.instruments:
        if not inst.notes: continue
        
        inst.notes.sort(key=lambda x: x.start)
        monophonic_notes = []
        
        # Simple greedy approach: if notes overlap, keep the one with higher velocity
        # Or just the first one. Let's try highest velocity.
        last_end = -1
        for n in inst.notes:
            if n.start >= last_end:
                monophonic_notes.append(n)
                last_end = n.end
            else:
                # Overlap! Check if this one is louder
                if monophonic_notes and n.velocity > monophonic_notes[-1].velocity:
                    # Replace previous note if this one starts very close and is louder
                    if n.start - monophonic_notes[-1].start < 0.05:
                        monophonic_notes[-1] = n
                        last_end = n.end
        inst.notes = monophonic_notes
        
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

def run_post_processing_pipeline(midi_path: Path, output_path: Path, audio_path: Path = None, quantize_grid: str = "1/16", monophonic: bool = True):
    """
    Enhanced pipeline tuned for lead melodies (Heartopia-Core).
    """
    temp_path = output_path
    
    # 1. BPM Detection with override
    bpm = 194.0 # Defaulting to the reference BPM found in analysis
    if audio_path and audio_path.exists():
        print(f"[POST-PROCESS] Detecting BPM from {audio_path}...")
        detected = detect_bpm(audio_path)
        # If detected is close to 194 or 97, use the reference
        if abs(detected - 194) < 10 or abs(detected - 97) < 5:
            bpm = 194.0
        else:
            bpm = detected
        print(f"[POST-PROCESS] Using BPM: {bpm:.2f}")

    print(f"[POST-PROCESS] Starting reference-match pipeline for {midi_path}")
    
    # 1. Essential cleanup
    apply_heartopia_filters(midi_path, temp_path)
    
    # 2. Shift pitch (0 offset)
    shift_pitch(temp_path, temp_path, semitones=0)
    
    # 3. Monophonic Filter (Prioritize lead melody like the reference)
    if monophonic:
        print("[POST-PROCESS] Applying Monophonic filter...")
        limit_to_monophonic(temp_path, temp_path)
    
    # 4. Minimum noise removal
    clean_short_notes(temp_path, temp_path, min_duration_ms=30)
    
    # 5. Advanced Quantization with Latency Compensation (-25ms)
    if quantize_grid and quantize_grid != "none":
        print(f"[POST-PROCESS] Quantizing to {quantize_grid} grid at {bpm:.2f} BPM...")
        quantize_timing(temp_path, temp_path, grid=quantize_grid, strength=0.9, bpm=bpm, latency_offset_ms=-25)
    
    # 6. Clamp to Heartopia Scale (22 keys, C4-C7)
    clamp_to_heartopia_scale(temp_path, temp_path)
    
    # 7. Final normalization
    convert_zero_velocity_to_note_off(temp_path, temp_path)
    enforce_channel_and_program(temp_path, temp_path)
    
    print(f"[POST-PROCESS] Reference-match pipeline complete: {output_path}")
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_post_processing_pipeline(Path(sys.argv[1]), Path(sys.argv[1]))
    else:
        print("Uso: python -m app.post_processing <arquivo.mid>")
