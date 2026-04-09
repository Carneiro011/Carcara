# 🦅 Projeto Carcará
### Sistema de Localização de Focos de Incêndio por Triangulação

---

## Visão Geral

O **Carcará** é um servidor central que recebe observações de usuários em campo (via aplicativo mobile), processa as direções de visão a partir das posições dos observadores e calcula a **localização provável de um foco de incêndio por triangulação geométrica**.

Cada observação carrega a posição do observador (latitude, longitude e elevação), a direção da visada (azimute horizontal), o tipo de ocorrência e a severidade. Com duas ou mais observações de pontos distintos, o algoritmo cruza os vetores de visão e estima as coordenadas do foco. O nível de confiança da estimativa é calculado dinamicamente a partir de parâmetros configuráveis pelo staff.

---

## Estrutura do Projeto

```
Carcara/
├── requirements.txt
├── README.md
└── carcara/
    ├── manage.py
    ├── carcara/                         ← Configurações do projeto Django
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── accounts/                        ← App de autenticação (JWT)
    │   ├── models.py                    ← Modelo Usuario (AbstractUser)
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    └── observacoes/                     ← App principal
        ├── models.py                    ← Observacao, Grupo, FocoEstimado,
        │                                   Relatorio, ConfiguracaoSistema
        ├── serializers.py
        ├── views.py
        ├── urls.py
        ├── mapa.py                      ← Página Leaflet (HTML inline)
        ├── migrations/
        │   ├── 0001_initial.py
        │   ├── 0002_configuracaosistema_completo.py
        │   └── 0003_configuracao_confianca.py
        ├── reports/
        │   └── generate_report.py      ← Geração de relatório JSON
        └── services/
            └── geo_utils/
                ├── geo_utils.py        ← Conversão WGS84 ↔ UTM
                ├── distance_calc.py    ← Haversine, agrupamento Union-Find
                ├── grupo_service.py    ← Agrupamento espaço-temporal
                └── triangulation.py   ← Algoritmo de triangulação (MQ)
```

---

## Instalação

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd Carcara/carcara

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente (veja seção abaixo)

# 5. Rode as migrations
python manage.py migrate

# 6. Crie um superusuário
python manage.py createsuperuser

# 7. Inicie o servidor
python manage.py runserver
```

---

## Variáveis de Ambiente

Crie um arquivo `.env` na mesma pasta do `manage.py`:

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
observacoes              grupos               focos_estimados
──────────────────       ──────────────       ────────────────────
id (PK)                  id (PK)              id (PK)
usuario_id               status               grupo_id (FK)
timestamp                severity_media       lat_foco
lat                      criado_em            lon_foco
lon                      atualizado_em        distancia_media_m
azimute                                       residuo_medio_m
elevacao                                      n_observacoes
precisao_gps                                  nivel_confianca
foto_url                                      distancia_elevacao_m
occurrence_type                               calculado_em
severity_level
description
grupo_id (FK)            relatorios           configuracoes_sistema
criado_em                ──────────────       ─────────────────────
                         id (PK)              id (PK)
                         foco_id (FK)         raio_espacial_km
                         conteudo_json        raio_confianca_alto_m
                         gerado_em            raio_confianca_medio_m
                         enviado              raio_confianca_baixo_m
                                              min_obs_alto
                                              residuo_alto_m
                                              dist_media_alto_m
                                              min_obs_medio
                                              angulo_min_graus
                                              residuo_medio_m
```

### Campos da Observação

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `usuario_id` | string | ✅ | Identificador do usuário no app |
| `timestamp` | datetime | ✅ | Momento da observação (ISO 8601) |
| `lat` | float | ✅ | Latitude do observador (WGS84) |
| `lon` | float | ✅ | Longitude do observador (WGS84) |
| `azimute` | float | ✅ | Direção horizontal da visada em graus (0–360°) |
| `elevacao` | float | ❌ | Altitude do observador em metros (nível do mar) |
| `precisao_gps` | float | ❌ | Precisão do GPS em metros |
| `occurrence_type` | string | ❌ | Tipo: `fogo` ou `fumaca` |
| `severity_level` | int | ❌ | Severidade de 0 a 10 (0–3 baixo, 4–6 médio, 7–10 alto) |
| `description` | string | ❌ | Descrição livre da ocorrência |
| `foto_url` | string | ❌ | URL da foto enviada pelo app |

### Modelo de Usuário

O modelo `Usuario` estende `AbstractUser` do Django com os campos adicionais:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome_completo` | string | Nome completo do usuário |
| `instituicao` | string | Instituição (ex: Corpo de Bombeiros, ICMBio) |
| `tipo_usuario` | string | `ADMIN` ou `USUARIO` |
| `email` | string | E-mail único (obrigatório) |

---

## Autenticação JWT

A API usa **JSON Web Tokens (JWT)**. O fluxo é:

1. Faça login → receba `access` (válido 60 min) e `refresh` (válido 7 dias)
2. Envie o `access` em toda requisição protegida:
   ```
   Authorization: Bearer <access_token>
   ```
3. Quando o `access` expirar, use o `refresh` para renovar

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
| `GET` | `/api/configuracoes/` | Ver configurações do sistema | Sim |
| `PATCH` | `/api/configuracoes/` | Alterar configurações | Staff |
| `POST` | `/api/observacoes/` | Enviar nova observação | Sim |
| `GET` | `/api/observacoes/` | Listar observações | Sim |
| `GET` | `/api/observacoes/{id}/` | Detalhar observação | Sim |
| `GET` | `/api/grupos/` | Listar grupos | Sim |
| `GET` | `/api/grupos/{id}/` | Detalhar grupo | Sim |
| `POST` | `/api/grupos/{id}/processar/` | Reprocessar triangulação | Staff |
| `GET` | `/api/focos/` | Listar focos estimados | Sim |
| `GET` | `/api/focos/{id}/` | Detalhar foco | Sim |
| `GET` | `/api/relatorios/{foco_id}/` | Relatório completo (JSON) | Sim |
| `GET` | `/api/mapa/dados/` | GeoJSON para o mapa | Não |
| `GET` | `/mapa/` | Visualização Leaflet interativa | Não |

---

## Payload — POST `/api/observacoes/`

```json
{
  "usuario_id": "brigadista_01",
  "timestamp": "2026-04-08T14:32:10",
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
  "severity_level": 8,
  "severity_label": "alto",
  "grupo_id": 7,
  "criado_em": "2026-04-08T14:32:11Z"
}
```

---

## Payload — PATCH `/api/configuracoes/`

Requer `is_staff=True` ou `is_superuser=True`.

```json
{
  "raio_espacial_km": 3.0,
  "raio_confianca_alto_m": 500.0,
  "raio_confianca_medio_m": 1500.0,
  "raio_confianca_baixo_m": 3000.0,
  "min_obs_alto": 3,
  "residuo_alto_m": 500.0,
  "dist_media_alto_m": 5000.0,
  "min_obs_medio": 2,
  "angulo_min_graus": 15.0,
  "residuo_medio_m": 500.0
}
```

Todos os campos são opcionais (PATCH parcial). Validações aplicadas:

- `raio_espacial_km`: entre 0.1 e 50.0 km
- `min_obs_alto` deve ser ≥ `min_obs_medio`
- Raios de mapa: entre 50 m e 50.000 m
- Resíduos: entre 10 m e 10.000 m
- Ângulo: entre 1° e 90°

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
    "timestamp": "2026-04-08T14:32:10",
    "lat": -10.9172,
    "lon": -37.0731,
    "azimute": 73.2,
    "elevacao": 342.0,
    "precisao_gps": 12.0,
    "occurrence_type": "fumaca",
    "severity_level": 8,
    "description": "Coluna de fumaça na encosta norte"
  }'

# 3. Ver grupos formados
curl -X GET http://localhost:8000/api/grupos/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN"

# 4. Ver foco estimado
curl -X GET http://localhost:8000/api/focos/1/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN"

# 5. Alterar configurações (requer staff)
curl -X PATCH http://localhost:8000/api/configuracoes/ \
  -H "Authorization: Bearer SEU_ACCESS_TOKEN_STAFF" \
  -H "Content-Type: application/json" \
  -d '{"raio_espacial_km": 5.0, "min_obs_alto": 4}'
```

---

## Agrupamento Espaço-Temporal

Observações são agrupadas automaticamente ao chegar. Uma nova observação entra em um grupo existente se:

- A diferença de tempo com a observação mais recente do grupo for **≤ 30 minutos**
- A distância entre os observadores for **≤ raio configurado** (padrão: **3 km**)

Caso contrário, um novo grupo é criado. Após cada nova observação, o grupo é reprocessado em background e um novo `FocoEstimado` é calculado.

O raio de agrupamento pode ser ajustado via `PATCH /api/configuracoes/` por usuários com permissão **staff** ou **admin**.

---

## Algoritmo de Triangulação

### Problema

Cada observador está em uma posição conhecida `(x₀, y₀)` em coordenadas UTM e aponta o celular para a fumaça, gerando um **vetor de visão** definido pelo azimute `θ`:

```
d = (cos θ,  sin θ)
L(t) = O + t · d     (t ≥ 0)
```

Com N ≥ 2 observadores, o algoritmo encontra o ponto `P_foco` que **minimiza a soma das distâncias perpendiculares** a todas as linhas de visão.

### Formulação Matricial (Mínimos Quadrados)

Para cada linha de visão `i` com vetor unitário `d_i` e origem `O_i`:

```
M_i = I − d_i · d_iᵀ

A = Σ M_i
b = Σ M_i · O_i

P_foco = A⁻¹ · b
```

### Estimativa por Elevação (Pitch)

Quando o ângulo de elevação está disponível, estima-se a distância horizontal ao foco:

```
r = Δh / tan(φ)
```

onde `Δh` é a diferença de altitude entre observador e referência (padrão: 50 m). Serve como validação cruzada com a triangulação por azimute.

### Nível de Confiança (parametrizado)

A confiança é calculada em conjunção lógica (E), avaliada em ordem:

| Nível | Condição |
|-------|----------|
| **Alto** | n_obs ≥ `min_obs_alto` **E** resíduo ≤ `residuo_alto_m` **E** dist_média ≤ `dist_media_alto_m` |
| **Médio** | n_obs ≥ `min_obs_medio` **E** ângulo_min ≥ `angulo_min_graus` **E** resíduo ≤ `residuo_medio_m` |
| **Baixo** | qualquer outro caso |

**Valores padrão:**

| Parâmetro | Padrão |
|-----------|--------|
| `min_obs_alto` | 3 observadores |
| `residuo_alto_m` | 500 m |
| `dist_media_alto_m` | 5.000 m |
| `min_obs_medio` | 2 observadores |
| `angulo_min_graus` | 15° |
| `residuo_medio_m` | 500 m |

Todos os parâmetros são ajustáveis pelo staff via `PATCH /api/configuracoes/`.

---

## Mapa Interativo

Acesse: `http://localhost:8000/mapa/`

Visualização em tempo real com Leaflet (OpenStreetMap) mostrando:

- 📍 Posição dos observadores
- ➡️ Linhas de visada (azimute)
- 🔥 Focos estimados com raio de confiança colorido por nível
- Atualização automática a cada 15 segundos

---

## Painel Admin

Acesse: `http://localhost:8000/admin/`

Gerencie usuários, observações, grupos, focos e configurações diretamente pelo painel do Django.

---

## Relatório Gerado

Cada foco processado gera um relatório JSON armazenado no banco e acessível via `GET /api/relatorios/{foco_id}/`:

```json
{
  "projeto": "CARCARÁ — Sistema de Localização de Focos de Incêndio",
  "versao": "1.0",
  "gerado_em": "2026-04-08T14:35:00Z",
  "identificacao": {
    "foco_id": 1,
    "grupo_id": 7
  },
  "localizacao_estimada": {
    "latitude": -10.89341,
    "longitude": -37.06127,
    "google_maps": "https://www.google.com/maps?q=-10.89341,-37.06127",
    "waze": "https://waze.com/ul?ll=-10.89341%2C-37.06127&navigate=yes"
  },
  "metricas": {
    "n_observacoes": 3,
    "distancia_media_m": 2847.3,
    "distancia_media_km": 2.85,
    "residuo_medio_m": 124.7,
    "nivel_confianca": "alto",
    "interpretacao_confianca": "Estimativa com alta confiabilidade..."
  },
  "observacoes": [...],
  "midias": {
    "total_fotos": 2,
    "urls_fotos": ["https://..."]
  },
  "acoes_recomendadas": [
    "✅ Acionar brigada de combate ao incêndio.",
    "✅ Notificar Corpo de Bombeiros com coordenadas.",
    "📡 Monitorar novas observações no sistema CARCARÁ."
  ]
}
```

---

## Permissões

| Ação | Usuário comum | Staff | Admin/Superuser |
|------|:---:|:---:|:---:|
| Enviar observação | ✅ | ✅ | ✅ |
| Ver grupos e focos | ✅ | ✅ | ✅ |
| Ver configurações | ✅ | ✅ | ✅ |
| Alterar configurações | ❌ | ✅ | ✅ |
| Reprocessar grupo | ❌ | ✅ | ✅ |
| Painel admin | ❌ | ✅ | ✅ |

---

## Dependências Principais

| Pacote | Versão | Função |
|--------|--------|--------|
| Django | ≥ 5.0 | Framework web |
| djangorestframework | ≥ 3.15 | API REST |
| djangorestframework-simplejwt | — | Autenticação JWT |
| django-cors-headers | ≥ 4.3 | CORS para app mobile |
| psycopg2-binary | ≥ 2.9 | Conector PostgreSQL |
| numpy | ≥ 1.26 | Álgebra linear (triangulação) |
| pyproj | ≥ 3.6 | Conversão WGS84 ↔ UTM |
| python-dotenv | ≥ 1.0 | Variáveis de ambiente |

---

