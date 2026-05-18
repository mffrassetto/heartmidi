import mido
from mido import Message, MidiFile, MidiTrack
from pathlib import Path
from app.formatter import clamp_to_heartopia_scale, HEARTOPIA_ALLOWED_NOTES

def create_dummy_midi(midi_path: Path):
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)
    
    # Add note_on and note_off messages with different octave notes
    # C3 (48), D3 (50), E3 (52), C5 (72), C8 (108)
    notes = [48, 50, 52, 72, 108]
    for note in notes:
        track.append(Message('note_on', note=note, velocity=64, time=100))
        track.append(Message('note_off', note=note, velocity=0, time=100))
        
    mid.save(str(midi_path))

def main():
    test_dir = Path("/Users/maria/Documents/heartmidi/.agents/scratch")
    input_path = test_dir / "input_test.mid"
    output_path = test_dir / "output_test.mid"
    
    create_dummy_midi(input_path)
    print("Dummy MIDI created.")
    
    clamp_to_heartopia_scale(input_path, output_path)
    print("clamp_to_heartopia_scale completed successfully.")
    
    # Read the output MIDI to verify
    mid = MidiFile(str(output_path))
    print("\nVerifying Output Notes:")
    for msg in mid.tracks[0]:
        if msg.type == 'note_on':
            print(f"Note On: {msg.note}")

if __name__ == "__main__":
    main()
