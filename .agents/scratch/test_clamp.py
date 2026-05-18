import numpy as np

HEARTOPIA_ALLOWED_NOTES = [
    60, 62, 64, 65, 67, 69, 71, # Octave 4
    72, 74, 76, 77, 79, 81, 83, # Octave 5
    84, 86, 88, 89, 91, 93, 95, # Octave 6
    96                          # C7
]

def test_clamp(note_val):
    allowed = np.array(HEARTOPIA_ALLOWED_NOTES)
    orig_note = note_val
    
    # Octave transposition
    if note_val < 60:
        while note_val < 60:
            note_val += 12
    elif note_val > 96:
        while note_val > 96:
            note_val -= 12
            
    idx = (np.abs(allowed - note_val)).argmin()
    clamped = int(allowed[idx])
    print(f"Orig: {orig_note} -> Transposed: {note_val} -> Clamped: {clamped}")
    return clamped

# Test values
test_clamp(48) # C3
test_clamp(50) # D3
test_clamp(52) # E3
test_clamp(36) # C2
test_clamp(72) # C5 (in range)
test_clamp(97) # C#7 (above range)
test_clamp(108) # C8
