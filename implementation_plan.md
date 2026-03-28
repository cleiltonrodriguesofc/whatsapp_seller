# Plano: Status Automático + Refatoração + Mobile

## Estratégia de Branches

A abordagem profissional é **uma branch por fase**, cada uma representando um incremento testável e
revisável isoladamente. Isso garante:
- PRs pequenos e focados → revisão mais fácil
- Rollback cirúrgico se algo quebrar
- CI verde em cada merge antes de avançar
- Histórico de commits limpo e rastreável

```
development
├── feat/refactor-app-routers        # Fase 1: Refatoração do app.py
├── feat/status-update               # Fase 2: Status Automático (branch atual)
└── feat/mobile-responsiveness       # Fase 3: Mobile/Landing
```

Merge order: `feat/refactor-app-routers` → `development` → rebases Fase 2 em cima → merge → Fase 3.

---

## Fase 1 — Refatoração do `app.py` (`feat/refactor-app-routers`)

> **Branch:** `feat/refactor-app-routers` criada a partir de `development`
> **Critério de conclusão:** `pytest` verde, app sobe sem erros, zero URLs mudadas.

### Objetivo

Dividir o `app.py` de 1722 linhas em módulos coesos, sem alterar nenhum comportamento ou URL.

### Estrutura Proposta

```
core/presentation/web/
├── app.py              # ~100 linhas: init, middlewares, startup, include_router
├── scheduler.py        # background tasks: scheduler loop, execute_*_task, send_*
└── routers/
    ├── __init__.py
    ├── auth.py         # GET/POST /login, /register, /logout
    ├── campaigns.py    # GET /, POST /campaign/*
    ├── status_campaigns.py # GET/POST /status/*
    ├── products.py     # GET/POST /products/*
    ├── whatsapp.py     # GET/POST /whatsapp/*, /api/v1/whatsapp/*
    └── storage.py      # GET /storage/view/*, GET /l/*, POST /campaign/upload, helpers
```

### Regras

- Zero lógica de negócio nova — só mover código existente.
- Dependências compartilhadas (`get_db`, `get_current_user`, `login_required`, `templates`) migram para `core/presentation/web/dependencies.py`.
- Cada router: `APIRouter(prefix="...", tags=["..."])`.
- `scheduler.py` importa `SessionLocal`, repositories e services — sem importar `app`.

### Arquivos

#### [MODIFY] [app.py](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/app.py)
#### [NEW] core/presentation/web/dependencies.py
#### [NEW] core/presentation/web/scheduler.py
#### [NEW] core/presentation/web/routers/__init__.py
#### [NEW] core/presentation/web/routers/auth.py
#### [NEW] core/presentation/web/routers/campaigns.py
#### [NEW] core/presentation/web/routers/status_campaigns.py
#### [NEW] core/presentation/web/routers/products.py
#### [NEW] core/presentation/web/routers/whatsapp.py
#### [NEW] core/presentation/web/routers/storage.py

### Testes (Fase 1)

```bash
# Verificação estrutural
pytest tests/ -v --tb=short

# Verificação manual: app sobe sem erros
uvicorn core.presentation.web.app:app --reload
```

---

## Fase 2 — Status Automático + Bug Fixes (`feat/status-update`)

> **Branch:** `feat/status-update` (branch atual — fazer rebase em `development` após Fase 1 mergida)
> **Critério:** Upload funciona, status atualiza corretamente, imagem com boa qualidade.

### 2.1 — Bucket `images` e Qualidade de Imagem

#### [MODIFY] [supabase_storage.py](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/infrastructure/services/supabase_storage.py)

- `self.bucket_name = "images"` (era `"produtos"`)
- Aceitar `bucket_name` como parâmetro no `__init__` para testabilidade

#### [MODIFY] [image_utils.py](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/infrastructure/utils/image_utils.py)

- `max_size` default: `(400, 400)` → `(1080, 1920)` (portrait para status)
- `quality` default: `70` → `88`

### 2.2 — Endpoint `POST /status/upload` (bug: upload quebrado)

#### [MODIFY] `routers/status_campaigns.py` (ou `routers/storage.py`)

```python
@router.post("/status/upload")
async def upload_status_image(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(login_required),
):
    url = await _save_uploaded_image(file, quality=88, max_size=(1080, 1920))
    return {"url": url}
```

Também adicionar `POST /campaign/upload` como alias retroativo (o template chama essa URL).

#### [MODIFY] `_save_uploaded_image` helper

Adicionar parâmetros `quality: int = 75` e `max_size: tuple = (800, 800)` para customização por contexto.

### 2.3 — Fix: Status travado em "SENDING"

**Causa raiz identificada:** O scheduler marca `model.status = SENDING` e commita numa sessão.
A tarefa background (`execute_status_campaign_task`) abre **nova sessão** (`SessionLocal()`). Ao
chamar `repo.save(campaign)`, a entidade em memória pode estar "detached" ou o `db.refresh` não
ocorrer corretamente após o commit.

**Correção:**

```python
async def send_status_campaign(campaign_id: int, db: Session):
    # relê a entidade com a sessão ativa para garantir sync
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id)
    if not campaign:
        return

    success = True
    try:
        for item in campaign.items:
            ok = await whatsapp_service.send_status(...)
            if not ok:
                success = False
    except Exception as e:
        logger.error(...)
        success = False
    finally:
        campaign.status = (
            DomainStatusCampaignStatus.SENT if success
            else DomainStatusCampaignStatus.FAILED
        )
        campaign.sent_at = datetime.utcnow()
        repo.save(campaign)
```

### 2.4 — Frontend: Status Editor

#### [MODIFY] [status_editor.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/status_editor.html)

- Mudar endpoint: `/campaign/upload` → `/status/upload`
- Adicionar feedback de erro explícito no upload
- Validação client-side: bloquear submit sem imagem

#### [MODIFY] [status_list.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/status_list.html)

- Polling automático a cada 5s quando houver badge `sending` na lista
- Auto-para o polling quando nenhum badge estiver em `sending`

### 2.5 — Testes (Fase 2)

```bash
pytest tests/unit/test_image_utils.py -v
pytest tests/unit/test_supabase_storage.py -v

# Novos testes a criar:
pytest tests/unit/test_status_upload.py -v         # testa POST /status/upload
pytest tests/unit/test_status_send.py -v           # testa send_status_campaign bug fix
pytest tests/ -v --tb=short                         # suite completa
```

---

## Fase 3 — Mobile Responsiveness (`feat/mobile-responsiveness`)

> **Branch:** `feat/mobile-responsiveness` a partir de `development` (após Fase 1 e 2 mergiadas)
> **Critério:** Nenhum botão, card ou container saindo da tela em 375px, 414px, 768px.

### Problemas Identificados

| Página | Problemas |
|---|---|
| `landing.html` (31KB!) | Botões CTA saindo do container, seções mal dimensionadas no mobile |
| `dashboard.html` | Cards de métricas sem wrap em telas pequenas |
| `status_editor.html` | Grid de cards de item não colapsa corretamente |
| `status_list.html` | Colunas da lista não reorganizam em mobile |
| `new_campaign.html` + `edit_campaign.html` | Formulários com campos lado a lado que não colapsam |
| `connect_whatsapp.html` | Botões de ação saindo do card |

### Abordagem

1. **Audit visual** — abrir cada página no DevTools em 375px e mapear todos os overflows.
2. **Corrigir via CSS**: `overflow-x: hidden` no body, `box-sizing: border-box` universal, `max-width: 100%` em imagens.
3. **Breakpoints consistentes**: `@media (max-width: 768px)` para tablet, `@media (max-width: 480px)` para phone.
4. **Botões**: `width: 100%` em mobile para todos os CTAs principais.
5. **Grids**: Converter todos os `grid-template-columns: repeat(N, 1fr)` para `1fr` em mobile.
6. **Landing page** especificamente: revisar hero section, pricing cards, feature grid.

### Arquivos Impactados

#### [MODIFY] [landing.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/landing.html)
#### [MODIFY] [dashboard.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/dashboard.html)
#### [MODIFY] [status_editor.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/status_editor.html)
#### [MODIFY] [status_list.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/status_list.html)
#### [MODIFY] [new_campaign.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/new_campaign.html)
#### [MODIFY] [edit_campaign.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/edit_campaign.html)
#### [MODIFY] [connect_whatsapp.html](file:///c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/core/presentation/web/templates/connect_whatsapp.html)

### Testes (Fase 3)

- Visual: DevTools em 375px, 414px, 768px em cada página.
- Automatizado: script Playwright verificando ausência de overflow horizontal.

---

## Cronograma Sugerido

```
Fase 1 → PR → sua aprovação → merge development
Fase 2 → rebase → PR → sua aprovação → merge development  
Fase 3 → PR → sua aprovação → merge development
```

> [!IMPORTANT]
> Antes de qualquer merge, confirmar:
> - [ ] `pytest` passando (todos os testes)
> - [ ] App sobe sem erros
> - [ ] Behavior existente não foi quebrado
> - [ ] Sem secrets no código
> - [ ] Aprovação explícita sua

---

## Questões Abertas

> [!IMPORTANT]
> **Bucket Supabase**: Você precisa criar manualmente o bucket `images` no painel do Supabase antes da Fase 2 ir para produção. **Confirma que vai fazer isso antes do deploy?**

> [!NOTE]
> **Ordem de execução**: O plano sugere Fase 1 → 2 → 3. Mas se quiser valor mais rápido, podemos fazer Fase 2 → 1 → 3 (entrega a funcionalidade logo, refatora depois). Qual prefere?
