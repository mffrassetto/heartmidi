import numpy as np
from pathlib import Path
import basic_pitch.inference as inference_module
import basic_pitch
import pretty_midi
import os
import traceback
import librosa

def transcribe_audio(audio_path: Path, output_dir: Path) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")
    
    print(f"[PROCESSOR] Loading basic-pitch model...")
    model_path = basic_pitch.ICASSP_2022_MODEL_PATH
    print(f"[PROCESSOR] Model path: {model_path}")
    model_loaded = inference_module.Model(model_path)
    print(f"[PROCESSOR] Running inference on {audio_path}...")
    
    try:
        result = inference_module.run_inference(
            audio_path=str(audio_path),
            model_or_model_path=model_loaded,
            debug_file=None
        )
    except Exception as e:
        print(f"[PROCESSOR] Inference error: {e}")
        print(f"[PROCESSOR] Traceback: {traceback.format_exc()}")
        raise
    
    print(f"[PROCESSOR] Result keys: {result.keys() if result else 'None'}")
    
    if not result:
        raise RuntimeError("Falha ao gerar arquivo MIDI: resultado vazio")
    
    output_midi = output_dir / "output.mid"
    
    if 'midi' in result:
        with open(output_midi, 'wb') as f:
            f.write(result['midi'])
    elif 'note' in result or 'onset' in result or 'contour' in result:
        print(f"[PROCESSOR] Generating MIDI from model output...")
        
        import numpy as np
        
        onset_data = result.get('onset') or result.get('note')
        contour_data = result.get('contour') or result.get('note')
        
        if hasattr(onset_data, 'shape'):
            print(f"[PROCESSOR] Data shape: {onset_data.shape}")
        
        notes_list = []
        
if onset_data is not None:
            try:
                onset_arr = np.array(onset_data, dtype=np.float32)
            except Exception as e:
                print(f"[PROCESSOR] Error converting onset_data: {e}")
                onset_arr = np.zeros((1, 1), dtype=np.float32)
            
            try:
                if len(onset_arr.shape) == 2 and onset_arr.shape[1] <= 128:
                    onset_arr = onset_arr.T
                elif len(onset_arr.shape) > 2:
                    onset_arr = onset_arr.reshape(onset_arr.shape[0], -1)
                    if onset_arr.shape[1] > 128:
                        onset_arr = onset_arr[:, :128]
            except Exception as e:
                print(f"[PROCESSOR] Error reshaping: {e}")
                continue
            
            print(f"[PROCESSOR] Onset array shape: {onset_arr.shape}")
            
            try:
                onset_min = float(onset_arr.min())
                onset_max = float(onset_arr.max())
                print(f"[PROCESSOR] Onset min: {onset_min:.4f}, max: {onset_max:.4f}")
            except Exception as e:
                print(f"[PROCESSOR] Error getting min/max: {e}")
                onset_min = onset_max = 0.0
            
            fps = 22050 / 512
            min_onset_value = 0.3
            min_duration_frames = int(0.05 * fps)
            
            try:
                onset_thresholded = (onset_arr > min_onset_value).astype(np.float32)
                print(f"[PROCESSOR] Frames above threshold: {int(onset_thresholded.sum())}")
            except Exception as e:
                print(f"[PROCESSOR] Error in threshold: {e}")
                onset_thresholded = np.zeros_like(onset_arr)
            
            try:
                for pitch_idx in range(min(onset_arr.shape[0], 128)):
                    pitch_onsets = onset_arr[pitch_idx]
                    if pitch_onsets.ndim > 1:
                        pitch_onsets = pitch_onsets.flatten()
                    
                    try:
                        above_threshold = np.where(pitch_onsets > min_onset_value)[0]
                    except Exception as e:
                        print(f"[PROCESSOR] Error in where: {e}")
                        continue
                    
                    if len(above_threshold) == 0:
                        continue
                    
                    onsets_grouped = []
                    start = int(above_threshold[0])
                    
                    for i in range(1, len(above_threshold)):
                        if int(above_threshold[i]) - int(above_threshold[i-1]) > 10:
                            onsets_grouped.append(start)
                            start = int(above_threshold[i])
                    onsets_grouped.append(start)
                    
                    for t_start in onsets_grouped:
                        t_start_val = int(t_start)
                        t_end = t_start_val + min_duration_frames
                        if t_end < len(pitch_onsets):
                            try:
                                t_end = int(np.argmax(pitch_onsets[t_start_val:]) + t_start_val)
                            except:
                                t_end = t_start_val + min_duration_frames
                        else:
                            t_end = len(pitch_onsets) - 1
                        
                        notes_list.append([
                            t_start_val / fps,
                            t_end / fps,
                            pitch_idx + 21,
                            80
                        ])
            except Exception as e:
                print(f"[PROCESSOR] Error in pitch loop: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"[PROCESSOR] Created {len(notes_list)} notes")
        
        if not notes_list or len(notes_list) == 0:
            raise RuntimeError("Nenhuma nota detectada pelo modelo")
        
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(0)
        
        notes_added = 0
        for i, note in enumerate(notes_list):
            print(f"[PROCESSOR] Processing note {i}: {note}, type: {type(note)}")
            if isinstance(note, (list, tuple)) and len(note) >= 3:
                try:
                    start = float(note[0])
                    end = float(note[1])
                    pitch = int(note[2])
                    velocity = int(note[3]) if len(note) > 3 else 100
                    
                    if bool(end > start) and bool(start >= 0):
                        midi_note = pretty_midi.Note(
                            velocity=velocity,
                            pitch=pitch,
                            start=start,
                            end=end
                        )
                        instrument.notes.append(midi_note)
                        notes_added += 1
                        if notes_added <= 10:
                            print(f"[PROCESSOR] Added note: start={start}, end={end}, pitch={pitch}")
                except Exception as e:
                    print(f"[PROCESSOR] Error adding note: {e}")
        
        print(f"[PROCESSOR] Total notes added: {notes_added}")
        
        pm.instruments.append(instrument)
        print(f"[PROCESSOR] Writing MIDI file...")
        pm.write(str(output_midi))
        print(f"[PROCESSOR] MIDI written, size={output_midi.stat().st_size}")
    else:
        raise RuntimeError(f"Falha ao gerar arquivo MIDI: nenhuma chave compatível. chaves: {result.keys()}")
    
    if not output_midi.exists():
        raise RuntimeError("Falha ao gerar arquivo MIDI")
    
    print(f"[PROCESSOR] MIDI generated: {output_midi}")
    return output_midi