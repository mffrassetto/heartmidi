# Arquitetura heartmid: Cloudflare & Async Flow

Este documento descreve a arquitetura técnica implementada para garantir alta disponibilidade e contornar limitações de timeout em ambientes de produção (especialmente Cloudflare).

## 1. O Desafio: Timeout de 100s
O Cloudflare impõe um limite rígido de 100 segundos para respostas HTTP (Erro 524). Modelos de transcrição musical como o utilizado pelo heartmid podem levar vários minutos para processar áudios longos em CPUs padrão.

## 2. A Solução: Arquitetura Orientada a Eventos
Para resolver isso, o sistema foi migrado de um fluxo síncrono (Request -> Wait -> Response) para um fluxo assíncrono baseado em Jobs.

### Fluxo de Processamento
1.  **Submissão (FastAPI)**:
    *   O usuário envia um arquivo ou URL.
    *   O backend valida os dados, cria um registro na tabela `jobs` do Supabase com status `processing`.
    *   Retorna imediatamente um `job_id` para o frontend.
2.  **Processamento (Background Tasks)**:
    *   Uma tarefa assíncrona (`asyncio.create_task`) inicia o download e a transcrição.
    *   O backend atualiza os campos `progress` e `stage` na tabela `jobs` durante cada etapa crítica.
3.  **Sincronização (Supabase Realtime)**:
    *   O frontend utiliza WebSockets para "escutar" mudanças no registro do Job específico.
    *   As atualizações são refletidas na UI em milissegundos após a alteração no banco de dados.

## 3. Componentes Técnicos

### Backend (Python/FastAPI)
*   **Endpoints Non-blocking**: `/convert` e `/youtube-to-mp3` são otimizados para resposta instantânea.
*   **Controle de Cache**: Headers `Cache-Control: no-store` garantem que o Cloudflare não cacheie estados intermediários.
*   **Job Manager**: Classe centralizada para gerenciar a persistência de estado e atualizações de progresso via cliente admin do Supabase.

### Frontend (JavaScript/Supabase JS)
*   **Realtime Subscription**: Inscrição dinâmica no canal `postgres_changes`.
*   **Session Persistence**: O `localStorage` armazena o `currentJobId`. Se o usuário atualizar a página, o frontend detecta o job pendente e retoma a escuta do progresso.
*   **Fallback Strategy**: Se a conexão WebSocket falhar, o sistema reverte para um polling HTTP lento (10s) para garantir a entrega do resultado.

### Banco de Dados (PostgreSQL/Supabase)
*   **Tabela `jobs`**: Armazena metadados, status, progresso e caminhos de arquivos.
*   **RLS (Row Level Security)**: Garante que usuários só possam monitorar e baixar seus próprios arquivos.
*   **Realtime Enabled**: Publicação `supabase_realtime` configurada especificamente para a tabela de jobs.

## 4. Vantagens
*   **UX Fluida**: O usuário vê o progresso subir em tempo real.
*   **Escalabilidade**: O backend pode ser distribuído em múltiplos workers sem perder o rastro do progresso.
*   **Resiliência**: Falhas de rede no frontend não interrompem o processamento no servidor.
