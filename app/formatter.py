import mido
from mido import MidiFile, MidiTrack, Message, tempo2bpm, bpm2tempo
from pathlib import Path
from typing import List, Tuple

MIN_NOTE_DURATION_MS = 50
DEFAULT_VELOCITY = 64

def apply_heartopia_filters(midi_path: Path, output_path: Path) -> Path:
    mid = MidiFile(str(midi_path))
    
    for track in mid.tracks:
        messages = list(track)
        
        filtered_messages = []
        pending_noteoffs = {}
        
        i = 0
        while i < len(messages):
            msg = messages[i]
            
            if msg.type == 'note_on':
                note = msg.note
                velocity = msg.velocity
                time = msg.time
                
                if velocity > 0:
                    pending_noteoffs[note] = {'time': time, 'velocity': velocity}
                else:
                    if note in pending_noteoffs:
                        del pending_noteoffs[note]
                    
                    filtered_messages.append(msg)
            
            elif msg.type == 'note_off':
                note = msg.note
                if note in pending_noteoffs:
                    del pending_noteoffs[note]
                filtered_messages.append(msg)
            
            elif msg.type in ['text', 'marker', 'lyric']:
                pass
            
            else:
                filtered_messages.append(msg)
            
            i += 1
        
        track[:] = filtered_messages
    
    mid.save(str(output_path))
    return output_path

def quantize_timing(midi_path: Path, output_path: Path, grid: str = "1/16") -> Path:
    mid = MidiFile(str(midi_path))
    ticks_per_beat = mid.ticks_per_beat
    
    grid_fractions = {"1/4": 1, "1/8": 2, "1/16": 4, "1/32": 8}
    grid_multiplier = grid_fractions.get(grid, 4)
    
    for track in mid.tracks:
        cumulative_time = 0
        
        for msg in track:
            cumulative_time += msg.time
            
            if msg.type in ['note_on', 'note_off', 'pitchwheel']:
                aligned_ticks = (cumulative_time * grid_multiplier) // grid_multiplier
                msg.time = aligned_ticks - (cumulative_time - msg.time)
    
    mid.save(str(output_path))
    return output_path

def transpose_to_range(midi_path: Path, output_path: Path, min_note: int = 36, max_note: int = 84) -> Path:
    mid = MidiFile(str(midi_path))
    
    for track in mid.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off', 'note_at']:
                if msg.note < min_note:
                    msg.note = min_note
                elif msg.note > max_note:
                    msg.note = max_note
    
    mid.save(str(output_path))
    return output_path

def clean_short_notes(midi_path: Path, output_path: Path, min_duration_ms: int = MIN_NOTE_DURATION_MS) -> Path:
    mid = MidiFile(str(midi_path))
    ticks_per_ms = (mid.ticks_per_beat * 1000) / 500000
    min_ticks = int(min_duration_ms * ticks_per_ms)
    
    for track in mid.tracks:
        active_notes = {}
        new_messages = []
        
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = msg.time
                new_messages.append(msg)
            
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                note = msg.note
                if note in active_notes:
                    note_duration = msg.time - active_notes[note]
                    if note_duration >= min_ticks:
                        new_messages.append(msg)
                    del active_notes[note]
                else:
                    new_messages.append(msg)
            else:
                new_messages.append(msg)
        
        track[:] = new_messages
    
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