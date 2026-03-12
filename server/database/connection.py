"""
Módulo de conexão com o banco de dados PostgreSQL/PostGIS.
Gerencia a sessão SQLAlchemy e o engine de conexão.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.exc import OperationalError
import logging

logger = logging.getLogger(__name__)

# URL de conexão — sobrescreva via variável de ambiente DATABASE_URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://carcara:carcara123@localhost:5432/carcara"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # verifica conexão antes de usar do pool
    pool_size=10,
    max_overflow=20,
    echo=False,               # True para logar SQL em desenvolvimento
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


def get_db():
    """
    Dependency do FastAPI — fornece uma sessão de banco e a fecha ao final.
    Uso: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicializa o banco: habilita a extensão PostGIS e cria as tabelas.
    Chamado uma única vez na inicialização da aplicação.
    """
    from server.database import models  # importação local para evitar ciclo

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
            logger.info("Extensão PostGIS habilitada.")
    except OperationalError as e:
        logger.error(f"Erro ao habilitar PostGIS: {e}")
        raise

    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas/verificadas com sucesso.")
