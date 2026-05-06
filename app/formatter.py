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
    # Identify meta-only track (usually track 0) and instrument tracks
    meta_track_index = 0 if mid.tracks else -1
    # Remove any channel messages from the meta-only track first
    if meta_track_index >= 0 and meta_track_index < len(mid.tracks):
        t0 = mid.tracks[meta_track_index]
        t0[:] = [m for m in t0 if m.is_meta]
    # Now find first instrument track (skip meta track)
    instr_track_index = None
    for idx, t in enumerate(mid.tracks):
        if idx == meta_track_index:
            continue
        has_channel = any((not m.is_meta and hasattr(m, 'channel')) for m in t)
        if has_channel:
            instr_track_index = idx
            break
    # Default to track 1 if present
    if instr_track_index is None and len(mid.tracks) > 1:
        instr_track_index = 1
    # Ensure a program change at beginning of instrument track
    if instr_track_index is not None:
        t = mid.tracks[instr_track_index]
        has_pc = any((not m.is_meta and m.type == 'program_change') for m in t)
        if not has_pc:
            t.insert(0, Message('program_change', program=prog, time=0, channel=ch))
        # Normalize channel and program for all channel messages in instrument tracks
        for ti, tr in enumerate(mid.tracks):
            for m in tr:
                if not m.is_meta and hasattr(m, 'channel'):
                    m.channel = ch
                if not m.is_meta and m.type == 'program_change':
                    m.program = prog
    mid.save(str(output_path))
    return output_path

def convert_zero_velocity_to_note_off(midi_path: Path, output_path: Path) -> Path:
    mid = MidiFile(str(midi_path))
    for tr in mid.tracks:
        for i, m in enumerate(tr):
            if not m.is_meta and m.type == 'note_on' and m.velocity == 0:
                # Replace with explicit note_off preserving time/note/channel
                tr[i] = Message('note_off', note=m.note, velocity=0, time=m.time, channel=getattr(m, 'channel', 0))
    mid.save(str(output_path))
    return output_path

def deduplicate_notes(midi_path: Path, output_path: Path, start_threshold_ms: int = 12, min_gap_ms: int = 8) -> Path:
    """Merge duplicate/overlapping notes per pitch after quantization.
    - start_threshold_ms: merge notes of same pitch whose starts are within this window
    - min_gap_ms: treat tiny gaps between consecutive notes of same pitch as legato, merge them
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    thr = max(0.0, (start_threshold_ms or 0) / 1000.0)
    gap = max(0.0, (min_gap_ms or 0) / 1000.0)
    for inst in pm.instruments:
        by_pitch = {}
        for n in inst.notes:
            by_pitch.setdefault(n.pitch, []).append(n)
        merged_all = []
        for pitch, notes in by_pitch.items():
            notes.sort(key=lambda x: (x.start, x.end))
            merged = []
            for n in notes:
                if not merged:
                    merged.append(n)
                    continue
                last = merged[-1]
                # Same pitch, near-same start or overlapping/near-tie
                if abs(n.start - last.start) <= thr or n.start <= (last.end + gap):
                    if n.end > last.end:
                        last.end = n.end
                else:
                    merged.append(n)
            merged_all.extend(merged)
        # Preserve instrument attrs; replace notes with merged set sorted by start
        inst.notes = sorted(merged_all, key=lambda x: (x.start, x.end))
    pm.write(str(output_path))
    return output_path

def limit_polyphony(midi_path: Path, output_path: Path, max_simultaneous: int = 6, same_start_ms: int = 15) -> Path:
    """Limit number of simultaneously starting notes per pitch group.
    Heuristic: if more than max_simultaneous notes start within same_start_ms,
    keep the lowest pitches (favor fundamentals) and drop the rest.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    eps = max(0.0, (same_start_ms or 0) / 1000.0)
    for inst in pm.instruments:
        notes = sorted(inst.notes, key=lambda n: (n.start, n.pitch))
        kept = []
        i = 0
        while i < len(notes):
            s0 = notes[i].start
            group = [notes[i]]
            j = i + 1
            while j < len(notes) and abs(notes[j].start - s0) <= eps:
                group.append(notes[j])
                j += 1
            if len(group) > max_simultaneous:
                group = sorted(group, key=lambda n: n.pitch)[:max_simultaneous]
            kept.extend(group)
            i = j
        inst.notes = sorted(kept, key=lambda n: (n.start, n.pitch))
    pm.write(str(output_path))
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