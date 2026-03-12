"""
Modelos ORM do Projeto CARCARÁ.

Tabelas:
  - observacoes     : cada leitura enviada pelo aplicativo mobile
  - grupos          : agrupamento de observações próximas
  - focos_estimados : resultado do processamento de triangulação
  - relatorios      : relatório final gerado para cada foco
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, Float, String, DateTime,
    ForeignKey, Text, Boolean, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum

from server.database.connection import Base


class StatusGrupo(str, enum.Enum):
    PENDENTE    = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO   = "concluido"
    ERRO        = "erro"


class NivelConfianca(str, enum.Enum):
    BAIXO  = "baixo"   # 1 observação
    MEDIO  = "medio"   # 2 observações
    ALTO   = "alto"    # 3+ observações com boa geometria


class Observacao(Base):
    """
    Registra uma única observação enviada pelo aplicativo.
    Cada observação é um vetor de visada a partir do celular do usuário.
    """
    __tablename__ = "observacoes"

    id            = Column(Integer, primary_key=True, index=True)
    usuario_id    = Column(String(64), nullable=False, index=True)
    timestamp     = Column(DateTime, nullable=False, index=True)
    lat           = Column(Float, nullable=False)
    lon           = Column(Float, nullable=False)
    azimute       = Column(Float, nullable=False)   # graus, 0–360
    elevacao      = Column(Float, nullable=True)    # ângulo vertical em graus
    precisao_gps  = Column(Float, nullable=True)    # metros
    foto_url      = Column(String(512), nullable=True)
    criado_em     = Column(DateTime, default=datetime.utcnow)

    # FK para o grupo ao qual esta observação foi atribuída
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    grupo    = relationship("Grupo", back_populates="observacoes")

    def __repr__(self):
        return (
            f"<Observacao id={self.id} usuario={self.usuario_id} "
            f"az={self.azimute}° ts={self.timestamp}>"
        )


class Grupo(Base):
    """
    Agrupamento espacial-temporal de observações que provavelmente
    descrevem o mesmo foco de incêndio.
    """
    __tablename__ = "grupos"

    id          = Column(Integer, primary_key=True, index=True)
    status      = Column(SAEnum(StatusGrupo), default=StatusGrupo.PENDENTE)
    criado_em   = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    observacoes  = relationship("Observacao", back_populates="grupo")
    foco_estimado = relationship("FocoEstimado", back_populates="grupo", uselist=False)

    def __repr__(self):
        return f"<Grupo id={self.id} status={self.status} obs={len(self.observacoes)}>"


class FocoEstimado(Base):
    """
    Resultado do algoritmo de triangulação para um grupo de observações.
    Armazena a localização estimada do foco e métricas de qualidade.
    """
    __tablename__ = "focos_estimados"

    id                  = Column(Integer, primary_key=True, index=True)
    grupo_id            = Column(Integer, ForeignKey("grupos.id"), unique=True)

    lat_foco            = Column(Float, nullable=False)
    lon_foco            = Column(Float, nullable=False)

    # Métricas de triangulação
    distancia_media_m   = Column(Float, nullable=True)   # metros
    residuo_medio_m     = Column(Float, nullable=True)   # desvio médio das linhas de visão
    n_observacoes       = Column(Integer, nullable=False)
    nivel_confianca     = Column(SAEnum(NivelConfianca), nullable=False)

    # Estimativa via ângulo de elevação (quando disponível)
    distancia_elevacao_m = Column(Float, nullable=True)

    calculado_em = Column(DateTime, default=datetime.utcnow)

    grupo    = relationship("Grupo", back_populates="foco_estimado")
    relatorio = relationship("Relatorio", back_populates="foco", uselist=False)

    def __repr__(self):
        return (
            f"<FocoEstimado id={self.id} "
            f"lat={self.lat_foco:.4f} lon={self.lon_foco:.4f} "
            f"confianca={self.nivel_confianca}>"
        )


class Relatorio(Base):
    """
    Relatório final consolidado de um foco estimado.
    """
    __tablename__ = "relatorios"

    id         = Column(Integer, primary_key=True, index=True)
    foco_id    = Column(Integer, ForeignKey("focos_estimados.id"), unique=True)

    conteudo_json = Column(Text, nullable=False)   # JSON serializado do relatório
    gerado_em     = Column(DateTime, default=datetime.utcnow)
    enviado       = Column(Boolean, default=False)

    foco = relationship("FocoEstimado", back_populates="relatorio")

    def __repr__(self):
        return f"<Relatorio id={self.id} foco_id={self.foco_id}>"
