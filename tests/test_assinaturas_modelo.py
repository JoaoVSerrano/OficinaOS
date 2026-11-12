"""T11.1: tabela `assinaturas` do payment-service (uma linha por oficina)."""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent


def _sql_offline() -> str:
    cfg = Config(str(ROOT / 'alembic-payment.ini'))
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(cfg, '0001_payment_init:0002_assinaturas', sql=True)
    return buf.getvalue()


def test_migracao_cria_tabela_assinaturas_com_oficina_unica():
    sql = _sql_offline()
    assert 'CREATE TABLE assinaturas' in sql
    for coluna in ('oficina_id', 'usuario_id', 'stripe_customer_id', 'stripe_subscription_id',
                   'plano', 'status', 'valor_mensal_centavos', 'moeda', 'periodo_fim',
                   'inadimplente', 'ultimo_evento_em', 'atualizado_em'):
        assert coluna in sql
    assert 'UNIQUE' in sql and 'oficina_id' in sql


@pytest.fixture
def db():
    from payment_service.database import Base
    import payment_service.models  # noqa: F401
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_oficina_so_pode_ter_uma_assinatura(db):
    from payment_service.models import Assinatura
    db.add(Assinatura(oficina_id=1, plano='free', status='free'))
    db.commit()
    db.add(Assinatura(oficina_id=1, plano='pro', status='active'))
    with pytest.raises(IntegrityError):
        db.commit()


def test_defaults_sao_free_sem_inadimplencia(db):
    from payment_service.models import Assinatura
    a = Assinatura(oficina_id=7)
    db.add(a)
    db.commit()
    assert (a.plano, a.inadimplente, a.moeda) == ('free', False, 'brl')


def test_oficina_sem_linha_e_free(db):
    from payment_service.planos import plano_da_oficina
    assert plano_da_oficina(db, 999) == {'plano': 'free', 'status': 'free', 'inadimplente': False}


def test_plano_pro_ativo_e_lido_do_banco(db):
    from payment_service.models import Assinatura
    from payment_service.planos import plano_da_oficina
    db.add(Assinatura(oficina_id=3, plano='pro', status='active'))
    db.commit()
    assert plano_da_oficina(db, 3)['plano'] == 'pro'


def test_legado_stripe_customers_e_migrado_para_assinaturas_sem_perder_customer():
    from payment_service.migracao_legado import legado_para_assinaturas
    engine = create_engine('sqlite://')
    from payment_service.database import Base
    import payment_service.models  # noqa: F401
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        from payment_service.models import StripeCustomer, Assinatura
        s.add(StripeCustomer(google_id='g1', stripe_customer_id='cus_1'))
        s.commit()
        # sem oficina conhecida o legado não vira assinatura: só é contado
        assert legado_para_assinaturas(s, {}) == 0
        assert s.query(Assinatura).count() == 0
        assert legado_para_assinaturas(s, {'g1': (5, 11)}) == 1
        a = s.query(Assinatura).one()
        assert (a.oficina_id, a.usuario_id, a.stripe_customer_id, a.plano) == (5, 11, 'cus_1', 'free')
