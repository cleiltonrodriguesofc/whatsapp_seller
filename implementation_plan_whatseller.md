# WhatSeller Pro — Plano de Implementação

## Contexto do Projeto

Stack: FastAPI + SQLAlchemy 2.0 + Jinja2 + PostgreSQL (prod) / SQLite (dev)  
Autenticação: JWT em HttpOnly cookies  
Deploy: Render  
Arquitetura: Clean Architecture (domain / application / infrastructure / presentation)

---

## Escopo desta implementação

1. Página de Termos de Uso
2. Página de Política de Privacidade
3. Página de Documentação
4. Seção de Planos e Preços (landing page)
5. Fluxo de Checkout com gateway de pagamento
6. Trial gratuito de 3 dias para novos usuários
7. Programa de indicação (referral) com recompensa

---

## 1. Páginas Estáticas (Termos, Privacidade, Documentação)

### O que fazer

Criar três novas rotas e templates Jinja2:

- `GET /terms` → `terms.html`
- `GET /privacy` → `privacy.html`
- `GET /docs` → `documentation.html`

### Localização no projeto

- Rotas: `core/presentation/routes/static_pages.py` (arquivo novo)
- Templates: `core/presentation/templates/`
- Registrar o router no `main.py` ou `app.py`

### Conteúdo mínimo de cada página

**Termos de Uso (`terms.html`)**
- Objeto do serviço
- Responsabilidades do usuário (uso dentro das políticas do WhatsApp)
- Limitação de responsabilidade por banimento de conta
- Política de cancelamento (acesso até fim do período pago, sem cobrança automática)
- Contato para suporte

**Política de Privacidade (`privacy.html`)**
- Quais dados são coletados (nome, e-mail, dados de sessão)
- Como são usados (autenticação, envio de campanhas)
- Armazenamento e segurança
- Direitos do titular (LGPD)
- Cookies e sessões
- Contato do responsável pelos dados

**Documentação (`documentation.html`)**
Estruturar como guia de início rápido com seções:
- Primeiros passos: criar conta e conectar WhatsApp
- Conectar instância via QR Code
- Criar produto no catálogo
- Criar e agendar campanha
- Usar IA para gerar copy
- Programa de indicação: como funciona e como sacar

### Atualização nos links do rodapé

No template base (`base.html` ou equivalente), atualizar:
```html
<!-- DE -->
<a href="#">Termos de Uso</a>
<a href="#">Privacidade</a>
<a href="#">Documentação</a>

<!-- PARA -->
<a href="/terms">Termos de Uso</a>
<a href="/privacy">Privacidade</a>
<a href="/docs">Documentação</a>
```

---

## 2. Seção de Planos e Preços na Landing Page

### O que fazer

Adicionar uma seção `#pricing` na `index.html` com três planos:

| Plano | Preço | Instâncias | Campanhas/mês | IA |
|-------|-------|------------|---------------|-----|
| Starter | R$97/mês | 1 | 5 | ❌ |
| Pro | R$197/mês | 3 | Ilimitadas | ✅ |
| Agência | R$397/mês | Ilimitadas | Ilimitadas | ✅ |

- Destacar visualmente o plano Pro como "Mais popular"
- Cada card deve ter botão "Começar trial grátis" apontando para `/register?plan=starter` (ou pro, agency)
- Atualizar o link "Ver como funciona" no hero para `#features` e adicionar link `#pricing` no menu de navegação

---

## 3. Modelo de Dados — Assinaturas e Referral

### Novas tabelas no banco de dados

Criar via SQLAlchemy (em `core/infrastructure/database/models.py` ou arquivo separado):

```python
# Planos disponíveis
class Plan(Base):
    __tablename__ = "plans"
    id: int (PK)
    name: str          # "starter", "pro", "agency"
    display_name: str  # "Starter", "Pro", "Agência"
    price_brl: float   # 97.00, 197.00, 397.00
    max_instances: int # 1, 3, -1 (ilimitado)
    has_ai: bool
    stripe_price_id: str  # ID do preço no Stripe

# Assinaturas
class Subscription(Base):
    __tablename__ = "subscriptions"
    id: int (PK)
    user_id: int (FK → users)
    plan_id: int (FK → plans)
    status: str         # "trialing", "active", "canceled", "past_due"
    trial_ends_at: datetime
    current_period_end: datetime
    stripe_subscription_id: str
    stripe_customer_id: str
    created_at: datetime

# Programa de indicação
class ReferralCode(Base):
    __tablename__ = "referral_codes"
    id: int (PK)
    user_id: int (FK → users)       # dono do código
    code: str (único, indexado)     # ex: "CLEILTON42"
    created_at: datetime

class ReferralConversion(Base):
    __tablename__ = "referral_conversions"
    id: int (PK)
    referrer_id: int (FK → users)   # quem indicou
    referred_id: int (FK → users)   # quem se cadastrou
    status: str   # "pending", "converted", "rewarded"
    reward_brl: float               # valor do bônus
    rewarded_at: datetime
    created_at: datetime
```

Adicionar coluna na tabela `users`:
```python
referral_code_id: int (FK → referral_codes, nullable)  # código usado no cadastro
```

---

## 4. Trial Gratuito de 3 Dias

### Lógica de negócio

- Todo usuário novo recebe automaticamente uma `Subscription` com `status="trialing"` e `trial_ends_at = now() + 3 days`
- Não exigir cartão de crédito no cadastro
- Ao final do trial, o status muda para `"canceled"` e o acesso às funcionalidades pagas é bloqueado
- O usuário é redirecionado para `/pricing` ou recebe banner de upgrade

### Onde implementar

**No use case de registro** (`core/application/use_cases/register_user.py`):
```python
# Após criar o usuário, criar subscription de trial
subscription = Subscription(
    user_id=new_user.id,
    plan_id=FREE_TRIAL_PLAN_ID,
    status="trialing",
    trial_ends_at=datetime.utcnow() + timedelta(days=3),
)
session.add(subscription)
```

**Middleware ou dependency de autenticação:**
```python
# Verificar status da assinatura em rotas protegidas
def require_active_subscription(current_user, session):
    subscription = get_subscription(current_user.id, session)
    if subscription.status == "trialing" and subscription.trial_ends_at < datetime.utcnow():
        subscription.status = "canceled"
        session.commit()
    if subscription.status not in ("trialing", "active"):
        raise HTTPException(status_code=402, headers={"Location": "/pricing"})
```

**Banner de trial no dashboard:**
```html
<!-- Exibir quando status="trialing" -->
<div class="trial-banner">
  Seu trial gratuito termina em <strong>{{ dias_restantes }} dias</strong>.
  <a href="/pricing">Assinar agora</a>
</div>
```

---

## 5. Checkout com Mercado Pago

### Por que Mercado Pago

- PIX, boleto e cartão de crédito nativos no Brasil
- SDK Python oficial bem mantido
- Assinaturas recorrentes (preapproval) com cobrança automática
- Familiar para o público brasileiro — aumenta conversão
- Sandbox completo para testes

### Instalação

```bash
pip install mercadopago
```

Adicionar ao `requirements.txt`:
```
mercadopago>=2.2.0
```

### Variáveis de ambiente (adicionar ao `.env.example`)

```
MP_ACCESS_TOKEN=APP_USR-...         # token de produção
MP_WEBHOOK_SECRET=...               # chave para validar webhooks
MP_PLAN_STARTER_ID=...              # ID do plano criado no MP
MP_PLAN_PRO_ID=...                  # ID do plano criado no MP
MP_PLAN_AGENCY_ID=...               # ID do plano criado no MP
```

### Criar planos no Mercado Pago (uma vez, via API ou dashboard)

```python
import mercadopago

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

plan = sdk.preapproval_plan().create({
    "reason": "WhatSeller Pro — Plano Pro",
    "auto_recurring": {
        "frequency": 1,
        "frequency_type": "months",
        "transaction_amount": 197.00,
        "currency_id": "BRL",
    },
    "back_url": "https://whatsellerpro.onrender.com/checkout/success",
    "status": "active",
})
# Salvar plan["response"]["id"] como MP_PLAN_PRO_ID no .env
```

Repetir para Starter (R$97) e Agência (R$397).

### Novas rotas de checkout

Criar `core/presentation/routes/billing.py`:

```
GET  /pricing                       → página de planos
POST /checkout/create-session       → cria link de assinatura MP e redireciona
GET  /checkout/success              → página de sucesso pós-pagamento
GET  /checkout/cancel               → página de cancelamento
POST /webhooks/mercadopago          → recebe notificações do MP (assinatura criada, renovada, cancelada)
GET  /dashboard/billing             → painel de faturamento do usuário (plano atual, próxima cobrança, cancelar)
```

### Fluxo completo

```
Usuário clica "Assinar Pro"
    → POST /checkout/create-session { plan: "pro" }
    → Backend cria preapproval com MP_PLAN_PRO_ID
    → Retorna init_point (link de pagamento do MP)
    → Redireciona usuário para o link do Mercado Pago
    → Usuário paga via PIX, boleto ou cartão
    → MP redireciona para /checkout/success
    → MP dispara webhook com status "authorized"
    → Backend atualiza Subscription.status = "active"
    → Usuário vê dashboard liberado
```

### Criar sessão de checkout (rota)

```python
@router.post("/checkout/create-session")
async def create_checkout(plan: str, current_user: User, session: Session):
    plan_id_map = {
        "starter": MP_PLAN_STARTER_ID,
        "pro": MP_PLAN_PRO_ID,
        "agency": MP_PLAN_AGENCY_ID,
    }
    mp_plan_id = plan_id_map.get(plan)

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    preapproval = sdk.preapproval().create({
        "preapproval_plan_id": mp_plan_id,
        "payer_email": current_user.email,
        "back_url": "https://whatsellerpro.onrender.com/checkout/success",
        "external_reference": str(current_user.id),  # para identificar no webhook
    })

    init_point = preapproval["response"]["init_point"]
    return RedirectResponse(url=init_point)
```

### Webhook handler (lógica principal)

```python
@router.post("/webhooks/mercadopago")
async def mp_webhook(request: Request, session: Session):
    data = await request.json()
    topic = data.get("type")

    if topic == "subscription_preapproval":
        preapproval_id = data["data"]["id"]
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        result = sdk.preapproval().get(preapproval_id)
        preapproval = result["response"]

        user_id = int(preapproval["external_reference"])
        status = preapproval["status"]  # "authorized", "paused", "cancelled"

        subscription = session.query(Subscription).filter_by(user_id=user_id).first()

        if status == "authorized":
            subscription.status = "active"
            subscription.mp_preapproval_id = preapproval_id
        elif status == "cancelled":
            subscription.status = "canceled"
        elif status == "paused":
            subscription.status = "past_due"

        session.commit()
```

Adicionar campo `mp_preapproval_id: str` no modelo `Subscription`.

---

## 6. Programa de Indicação (Referral)

### Como funciona

1. Cada usuário ativo recebe um link único: `https://whatsellerpro.onrender.com/register?ref=CODIGO`
2. Quando alguém se cadastra via esse link, o `referred_id` é registrado
3. Quando o indicado assina um plano pago (webhook `customer.subscription.created`), a conversão é confirmada
4. O indicador recebe recompensa

### Estrutura de recompensa sugerida

- **30% da primeira mensalidade** do indicado (ex: indicou alguém no plano Pro → recebe R$59,10)
- Bônus acumula em saldo dentro da plataforma
- Saque via PIX quando atingir R$100 (ou aplicar como desconto na própria assinatura)

### Novas rotas de referral

Criar `core/presentation/routes/referral.py`:

```
GET  /referral                    → painel do programa (código, link, histórico, saldo)
POST /referral/request-withdrawal → solicitação de saque
```

### Lógica de cadastro com referral

No use case de registro:
```python
# Verificar se veio com ?ref=CODIGO na URL
ref_code = request.query_params.get("ref")
if ref_code:
    referral = session.query(ReferralCode).filter_by(code=ref_code).first()
    if referral and referral.user_id != new_user.id:
        conversion = ReferralConversion(
            referrer_id=referral.user_id,
            referred_id=new_user.id,
            status="pending",
        )
        session.add(conversion)
```

### Lógica de recompensa (no webhook do Stripe)

```python
# Quando customer.subscription.created
conversion = session.query(ReferralConversion).filter_by(
    referred_id=user_id, status="pending"
).first()
if conversion:
    plan_price = get_plan_price(subscription.plan_id)
    reward = round(plan_price * 0.30, 2)
    conversion.status = "rewarded"
    conversion.reward_brl = reward
    conversion.rewarded_at = datetime.utcnow()
    # Adicionar ao saldo do referrer
    referrer.referral_balance += reward
    session.commit()
```

### Painel de indicação no dashboard

Exibir para o usuário:
- Seu link de indicação (com botão de copiar)
- Quantas pessoas se cadastraram pelo seu link
- Quantas converteram para pago
- Saldo disponível para saque
- Histórico de recompensas

---

## 7. Ordem de Implementação Recomendada

Execute nesta sequência para evitar dependências quebradas:

```
1. Criar modelos de banco (Plan, Subscription, ReferralCode, ReferralConversion)
2. Gerar e rodar migration (Alembic ou create_all)
3. Popular tabela plans com os 3 planos
4. Implementar trial automático no registro
5. Implementar middleware de verificação de assinatura
6. Criar páginas estáticas (terms, privacy, docs)
7. Adicionar seção de pricing na landing page
8. Configurar Stripe (criar produtos e preços no dashboard do Stripe)
9. Implementar rotas de checkout e webhook
10. Implementar programa de referral
11. Criar painel de billing e referral no dashboard
12. Testar fluxo completo em ambiente de staging com Stripe test mode
```

---

## 8. Testes a Implementar

Adicionar em `tests/`:

- `test_trial.py` — verifica que novo usuário recebe trial de 3 dias e que acesso é bloqueado após expirar
- `test_referral.py` — verifica que conversão é registrada e recompensa calculada corretamente
- `test_billing.py` — testa webhook handler com payloads simulados do Mercado Pago
- `test_static_pages.py` — verifica que rotas /terms, /privacy, /docs retornam 200

---

## 9. Checklist Final

- [ ] Links do rodapé apontam para rotas reais
- [ ] Novo usuário entra em trial de 3 dias sem cartão
- [ ] Banner de trial aparece no dashboard com contagem regressiva
- [ ] Checkout com Mercado Pago funciona em sandbox
- [ ] Webhook atualiza status da assinatura corretamente (authorized / cancelled / paused)
- [ ] Link de referral é gerado automaticamente para cada usuário
- [ ] Recompensa de 30% é creditada quando indicado assina
- [ ] Painel de billing mostra plano atual e próxima cobrança
- [ ] Painel de referral mostra saldo e histórico
- [ ] `.env.example` atualizado com todas as novas variáveis
- [ ] Testes passando no CI

---

*Gerado para o projeto WhatSeller Pro — cleiltonrodriguesofc/whatsapp_seller*
