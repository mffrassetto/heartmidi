import mido
from mido import MidiFile, MidiTrack, Message, tempo2bpm, bpm2tempo
import pretty_midi
from pathlib import Path
from typing import List, Tuple
import numpy as np

MIN_NOTE_DURATION_MS = 50 # Adjusted to 50ms as per project.md
DEFAULT_VELOCITY = 80

# Heartopia 22-key layout (3 octaves of C Major + C7)
# Range: C4 (60) to C7 (96)
# Notes: C, D, E, F, G, A, B
HEARTOPIA_ALLOWED_NOTES = [
    60, 62, 64, 65, 67, 69, 71, # Octave 4
    72, 74, 76, 77, 79, 81, 83, # Octave 5
    84, 86, 88, 89, 91, 93, 95, # Octave 6
    96                          # C7
]

def clamp_to_heartopia_scale(midi_path: Path, output_path: Path) -> Path:
    """Force all notes to the nearest valid key in the 22-key Heartopia layout."""
    mid = MidiFile(str(midi_path))
    allowed = np.array(HEARTOPIA_ALLOWED_NOTES)
    
    for track in mid.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                # Find nearest allowed note
                idx = (np.abs(allowed - msg.note)).argmin()
                msg.note = int(allowed[idx])
                
    mid.save(str(output_path))
    return output_path

def apply_heartopia_filters(midi_path: Path, output_path: Path) -> Path:
    """Keep only essential messages for game engines."""
    mid = MidiFile(str(midi_path))
    allowed_meta = {'set_tempo', 'time_signature', 'end_of_track'}
    allowed_channel = {'note_on', 'note_off', 'program_change', 'control_change'}
    
    for track in mid.tracks:
        filtered = []
        for msg in track:
            if msg.is_meta:
                if msg.type in allowed_meta:
                    filtered.append(msg)
            else:
                if msg.type in allowed_channel:
                    filtered.append(msg)
        track[:] = filtered
    
    mid.save(str(output_path))
    return output_path

def shift_pitch(midi_path: Path, output_path: Path, semitones: int = -12) -> Path:
    """Shift all notes by a fixed number of semitones."""
    mid = MidiFile(str(midi_path))
    for track in mid.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                new_note = msg.note + semitones
                msg.note = max(0, min(127, new_note))
    mid.save(str(output_path))
    return output_path

def detect_bpm(audio_path: Path) -> float:
    """Detect BPM of the audio file using Librosa."""
    import librosa
    try:
        y, sr = librosa.load(str(audio_path), sr=22050)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # tempo is usually returned as a float or an array
        if isinstance(tempo, (np.ndarray, list)):
            tempo = tempo[0]
        return float(tempo)
    except Exception as e:
        print(f"[AVISO] Falha ao detectar BPM: {e}")
        return 120.0

def quantize_timing(midi_path: Path, output_path: Path, grid: str = "1/16", strength: float = 1.0, bpm: float = None, latency_offset_ms: float = -25) -> Path:
    """
    Advanced quantization with latency compensation.
    latency_offset_ms: -25ms to compensate for processing delay.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    
    total_notes = sum(len(inst.notes) for inst in pm.instruments)
    if total_notes < 1:
        pm.write(str(output_path))
        return output_path

    tempo = bpm or 120.0
    grid_map = {"1/1":1, "1/2":2, "1/4":4, "1/8":8, "1/16":16, "1/32":32}
    spb = grid_map.get(grid, 16)
    
    seconds_per_beat = 60.0 / tempo
    step = seconds_per_beat / (spb / 4.0)
    offset_s = latency_offset_ms / 1000.0
    
    for inst in pm.instruments:
        for n in inst.notes:
            # Apply latency offset first
            n.start = max(0, n.start + offset_s)
            n.end = max(n.start + 0.05, n.end + offset_s)
            
            # Snap to grid
            target_start = round(n.start / step) * step
            n.start = n.start + strength * (target_start - n.start)
            
            # Snap end
            target_end = round(n.end / step) * step
            n.end = max(n.start + 0.05, n.end + strength * (target_end - n.end))
            
    pm.write(str(output_path))
    return output_path

def transpose_to_range(midi_path: Path, output_path: Path, min_note: int = 36, max_note: int = 84) -> Path:
    """
    Range adjusted to C2-C6 (common for game instruments) while preserving octave transpositions.
    
    NOTE: This function is MUTUALLY EXCLUSIVE with clamp_to_heartopia_scale.
    Calling both in sequence will double-transpose notes and produce incorrect results.
    For Heartopia game output, use clamp_to_heartopia_scale instead.
    """
    mid = MidiFile(str(midi_path))
    for track in mid.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                if msg.note < min_note:
                    # Try to transpose up by octaves instead of clipping
                    while msg.note < min_note:
                        msg.note += 12
                elif msg.note > max_note:
                    # Try to transpose down by octaves
                    while msg.note > max_note:
                        msg.note -= 12
                # Final clip just in case
                msg.note = max(min_note, min(max_note, msg.note))
    mid.save(str(output_path))
    return output_path

def clean_short_notes(midi_path: Path, output_path: Path, min_duration_ms: int = MIN_NOTE_DURATION_MS) -> Path:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    threshold_s = max(0.0, (min_duration_ms or 0) / 1000.0)
    for inst in pm.instruments:
        inst.notes = [n for n in inst.notes if (n.end - n.start) >= threshold_s]
    pm.write(str(output_path))
    return output_path

def normalize_velocity(midi_path: Path, output_path: Path, velocity: int = DEFAULT_VELOCITY) -> Path:
    mid = MidiFile(str(midi_path))
    vel = max(1, min(127, int(velocity)))
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                msg.velocity = vel
    mid.save(str(output_path))
    return output_path

def deduplicate_notes(midi_path: Path, output_path: Path, overlap_threshold: float = 0.5, snap_window_ms: float = 30.0) -> Path:
    """
    Refined Merge logic:
    1. Snaps notes starting within snap_window_ms to the same start time.
    2. Merges notes of same pitch that overlap or are extremely close.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    snap_s = snap_window_ms / 1000.0
    
    for inst in pm.instruments:
        if not inst.notes: continue
        
        # Step 1: Align starts (Chord Snapping)
        # Uses group-based clustering: all notes within snap_window_ms of the
        # group's anchor (first note) are aligned to that anchor.
        # This avoids the sequential propagation bug where pairwise snapping
        # could misalign notes in chords of 3+ simultaneous notes.
        inst.notes.sort(key=lambda x: x.start)
        group_anchor = inst.notes[0].start
        for i in range(1, len(inst.notes)):
            if inst.notes[i].start - group_anchor < snap_s:
                inst.notes[i].start = group_anchor
            else:
                group_anchor = inst.notes[i].start

        # Step 2: Merge overlapping same-pitch notes
        by_pitch = {}
        for n in inst.notes:
            by_pitch.setdefault(n.pitch, []).append(n)
        
        merged_all = []
        for pitch, notes in by_pitch.items():
            notes.sort(key=lambda x: x.start)
            merged = []
            if not notes: continue
            
            current = notes[0]
            for i in range(1, len(notes)):
                next_n = notes[i]
                # Merge if they overlap or are within 50ms of each other
                if next_n.start <= current.end + 0.05:
                    current.end = max(current.end, next_n.end)
                    current.velocity = max(current.velocity, next_n.velocity)
                else:
                    merged.append(current)
                    current = next_n
            merged.append(current)
            merged_all.extend(merged)
            
        inst.notes = sorted(merged_all, key=lambda x: x.start)
    
    pm.write(str(output_path))
    return output_path

def limit_polyphony(midi_path: Path, output_path: Path, max_simultaneous: int = 3) -> Path:
    """
    Limits simultaneous notes to max_simultaneous.
    Prioritizes notes with higher velocity (intensity) and higher pitch (melody).
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    for inst in pm.instruments:
        if len(inst.notes) <= max_simultaneous:
            continue
            
        # Sort notes by start time
        notes = sorted(inst.notes, key=lambda n: n.start)
        kept = []
        
        for n in notes:
            # Find notes that would overlap with this one
            active = [k for k in kept if k.start <= n.start < k.end]
            
            if len(active) < max_simultaneous:
                kept.append(n)
            else:
                # If we're at the limit, see if this new note is "better" than the weakest active note
                # "Better" = significantly higher velocity or much higher pitch
                # "Better" = significantly higher velocity (importance)
                # We reduced the pitch bias to avoid swallowing middle notes
                active.sort(key=lambda x: (x.velocity, x.pitch))
                weakest = active[0]
                
                if n.velocity >= weakest.velocity or (n.pitch > weakest.pitch and n.velocity >= weakest.velocity * 0.9):
                    # Replace weakest with this one, but truncate weakest's end time
                    weakest.end = n.start
                    kept.append(n)
                else:
                    # Skip this note to preserve polyphony limit
                    pass
        
        # Remove notes that were truncated to zero length
        inst.notes = [n for n in kept if n.end > n.start]
        
    pm.write(str(output_path))
    return output_path

def enforce_channel_and_program(midi_path: Path, output_path: Path, channel: int = 0, program: int = 0) -> Path:
    mid = MidiFile(str(midi_path))
    for track in mid.tracks:
        for msg in track:
            if not msg.is_meta and hasattr(msg, 'channel'):
                msg.channel = channel
            if not msg.is_meta and msg.type == 'program_change':
                msg.program = program
    
    # Ensure program change at start if missing
    if mid.tracks:
        has_pc = any(m.type == 'program_change' for m in mid.tracks[0])
        if not has_pc:
            mid.tracks[0].insert(0, Message('program_change', program=program, time=0, channel=channel))
            
    mid.save(str(output_path))
    return output_path

def convert_zero_velocity_to_note_off(midi_path: Path, output_path: Path) -> Path:
    """Normalize zero-velocity note_on messages to explicit note_off for better compatibility."""
    mid = MidiFile(str(midi_path))
    for tr in mid.tracks:
        for i, m in enumerate(tr):
            if not m.is_meta and m.type == 'note_on' and m.velocity == 0:
                tr[i] = Message('note_off', note=m.note, velocity=0, time=m.time, channel=getattr(m, 'channel', 0))
    mid.save(str(output_path))
    return output_path

def main():
    import sys
    if len(sys.argv) > 1:
        mid_file = Path(sys.argv[1])
        if mid_file.exists():
            print(f"Processando {mid_file}...")
            apply_heartopia_filters(mid_file, mid_file)
            clean_short_notes(mid_file, mid_file)
            deduplicate_notes(mid_file, mid_file)
            print("Concluído.")
    else:
        print("Uso: python -m app.formatter <arquivo.mid>")

if __name__ == "__main__":
    main()