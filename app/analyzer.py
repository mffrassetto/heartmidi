import librosa
import numpy as np
import scipy.fftpack
from pathlib import Path
import sys

def analyze_peak_frequency(audio_path: str):
    print(f"Analisando: {audio_path}")
    
    # Load audio
    y, sr = librosa.load(audio_path, sr=None)
    
    # Apply FFT
    N = len(y)
    yf = scipy.fftpack.fft(y)
    xf = np.linspace(0.0, sr / 2.0, N // 2)  # Nyquist frequency
    
    # Find peak in the positive frequency range
    magnitudes = 2.0/N * np.abs(yf[:N//2])
    peak_idx = np.argmax(magnitudes)
    peak_freq = xf[peak_idx]
    
    # Reference for Middle C (C4)
    middle_c_ref = 261.63
    diff = peak_freq - middle_c_ref
    
    print("-" * 30)
    print(f"Frequência de Pico Detectada: {peak_freq:.2f} Hz")
    print(f"Referência (Dó Central):    {middle_c_ref:.2f} Hz")
    print(f"Desvio:                     {diff:+.2f} Hz")
    
    if abs(diff) > 0.1:
        correction_factor = middle_c_ref / peak_freq
        print(f"Fator de Correção sugerido: {correction_factor:.6f}")
    else:
        print("Nenhuma correção significativa necessária.")
    print("-" * 30)
    
    return peak_freq, diff

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_peak_frequency(sys.argv[1])
    else:
        print("Uso: python app/analyzer.py <caminho_do_audio>")
