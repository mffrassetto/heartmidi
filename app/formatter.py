import mido
from mido import MidiFile, MidiTrack, Message, tempo2bpm, bpm2tempo
import pretty_midi
from pathlib import Path
from typing import List, Tuple

MIN_NOTE_DURATION_MS = 50
DEFAULT_VELOCITY = 64

def apply_heartopia_filters(midi_path: Path, output_path: Path) -> Path:
    mid = MidiFile(str(midi_path))
    # Keep only essential meta and note/program messages for game engines
    allowed_meta = {'set_tempo', 'time_signature', 'end_of_track'}
    allowed_channel = {'note_on', 'note_off', 'program_change'}
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

def quantize_timing(midi_path: Path, output_path: Path, grid: str = "1/16") -> Path:
    # Quantize by rounding note start/end times to nearest grid step using PrettyMIDI
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    total_notes = sum(len(inst.notes) for inst in pm.instruments)
    if total_notes < 2:
        # Not enough notes to estimate a tempo robustly; skip quantization
        pm.write(str(output_path))
        return output_path
    # Estimate a single representative tempo
    try:
        tempi = pm.estimate_tempo()
    except Exception:
        tempi = 120.0
    # Steps per beat
    grid_map = {"1/1":1, "1/2":2, "1/4":4, "1/8":8, "1/16":16, "1/32":32}
    spb = grid_map.get(grid, 16)
    if tempi <= 0:
        tempi = 120.0
    seconds_per_beat = 60.0 / tempi
    step = seconds_per_beat / spb
    for inst in pm.instruments:
        for n in inst.notes:
            n.start = round(n.start / step) * step
            n.end = max(n.start, round(n.end / step) * step)
    pm.write(str(output_path))
    return output_path

def transpose_to_range(midi_path: Path, output_path: Path, min_note: int = 36, max_note: int = 84) -> Path:
    mid = MidiFile(str(midi_path))
    for track in mid.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                if msg.note < min_note:
                    msg.note = min_note
                elif msg.note > max_note:
                    msg.note = max_note
    mid.save(str(output_path))
    return output_path

def clean_short_notes(midi_path: Path, output_path: Path, min_duration_ms: int = MIN_NOTE_DURATION_MS) -> Path:
    # Use PrettyMIDI for robust duration computation and filtering
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

def enforce_channel_and_program(midi_path: Path, output_path: Path, channel: int = 0, program: int = 0) -> Path:
    ch = max(0, min(15, int(channel)))
    prog = max(0, min(127, int(program)))
    mid = MidiFile(str(midi_path))
    # Ensure a program change exists at start of first non-meta track
    for t in mid.tracks:
        # Insert a program change at the beginning if none present
        has_pc = any((not m.is_meta and m.type == 'program_change') for m in t)
        if not has_pc:
            t.insert(0, Message('program_change', program=prog, time=0, channel=ch))
        # Normalize channel on channel messages
        for m in t:
            if not m.is_meta and hasattr(m, 'channel'):
                m.channel = ch
            if not m.is_meta and m.type == 'program_change':
                m.program = prog
        break
    mid.save(str(output_path))
    return output_path

def main():
    mid_files = list(Path("data").glob("*.mid"))
    for mid_file in mid_files:
        print(f"Processando {mid_file.name}...")
        temp_path = mid_file.with_suffix('.processed.mid')
        
        clean_short_notes(mid_file, temp_path, MIN_NOTE_DURATION_MS)
        apply_heartopia_filters(temp_path, temp_path)
        transpose_to_range(temp_path, temp_path)
        
        temp_path.rename(mid_file)
        print(f"Concluído: {mid_file.name}")

if __name__ == "__main__":
    main()