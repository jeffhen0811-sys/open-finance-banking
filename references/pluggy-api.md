# Referência da API Pluggy (Meu Pluggy)

## Visão Geral

A [Pluggy](https://pluggy.ai) é uma plataforma de Open Finance regulada pelo Banco Central do Brasil.
Oferece uma API REST para acesso a dados bancários de +130 instituições financeiras.

### URL Base
```
https://api.pluggy.ai
```

### Autenticação
1. **`POST /auth`** com `clientId` + `clientSecret` → retorna `apiKey` (⚠️ NÃO `/api` — endpoint antigo documentado retorna 403)
2. `apiKey` válida por **2 horas**, usada no header `X-API-KEY`
3. SDKs disponíveis: Node.js, Python (pacote `pluggy-sdk`), .NET, Java

### SDK Oficial (Python)
```python
from pluggy_sdk import ApiClient, Configuration, AuthApi, AuthRequest

config = Configuration()
client = ApiClient(config)

# Auth usa POST /auth (o SDK faz isso internamente)
auth_api = AuthApi(client)
resp = auth_api.auth_create(auth_request=AuthRequest(
    client_id=os.environ["PLUGGY_CLIENT_ID"],
    client_secret=os.environ["PLUGGY_CLIENT_SECRET"],
))

# Configura apiKey corretamente (dict, não header direto)
config.api_key = {'X-API-KEY': resp.api_key}
```

### 🔴 Pitfall: Auth endpoint `/api` vs `/auth`
A documentação mais antiga da Pluggy cita `POST /api` como endpoint de autenticação.
**O endpoint real é `POST /auth`.** Usar `/api` retorna **403 Forbidden** mesmo com
credenciais válidas. O SDK oficial `pluggy-sdk` usa `/auth` e funciona.

### 🟡 Pitfall: MeuPluggy precisa estar vinculado no Dashboard
Para que `/items` retorne dados, a aplicação no Dashboard precisa ter o conector
**MeuPluggy (id=200)** adicionado e vinculado à sua conta do meu.pluggy.ai.
Sem isso, `GET /items` retorna 401 (array vazio). Passos:
1. Criar conta em meu.pluggy.ai e conectar os bancos
2. Criar aplicação em dashboard.pluggy.ai
3. No Dashboard, adicionar conector MeuPluggy à aplicação e fazer login
4. Só então a API retorna os dados bancários

### Plano Gratuito - Meu Pluggy
- Conecte **suas** contas em [meu.pluggy.ai](https://meu.pluggy.ai)
- Obtenha credenciais no [dashboard.pluggy.ai](https://dashboard.pluggy.ai)
- **Gratuito**, sem prazo de expiração
- Apenas contas do próprio usuário (mesmo CPF)

---

## Endpoints Principais

### Items (Conexões)
- `GET /items` — Lista conexões. **⚠️ Trial bloqueia** — retorna `LIST_ITEMS_FEATURE_NOT_ENABLED`
- `GET /items/{id}` — Detalhes da conexão. ✅ **Funciona no trial** — use ID fixo
- `POST /items/{id}/update` — Força sincronização. ⚠️ **Bloqueado no trial** (403)
- `DELETE /items/{id}` — Remove conexão

### Accounts (Contas)
- `GET /accounts?itemId={itemId}` — Contas de uma conexão. Paginação **v1** (`page` é **int**)
- **Saldo**: está em `balance` no nível PRINCIPAL do JSON, não em `bankData.balance`
- `GET /accounts/{id}` — Detalhes da conta
- `GET /accounts/{id}/balance` — Saldo em tempo real (⚠️ 404 no MeuPluggy)

### Transactions (Transações)
⚠️ **Deprecated**: `GET /transactions` retorna 410. Use **`GET /v2/transactions`**.
- `GET /v2/transactions?accountId={id}` — Transações, paginação **v2** (cursor-based)
- Filtros: `dateFrom`, `dateTo` (camelCase — NÃO `from`/`to` nem `date_from`/`date_to`)
- Primeira sync: últimos **12 meses**. Syncs subsequentes: apenas dados novos
- `page` na resposta é dict com `nextCursor` para próxima página

### Credit Cards (Cartões)
- Via `GET /accounts?itemId={id}` — filtrar `type=CREDIT`
- Bills/Faturas: `GET /bills?accountId={cardId}`

### Investments (Investimentos)
- `GET /investments?itemId={itemId}` — Lista investimentos
- `GET /investments/{id}` — Detalhes do investimento
- `GET /investment-transactions?investmentId={id}` — Transações do investimento

### Identity (Identidade)
- `GET /identity?itemId={itemId}` — Dados cadastrais

### Connectors
- `GET /connectors` — Lista todas as instituições suportadas
- `GET /connectors/{id}` — Detalhes do conector

---

## Cobertura por Instituição (Fonte: docs.pluggy.ai)

### Itaú Unibanco (conector OF/Pluggy)
| Recurso | Cobertura |
|---------|-----------|
| Conta Corrente | ✅ |
| Poupança | ✅ |
| Cartão de Crédito (Itaú Cartões) | ✅ Múltiplos cartões, parcelas, limite flexível, fechamento, vencimento |
| Fatura | ✅ Fechamento, vencimento, total, pago, status |
| Investimentos (Itaú Empresas) | ✅ Renda Fixa, Fundos |

### Caixa Econômica Federal (conector OF/Pluggy)
| Recurso | Cobertura |
|---------|-----------|
| Conta Corrente | ✅ |
| Poupança | ✅ |
| Cartão de Crédito | ✅ Múltiplos cartões, parcelas, limite, pagamento mínimo |
| Fatura | ✅ Vencimento, total — sem data de fechamento |
| Investimentos | ✅ Renda Fixa, Fundos, Títulos (Security) |

---

## Rate Limits (Plano Meu Pluggy)
- Leitura: limites por rota (consultar documentação)
- Sem SLA para plano gratuito
- Atualização automática 1x/dia

## Webhooks
- `ITEM.UPDATED` — Dados sincronizados
- `ITEM.ERROR` — Erro na sincronização
- `TRANSACTION.UPDATED` — Novas transações
- `TRANSACTION.CREATED` — Transações criadas