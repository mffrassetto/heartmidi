# Heartopia MIDI Converter 🎹

Transforme músicas do YouTube ou arquivos locais em arquivos MIDI de alta fidelidade, otimizados especificamente para o motor musical do jogo **Heartopia**.

O sistema utiliza o estado da arte em transcrição polifônica de piano (Kong et al., 2020) e aplica filtros inteligentes para garantir que o resultado seja 100% compatível com os instrumentos in-game.

---

## ✨ Funcionalidades

- **Transcrição de Alta Precisão**: Motor neural `piano-transcription-inference` treinado em datasets MAESTRO/MAPS, capaz de detectar onsets, offsets e velocidades precisas.
- **Suporte a YouTube**: Basta colar o link para baixar e converter.
- **Filtros Heartopia (Smart Engine)**:
    - **Escala Compatível**: Clamping automático para a escala de 22 teclas (Dó Maior, C4 a C7).
    - **Gestão de Polifonia**: Limite inteligente de até 6 notas simultâneas para evitar sobrecarga no motor do jogo.
    - **Limpeza de Ruído**: Remoção de artefatos de transcrição menores que 30ms.
    - **Quantização Opcional**: Ajuste rítmico (Grid Snapping) com detecção automática de BPM.
- **Interface Web Moderna**: Dashboard responsivo para gerenciar conversões, visualizar progresso e baixar resultados.

---

## 🛠️ Requisitos de Sistema

- **Python**: 3.10 ou 3.11 (Recomendado)
- **FFmpeg**: Necessário para processamento de áudio.
- **Arquitetura**: x86_64 ou ARM64 (macOS Silicon).

---

## 🚀 Instalação e Configuração

### 1. Clonar e Preparar Ambiente

```bash
# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 2. Instalar FFmpeg

- **macOS**: `brew install ffmpeg`
- **Ubuntu/Linux**: `sudo apt update && sudo apt install ffmpeg libsndfile1`

---

## 💻 Como Executar

Inicie o servidor FastAPI:

```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse a interface em: `http://localhost:8000`

---

## 📖 Estrutura Técnica

O pipeline de processamento segue estas etapas:

1.  **Ingestão**: Download via `yt-dlp` ou upload de arquivo.
2.  **Normalização**: Conversão para WAV 16kHz Mono via `ffmpeg`.
3.  **Inferência**: Processamento pelo modelo de rede neural (Kong 2020).
4.  **Pós-Processamento**:
    - Remoção de notas curtíssimas.
    - Limite de polifonia (6 vozes).
    - Mapeamento de escala (C4-C7).
    - Quantização rítmica (se solicitado).

---

## 📝 Licença

Desenvolvido para a comunidade de Heartopia.