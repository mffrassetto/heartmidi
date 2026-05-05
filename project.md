# Sistema de Transcrição Musical para Heartopia (Audio-to-MIDI)

Este documento contém a arquitetura técnica e as instruções de sistema para a implementação de um conversor de áudio (YouTube/MP3) para o formato MIDI compatível com os instrumentos do jogo Heartopia.

## 1. Escopo e Infraestrutura
Desenvolver uma API para ingestão, transcrição e filtragem de áudio. O sistema é projetado para deploy via containers Docker em uma infraestrutura de VPS com arquitetura x86_64 (gerenciável via Portainer ou Coolify).

## 2. Stack Tecnológica
*   **Linguagem Core:** Python 3.10+ (Ideal para bibliotecas de ML e DSP).
*   **Framework API:** FastAPI (Alta performance e geração automática de docs).
*   **Ingestão de Mídia:** `yt-dlp` (Para extração de áudio de URLs do YouTube).
*   **Motor de Transcrição (IA):** `basic-pitch` (Modelo de rede neural do Spotify para conversão Audio-to-MIDI).
*   **Processamento MIDI:** `mido` ou `pretty_midi` (Para aplicação dos filtros de escala e tempo).
*   **Dependência de Sistema:** `ffmpeg` (Essencial para conversão e normalização de áudio).

## 3. Pipeline de Processamento

### Etapa A: Ingestão e Normalização
1.  O endpoint da API recebe um arquivo de áudio (`.mp3`, `.wav`) ou uma URL.
2.  Caso seja URL, utilizar `yt-dlp` para baixar a stream de áudio.
3.  Processar o áudio via `ffmpeg` convertendo-o estritamente para **mono** e taxa de amostragem de **22050 Hz**.

### Etapa B: Inferência Neural
1.  Carregar o áudio normalizado no motor `basic-pitch`.
2.  Gerar o mapeamento inicial de frequências para eventos MIDI (Pitch, Onset, Offset, Velocity).

### Etapa C: Filtros de Compatibilidade Heartopia (Crítico)
Instrumentos in-game não suportam arquivos MIDI densos ou com sobreposição complexa. O script de manipulação MIDI (`mido`) deve obrigatoriamente aplicar:
1.  **Quantização (Grid Snapping):** Arredondar o tempo de início das notas para o compasso mais próximo (1/16 ou 1/8) para evitar que o motor do jogo "atropele" os sons.
2.  **Limpeza de Ruído:** Remover qualquer evento de nota com duração inferior a 50ms (geralmente falsos positivos da transcrição).
3.  **Achatamento de Melodia:** Em momentos de polifonia excessiva, isolar a melodia mantendo apenas a nota mais aguda ou a de maior *velocity*, removendo o excesso de notas simultâneas.
4.  **Transposição Automática:** Mapear e mover todas as notas resultantes para garantir que fiquem estritamente dentro das oitavas suportadas pelo instrumento do jogo (ex: C3 a C5).

## 4. Estrutura do Projeto
```text
/heartopia-converter
├── app/
│   ├── main.py            # Rotas da FastAPI (/convert)
│   ├── processor.py       # Lógica do Basic Pitch
│   ├── formatter.py       # Algoritmos do Filtro Heartopia (Mido)
│   └── downloader.py      # Lógica do yt-dlp
├── data/                  # Volume temporário para processamento (limpeza automática)
├── requirements.txt       # Dependências Python
└── Dockerfile             # Setup do ambiente x86_64 com FFmpeg e Python

##6. Dependências Adicionais Necessárias

### Python (requirements.txt)
Além das bibliotecas principais, incluir:
- `torch` - Necessário para o basic-pitch (PyTorch)
- `numpy` - Dependência fundamental para ML e DSP
- `librosa` - Opcional, para manipulação avançada de áudio

### Sistema (Dockerfile)
O basic-pitch requer bibliotecas nativas adicionais:
- `libsndfile1` - Para leitura de arquivos de áudio
- `libasound2-dev` - Para áudio ALSA (opcional)
- Verificar compatibilidade do basic-pitch com Python 3.10+

### Notas sobre Compatibilidade
- O `basic-pitch` pode ter conflitos de versão com bibliotecas Python recentes - testar versões específicas
- O `yt-dlp` pode precisar de dependências extras para alguns formatos de áudio
- Recomenda-se usar virtual environment para isolar dependências

##7. Instruções de Setup para o Agente de Código
Escrever o Dockerfile utilizando python:3.10-slim.
Adicionar RUN apt-get update && apt-get install -y ffmpeg libsndfile1 no Dockerfile.
No requirements.txt, incluir: basic-pitch, mido, yt-dlp, fastapi, uvicorn, python-multipart, torch, numpy.
Implementar o endpoint principal e expor a API na porta 8000.