# AGENTS.md instructions for /Users/menon/git/nmr5dbweb

## Objetivo
- Estabilizar codigo.
- Evitar refatoracoes amplas.

## Regras de conduta (criticas)
- NUNCA criar branch novo nem PR novo sem autorizacao explicita.
- Nao criar worktree/pasta sem aprovacao.
- NUNCA fechar/abrir PR sem pedido explicito.
- Nao editar nada antes de aprovar plano.
- Nao alterar arquivo preexistente sem listar impacto antes.
- Nao misturar idiomas: comunicacao tecnica em PT-BR. Codigo/comentarios em ASCII.
- Sem acentos/cedilha/emojis/em-dash em codigo e mensagens tecnicas.
- Nao fazer mudancas fora do escopo; se algo parecer necessario, parar e pedir confirmacao.
- Nada de try/except vazio, nada de suppress que esconda erro real, nada de self-healing silencioso.
- Evitar qualquer mudanca de layout/posicionamento na GUI (a menos que seja pedido explicitamente).
- Nao alterar nada fora do escopo do sprint a menos que explicitamente solicitado.
- Nao adicionar wrappers/mixins/helpers extras desnecessarios.
- Nao usar reset --hard ou comandos destrutivos.
- Nao quebrar usabilidade entre ciclos; cada ciclo precisa fechar com estabilidade e usabilidade.

## Processo (ciclo curto, estilo XP)
0) Commits atomicos e rollback facil por feature.
1) Diagnosticar e isolar o problema (com evidencia: arquivo/linha/log/repro).
2) Propor plano curto + diff previsto antes de editar (menor patch possivel).
3) Implementar em slice pequeno.
4) Validar localmente: py_compile + ruff + pytest focado (com timeout quando fizer sentido).
5) Commit atomico (um por slice), push, checar bots/checks.
6) Se houver itens nao bloqueantes: registrar no local apropriado (ex.: RECOVERY_BACKLOG.md).
7) Priorizar correcao de risco real; evitar refactor transversal fora de escopo.
8) Quando alterar arquivos de config, criar backup com timestamp.

## Confirmacao explicita
1) Nao inferir permissao por respostas genericas como continue/segue/ok.
2) Mudanca de layout so com pedido explicito.
3) Nao executar rollback sem comando explicito com reverter + escopo.
4) Em ambiguidade: pedir confirmacao binaria (sim/nao) com checklist objetivo.
5) Default em ambiguidade: apenas diagnostico/testes, sem editar.

## Higiene de workspace
- Rodar `git status --short` no inicio.
- Confirmar pasta e branch de trabalho.
- Nao comitar sem confirmacao arquivos locais/fora de escopo (`.envrc`, `.python-version`, segredos etc).
- Se aparecer mudanca em `.gitignore*` fora do pedido: parar e perguntar.
- Estabilizar import/startup e pontos de concorrencia (race/deadlock/cancel/locks/IO) com mudanca minima e verificavel.
- Otimizar carregamento/desempenho da GUI com mudancas minimas e sem excesso defensivo.
- Sugerir mudancas de layout minimas so quando pedido explicito.
- Verificar status e condicoes de loops.

## Validacao e testes
- Python: usar uv para python/python3/pip3/pip.
- Rodar sempre: `python -m py_compile`, `ruff check`, `ty`, `pytest` focado para derivadas.
- Evitar testes viciados; priorizar regressao real (concorrencia/cancel/IO/locks).
- Incluir testes novos quando houver omissao clara.
- Para aplicacao node, usar exclusivamente pnpm ou bun.

## Regras adicionais para nao perder pedidos do usuario
- Manter checklist vivo de pedidos atuais antes de qualquer edicao.
- Antes de fechar ciclo, publicar matriz: aberto x resolvido x falso-positivo (com evidencia).
- Nao classificar thread como historico/debito sem justificar em linha unica: risco, impacto, motivo de nao-bloqueio.
- Se o item for pequeno e de baixo risco, corrigir no mesmo ciclo ao inves de adiar.
- Se o item exigir refactor amplo, parar e pedir confirmacao com 2 opcoes objetivas.

## Configuracoes operacionais do Codex (derivadas do AGENTS)
- Sempre iniciar com: workspace/branch/status.
- Sempre mostrar plano curto e impacto antes de editar.
- Sempre separar mudancas por slice minimo com validacao focada.
- Sempre priorizar risco real (seguranca, corrupcao, perda de dados, crash, regressao de fluxo principal).
- Sempre evitar mudanca estrutural ampla sem pedido explicito.
- Sempre manter rastreabilidade por arquivo/linha/teste.

# Kluster Rules (Auto-generated)
<kluster.ai mandaroty rules>

## 1. Automatic Code Review (kluster_code_review_auto)

### MANDATORY EXECUTION
- WHEN TO RUN: Execute after ANY file creation, modification, or code change.
- Applies to ALL file types.
- ZERO EXCEPTIONS POLICY.
- After any kluster_code_review_auto analysis, ALWAYS tell the user what issues were found and what you are about to fix BEFORE making any changes.

### KLUSTER PURPOSE CLARIFICATION
- Kluster is NOT a traditional testing, syntax, lint, or build replacement.
- Kluster performs security, quality, and compliance verification.
- Call kluster immediately after file modification.

### STRICT COMPLIANCE
- Follow kluster_code_review_auto field descriptions exactly.

## 2. Manual Code Review (kluster_code_review_manual)

### WHEN TO RUN
- Only when explicitly requested by user.

### TRIGGER PHRASES
- verify with kluster
- verify this file
- verify project
- check for bugs
- check security

## 3. Dependency Validation (kluster_dependency_check)

### WHEN TO RUN
- Before package manager operations or dependency file changes.

## 4. Chat ID Management

### FIRST CALL
- Do not include chat_id in first kluster call.

### SUBSEQUENT CALLS
- Always include exact chat_id returned by previous kluster call.

## 5. Agent Todo List Management
- Always execute and strictly follow agent_todo_list from kluster response.
- Do not stop until all items are completed.

## 6. End of chat session - kluster summary
- Mandatory at end of any conversation where kluster was used (except clarification mode).
- Must include full journey of all kluster calls since last user request.
- Include external knowledge line when present.

## 7. New Feature Branch Protocol (Global)
- State one main goal.
- State secondary goals.
- Provide detailed execution plan before implementation.
- Prefer minimal-risk changes.
- Keep atomic commits.
- Validate before push.
- Fix blockers first.
- Keep deferred non-blocking items in backlog file.

</kluster.ai mandaroty rules>
