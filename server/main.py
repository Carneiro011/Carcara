"""
PROJETO CARCARÁ — Servidor Central de Localização de Focos de Incêndio
=======================================================================

Inicialização da aplicação FastAPI.
Configuração de middleware, rotas e eventos de ciclo de vida.

Uso:
    uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

Variáveis de ambiente:
    DATABASE_URL  : URL de conexão PostgreSQL (default: localhost)
    APP_DEBUG     : "true" para modo debug (default: false)
    ALLOWED_HOSTS : hosts permitidos separados por vírgula
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.database.connection import init_db
from server.api.receive_data import router as api_router
from server.api.mapa import router as mapa_router

# ── Configuração de logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.getenv("APP_DEBUG", "false").lower() == "true"
          else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("caraca")


# ── Ciclo de vida da aplicação ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executado na inicialização e encerramento do servidor.
    Garante que o banco de dados esteja pronto antes de aceitar requisições.
    """
    logger.info("🦅 CARCARÁ iniciando — configurando banco de dados...")
    init_db()
    logger.info("✅ Banco de dados pronto. Servidor disponível.")
    yield
    logger.info("🛑 CARCARÁ encerrando.")


# ── Instância principal ───────────────────────────────────────────────────────
app = FastAPI(
    title="Projeto CARCARÁ",
    description=(
        "Sistema de localização de focos de incêndio por triangulação "
        "de observações coletadas por dispositivos móveis.\n\n"
        "Desenvolvido para o **NUPREDS** — Núcleo de Pesquisa e "
        "Desenvolvimento em Sensoriamento Remoto e Desastres."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — permite acesso da rede local e do aplicativo mobile ────────────────
allowed_origins = os.getenv(
    "ALLOWED_HOSTS",
    "http://localhost,http://localhost:3000,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rotas ─────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")
app.include_router(mapa_router, prefix="/api/v1")


# ── Rota raiz → redireciona para o mapa ──────────────────────────────────────
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/api/v1/mapa")



@app.get("/health", tags=["Sistema"])
def health_check():
    """Endpoint de health check para monitoramento."""
    return {"status": "ok"}


# ── Handler global de exceções ────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor. Verifique os logs."},
    )