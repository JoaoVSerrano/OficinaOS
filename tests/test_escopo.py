"""Helper de escopo: consulta sem oficina não existe e registro de outra oficina some."""
from __future__ import annotations

import pytest

from backend import escopo
from backend.database import Base
from backend.models import Cliente, Oficina
from tests.conftest import make_sqlite_scope


def test_consulta_sem_oficina_levanta_erro():
    for vazio in (None, 0):
        with pytest.raises(escopo.SemOficina):
            escopo.consulta(Cliente, vazio)


def test_obter_de_outra_oficina_devolve_none():
    _, scope = make_sqlite_scope(Base)
    with scope() as db:
        db.add_all([Oficina(id=1, nome='A', codigo_convite='A'), Oficina(id=2, nome='B', codigo_convite='B')])
        db.flush()
        db.add(Cliente(id=10, oficina_id=1, nome='Da A'))
    with scope() as db:
        assert escopo.obter(db, Cliente, 10, 1).nome == 'Da A'
        assert escopo.obter(db, Cliente, 10, 2) is None
        assert escopo.listar(db, Cliente, 2) == []
