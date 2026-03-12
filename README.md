# 🦅 PROJETO CARCARÁ
### Sistema de Localização de Focos de Incêndio por Triangulação

---

## Visão Geral

O **CARCARÁ** é um servidor central que recebe observações de usuários em campo (via aplicativo mobile), processa as direções de visão a partir das posições dos observadores e calcula a **localização provável de um foco de incêndio** por triangulação geométrica.

---

## Estrutura do Projeto

```
server/
├── main.py                    ← Aplicação FastAPI (ponto de entrada)
├── api/
│   └── receive_data.py        ← Todos os endpoints REST
├── processing/
│   ├── triangulation.py       ← Algoritmo de triangulação (mínimos quadrados)
│   └── distance_calc.py       ← Distâncias e agrupamento espaço-temporal
├── reports/
│   └── generate_report.py     ← Geração do relatório final
├── database/
│   ├── connection.py          ← Engine SQLAlchemy e sessões
│   └── models.py              ← Modelos ORM (Observacao, Grupo, FocoEstimado, Relatorio)
└── utils/
    └── geo_utils.py           ← Conversão WGS84 ↔ UTM com Pyproj
```

---

## Instalação

### 1. Pré-requisitos
- Python 3.11+
- PostgreSQL 14+ com extensão **PostGIS**

### 2. Banco de dados
```sql
-- Execute como superusuário postgres:
psql -U postgres -f setup_db.sql
```

### 3. Dependências Python
```bash
pip install -r requirements.txt
```

### 4. Configuração
```bash
cp .env.example .env
# Edite .env com os dados do seu PostgreSQL
```

### 5. Executar o servidor
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Documentação interativa disponível em: `http://localhost:8000/docs`

---

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/observacoes` | Receber nova observação do app |
| `GET`  | `/api/v1/observacoes` | Listar observações |
| `GET`  | `/api/v1/observacoes/{id}` | Detalhar observação |
| `GET`  | `/api/v1/grupos` | Listar grupos de observações |
| `GET`  | `/api/v1/grupos/{id}` | Detalhar grupo |
| `GET`  | `/api/v1/focos` | Listar focos estimados |
| `GET`  | `/api/v1/focos/{id}` | Detalhar foco |
| `GET`  | `/api/v1/relatorios/{foco_id}` | Relatório completo de um foco |
| `POST` | `/api/v1/processar/{grupo_id}` | Forçar reprocessamento |
| `GET`  | `/health` | Health check |

---

## Exemplo de Requisição POST

```bash
curl -X POST http://localhost:8000/api/v1/observacoes \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -10.9172,
    "lon": -37.0731,
    "azimute": 73.2,
    "elevacao": 6.0,
    "precisao_gps": 12,
    "timestamp": "2026-02-26T14:32:10",
    "usuario_id": "brigadista_01",
    "foto_url": "https://storage.nupreds.br/fotos/001.jpg"
  }'
```

---

## Algoritmo de Triangulação

### Problema
Cada observador está em uma posição conhecida `(x₀, y₀)` (UTM) e aponta o celular para a fumaça, gerando um **vetor de visão** definido pelo azimute `θ`:

```
L(t) = (x₀ + t·cos θ,  y₀ + t·sin θ)     (t ≥ 0)
```

Com N ≥ 2 observadores, queremos encontrar o ponto `P_foco` que **minimiza a soma das distâncias perpendiculares** a todas as linhas de visão.

### Formulação Matricial (Mínimos Quadrados)

Para cada linha de visão `i` com vetor unitário `dᵢ`:

```
Mᵢ = I − dᵢ · dᵢᵀ       (matriz de projeção perpendicular)

A = Σ Mᵢ
b = Σ Mᵢ · Oᵢ

P_foco = A⁻¹ · b         (solução do sistema linear 2×2)
```

Este método é ótimo no sentido de mínimos quadrados e robusto para N > 2 observações.

### Estimativa por Ângulo de Elevação

Quando disponível, o ângulo de elevação `φ` fornece uma estimativa independente da distância:

```
r = Δh / tan(φ)
```

onde `Δh` é a altura estimada da coluna de fumaça visível.

### Nível de Confiança

| Condição | Nível |
|----------|-------|
| 1 observação | Baixo |
| 2 obs. com ângulo < 15° entre elas | Baixo |
| 2 obs. com ângulo ≥ 15° | Médio |
| 3+ obs. com resíduo ≤ 500 m | Alto |
| Resíduo > 1000 m | Baixo (independente do número) |

---

## Modelo do Banco de Dados

```
observacoes          grupos              focos_estimados        relatorios
──────────────       ──────────────      ───────────────────    ──────────────
id (PK)              id (PK)             id (PK)                id (PK)
usuario_id           status              grupo_id (FK)          foco_id (FK)
timestamp            criado_em           lat_foco               conteudo_json
lat                  atualizado_em       lon_foco               gerado_em
lon                                      distancia_media_m      enviado
azimute                                  residuo_medio_m
elevacao                                 n_observacoes
precisao_gps                             nivel_confianca
foto_url                                 distancia_elevacao_m
grupo_id (FK)                            calculado_em
criado_em
```

---

## Exemplo de Relatório Gerado

```json
{
  "projeto": "CARCARÁ — Sistema de Localização de Focos de Incêndio",
  "localizacao_estimada": {
    "latitude": -10.89341,
    "longitude": -37.06127,
    "google_maps": "https://www.google.com/maps?q=-10.89341,-37.06127"
  },
  "metricas": {
    "n_observacoes": 3,
    "distancia_media_m": 2847.3,
    "distancia_media_km": 2.85,
    "residuo_medio_m": 124.7,
    "nivel_confianca": "alto",
    "interpretacao_confianca": "Estimativa com alta confiabilidade..."
  },
  "midias": {
    "total_fotos": 2,
    "urls_fotos": ["https://...", "https://..."]
  },
  "acoes_recomendadas": [
    "✅ Acionar brigada de combate ao incêndio.",
    "✅ Notificar Corpo de Bombeiros com coordenadas."
  ]
}
```
