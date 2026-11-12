"""Escopo obrigatório por oficina (tenant).

Toda consulta de domínio passa por aqui: `oficina_id` vem SEMPRE do usuário autenticado
(nunca de parâmetro, corpo ou URL). Registro de outra oficina simplesmente não existe
para quem consulta (`obter` devolve None, e a rota responde 404).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select

from backend.models import AnexoOS, ItemOS, NotaOS, Orcamento, OrdemServico, PagamentoOS

# tabelas sem oficina_id próprio: chegam à oficina pela OS
FILHOS_DA_OS = (ItemOS, AnexoOS, Orcamento, NotaOS, PagamentoOS)


class SemOficina(Exception):
    """Consulta de domínio sem oficina no contexto: é um bug de programação, nunca vira dado."""


def consulta(model: Any, oficina_id: int | None) -> Select:
    if not oficina_id:
        raise SemOficina(f'consulta de {getattr(model, "__tablename__", model)} sem oficina_id')
    if model in FILHOS_DA_OS:
        return select(model).join(OrdemServico, OrdemServico.id == model.os_id).where(
            OrdemServico.oficina_id == oficina_id, OrdemServico.excluida_em.is_(None)
        )
    stmt = select(model).where(model.oficina_id == oficina_id)
    if hasattr(model, 'excluida_em'):
        stmt = stmt.where(model.excluida_em.is_(None))
    return stmt


def obter(db: Any, model: Any, registro_id: int, oficina_id: int | None) -> Any | None:
    return db.scalar(consulta(model, oficina_id).where(model.id == registro_id))


def listar(db: Any, model: Any, oficina_id: int | None, *where: Any, order_by: Any = None) -> list[Any]:
    stmt = consulta(model, oficina_id)
    for cond in where:
        stmt = stmt.where(cond)
    stmt = stmt.order_by(order_by if order_by is not None else model.id)
    return list(db.scalars(stmt).all())
