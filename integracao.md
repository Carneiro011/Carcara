# Integração JWT — Projeto Carcará

## Arquivos gerados

```
carcara_jwt/
├── accounts/                   ← novo app (copiar para dentro de carcara/)
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py               ← modelo Usuario customizado
│   ├── serializers.py          ← login, registro, perfil, alterar senha
│   ├── views.py                ← todos os endpoints de auth
│   ├── urls.py                 ← rotas /auth/...
│   ├── tests.py                ← testes completos
│   └── migrations/
│       └── 0001_initial.py
├── carcara/
│   ├── settings.py             ← substituir o original
│   └── urls.py                 ← substituir o original
├── observacoes/
│   └── views.py                ← substituir o original (adiciona permission_classes)
└── .env.example
```

---

## Passo a passo de integração

### 1. Instalar dependências

```bash
pip install djangorestframework-simplejwt
```

Adicione ao `requirements.txt`:
```
djangorestframework-simplejwt>=5.3
```

### 2. Copiar arquivos

```bash
# Copiar o app accounts inteiro
cp -r carcara_jwt/accounts/  carcara/carcara/accounts/

# Substituir settings e urls
cp carcara_jwt/carcara/settings.py  carcara/carcara/carcara/settings.py
cp carcara_jwt/carcara/urls.py      carcara/carcara/carcara/urls.py

# Substituir views de observacoes (adiciona permission_classes)
cp carcara_jwt/observacoes/views.py  carcara/carcara/observacoes/views.py
```

### 3. Rodar as migrations

> ⚠️ Como o `AUTH_USER_MODEL` mudou, faça isso num banco limpo OU siga
> o passo de squash abaixo se já tiver dados.

**Banco novo (recomendado em desenvolvimento):**
```bash
cd carcara/carcara
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
```

**Banco existente com dados:**
```bash
# 1. Crie a migration do accounts
python manage.py makemigrations accounts

# 2. Rode as migrations de accounts antes das demais
python manage.py migrate accounts

# 3. Rode o resto
python manage.py migrate
```

### 4. Rodar os testes

```bash
python manage.py test accounts
```

---

## Endpoints disponíveis

| Método | URL | Descrição | Auth |
|--------|-----|-----------|------|
| `POST` | `/auth/token/` | Login → access + refresh + dados do usuário | ❌ |
| `POST` | `/auth/token/refresh/` | Renovar access token | ❌ |
| `POST` | `/auth/token/verify/` | Verificar validade do token | ❌ |
| `POST` | `/auth/registro/` | Criar nova conta | ❌ |
| `POST` | `/auth/logout/` | Invalidar refresh (blacklist) | ✅ |
| `GET` | `/auth/perfil/` | Dados do usuário logado | ✅ |
| `PATCH` | `/auth/perfil/` | Atualizar nome/instituição | ✅ |
| `POST` | `/auth/alterar-senha/` | Trocar senha | ✅ |

**Rotas da API principal** (todas exigem token agora):

| Método | URL | Permissão |
|--------|-----|-----------|
| `GET/POST` | `/api/observacoes/` | Autenticado |
| `GET` | `/api/grupos/` | Autenticado |
| `POST` | `/api/grupos/{id}/processar/` | **Staff only** |
| `GET` | `/api/focos/` | Autenticado |
| `GET` | `/api/relatorios/{id}/` | Autenticado |
| `GET` | `/api/mapa/dados/` | **Público** |
| `GET` | `/mapa/` | **Público** |

---

## Como usar nos clientes

### Login
```bash
curl -X POST http://localhost:8000/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "seu_usuario", "password": "sua_senha"}'
```

Resposta:
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "usuario": {
    "id": 1,
    "username": "seu_usuario",
    "email": "...",
    "nome_completo": "...",
    "instituicao": "...",
    "is_staff": false
  }
}
```

### Usar o token nas requisições
```bash
curl http://localhost:8000/api/observacoes/ \
  -H "Authorization: Bearer eyJ..."
```

### Renovar token (antes de expirar — padrão: 60 min)
```bash
curl -X POST http://localhost:8000/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ..."}'
```

### Logout
```bash
curl -X POST http://localhost:8000/auth/logout/ \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ..."}'
```

---

## Configurações relevantes no settings.py

```python
# Tempo de vida dos tokens (ajuste conforme necessidade)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,   # novo refresh a cada uso
    "BLACKLIST_AFTER_ROTATION": True, # invalida o refresh antigo
}
```

---

## Estrutura de permissões

```
Público (sem token)
├── POST /auth/token/
├── POST /auth/token/refresh/
├── POST /auth/registro/
├── GET  /api/mapa/dados/
└── GET  /mapa/

Autenticado (Bearer token)
├── GET/POST /api/observacoes/
├── GET      /api/grupos/
├── GET      /api/focos/
├── GET      /api/relatorios/{id}/
├── GET/PATCH /auth/perfil/
├── POST     /auth/logout/
└── POST     /auth/alterar-senha/

Staff apenas (is_staff=True)
└── POST /api/grupos/{id}/processar/
```