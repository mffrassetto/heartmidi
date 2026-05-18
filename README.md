# heartmid 🎹

Transforme músicas do YouTube ou arquivos locais em arquivos MIDI e MP3 de alta fidelidade instantaneamente.

O sistema utiliza o estado da arte em transcrição polifônica de áudio e inteligência artificial para extrair notas, onsets, offsets e dinâmicas com precisão absoluta, permitindo a edição direta através de um Piano Roll interativo.

---

## ✨ Funcionalidades

- **Transcrição de Alta Precisão (Audio-to-MIDI)**: Motor neural treinado em datasets de ponta, capaz de detectar onsets, offsets e dinâmicas de velocidade precisas.
- **YouTube para MIDI / YouTube para MP3**: Baixe e converta vídeos diretamente do YouTube informando apenas o link.
- **Instrumentos Destino**: Escolha o timbre instrumental alvo e configure sua conversão.
- **Quantização Rítmica Inteligente**: Ajuste rítmico automático com detecção precisa de BPM.
- **Piano Roll MIDI Editor**: Edite, mova, adicione, delete e redimensione notas diretamente pelo navegador com feedback sonoro ao vivo antes de exportar seu arquivo final.
- **Interface Web Premium**: Dashboard responsivo, moderno e totalmente otimizado.
- **Arquitetura Assíncrona e Escalável**: Fluxo baseado em jobs asíncronos com progresso em tempo real sincronizado via Supabase.

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

1.  **Ingestão**: Download via `yt-dlp` ou upload de arquivo de áudio local.
2.  **Normalização**: Conversão para WAV 16kHz Mono via `ffmpeg`.
3.  **Inferência**: Transcrição pelo modelo de rede neural polifônico.
4.  **Pós-Processamento**:
    - Ajuste rítmico por quantização (opcional).
    - Ajustes de velocidade e dinâmicas de notas.
5.  **Exibição & Edição**: Sincronização em tempo real para o Piano Roll no frontend.

---

## 📝 Créditos e Licença

Desenvolvido com excelência por **Maria Fernanda Frassetto - MFF Web Agency**. Todos os direitos reservados.
