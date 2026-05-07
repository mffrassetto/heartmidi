import numpy as np
from pathlib import Path
import pretty_midi
import os
import traceback

def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    # Legacy params kept for API compatibility — ignored by the new engine
    onset_threshold: float = 0.3,
    frame_threshold: float = 0.1,
    minimum_note_length: float = 50,
    minimum_frequency: float = None,
    maximum_frequency: float = None,
    use_dynamic_threshold: bool = True
) -> Path:
    """
    Transcribe a polyphonic piano audio file to MIDI using the
    piano-transcription-inference engine (Kong et al., 2020).

    This model was trained on the MAESTRO and MAPS datasets and explicitly
    detects both note onsets AND offsets, making it far superior to
    basic-pitch for:
      - Full polyphony (chords, multiple simultaneous voices)
      - Sustained notes with natural piano decay (correct Note-Off timing)
      - Synthesized piano timbres (Game instruments)

    Parameters
    ----------
    audio_path : Path
        Path to the input WAV/audio file.
    output_dir : Path
        Directory where output.mid will be written.
    onset_threshold, frame_threshold, minimum_note_length,
    minimum_frequency, maximum_frequency, use_dynamic_threshold :
        Retained for backward-compatibility with existing callers in main.py.
        The piano-transcription engine handles these internally.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    print(f"[PROCESSOR] Transcribing with piano-transcription-inference (Kong 2020)...")
    print(f"[PROCESSOR] Input: {audio_path}")

    try:
        import torch
        import librosa
        from piano_transcription_inference import PianoTranscription, sample_rate

        # ── Monkey-patch fix ──────────────────────────────────────────────────
        # piano_transcription_inference 0.0.6 passes map_location='auto' to
        # torch.load(), which PyTorch cannot resolve ("don't know how to restore
        # data location of UntypedStorage tagged with auto").
        # We intercept that call and force 'cpu' whenever 'auto' is requested.
        _original_torch_load = torch.load

        def _patched_torch_load(f, map_location=None, *args, **kwargs):
            if map_location == 'auto':
                map_location = 'cpu'
            return _original_torch_load(f, map_location=map_location, *args, **kwargs)

        torch.load = _patched_torch_load
        # ──────────────────────────────────────────────────────────────────────

        # Load and resample audio to the model's expected 16 kHz using librosa,
        # which uses libsndfile (already present in Docker) — avoids audioread issues.
        print(f"[PROCESSOR] Loading audio at {sample_rate} Hz via librosa...")
        audio, _ = librosa.load(str(audio_path), sr=sample_rate, mono=True)

        # Instantiate transcriber — checkpoint is downloaded on first run (~165 MB).
        # device='cpu' is explicit here; the monkey-patch above also guarantees it.
        transcriptor = PianoTranscription(device='cpu', checkpoint_path=None)

        output_midi = output_dir / "output.mid"

        # transcribe() writes the MIDI file directly and returns metadata
        result = transcriptor.transcribe(audio, str(output_midi))

        note_count = sum(
            1 for n in result.get('est_note_events', [])
        ) if result else 0

        print(f"[PROCESSOR] Transcription complete: {note_count} note events detected.")
        print(f"[PROCESSOR] MIDI written to: {output_midi}")

    except ImportError:
        raise RuntimeError(
            "piano-transcription-inference não está instalado.\n"
            "Execute: pip install piano-transcription-inference torch torchvision"
        )
    except Exception as e:
        print(f"[PROCESSOR] Transcription error: {e}")
        print(f"[PROCESSOR] Traceback: {traceback.format_exc()}")
        raise

    if not output_midi.exists():
        raise RuntimeError("Falha ao salvar arquivo MIDI após transcrição.")

    # Verify and log actual MIDI note count
    pm = pretty_midi.PrettyMIDI(str(output_midi))
    actual_count = sum(len(inst.notes) for inst in pm.instruments)
    print(f"[PROCESSOR] Verified MIDI note count: {actual_count} notes, "
          f"{output_midi.stat().st_size} bytes")

    return output_midi