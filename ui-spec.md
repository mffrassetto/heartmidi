# heartmid - Interface Definition

A interface do sistema foi projetada para ser simples, intuitiva e focada em produtividade para músicos e produtores.

## 🎨 Design System

-   **Estilo**: Glassmorphism com Dark Mode.
-   **Cores**:
    -   Fundo: Midnight Blue (#0f0f1a).
    -   Destaque: Emerald Green (#22c55e).
    -   Ações Secundárias: Royal Purple (#8b5cf6).
-   **Interatividade**: Transições suaves, estados de hover animados e feedback visual de progresso.

---

## 📱 Componentes da Interface

### 1. Painel de Ingestão
-   **URL do YouTube**: Suporte a links diretos para conversão MIDI ou MP3.
-   **Upload de Arquivos**: Suporte a MP3, WAV e M4A.
-   **Configurações Rápidas**:
    -   Escolha de Instrumento Destino (Dropdown).
    -   Seleção de Quantização (Nenhuma, 1/8, 1/16, 1/32).

### 2. Monitor de Progresso
-   Exibição em tempo real das etapas:
    -   📥 Baixando áudio...
    -   🧠 Transcrevendo com IA...
    -   🎼 Processando MIDI...
    -   ✅ Concluído!

### 3. Painel de Resultado
-   **Estatísticas**: Contagem de notas e duração do áudio.
-   **Download**: Botão direto para o arquivo `.mid` ou `.mp3` finalizado.
-   **Preview & Edição**: Piano Roll MIDI Editor integrado para visualização e edição direta das notas em tempo real.

---

## 🛠️ Tecnologias Utilizadas

-   **Frontend**: HTML5 Semântico, CSS3 (Vanilla + Custom Properties), Javascript (Fetch API).
-   **Backend Rendering**: FastAPI StaticFiles.
-   **Assets**: Google Fonts (Inter), Feather Icons.