# Documentação da API de Integração com YouTube - heartmid

Esta documentação descreve os endpoints e a lógica de processamento para a integração com o YouTube no sistema **heartmid**. O sistema utiliza `yt-dlp` para extração de áudio e `ffmpeg` para conversão e normalização.

## 1. Visão Geral
A integração com o YouTube permite que os usuários:
1.  Convertam vídeos do YouTube diretamente para arquivos MIDI (otimizados para o motor de jogo Heartopia).
2.  Extraiam áudio de vídeos do YouTube em formato MP3 com qualidade configurável (até 320kbps).

---

## 2. Endpoints da API

### 2.1. Converter YouTube para MIDI
Inicia um processo assíncrono para baixar o áudio de um vídeo e transcrevê-lo para MIDI.

-   **URL:** `/convert`
-   **Método:** `POST`
-   **Autenticação:** Requer JWT no Header `Authorization: Bearer <token>`
-   **Corpo (Form Data):**
    -   `source`: `"url"` (obrigatório)
    -   `url`: URL do vídeo do YouTube (obrigatório)
    -   `instrument`: Tipo de instrumento (ex: `"piano"`)
    -   `apply_filters`: `true`/`false` (aplica filtros de polifonia e escala)
    -   `quantize`: `"none"`, `"1/4"`, `"1/8"`, `"1/16"`, etc.

**Resposta de Sucesso:**
```json
{
  "status": "processing",
  "job_id": "uuid-do-job",
  "message": "Processamento iniciado"
}
```

---

### 2.2. Converter YouTube para MP3
Inicia a extração de áudio e conversão para o formato MP3.

-   **URL:** `/youtube-to-mp3`
-   **Método:** `POST`
-   **Autenticação:** Requer JWT
-   **Corpo (Form Data):**
    -   `url`: URL do vídeo do YouTube (obrigatório)
    -   `bitrate`: Qualidade do áudio (ex: `"128k"`, `"192k"`, `"256k"`, `"320k"`)

**Resposta de Sucesso:**
```json
{
  "status": "processing",
  "job_id": "uuid-do-job",
  "message": "Conversão para MP3 iniciada"
}
```

---

### 2.3. Consultar Status do Processamento
Verifica o progresso de um job (seja MIDI ou MP3).

-   **URL:** `/status/{job_id}`
-   **Método:** `GET`
-   **Autenticação:** Requer JWT (o usuário só pode ver seus próprios jobs)

**Exemplo de Resposta (Processando):**
```json
{
  "id": "uuid",
  "status": "processing",
  "progress": 50,
  "stage": "Convertendo para MP3 (320k)...",
  "metadata": { "bitrate": "320k" }
}
```

---

### 2.4. Download do Resultado
Endpoints para baixar os arquivos após a conclusão (`status: "completed"`).

-   **MIDI:** `GET /download/{job_id}`
-   **MP3:** `GET /download-mp3/{job_id}`

---

## 3. Implementação Técnica

### 3.1. Downloader (`app/downloader.py`)
Utiliza a biblioteca `yt-dlp` com as seguintes configurações principais:
-   **Cookies:** Opcionalmente utiliza um arquivo `cookies.txt` (definido pela variável de ambiente `COOKIES_FILE`) para contornar restrições de idade ou bots do YouTube.
-   **Formatos:** Prioriza `bestaudio/best`.
-   **Fallback:** Se o processamento de áudio falhar, o sistema tenta baixar o container original e extrair via FFmpeg.

### 3.2. Pré-processamento e Normalização
Antes da transcrição para MIDI, o áudio passa por:
1.  **Loudness Normalization (EBU R128):** Garante volume consistente.
2.  **FFT Denoiser (afftdn):** Remove ruídos de fundo.
3.  **Filtros Passa-Banda (100Hz - 8kHz):** Isola a faixa de frequência do piano para melhorar a precisão da IA de transcrição.

---

## 4. Requisitos e Dependências do Servidor
Para que a API do YouTube funcione corretamente, o servidor deve ter instalado:

1.  **FFmpeg:** Essencial para todas as conversões de áudio.
2.  **yt-dlp:** Atualizado frequentemente para acompanhar mudanças no YouTube.
3.  **Python Packages:** `yt-dlp`, `aiofiles`.

## 5. Variáveis de Ambiente (.env)
Configurações relevantes para a parte de YouTube:

```env
# Caminho para o arquivo de cookies (opcional, para evitar bloqueios)
COOKIES_FILE=/Users/maria/Documents/heartmidi/data/cookies.txt

# Diretório de dados temporários
DATA_DIR=./data
```

---
*Documentação gerada automaticamente para o projeto heartmid.*
