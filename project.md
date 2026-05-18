# Documentação Técnica: heartmid
**Desenvolvedor: Maria Fernanda Frassetto - MFF Web Agency**

Este documento detalha a arquitetura, os algoritmos e as decisões de design do conversor Audio-to-MIDI e YouTube-to-MP3 **heartmid**.

## 1. Visão Geral da Arquitetura

O sistema é construído como uma aplicação distribuída em camadas:

-   **Interface (Frontend)**: Dashboard em HTML5/Vanilla JS integrado à FastAPI com um editor de Piano Roll completo e interativo.
-   **API (Backend)**: FastAPI gerenciando jobs assíncronos via `asyncio.create_task`.
-   **Motor de IA (Inference)**: `piano-transcription-inference` baseado no modelo de Kong et al. (2020).
-   **Processamento de Sinal (DSP)**: `librosa` e `ffmpeg` para normalização.
-   **Formatador MIDI**: Lógica de pós-processamento usando `mido` e `pretty_midi`.

---

## 2. Pipeline de Processamento (Step-by-Step)

### Etapa 1: Ingestão de Mídia (`downloader.py`)
-   Utiliza `yt-dlp` para extrair áudio de links externos.
-   Suporta downloads de MP3 em bitrates configuráveis.
-   Normaliza o áudio para WAV, 16.000 Hz, Mono (requisito do modelo de IA).

### Etapa 2: Transcrição Neural (`processor.py`)
-   **Modelo**: High-resolution Piano Transcription with Onset and Offset Detection.
-   **Vantagem**: Ao contrário de modelos mais simples (como Basic-Pitch), este modelo detecta com precisão o final da nota (offset), preservando a expressividade da performance original.
-   **Patch de Compatibilidade**: Implementa um monkey-patch no `torch.load` para garantir compatibilidade com versões recentes do PyTorch e evitar erros de `map_location`.

### Etapa 3: Pós-Processamento e Quantização (`formatter.py`)
Para produzir arquivos MIDI de alta qualidade, aplicamos:

1.  **Limpeza de Notas Curtas**: Notas residuais extremamente curtas são limpas para evitar ruídos de transcrição.
2.  **Quantização Rítmica (Opcional)**: Se ativado, o sistema detecta o BPM do áudio original e ajusta os onsets para o grid rítmico selecionado (1/16, 1/8, etc.) com força ajustável, refinando o tempo sem perder o "feel" musical humano.

---

## 3. Gestão de Jobs e Persistência

Os jobs são armazenados e monitorados em tempo real:
-   Arquitetura de fila de jobs assíncrona baseada em token de autorização.
-   Sincronização em tempo real do status e progresso do processamento usando Supabase para uma experiência de usuário rica e ágil.
-   Interface de download direto e edição de MIDI através do Piano Roll integrado.

---

## 4. Estrutura de Arquivos

```text
app/
├── main.py            # API, Rotas e Orquestração de Jobs
├── downloader.py      # Download (yt-dlp) e Normalização (FFmpeg)
├── processor.py       # Inferência de IA (Kong 2020)
├── formatter.py       # Pós-processamento e Filtros MIDI
└── static/            # Frontend (HTML/JS/CSS, Piano Roll Editor)
```

---

## 5. Manutenção e Debugging

-   **Logs**: O sistema gera logs detalhados no console de execução da aplicação FastAPI.
-   **Limpeza**: O diretório `data/` armazena os arquivos de áudio temporários e os MIDIs gerados.
-   **Memória**: O modelo neural consome aproximadamente 1.5GB de RAM durante a inferência.