"""Histórico do veículo, pagamentos recebidos nas OS e resumo financeiro do mês.

Regras:
- `oficina_id` vem sempre do usuário autenticado (`g.user`); registro de outra oficina responde 404.
- Dinheiro em centavos (int). O valor devido é o total da OS menos o desconto do orçamento aprovado
  (`ordens.valor_devido`); a soma dos pagamentos nunca passa dele.
- Entregar o veículo não exige pagamento: o que falta pagar aparece em "a receber".
- O cliente vê o histórico dos próprios veículos, mas nunca valores pagos ou devidos.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, select

from backend import escopo, ordens
from backend.database import session_scope
from backend.dominio import _json, _veiculo_visivel, erro, log_negocio, negar_nao_encontrado, require_roles
from backend.models import FORMAS_PAGAMENTO, OrdemServico, PagamentoOS

bp = Blueprint('financeiro', __name__)

STATUS_COBRAVEIS = ('pronta', 'entregue')
RE_MES = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
RE_DATA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
VALOR_MAX = 100_000_000_00  # R$ 100 milhões: trava contra valores absurdos


def _iso(d: date | datetime | None) -> str | None:
    return d.isoformat() if d else None


def _pago(db, os_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(PagamentoOS.valor_centavos), 0))
                         .where(PagamentoOS.os_id == os_id)) or 0)


# ---------------------------------------------------------------------------
# Histórico do veículo
# ---------------------------------------------------------------------------

@bp.get('/api/veiculos/<int:veiculo_id>/historico')
@require_roles('dono', 'mecanico', 'cliente')
def historico_veiculo(veiculo_id: int):
    user = g.user
    with session_scope() as db:
        veiculo = _veiculo_visivel(db, user, veiculo_id)
        if not veiculo:
            return negar_nao_encontrado(user, 'veiculo', veiculo_id)
        lista = escopo.listar(db, OrdemServico, user['oficina_id'], OrdemServico.veiculo_id == veiculo.id,
                              *ordens._filtro_visibilidade(db, user),
                              order_by=OrdemServico.id.desc())
        lista.sort(key=lambda o: (o.criada_em or datetime.min, o.id), reverse=True)
        itens = []
        for o in lista:
            item = {'id': o.id, 'status': o.status, 'descricao': o.descricao, 'km_entrada': o.km_entrada,
                    'criada_em': _iso(o.criada_em), 'entregue_em': _iso(o.entregue_em),
                    'valor_total_centavos': o.valor_total_centavos}
            if user['role'] == 'dono':  # o cliente (e o mecânico) não recebem valores de pagamento
                item['valor_devido_centavos'] = ordens.valor_devido(db, o)
                item['pago_centavos'] = _pago(db, o.id)
            itens.append(item)
        kms = [o.km_entrada for o in lista if o.km_entrada is not None]
        corpo = {'veiculo': {'placa': veiculo.placa, 'marca': veiculo.marca, 'modelo': veiculo.modelo,
                             'ano': veiculo.ano},
                 'ultimo_km': max(kms) if kms else None, 'ordens': itens}
    return jsonify(corpo)


# ---------------------------------------------------------------------------
# Pagamentos da OS (só o dono)
# ---------------------------------------------------------------------------

def _pagamento_dict(p: PagamentoOS) -> dict[str, Any]:
    return {'id': p.id, 'valor_centavos': int(p.valor_centavos), 'forma': p.forma, 'pago_em': _iso(p.pago_em),
            'observacao': p.observacao, 'registrado_por': p.registrado_por}


def _situacao(db, os_: OrdemServico) -> dict[str, Any]:
    pagamentos = db.scalars(select(PagamentoOS).where(PagamentoOS.os_id == os_.id)
                            .order_by(PagamentoOS.pago_em, PagamentoOS.id)).all()
    devido = ordens.valor_devido(db, os_)
    pago = sum(int(p.valor_centavos) for p in pagamentos)
    return {'pagamentos': [_pagamento_dict(p) for p in pagamentos], 'valor_devido_centavos': devido,
            'pago_centavos': pago, 'saldo_centavos': max(0, devido - pago)}


def _os_do_dono(db, os_id: int, travar: bool = False) -> OrdemServico | None:
    stmt = escopo.consulta(OrdemServico, g.user['oficina_id']).where(OrdemServico.id == os_id)
    return db.scalar(stmt.with_for_update() if travar else stmt)


def _validar_pagamento(dados: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    valor = dados.get('valor_centavos')
    if not isinstance(valor, int) or isinstance(valor, bool) or not 1 <= valor <= VALOR_MAX:
        return None, 'Informe o valor em centavos (inteiro maior que zero).'
    forma = dados.get('forma')
    if forma not in FORMAS_PAGAMENTO:
        return None, f"Forma de pagamento inválida. Use: {', '.join(FORMAS_PAGAMENTO)}."
    hoje = ordens.agora().date()
    pago_em = dados.get('pago_em')
    if pago_em in (None, ''):
        data = hoje
    else:
        if not isinstance(pago_em, str) or not RE_DATA.match(pago_em):
            return None, 'Data do pagamento inválida (use AAAA-MM-DD).'
        try:
            data = date.fromisoformat(pago_em)
        except ValueError:
            return None, 'Data do pagamento inválida (use AAAA-MM-DD).'
        if data > hoje:
            return None, 'A data do pagamento não pode ser futura.'
    observacao = dados.get('observacao')
    if observacao is not None:
        if not isinstance(observacao, str) or len(observacao.strip()) > 255:
            return None, 'Observação inválida (até 255 caracteres).'
        observacao = observacao.strip() or None
    return {'valor_centavos': valor, 'forma': forma, 'pago_em': data, 'observacao': observacao}, None


@bp.get('/api/os/<int:os_id>/pagamentos')
@require_roles('dono')
def listar_pagamentos(os_id: int):
    with session_scope() as db:
        os_ = _os_do_dono(db, os_id)
        if not os_:
            return negar_nao_encontrado(g.user, 'os', os_id)
        corpo = _situacao(db, os_)
    return jsonify(corpo)


@bp.post('/api/os/<int:os_id>/pagamentos')
@require_roles('dono')
def registrar_pagamento(os_id: int):
    user = g.user
    campos, msg = _validar_pagamento(_json())
    if msg:
        return erro(msg)
    with session_scope() as db:
        os_ = _os_do_dono(db, os_id, travar=True)  # trava a OS: dois pagamentos simultâneos não passam do devido
        if not os_:
            return negar_nao_encontrado(user, 'os', os_id)
        if os_.status not in STATUS_COBRAVEIS:
            return erro('Pagamentos só podem ser registrados com a OS pronta ou entregue.', 409)
        if _pago(db, os_.id) + campos['valor_centavos'] > ordens.valor_devido(db, os_):
            return erro('Valor maior que o saldo da OS.', 409)
        pagamento = PagamentoOS(os_id=os_.id, registrado_por=user['id'], **campos)
        db.add(pagamento)
        db.flush()
        pagamento_id = pagamento.id
        corpo = _situacao(db, os_)
    log_negocio('pagamento.registrado', user, 'os', os_id, {'pagamento_id': pagamento_id,
                                                             'valor_centavos': campos['valor_centavos'],
                                                             'forma': campos['forma']})
    return jsonify(corpo), 201


@bp.delete('/api/os/<int:os_id>/pagamentos/<int:pagamento_id>')
@require_roles('dono')
def remover_pagamento(os_id: int, pagamento_id: int):
    user = g.user
    with session_scope() as db:
        os_ = _os_do_dono(db, os_id)
        pagamento = db.get(PagamentoOS, pagamento_id) if os_ else None
        if not os_ or not pagamento or pagamento.os_id != os_.id:
            return negar_nao_encontrado(user, 'pagamento', pagamento_id)
        detalhe = {'pagamento_id': pagamento_id, 'valor_centavos': int(pagamento.valor_centavos),
                   'forma': pagamento.forma}
        db.delete(pagamento)
        db.flush()
        corpo = _situacao(db, os_)
    log_negocio('pagamento.removido', user, 'os', os_id, detalhe)
    return jsonify(corpo)


# ---------------------------------------------------------------------------
# Resumo financeiro do mês (só o dono)
# ---------------------------------------------------------------------------

def _limites_do_mes(mes: str) -> tuple[date, date]:
    ano, m = int(mes[:4]), int(mes[5:])
    inicio = date(ano, m, 1)
    fim = date(ano + 1, 1, 1) if m == 12 else date(ano, m + 1, 1)
    return inicio, fim


def a_receber(db, oficina_id: int) -> int:
    """Hoje: soma do que falta pagar nas OS prontas ou entregues (não excluídas) da oficina."""
    cobraveis = escopo.listar(db, OrdemServico, oficina_id, OrdemServico.status.in_(STATUS_COBRAVEIS))
    return sum(max(0, ordens.valor_devido(db, o) - _pago(db, o.id)) for o in cobraveis)


@bp.get('/api/financeiro/resumo')
@require_roles('dono')
def resumo_financeiro():
    oficina_id = g.user['oficina_id']
    mes = request.args.get('mes') or ordens.agora().strftime('%Y-%m')
    if not RE_MES.match(mes):
        return erro('Mês inválido (use AAAA-MM).')
    inicio, fim = _limites_do_mes(mes)
    with session_scope() as db:
        pagamentos = db.scalars(escopo.consulta(PagamentoOS, oficina_id).where(
            PagamentoOS.pago_em >= inicio, PagamentoOS.pago_em < fim)).all()
        por_forma: dict[str, int] = {}
        for p in pagamentos:
            por_forma[p.forma] = por_forma.get(p.forma, 0) + int(p.valor_centavos)
        faturado = sum(por_forma.values())
        os_pagas = len({p.os_id for p in pagamentos})
        entregues = int(db.scalar(select(func.count()).select_from(escopo.consulta(OrdemServico, oficina_id).where(
            OrdemServico.entregue_em >= datetime.combine(inicio, datetime.min.time()),
            OrdemServico.entregue_em < datetime.combine(fim, datetime.min.time())).subquery())) or 0)
        corpo = {'mes': mes, 'faturado_centavos': faturado, 'por_forma': por_forma, 'os_entregues': entregues,
                 'ticket_medio_centavos': faturado // os_pagas if os_pagas else 0,
                 'a_receber_centavos': a_receber(db, oficina_id)}
    return jsonify(corpo)
