# 🦅 Projeto Carcará
### Sistema de Localização de Focos de Incêndio por Triangulação

---

## Visão Geral

O **Carcará** é um servidor central que recebe observações de usuários em campo (via aplicativo mobile), processa as direções de visão a partir das posições dos observadores e calcula a **localização provável de um foco de incêndio por triangulação geométrica**.

Cada observação carrega a posição 3D do observador (latitude, longitude e elevação acima do nível do mar), a direção da visada (azimute horizontal + pitch vertical do dispositivo), o tipo de ocorrência e a severidade. Com duas ou mais observações de pontos distintos, o algoritmo cruza os vetores de visão e estima as coordenadas do foco.

---

## Estrutura do Projeto

```
carcara/
├── manage.py
├── accounts/                        ← App de autenticação (JWT)
│   ├── models.py                    ← Modelo Usuario (AbstractUser)
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
├── observacoes/                     ← App principal
│   ├── models.py          ✏️        ← Observacao, Grupo, FocoEstimado, Relatorio
│   ├── serializers.py     ✏️
│   ├── views.py
│   ├── urls.py
│   ├── mapa.py                      ← Visualização Leaflet
│   └── services/
│       └── geo_utils/
│           ├── grupo_service.py ✏️  ← Agrupamento + média de severidade
│           └── triangulation.py    ← Algoritmo de triangulação (mínimos quadrados)
└── carcara/                         ← Configurações do projeto
    ├── settings.py
    └── urls.py
```

> ✏️ Arquivos alterados na última atualização — ver seção **Arquivos Alterados** abaixo.

---

## Instalação

```bash
# 1. Entre na pasta do projeto
cd carcara

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente (veja seção abaixo)

# 5. Rode as migrations
python manage.py makemigrations accounts
python manage.py makemigrations observacoes
python manage.py migrate

# 6. Crie um superusuário
python manage.py createsuperuser

# 7. Inicie o servidor
python manage.py runserver
```

---

## Variáveis de Ambiente

Crie um arquivo `.env` na pasta onde está o `manage.py`:

```env
DEBUG=true
SECRET_KEY=sua-chave-secreta-aqui
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=carcara_db
DB_USER=carcara_user
DB_PASSWORD=carcara_pass
DB_HOST=localhost
DB_PORT=5432

CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## Modelo do Banco de Dados

```
observacoes              grupos                 focos_estimados          relatorios
─────────────────────    ──────────────────     ────────────────────     ──────────────
id (PK)                  id (PK)                id (PK)                  id (PK)
usuario_id               status                 grupo_id (FK)            foco_id (FK)
timestamp                severity_media ← novo  lat_foco                 conteudo_json
lat                      criado_em              lon_foco                 gerado_em
lon                      atualizado_em          distancia_media_m        enviado
azimute                                         residuo_medio_m
elevacao                                        n_observacoes
precisao_gps                                    nivel_confianca
foto_url                                        distancia_elevacao_m
occurrence_type                                 calculado_em
severity_level ← novo
description
grupo_id (FK)
criado_em
```

### Campos da Observação

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `usuario_id` | string | ✅ | Identificador do usuário no app |
| `timestamp` | datetime | ✅ | Momento da observação (ISO 8601) |
| `lat` | float | ✅ | Latitude do observador (WGS84) |
| `lon` | float | ✅ | Longitude do observador (WGS84) |
| `azimute` | float | ✅ | Direção horizontal da visada em graus (0–360°) |
| `pitch` | float | ❌ | Ângulo vertical do dispositivo em graus (-90° a +90°) |
| `elevacao` | float | ❌ | Altitude do observador em metros acima do nível do mar |
| `precisao_gps` | float | ❌ | Precisão do GPS em metros |
| `occurrence_type` | string | ❌ | Tipo: `fogo` ou `fumaca` |
| `severity_level` | integer | ❌ | Severidade de **0 a 10** — barra de rolagem no app. 0–3 baixo, 4–6 médio, 7–10 alto |
| `description` | string | ❌ | Descrição livre da ocorrência |
| `foto_url` | string | ❌ | URL da foto enviada pelo app |

### Escala de Severidade

| Valor | Rótulo | Significado |
|-------|--------|-------------|
| 0 – 3 | `baixo` | Foco pequeno, sem expansão visível |
| 4 – 6 | `medio` | Foco moderado, fumaça visível |
| 7 – 10 | `alto` | Foco intenso, risco elevado |

O campo `severity_level` é enviado pelo app como um **inteiro de 0 a 10** (barra de rolagem/scroll). O servidor converte automaticamente para o rótulo semântico (`severity_label`) na resposta e calcula a **média (`severity_media`)** de todas as observações do grupo.

---

## Arquivos Alterados

### `observacoes/models.py`
- `Observacao`: adicionados `occurrence_type` (choices: `fogo`/`fumaca`), `severity_level` (`IntegerField` 0–10), `description` e property `severity_label`
- `Grupo`: adicionado `severity_media` (`FloatField`) — média automática do grupo

### `observacoes/serializers.py`
- `ObservacaoInputSerializer`: `severity_level` validado entre 0 e 10; novos campos `occurrence_type` e `description`
- `ObservacaoSerializer`: expõe `severity_label` (rótulo calculado via property do model)
- `GrupoSerializer`: expõe `severity_media` e `severity_label` do grupo

### `observacoes/services/geo_utils/grupo_service.py`
- Nova função `_atualizar_severity_media(grupo)` — usa `Avg` do Django ORM, ignorando observações sem severidade
- Chamada automática em `atribuir_ou_criar_grupo()` sempre que uma observação entra em um grupo

> Após aplicar os arquivos, rode:
> ```bash
> python manage.py makemigrations observacoes
> python manage.py migrate
> ```

---

## Autenticação JWT

A API usa **JSON Web Tokens (JWT)**. O fluxo é:

1. Faça login → receba `access` (válido 60 min) e `refresh` (válido 7 dias)
2. Envie o `access` em toda requisição protegida:
   ```
   Authorization: Bearer <access_token>
   ```
3. Quando o `access` expirar, use o `refresh` para obter um novo

---

## Endpoints — Autenticação `/auth/`

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| `POST` | `/auth/token/` | Login | Não |
| `POST` | `/auth/token/refresh/` | Renovar token | Não |
| `POST` | `/auth/token/verify/` | Verificar token | Não |
| `POST` | `/auth/registro/` | Criar conta | Não |
| `GET` | `/auth/perfil/` | Ver perfil | Sim |
| `PATCH` | `/auth/perfil/` | Atualizar perfil | Sim |
| `POST` | `/auth/alterar-senha/` | Trocar senha | Sim |
| `POST` | `/auth/logout/` | Logout (blacklist) | Sim |

---

## Endpoints — API Principal

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| `POST` | `/api/observacoes/` | Enviar nova observação | Sim |
| `GET` | `/api/observacoes/` | Listar observações | Sim |
| `GET` | `/api/observacoes/{id}/` | Detalhar observação | Sim |
| `GET` | `/api/grupos/` | Listar grupos | Sim |
| `GET` | `/api/grupos/{id}/` | Detalhar grupo | Sim |
| `POST` | `/api/grupos/{id}/processar/` | Reprocessar triangulação | Staff |
| `GET` | `/api/focos/` | Listar focos estimados | Sim |
| `GET` | `/api/focos/{id}/` | Detalhar foco | Sim |
| `GET` | `/api/relatorios/{foco_id}/` | Relatório completo | Sim |
| `GET` | `/api/mapa/dados/` | GeoJSON para o mapa | Não |
| `GET` | `/mapa/` | Visualização do mapa (Leaflet) | Não |

---

## Payload — POST `/api/observacoes/`

```json
{
  "usuario_id": "brigadista_01",
  "timestamp": "2026-04-03T14:32:10",
  "lat": -10.9172,
  "lon": -37.0731,
  "azimute": 73.2,
  "elevacao": 342.0,
  "precisao_gps": 12.0,
  "foto_url": "https://storage.carcara.br/fotos/001.jpg",
  "occurrence_type": "fumaca",
  "severity_level": 8,
  "description": "Coluna de fumaça densa avistada na encosta norte"
}
```

**Resposta (201):**
```json
{
  "id": 42,
  "usuario_id": "brigadista_01",
  "lat": -10.9172,
  "lon": -37.0731,
  "azimute": 73.2,
  "elevacao": 342.0,
  "precisao_gps": 12.0,
  "foto_url": "https://storage.carcara.br/fotos/001.jpg",
  "occurrence_type": "fumaca",
  "severity_level": 8,
  "severity_label": "alto",
  "description": "Coluna de fumaça densa avistada na encosta norte",
  "grupo_id": 7,
  "criado_em": "2026-04-03T14:32:11Z"
}
```

---

## Exemplo com curl

```bash
# 1. Login
curl -X POST http://localhost:8000/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "brigadista_01", "password": "suasenha"}'

# 2. Enviar observação
curl -X POST http://localhost:8000/api/observacoes/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "brigadista_01",
    "timestamp": "2026-04-03T14:32:10",
    "lat": -10.9172,
    "lon": -37.0731,
    "azimute": 73.2,
    "elevacao": 342.0,
    "precisao_gps": 12.0,
    "foto_url": "https://storage.carcara.br/fotos/001.jpg",
    "occurrence_type": "fumaca",
    "severity_level": 8,
    "description": "Coluna de fumaça densa avistada na encosta norte"
  }'

# 3. Ver grupos formados (inclui severity_media e severity_label)
curl -X GET http://localhost:8000/api/grupos/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN"

# 4. Ver foco estimado
curl -X GET http://localhost:8000/api/focos/1/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN"
```

---

## Algoritmo de Triangulação

### Problema

Cada observador está em uma posição 3D conhecida `(x₀, y₀, z₀)` (UTM + elevação) e aponta o celular para a fumaça, gerando um **vetor de visão 3D** definido pelo azimute `θ` e pelo pitch `φ`:

```
d = (cos φ · sin θ,  cos φ · cos θ,  sin φ)

L(t) = O + t · d     (t ≥ 0)
```

Com N ≥ 2 observadores, o algoritmo encontra o ponto `P_foco` que **minimiza a soma das distâncias perpendiculares** a todas as linhas de visão.

### Formulação Matricial (Mínimos Quadrados)

Para cada linha de visão `i` com vetor unitário `dᵢ` e origem `Oᵢ`:

```
M�� = I − dᵢ · dᵢᵀ

A = Σ Mᵢ
b = Σ Mᵢ · Oᵢ

P_foco = A⁻¹ · b
```

### Estimativa por Pitch

Quando o `pitch` está disponível, é possível estimar a distância horizontal ao foco independentemente:

```
Δh = elevacao_observador − elevacao_estimada_foco
r  = Δh / tan(pitch)
```

Esse valor serve como validação cruzada com a triangulação por azimute.

### Nível de Confiança

| Condição | Nível |
|----------|-------|
| 1 observação | Baixo |
| 2 obs. com ângulo entre visadas < 15° | Baixo |
| 2 obs. com ângulo ≥ 15° | Médio |
| 3+ obs. com resíduo ≤ 500 m | Alto |
| Resíduo > 1000 m (qualquer N) | Baixo |

---

## Agrupamento Espaço-Temporal

Observações são agrupadas automaticamente ao chegar. Uma nova observação entra em um grupo existente se:

- A diferença de tempo com a observação mais recente do grupo for **≤ 30 minutos**
- A distância entre os observadores for **≤ 10 km**

Caso contrário, um novo grupo é criado. Após cada nova observação, o grupo é reprocessado em background e um novo `FocoEstimado` é calculado.

A **média de severidade** (`severity_media`) do grupo é recalculada automaticamente a cada observação adicionada, considerando apenas observações que informaram `severity_level`.

---

## Relatório Gerado

```json
{
  "projeto": "CARCARÁ — Sistema de Localização de Focos de Incêndio",
  "localizacao_estimada": {
    "latitude": -10.89341,
    "longitude": -37.06127,
    "google_maps": "https://www.google.com/maps?q=-10.89341,-37.06127"
  },
  "ocorrencia": {
    "tipo": "fumaca",
    "severity_level": 8,
    "severity_label": "alto",
    "descricoes": [
      "Coluna de fumaça densa avistada na encosta norte"
    ]
  },
  "metricas": {
    "n_observacoes": 3,
    "distancia_media_m": 2847.3,
    "distancia_media_km": 2.85,
    "residuo_medio_m": 124.7,
    "nivel_confianca": "alto",
    "interpretacao": "Estimativa com alta confiabilidade — 3 observadores com baixo resíduo."
  },
  "midias": {
    "total_fotos": 2,
    "urls_fotos": [
      "https://storage.carcara.br/fotos/001.jpg",
      "https://storage.carcara.br/fotos/002.jpg"
    ]
  },
  "acoes_recomendadas": [
    "✅ Acionar brigada de combate ao incêndio.",
    "✅ Notificar Corpo de Bombeiros com as coordenadas estimadas.",
    "✅ Monitorar evolução com novas observações."
  ]
}
```

---

## Mapa Interativo

Acesse: `http://localhost:8000/mapa/`

Visualização em tempo real com Leaflet mostrando:
- 📍 Posição dos observadores
- ➡️ Linhas de visada (azimute + pitch)
- 🔥 Focos estimados com raio de confiança colorido por severidade

---

## Painel Admin

Acesse: `http://localhost:8000/admin/`

Gerencie usuários, observações, grupos e focos diretamente pelo painel do Django.

---

## Dependências Principais

| Pacote | Função |
|--------|--------|
| Django 5.x | Framework web |
| djangorestframework | API REST |
| djangorestframework-simplejwt | Autenticação JWT |
| django-cors-headers | CORS para frontend/app mobile |
| psycopg2 | Conector PostgreSQL |
| numpy | Álgebra linear para triangulação |
| pyproj | Conversão WGS84 ↔ UTM |