# Documentação Técnica: Sistema de Transcrição Heartopia

Este documento detalha a arquitetura, os algoritmos e as decisões de design do conversor Audio-to-MIDI otimizado para o jogo Heartopia.

## 1. Visão Geral da Arquitetura

O sistema é construído como uma aplicação distribuída em camadas:

-   **Interface (Frontend)**: Dashboard em HTML5/Vanilla JS integrado à FastAPI.
-   **API (Backend)**: FastAPI gerenciando jobs assíncronos via `asyncio.create_task`.
-   **Motor de IA (Inference)**: `piano-transcription-inference` baseado no modelo de Kong et al. (2020).
-   **Processamento de Sinal (DSP)**: `librosa` e `ffmpeg` para normalização.
-   **Formatador MIDI**: Lógica customizada usando `mido` e `pretty_midi` para filtros de compatibilidade.

---

## 2. Pipeline de Processamento (Step-by-Step)

### Etapa 1: Ingestão de Mídia (`downloader.py`)
-   Utiliza `yt-dlp` para extrair áudio de links externos.
-   Suporta cookies para acesso a conteúdos restritos.
-   Normaliza o áudio para WAV, 16.000 Hz, Mono (requisito do modelo de IA).

### Etapa 2: Transcrição Neural (`processor.py`)
-   **Modelo**: High-resolution Piano Transcription with Onset and Offset Detection.
-   **Vantagem**: Ao contrário de modelos mais simples (como Basic-Pitch), este modelo detecta com precisão o final da nota (offset), o que é vital para instrumentos com sustain em Heartopia.
-   **Patch de Compatibilidade**: Implementa um monkey-patch no `torch.load` para garantir compatibilidade com versões recentes do PyTorch e evitar erros de `map_location`.

### Etapa 3: Filtros de Compatibilidade (`formatter.py`)
Para que o MIDI funcione perfeitamente no jogo, aplicamos:

1.  **Limpeza de Notas Curtas**: Notas < 30ms são removidas como ruído de transcrição.
2.  **Limite de Polifonia**: O motor do jogo suporta polifonia limitada em passagens densas. Limitamos a 6 notas simultâneas, priorizando as notas com maior *velocity* (intensidade).
3.  **Clamp de Escala (22 teclas)**: O piano de Heartopia possui um range fixo de 22 notas em Dó Maior (C4 a C7). Qualquer nota fora desse range é transposta por oitavas até entrar no limite ou removida se for excessivamente fora.
4.  **Quantização (Opcional)**: Se ativado, o sistema detecta o BPM do áudio via `analyzer.py` e ajusta os onsets para o grid (1/16, 1/8, etc.) com força de 50%, mantendo o "feel" humano mas corrigindo imprecisões.

---

## 3. Gestão de Jobs e Persistência

Os jobs são armazenados em `data/` como arquivos JSON (`{job_id}.job.json`). Isso permite:
-   Resiliência a reinicializações do servidor.
-   Monitoramento de progresso em tempo real via endpoint `/status/{job_id}`.
-   Download posterior de resultados.

---

## 4. Estrutura de Arquivos

```text
app/
├── main.py            # API, Rotas e Orquestração de Jobs
├── downloader.py      # Download (yt-dlp) e Normalização (FFmpeg)
├── processor.py       # Inferência de IA (Kong 2020)
├── formatter.py       # Pós-processamento e Filtros MIDI
├── analyzer.py        # Detecção de BPM e análise rítmica
└── static/            # Frontend (HTML/JS/CSS)
```

---

## 5. Manutenção e Debugging

-   **Logs**: O sistema gera logs detalhados no console e pode ser configurado para persistir em `server.log`.
-   **Limpeza**: Recomenda-se um script de limpeza periódica para a pasta `data/` para remover arquivos temporários antigos.
-   **Memória**: O modelo de IA consome aproximadamente 1.5GB de RAM durante a inferência.