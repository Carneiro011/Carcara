# Projeto Carcará

> Sistema de detecção e triangulação de focos de incêndio por observações georreferenciadas colaborativas.

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação](#instalação)
- [Configuração .env](#configuração-env)
- [Migrations](#migrations)
- [Rodando o Servidor](#rodando-o-servidor)
- [Autenticação](#autenticação)
- [Endpoints da API](#endpoints-da-api)
- [Permissões](#permissões)
- [Configurações do Sistema](#configurações-do-sistema)
- [Checklist de Segurança](#checklist-de-segurança)
- [Testes](#testes)

---

## Visão Geral

O Carcará é uma API REST desenvolvida em Django + Django REST Framework que recebe observações de campo enviadas por um aplicativo mobile. Cada observação contém a posição GPS do observador, o azimute (direção da visada) e o ângulo de pitch (elevação acima do horizonte). O sistema agrupa observações próximas e aplica algoritmos de triangulação geoespacial para estimar a localização de focos de incêndio.

```
Observador A ──azimute──►
                          X  <- Foco estimado
Observador B ──azimute──►
```

---

## Arquitetura

```
carcara/
├── accounts/          App de autenticação (JWT + Google OAuth)
├── observacoes/       App principal (observações, grupos, focos, mapa)
└── carcara/           Pacote de configuração Django
```

Fluxo principal:

```
App Mobile
   |
   ├── POST /auth/token/         -> Login -> JWT
   |
   └── POST /api/observacoes/    -> Nova observação
              |
              v
         atribuir_ou_criar_grupo()
              |
              v
         processar_grupo_async()
              |
              v
         triangulação geoespacial
              |
              v
         FocoEstimado + Relatorio
```

---

## Tecnologias

| Camada | Tecnologia | Versão |
|---|---|---|
| Framework | Django | 6.0.3 |
| API REST | Django REST Framework | 3.17 |
| Autenticação | djangorestframework-simplejwt | >= 5.3 |
| OAuth | google-auth | >= 2.0 |
| Banco de dados | PostgreSQL | >= 14 |
| Driver DB | psycopg2 | 3.3.3 |
| Cálculo numérico | NumPy | 2.4.2 |
| Tipos geoespaciais | GeoAlchemy2 | 0.18.4 |
| CORS | django-cors-headers | — |

---

## Estrutura do Projeto

```
carcara/
├── accounts/
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   └── 0002_usuario_telefone_username_limit.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py          # Usuario (AbstractUser customizado)
│   ├── serializers.py     # login, registro, perfil, senha, recuperação
│   ├── tests.py           # 26 testes automatizados
│   ├── urls.py            # rotas /auth/...
│   └── views.py           # todas as views de autenticação
├── observacoes/
│   ├── migrations/
│   ├── services/
│   │   └── geo_utils/     # triangulação, agrupamento
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py
├── carcara/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── .env.example
```

---

## Instalação

### Pré-requisitos

- Python 3.11+
- PostgreSQL 14+

### Passos

```bash
# 1. Clonar o repositório
git clone https://github.com/nupreds/carcara.git
cd carcara/carcara

# 2. Criar e ativar ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependências
pip install -r requirements.txt
pip install google-auth

# 4. Configurar variáveis de ambiente
cp .env.example .env
# editar .env com seus valores reais

# 5. Criar banco de dados
createdb carcara_db

# 6. Rodar migrations
python manage.py migrate

# 7. Criar superusuário
python manage.py createsuperuser
```

---

## Configuração .env

```
# Django
DEBUG=false
SECRET_KEY=          # python -c "import secrets; print(secrets.token_hex(64))"
ALLOWED_HOSTS=       # ex: api.carcara.nupreds.br

# Banco de dados
DB_NAME=carcara_db
DB_USER=carcara_user
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# CORS
CORS_ORIGINS=        # ex: https://app.carcara.nupreds.br

# Google OAuth
GOOGLE_CLIENT_ID=    # console.cloud.google.com

# E-mail
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=Carcará <noreply@carcara.br>
FRONTEND_URL=
PASSWORD_RESET_TIMEOUT=259200

# Rate limiting
THROTTLE_ANON=20/hour
THROTTLE_USER=200/hour
THROTTLE_LOGIN=10/hour
```

> Nunca commite o `.env` no Git. Adicione ao `.gitignore`.

---

## Migrations

```bash
python manage.py migrate
python manage.py migrate accounts 0002       # telefone + limite username
python manage.py migrate observacoes 0006    # azimute opcional
python manage.py flushexpiredtokens          # limpar blacklist (executar periodicamente)
```

---

## Rodando o Servidor

```bash
# Desenvolvimento
python manage.py runserver

# Produção
gunicorn carcara.wsgi:application --workers 4 --bind 0.0.0.0:8000
```

---

## Autenticação

A API usa JWT via djangorestframework-simplejwt.

### Login

```bash
curl -X POST https://api.carcara.nupreds.br/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "joao", "password": "Senha@123"}'
```

Resposta:
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "usuario": {
    "id": 1, "username": "joao", "email": "joao@nupreds.br",
    "nome_completo": "João Silva", "telefone": "+55 88 99999-9999",
    "is_staff": false
  }
}
```

### Usando o token

```bash
curl https://api.carcara.nupreds.br/api/observacoes/ \
  -H "Authorization: Bearer eyJ..."
```

### Login com Google

```bash
curl -X POST https://api.carcara.nupreds.br/auth/google/ \
  -d '{"id_token": "<token_do_sdk_google>"}'
```

---

## Endpoints da API

### Autenticação (/auth/)

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | /auth/token/ | Login | Não |
| POST | /auth/token/refresh/ | Renovar token | Não |
| POST | /auth/token/verify/ | Verificar token | Não |
| POST | /auth/registro/ | Criar conta (retorna token) | Não |
| POST | /auth/google/ | Login com Google | Não |
| POST | /auth/logout/ | Logout (blacklist) | Sim |
| GET | /auth/perfil/ | Dados do usuário | Sim |
| PATCH | /auth/perfil/ | Atualizar perfil | Sim |
| POST | /auth/alterar-senha/ | Trocar senha | Sim |
| POST | /auth/esqueci-senha/ | Reset por e-mail | Não |
| POST | /auth/redefinir-senha/ | Redefinir com token | Não |

### API Principal (/api/)

| Método | Endpoint | Descrição | Permissão |
|---|---|---|---|
| GET/POST | /api/observacoes/ | Observações | Autenticado |
| GET | /api/grupos/ | Grupos de observações | Autenticado |
| POST | /api/grupos/{id}/processar/ | Reprocessar triangulação | Staff |
| GET | /api/focos/ | Focos estimados | Autenticado |
| GET | /api/relatorios/{id}/ | Relatório do foco | Autenticado |
| GET/PATCH | /api/configuracoes/ | Configurações do sistema | Autenticado/Staff |
| GET | /api/mapa/dados/ | GeoJSON do mapa | Público |

### Payload — Enviar Observação

```json
{
  "usuario_id":      "user_abc123",
  "timestamp":       "2025-04-21T14:30:00Z",
  "lat":             -3.7172,
  "lon":             -38.5433,
  "azimute":         145.5,
  "elevacao":        12.3,
  "precisao_gps":    8.5,
  "occurrence_type": "fogo",
  "severity_level":  7,
  "description":     "Fumaça espessa visível"
}
```

`azimute` e `elevacao` são opcionais — dispositivos sem bússola podem omiti-los.

---

## Permissões

| Recurso | Usuário | Admin |
|---|---|---|
| Enviar e ver observações | Sim | Sim |
| Ver configurações | Sim | Sim |
| Editar configurações | Não | Sim |
| Reprocessar triangulação | Não | Sim |
| Painel /admin/ | Não | Sim |

---

## Configurações do Sistema

| Parâmetro | Padrão | Descrição |
|---|---|---|
| raio_espacial_km | 3 km | Raio de agrupamento |
| min_obs_alto | 3 | Mínimo observadores (ALTA) |
| residuo_alto_m | 500 m | Resíduo máximo (ALTA) |
| dist_media_alto_m | 5000 m | Distância média máx (ALTA) |
| min_obs_medio | 2 | Mínimo observadores (MÉDIA) |
| angulo_min_graus | 15° | Ângulo mínimo entre visadas |
| residuo_medio_m | 500 m | Resíduo máximo (MÉDIA) |
| raio_confianca_alto_m | 500 m | Círculo no mapa (ALTA) |
| raio_confianca_medio_m | 1500 m | Círculo no mapa (MÉDIA) |
| raio_confianca_baixo_m | 3000 m | Círculo no mapa (BAIXA) |

---

## Checklist de Segurança

| Item | Status |
|---|---|
| JWT em todas as rotas | OK |
| Autorização user / staff | OK |
| Serializers sem password | OK |
| Variáveis no .env | OK |
| HTTPS em produção | OK |
| CORS restrito | OK |
| Rate limit login (10/hora) | OK |
| Rate limit geral | OK |
| Blacklist no logout | OK |
| Rotação de refresh token | OK |

---

## Testes

```bash
python manage.py test accounts
coverage run manage.py test accounts && coverage report -m
```

Cobertura: registro, login, refresh, logout, blacklist, perfil, alterar senha, recuperação por e-mail, proteção JWT e restrição de staff — 26 casos de teste.''''