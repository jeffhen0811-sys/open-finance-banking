---
name: open-finance-banking
description: Query bank accounts via Pluggy (Meu Pluggy). Read-only.
category: productivity
---

# Skill Open Finance Bancário

Skill para consultar dados bancários via **Open Finance Brasil** utilizando o agregador **Pluggy** (plano Meu Pluggy — gratuito para uso pessoal).

Permite que o Alfred consulte suas contas, saldos, transações, cartões, faturas e investimentos de forma padronizada, segura e 100% read-only.

---

## Quando usar esta skill

- Consultar saldo de todas as contas
- Ver extrato de um período específico
- Listar transações recentes
- Ver fatura atual do cartão de crédito
- Consultar investimentos
- Obter resumo financeiro consolidado ("como estão minhas finanças?")

## Quando NÃO usar

- Para fazer PIX ou transferências (não implementado)
- Para pagar boletos ou faturas (não implementado)
- Para movimentar investimentos (não implementado)
- Para alterar qualquer dado bancário
- Para consultar contas de terceiros (apenas dados do próprio usuário)

---

## 🏗️ Como funciona — Dois Portais

A Pluggy usa **dois portais separados** que precisam ser vinculados:

| Portal | URL | Finalidade |
|--------|-----|------------|
| **Meu Pluggy** (consumidor) | meu.pluggy.ai | Você conecta seus bancos via Open Finance (uma vez) |
| **Dashboard** (desenvolvedor) | dashboard.pluggy.ai | O Alfred obtém as credenciais de API (Client ID/Secret) |

O vinculo entre eles: no Dashboard, você adiciona o conector **MeuPluggy** e faz login com sua conta do Meu Pluggy. Só assim a API enxerga os dados.

---

## Pré-requisitos — Configuração Inicial (uma vez)

### 1. Crie sua conta no Meu Pluggy

Acesse [meu.pluggy.ai](https://meu.pluggy.ai) e crie sua conta.
Conecte cada banco que você quer acompanhar (Itaú, Caixa, etc.).
O consentimento é feito **dentro do app do banco** — suas credenciais nunca passam pela Pluggy.

### 2. Crie sua conta no Dashboard Pluggy

Acesse [dashboard.pluggy.ai](https://dashboard.pluggy.ai) e crie sua conta.

### 3. Crie uma aplicação e copie as credenciais

No Dashboard, crie uma aplicação. Copie o **Client ID** e o **Client Secret**.

### 4. Vincule o MeuPluggy à aplicação

No Dashboard, dentro da sua aplicação:
1. Vá em **Customization → Connectors**
2. Adicione o conector **MeuPluggy** (id=200) à lista de conectores disponíveis
3. Clique no MeuPluggy da lista e faça **login com sua conta do Meu Pluggy**
4. Autorize o acesso
5. Repita para cada banco conectado no Meu Pluggy

### 5. Anote o Item ID

Após vincular, o Dashboard mostra o **Item ID** (UUID) da conexão. Guarde-o — a API gratuita não permite listar items (`LIST_ITEMS_FEATURE_NOT_ENABLED`), mas acessar por ID direto funciona.

### 6. Configure as variáveis de ambiente

```bash
export PLUGGY_CLIENT_ID="seu_client_id"
export PLUGGY_CLIENT_SECRET="seu_client_secret"
export PLUGGY_ITEM_ID="seu_item_id"  # UUID da conexão no Dashboard
```

---

## Arquivos da Skill

```
skills/open-finance-banking/
├── SKILL.md                    ← Este arquivo
├── scripts/
│   ├── __init__.py
│   ├── models.py               ← Schemas/dataclasses normalizados
│   ├── financial_provider.py   ← Interface abstrata do provider
│   ├── pluggy_provider.py      ← Implementação Pluggy
│   ├── cache.py                ← Cache com TTL
│   ├── storage.py              ← Persistência de conexões
│   └── tools.py                ← Tools para o Alfred
├── references/
│   └── pluggy-api.md           ← Referência da API Pluggy
└── tests/
    └── test_provider.py        ← Testes unitários
```

---

## Arquitetura

```
Alfred → tools (financial_get_*) → FinancialProvider (interface)
                                        ↓
                                 PluggyProvider (implementação)
                                        ↓
                                 API Pluggy (REST)
                                        ↓
                                 Open Finance Brasil
                                        ↓
                                 Itaú | Caixa
```

---

## Como usar (para Agentes)

```python
import sys, os
sys.path.insert(0, "/opt/data/skills/open-finance-banking/scripts")
from tools import FinancialToolsProvider

tools = FinancialToolsProvider()

# Listar contas
contas = tools.financial_get_accounts()

# Saldos
saldos = tools.financial_get_balances()

# Transações recentes
transacoes = tools.financial_get_transactions(days=30)

# Cartões de crédito
cartoes = tools.financial_get_credit_cards()

# Fatura de um cartão
fatura = tools.financial_get_credit_card_invoice(card_id="card_xxx")

# Investimentos
investimentos = tools.financial_get_investments()

# Resumo financeiro
resumo = tools.financial_get_summary(days=30)
```

---

## ⏰ Cenários de Uso Programado (Cron)

A skill suporta buscas programadas diárias e semanais sem alterações no código.

### Rotina Diária (22:00 BRT) — Movimentações do dia anterior

Agendar um cron job que chama `financial_get_transactions(days=1)` ou
`financial_get_transactions(from_date=ontem, to_date=ontem)`.

```
Às 22h do dia 02/09 → busca dateFrom=2026-09-01, dateTo=2026-09-01
```

Isso captura **todas as movimentações bancárias** (entradas e saídas) + **gastos
do cartão de crédito** do dia anterior completo. Como já passaram 24h+ desde o
período buscado, o sync automático do Meu Pluggy já ocorreu — dados estão
disponíveis.

**Para buscar de TODAS as contas:** omita `account_id` — a tool já varre todas
as contas bancárias automaticamente (incluindo cartões de crédito como contas
separadas).

### Rotina Semanal (Domingo) — Movimentações de investimentos

⚠️ **Necessita implementação.** O endpoint `GET /investment-transactions`
está documentado na referência da API mas **não implementado** no código.
Veja detalhes no pitfall abaixo.

O padrão desejado:
```
Domingo 06/09 → busca investment-transactions de 30/08 até 05/09
```

Captura: aportes, retiradas e rendimentos dos cofrinhos/ investimentos da semana.

---

## Models Normalizados

```python
@dataclass
class Account:
    id: str
    institution: str
    name: str
    type: str
    currency: str
    balance: float
    available_balance: float

@dataclass
class Transaction:
    id: str
    account_id: str
    date: str
    description: str
    amount: float
    type: str
    category: str

@dataclass
class CreditCard:
    id: str
    institution: str
    name: str
    last_four_digits: str
    limit: float
    available_limit: float

@dataclass
class Invoice:
    card_id: str
    closing_date: str
    due_date: str
    total: float
    paid: float
    status: str

@dataclass
class Investment:
    id: str
    institution: str
    type: str
    name: str
    invested_amount: float
    current_value: float
    updated_at: str
```

---

## Segurança

- Nunca armazena credenciais bancárias
- Consentimento via Open Finance (app do banco)
- Tokens Pluggy via variáveis de ambiente apenas
- Nenhum dado financeiro completo em logs
- Cache com source_updated_at

---

## Pitfalls Conhecidos

### 🔴 Endpoint de auth: `POST /auth` (não `/api`)
A documentação antiga e algumas páginas da Pluggy citam `POST /api` para obter a apiKey,
mas o endpoint real é **`POST /auth`**. Usar `/api` retorna **403 Forbidden** mesmo com
credenciais perfeitamente válidas. O SDK oficial (`pluggy-sdk`) usa `/auth` internamente.

### 🔴 Trial não permite listar items
O trial grátis do Dashboard (15 dias) retorna `LIST_ITEMS_FEATURE_NOT_ENABLED` para
`GET /items`. Isso **não** significa que a API não funciona — apenas que você precisa
passar o **Item ID direto** via `GET /items/{id}`.

Solução: anote o Item ID (UUID) que aparece no Dashboard quando você vincula o
MeuPluggy, e configure como `PLUGGY_ITEM_ID` no ambiente.

### 🟡 SDK oficial: `pluggy-sdk`
A Pluggy mantém um SDK Python oficial (`pluggy-sdk` instalável via pip/uv) que lida
com a autenticação e serialização corretamente. Prefira usar o SDK em vez de chamadas
`requests` manuais — a serialização de tipos e os parâmetros de autenticação são
validados pelo SDK.

### 🟡 Dependências: `pluggy-sdk` + `requests`
Antes de usar a skill, instale as dependências:
```bash
source /opt/data/.venv/bin/activate
uv pip install pluggy-sdk requests
```

### 🟡 Paginação: v1 (page number) vs v2 (cursor string)
A API Pluggy tem **dois esquemas de paginação** que convivem:
- **v1** (accounts, bills, connectors, etc.): resposta tem `page` (int), `totalPages` (int), `results` (list). Navegue com `?page=N`.
- **v2** (transactions, etc.): resposta tem `results` (list) e **`next`** (string cursor ou null). **Não tem campo `page`**. Navegue com `?cursor=...` usando o valor de `next`.

⚠️ **Erro comum**: assumir que v2 tem `page.nextCursor` como dict. O campo de paginação v2 é **top-level `next`** (string), não `page.nextCursor`.
```python
# CERTO (v2):
cursor = data.get("next")       # string ou None
# ERRADO (v2):
cursor = data.get("page", {}).get("nextCursor")  # AttributeError
```

Para saber qual esquema um endpoint usa, faça uma chamada de teste e inspecione as chaves da resposta:
```python
r = requests.get(f"https://api.pluggy.ai/v2/transactions?...", headers=headers)
print(list(r.json().keys()))  # v2: ['results', 'next']; v1: ['results', 'page', 'totalPages']
```

O código da skill lida com ambos (usa `data.get("next")` primeiro, depois `page`/`totalPages` como fallback), mas ao adicionar manualmente um novo endpoint, verifique antes qual esquema ele usa.

### 🟠 Parâmetros de data no v2
O endpoint `GET /v2/transactions` usa `dateFrom`/`dateTo` (camelCase), **não** `from`/`to` ou `date_from`/`date_to`. Usar os nomes errados retorna 400:
```
"property from should not exist, property to should not exist"
```

### 🟠 Transações PENDING em cartão de crédito
O endpoint `/v2/transactions` retorna transações com status `PENDING` e `POSTED`. **Ambas devem ser consideradas** ao calcular a próxima fatura:
- `PENDING`: compras que ainda não fecharam mas já estão na fatura atual (compras recentes, parcelas)
- `POSTED`: compras já processadas

Filtrar apenas `POSTED` subestima o valor real da fatura. A fatura real é a soma de **todas** as transações (PENDING + POSTED) desde o último fechamento, **excluindo** pagamentos de faturas anteriores (identificáveis pela categoria `Credit card payment`).

```python
# Cálculo correto da próxima fatura:
fatura = [t for t in transactions if t['date'] >= ultimo_fechamento]
gastos = [t for t in fatura if t.get('category') != 'Credit card payment']
total_fatura = sum(abs(t['amount']) for t in gastos)
```

### 🟠 Saldo das contas: `balance` no topo, não em `bankData`
No endpoint `GET /accounts`, o saldo da conta corrente está no campo `balance` do nível **principal do JSON**, não dentro de `bankData.balance`. O campo `bankData.closingBalance` é um valor separado (pode ser igual). Sempre use `acc.get("balance", 0)` como fallback seguro.

### 🔴 Investment Transactions: endpoint não implementado no código

O endpoint `GET /investment-transactions?investmentId={id}` está documentado
na referência da API (`references/pluggy-api.md`) e existe na API Pluggy, mas
**não está implementado** no `pluggy_provider.py`.

A skill atual só retorna o saldo atual dos investimentos via `GET /investments`
(ex: valor total dos cofrinhos). Para obter **histórico de movimentações**
(aportes, retiradas, rendimentos), é necessário:

1. Adicionar o método `get_investment_transactions(investment_id, from_date, to_date)`
   no `PluggyProvider` (em `pluggy_provider.py`)
2. Expor via `financial_get_investment_transactions()` em `tools.py`

O padrão de implementação é idêntico ao `get_transactions()` já existente
(autenticação, paginação, erros) — basta trocar o endpoint e o schema de resposta.

### 🟡 Credenciais: ainda não configuradas no ambiente
Para acessar dados, a aplicação no Dashboard precisa ter o conector **MeuPluggy (id=200)**
adicionado e vinculado à sua conta do meu.pluggy.ai. Sequência correta:
1. Criar conta em meu.pluggy.ai e conectar bancos (uma vez)
2. Criar aplicação em dashboard.pluggy.ai → obter Client ID + Secret
3. Ir em **Customization → Connectors**, adicionar **MeuPluggy**
4. Fazer login com sua conta do Meu Pluggy para vincular
5. Anotar o Item ID gerado

### 🟡 MeuPluggy atualiza 1x/dia
Os dados sincronizam automaticamente uma vez ao dia. Não é possível forçar sync
pela API no plano gratuito (`POST /items/{id}/update` retorna 403). Dados podem
ter até 24h de defasagem.

### 🟠 Auth `/api` vs `/auth` — como os dois endpoints diferem
| Endpoint | Resultado no trial |
|----------|-------------------|
| `POST /auth` | ✅ Retorna apiKey funcional (usada pelo SDK) |
| `POST /api` | ❌ **403 Forbidden** — endpoint legado, desativado para contas novas |
| apiKey via `/auth` + `GET /connectors` | ✅ Funciona (236 conectores) |
| apiKey via `/auth` + `GET /items` | ❌ 401 — precisa de Item ID direto |
| apiKey via `/auth` + `GET /items/{id}` | ✅ Funciona |

### 🟠 Cuidado: token mix-up
A mensagem *"Make sure you're not mixing up your Connect Token and API Token"* aparece
quando se usa a apiKey como Bearer token ou em endpoints errados. A apiKey deve ir
no header **`X-API-KEY`** sempre.

---

## Cache Strategy

| Tipo | TTL |
|------|-----|
| Saldos | 5 min |
| Transações recentes | 30 min |
| Cartões/Faturas | 1h |
| Investimentos | 1h |
| Lista de conexões | 1h |
| Instituições | 24h |

---

## Limitações

- Sincronização: Meu Pluggy atualiza 1x/dia automaticamente
- Cartão Caixa: sem data de fechamento na cobertura atual
- Investimentos Itaú PF: pode ter cobertura parcial
- Dados de terceiros: não suportado no plano gratuito
- Sem tempo real: saldos são do último sync