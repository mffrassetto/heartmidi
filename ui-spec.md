# Heartopia Audio-to-MIDI Converter - Design Spec

## Visão Geral
- **Tipo**: Web Application (Dashboard)
- **Estilo**: Dark mode, moderno, musician-friendly
- **Stack**: HTML + Tailwind CSS

---

## Tela 1: Homepage / Converter

### Layout
- Container centralizado, max-width 800px
- Fundo: gradient escuro (#0f0f1a → #1a1a2e)

### Componentes

**Header**
- Logo "Heartopia MIDI" no topo (esquerda)
- Link "Histórico" à direita

**Hero Section**
- Título: "Converta áudio para MIDI"
- Subtítulo: "Transformemusicas do YouTube ou arquivos MP3/WAV em arquivos MIDI compatíveis com Heartopia"

**Input Section**
- Campo de URL do YouTube (input text)
- OU botão "Selecionar arquivo" para upload
- Radio buttons: "URL do YouTube" / "Arquivo local"

**Configurações (opcional collapse)**
- Dropdown: Instrumento destino (Piano, Guitar, Drums, etc.)
- Checkbox: "Aplicar filtros de compatibilidade Heartopia" (default: checked)

**Botão Principal**
- "Converter" - grande, verde (#22c55e)
- Animated gradient on hover

**Status/Progress**
- Barra de progresso animadapendente estágio:
  1. "Baixando áudio..."
  2. "Processando transcrição neural..."
  3. "Aplicando filtros..."
  4. "Finalizando..."

---

## Tela 2: Resultado / Download

### Layout
- Similar à homepage

### Componentes

**Card de Resultado**
- Nome do arquivo original
- Duração convertida
- Número de notas detectadas

**Preview MIDI**
- Visualização简易da melodia (piano roll simplificado)
- Ou lista de primeiras notas

**Ações**
- Botão "Download MIDI" - verde
- Botão "Novo Upload" - outline

---

## Tela 3: Histórico

### Layout
- Tabela ou cards
- Max-width 1000px

### Componentes
- Lista de conversões anteriores
- Columns: Data, Arquivo, Duração, Status, Ação
- Botão para re-download

---

## Cores e Estilo

### Paleta
- Primary: #22c55e (green-500)
- Background: #0f0f1a (dark)
- Surface: #1a1a2e (card bg)
- Text: #fafafa (white)
- Muted: #a1a1aa (gray-400)
- Accent: #8b5cf6 (purple-500)

### Tipografia
- Font: Inter ou system-ui
- Headings: Bold
- Body: Regular

### Efeitos
- Border radius: 12px
- Box shadows sutis
- Hover: scale(1.02) em cards