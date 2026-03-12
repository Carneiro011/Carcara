"""
Endpoints da API do Projeto CARCARÁ.

Rotas disponíveis:
  POST /observacoes          — recebe uma nova observação do aplicativo
  GET  /observacoes          — lista observações (com filtros opcionais)
  GET  /observacoes/{id}     — detalha uma observação específica
  GET  /grupos               — lista grupos processados
  GET  /grupos/{id}          — detalha um grupo e seu foco estimado
  GET  /focos                — lista todos os focos estimados
  GET  /focos/{id}           — detalha um foco específico
  GET  /relatorios/{foco_id} — retorna o relatório de um foco
  POST /processar/{grupo_id} — força reprocessamento de um grupo
"""

from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from server.database import (
    get_db, Observacao, Grupo, FocoEstimado, Relatorio
)
from server.database.models import StatusGrupo, NivelConfianca
from server.processing.distance_calc import agrupar_observacoes
from server.processing.triangulation import (
    preparar_observacoes, triangular
)
from server.reports.generate_report import gerar_relatorio, relatorio_para_json

logger = logging.getLogger(__name__)
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# Schemas Pydantic — validação de entrada e saída
# ══════════════════════════════════════════════════════════════════════════════

class ObservacaoEntrada(BaseModel):
    """
    Payload enviado pelo aplicativo mobile a cada observação.
    """
    lat:          float = Field(..., ge=-90,  le=90,  description="Latitude (°)")
    lon:          float = Field(..., ge=-180, le=180, description="Longitude (°)")
    azimute:      float = Field(..., ge=0,    le=360, description="Azimute magnético (°)")
    elevacao:     Optional[float] = Field(None, ge=-90, le=90,
                                          description="Ângulo de elevação (°)")
    precisao_gps: Optional[float] = Field(None, ge=0,
                                           description="Precisão GPS em metros")
    timestamp:    datetime = Field(..., description="Timestamp ISO 8601 da observação")
    usuario_id:   str = Field(..., min_length=1, max_length=64,
                              description="Identificador único do usuário/dispositivo")
    foto_url:     Optional[str] = Field(None, max_length=512,
                                        description="URL da foto opcional")

    @field_validator("azimute")
    @classmethod
    def normalizar_azimute(cls, v: float) -> float:
        """Garante que o azimute esteja no intervalo [0, 360)."""
        return v % 360


class ObservacaoSaida(BaseModel):
    """Representação de uma observação no retorno da API."""
    id:           int
    usuario_id:   str
    lat:          float
    lon:          float
    azimute:      float
    elevacao:     Optional[float]
    precisao_gps: Optional[float]
    timestamp:    datetime
    foto_url:     Optional[str]
    grupo_id:     Optional[int]
    criado_em:    datetime

    class Config:
        from_attributes = True


class FocoSaida(BaseModel):
    """Representação de um foco estimado no retorno da API."""
    id:                    int
    grupo_id:              int
    lat_foco:              float
    lon_foco:              float
    distancia_media_m:     Optional[float]
    residuo_medio_m:       Optional[float]
    n_observacoes:         int
    nivel_confianca:       str
    distancia_elevacao_m:  Optional[float]
    calculado_em:          datetime

    class Config:
        from_attributes = True


class GrupoSaida(BaseModel):
    """Representação de um grupo no retorno da API."""
    id:            int
    status:        str
    criado_em:     datetime
    atualizado_em: datetime
    n_observacoes: int
    foco:          Optional[FocoSaida]

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════════════════════
# Lógica de processamento (executada em background)
# ══════════════════════════════════════════════════════════════════════════════

def _processar_grupo(grupo_id: int, db: Session) -> None:
    """
    Função de processamento chamada em background após o recebimento
    de uma nova observação.

    Fluxo:
      1. Recupera o grupo e suas observações do banco
      2. Executa triangulação
      3. Persiste o FocoEstimado
      4. Gera e persiste o Relatório
      5. Atualiza status do grupo para CONCLUIDO
    """
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        logger.error(f"Grupo {grupo_id} não encontrado para processamento.")
        return

    grupo.status = StatusGrupo.PROCESSANDO
    db.commit()

    try:
        # Serializa observações para formato esperado pelo processamento
        obs_raw = [
            {
                "id":           o.id,
                "usuario_id":   o.usuario_id,
                "lat":          o.lat,
                "lon":          o.lon,
                "azimute":      o.azimute,
                "elevacao":     o.elevacao,
                "precisao_gps": o.precisao_gps,
                "foto_url":     o.foto_url,
                "timestamp":    o.timestamp,
            }
            for o in grupo.observacoes
        ]

        obs_processadas = preparar_observacoes(obs_raw)
        resultado = triangular(obs_processadas)

        # Remove foco anterior se existir (reprocessamento)
        foco_existente = db.query(FocoEstimado).filter(
            FocoEstimado.grupo_id == grupo_id
        ).first()
        if foco_existente:
            db.delete(foco_existente)
            db.commit()

        # Persiste FocoEstimado
        foco = FocoEstimado(
            grupo_id=grupo_id,
            lat_foco=resultado.lat_foco,
            lon_foco=resultado.lon_foco,
            distancia_media_m=resultado.distancia_media_m,
            residuo_medio_m=resultado.residuo_medio_m,
            n_observacoes=resultado.n_observacoes,
            nivel_confianca=NivelConfianca(resultado.nivel_confianca),
            distancia_elevacao_m=resultado.distancia_por_elevacao_m,
        )
        db.add(foco)
        db.flush()  # gera foco.id sem commit

        # Gera e persiste Relatório
        relatorio_dict = gerar_relatorio(
            foco_id=foco.id,
            lat_foco=resultado.lat_foco,
            lon_foco=resultado.lon_foco,
            distancia_media_m=resultado.distancia_media_m,
            residuo_medio_m=resultado.residuo_medio_m,
            n_observacoes=resultado.n_observacoes,
            nivel_confianca=resultado.nivel_confianca,
            distancia_por_elevacao_m=resultado.distancia_por_elevacao_m,
            detalhes_obs=resultado.detalhes_por_obs,
            grupo_id=grupo_id,
        )

        relatorio = Relatorio(
            foco_id=foco.id,
            conteudo_json=relatorio_para_json(relatorio_dict),
        )
        db.add(relatorio)

        grupo.status = StatusGrupo.CONCLUIDO
        db.commit()

        logger.info(
            f"Grupo {grupo_id} processado — foco em "
            f"lat={resultado.lat_foco} lon={resultado.lon_foco} "
            f"confiança={resultado.nivel_confianca}"
        )

    except Exception as exc:
        db.rollback()
        grupo.status = StatusGrupo.ERRO
        db.commit()
        logger.exception(f"Erro ao processar grupo {grupo_id}: {exc}")


def _atribuir_ou_criar_grupo(nova_obs: Observacao, db: Session) -> int:
    """
    Verifica se a nova observação pode ser agrupada com observações
    recentes ainda em processamento. Retorna o ID do grupo.
    """
    from server.processing.distance_calc import (
        sao_proximas_no_espaco, sao_proximas_no_tempo
    )

    # Busca observações recentes sem grupo ou em grupos ainda pendentes
    candidatas = (
        db.query(Observacao)
        .join(Grupo, Observacao.grupo_id == Grupo.id, isouter=True)
        .filter(
            Observacao.id != nova_obs.id,
            (Observacao.grupo_id.is_(None)) |
            (Grupo.status.in_([StatusGrupo.PENDENTE, StatusGrupo.CONCLUIDO]))
        )
        .all()
    )

    melhor_grupo_id = None
    for obs in candidatas:
        ts_nova = nova_obs.timestamp
        ts_obs  = obs.timestamp

        if (sao_proximas_no_tempo(ts_nova, ts_obs) and
                sao_proximas_no_espaco(
                    {"lat": nova_obs.lat, "lon": nova_obs.lon},
                    {"lat": obs.lat,      "lon": obs.lon}
                )):
            if obs.grupo_id:
                melhor_grupo_id = obs.grupo_id
                break

    if melhor_grupo_id:
        nova_obs.grupo_id = melhor_grupo_id
        db.commit()
        logger.info(
            f"Observação {nova_obs.id} adicionada ao grupo {melhor_grupo_id}."
        )
        return melhor_grupo_id

    # Nenhum grupo compatível — cria novo
    novo_grupo = Grupo()
    db.add(novo_grupo)
    db.flush()
    nova_obs.grupo_id = novo_grupo.id
    db.commit()
    logger.info(
        f"Novo grupo {novo_grupo.id} criado para observação {nova_obs.id}."
    )
    return novo_grupo.id


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/observacoes", response_model=ObservacaoSaida, status_code=201,
             summary="Receber nova observação do aplicativo",
             tags=["Observações"])
def receber_observacao(
    payload: ObservacaoEntrada,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Endpoint principal de ingestão de dados do aplicativo mobile.

    Fluxo:
      1. Valida e persiste a observação
      2. Agrupa com observações próximas
      3. Dispara processamento de triangulação em background
      4. Retorna a observação persistida imediatamente (resposta rápida)
    """
    obs = Observacao(
        usuario_id=payload.usuario_id,
        timestamp=payload.timestamp,
        lat=payload.lat,
        lon=payload.lon,
        azimute=payload.azimute,
        elevacao=payload.elevacao,
        precisao_gps=payload.precisao_gps,
        foto_url=payload.foto_url,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    grupo_id = _atribuir_ou_criar_grupo(obs, db)
    db.refresh(obs)

    # Processa em background para não bloquear o retorno ao app
    background_tasks.add_task(_processar_grupo, grupo_id, db)

    return obs


@router.get("/observacoes", response_model=list[ObservacaoSaida],
            summary="Listar observações",
            tags=["Observações"])
def listar_observacoes(
    usuario_id: Optional[str] = Query(None, description="Filtrar por usuário"),
    limite:     int           = Query(50,  ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Observacao)
    if usuario_id:
        q = q.filter(Observacao.usuario_id == usuario_id)
    return q.order_by(Observacao.timestamp.desc()).limit(limite).all()


@router.get("/observacoes/{obs_id}", response_model=ObservacaoSaida,
            summary="Detalhar observação",
            tags=["Observações"])
def detalhar_observacao(obs_id: int, db: Session = Depends(get_db)):
    obs = db.query(Observacao).filter(Observacao.id == obs_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada.")
    return obs


@router.get("/grupos", response_model=list[GrupoSaida],
            summary="Listar grupos",
            tags=["Grupos"])
def listar_grupos(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Grupo)
    if status:
        try:
            q = q.filter(Grupo.status == StatusGrupo(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Status inválido: {status}")

    grupos = q.order_by(Grupo.criado_em.desc()).limit(limite).all()
    resultado = []
    for g in grupos:
        resultado.append(GrupoSaida(
            id=g.id,
            status=g.status.value,
            criado_em=g.criado_em,
            atualizado_em=g.atualizado_em,
            n_observacoes=len(g.observacoes),
            foco=FocoSaida.model_validate(g.foco_estimado) if g.foco_estimado else None,
        ))
    return resultado


@router.get("/grupos/{grupo_id}", response_model=GrupoSaida,
            summary="Detalhar grupo",
            tags=["Grupos"])
def detalhar_grupo(grupo_id: int, db: Session = Depends(get_db)):
    g = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")
    return GrupoSaida(
        id=g.id,
        status=g.status.value,
        criado_em=g.criado_em,
        atualizado_em=g.atualizado_em,
        n_observacoes=len(g.observacoes),
        foco=FocoSaida.model_validate(g.foco_estimado) if g.foco_estimado else None,
    )


@router.get("/focos", response_model=list[FocoSaida],
            summary="Listar focos estimados",
            tags=["Focos"])
def listar_focos(
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(FocoEstimado)
        .order_by(FocoEstimado.calculado_em.desc())
        .limit(limite)
        .all()
    )


@router.get("/focos/{foco_id}", response_model=FocoSaida,
            summary="Detalhar foco",
            tags=["Focos"])
def detalhar_foco(foco_id: int, db: Session = Depends(get_db)):
    foco = db.query(FocoEstimado).filter(FocoEstimado.id == foco_id).first()
    if not foco:
        raise HTTPException(status_code=404, detail="Foco não encontrado.")
    return foco


@router.get("/relatorios/{foco_id}",
            summary="Retornar relatório de um foco",
            tags=["Relatórios"])
def obter_relatorio(foco_id: int, db: Session = Depends(get_db)):
    """
    Retorna o relatório JSON completo de um foco estimado,
    incluindo localização, métricas e lista de fotos.
    """
    relatorio = (
        db.query(Relatorio)
        .filter(Relatorio.foco_id == foco_id)
        .first()
    )
    if not relatorio:
        raise HTTPException(
            status_code=404,
            detail="Relatório não encontrado. O grupo pode ainda estar sendo processado."
        )
    import json
    return json.loads(relatorio.conteudo_json)


@router.post("/processar/{grupo_id}",
             summary="Forçar reprocessamento de um grupo",
             tags=["Processamento"])
def reprocessar_grupo(
    grupo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Força o reprocessamento de triangulação para um grupo existente.
    Útil após adição manual de observações ou correção de dados.
    """
    grupo = db.query(Grupo).filter(Grupo.id == grupo_id).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")

    if not grupo.observacoes:
        raise HTTPException(
            status_code=422,
            detail="O grupo não possui observações para processar."
        )

    grupo.status = StatusGrupo.PENDENTE
    db.commit()
    background_tasks.add_task(_processar_grupo, grupo_id, db)

    return {
        "mensagem": f"Reprocessamento do grupo {grupo_id} iniciado.",
        "grupo_id": grupo_id,
    }
