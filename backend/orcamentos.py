"""Orçamento com versões, anotações internas e link público para o cliente aprovar ou recusar.

Base criada na Fase 0 do OficinaOS v2: o blueprint já está registrado em backend/app.py e o
`session_scope` é importado no módulo (os testes o substituem). As rotas entram na Fase 1.
"""
from __future__ import annotations

from flask import Blueprint

from backend.database import session_scope  # noqa: F401  (usado pelas rotas; substituído nos testes)

bp = Blueprint('orcamentos', __name__)
