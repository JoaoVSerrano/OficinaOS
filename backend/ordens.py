"""Ordens de serviço: CRUD, itens e máquina de estados (seção 4.3 do plano).

status: aberta -> orcamento_aprovado -> em_servico -> pronta -> entregue   (cancelada só pelo dono, antes de entregue)
Transição inexistente => 409. Transição existente mas sem permissão do papel => 403.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, select

from backend import escopo, planos
from backend.database import session_scope
from backend.dominio import (_core, _ids_veiculos_do_cliente_logado, _json, erro, log_negocio, negar_nao_encontrado,
                             require_roles, resposta_limite)
from backend.models import Cliente, ItemOS, OrdemServico, Veiculo

bp = Blueprint('ordens', __name__)

FUSO = ZoneInfo('America/Sao_Paulo')
STATUS_ABERTOS = ('aberta', 'orcamento_aprovado', 'em_servico', 'pronta')
STATUS_FINAIS = ('entregue', 'cancelada')
STATUS_EDITAVEIS_ITENS = ('aberta', 'orcamento_aprovado', 'em_servico')

# (de, para) -> papéis que podem executar. 'cliente' só na própria OS (a visibilidade já garante isso).
TRANSICOES: dict[tuple[str, str], tuple[str, ...]] = {
    ('aberta', 'orcamento_aprovado'): ('dono', 'cliente'),
    ('orcamento_aprovado', 'em_servico'): ('dono', 'mecanico'),
    ('em_servico', 'pronta'): ('dono', 'mecanico'),
    ('pronta', 'entregue'): ('dono',),
    **{(origem, 'cancelada'): ('dono',) for origem in STATUS_ABERTOS},
}
EVENTO_POR_DESTINO = {'orcamento_aprovado': 'os.orcamento_aprovado', 'entregue': 'os.entregue',
                      'cancelada': 'os.cancelada'}


def agora() -> datetime:
    """Hora local de Brasília, sem fuso (gravada e comparada no mesmo referencial)."""
    return datetime.now(FUSO).replace(tzinfo=None)


def inicio_do_mes(ref: datetime) -> datetime:
    return ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Serialização e visibilidade
# ---------------------------------------------------------------------------

def _item_dict(i: ItemOS) -> dict[str, Any]:
    return {'id': i.id, 'tipo': i.tipo, 'descricao': i.descricao, 'quantidade': i.quantidade,
            'valor_unitario_centavos': i.valor_unitario_centavos,
            'subtotal_centavos': i.quantidade * i.valor_unitario_centavos}


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _os_dict(db, os_: OrdemServico, detalhado: bool = False) -> dict[str, Any]:
    veiculo = db.get(Veiculo, os_.veiculo_id)
    cliente = db.get(Cliente, veiculo.cliente_id) if veiculo else None
    dados = {
        'id': os_.id, 'status': os_.status, 'descricao': os_.descricao, 'mecanico_id': os_.mecanico_id,
        'valor_total_centavos': os_.valor_total_centavos, 'criada_em': _iso(os_.criada_em),
        'atualizada_em': _iso(os_.atualizada_em),
        'veiculo': {'id': veiculo.id, 'placa': veiculo.placa, 'marca': veiculo.marca, 'modelo': veiculo.modelo}
        if veiculo else None,
        'cliente': {'id': cliente.id, 'nome': cliente.nome} if cliente else None,
    }
    if detalhado:
        itens = db.scalars(select(ItemOS).where(ItemOS.os_id == os_.id).order_by(ItemOS.id)).all()
        dados['itens'] = [_item_dict(i) for i in itens]
    return dados


def _filtro_visibilidade(db, user: dict[str, Any]) -> list[Any]:
    """Condições extras de leitura por papel: dono vê toda a oficina; mecânico só as atribuídas; cliente as dos seus veículos."""
    if user['role'] == 'mecanico':
        return [OrdemServico.mecanico_id == user['id']]
    if user['role'] == 'cliente':
        return [OrdemServico.veiculo_id.in_(_ids_veiculos_do_cliente_logado(db, user) or [0])]
    return []


def os_visivel(db, user: dict[str, Any], os_id: int) -> OrdemServico | None:
    return db.scalar(escopo.consulta(OrdemServico, user['oficina_id']).where(
        OrdemServico.id == os_id, *_filtro_visibilidade(db, user)))


def _mecanico_valido(oficina_id: int, mecanico_id: Any) -> bool:
    """O mecânico indicado existe na equipe DESTA oficina (consulta ao auth-service)."""
    if not isinstance(mecanico_id, int):
        return False
    resp = _core()._forward_to_auth('GET', f'/internal/oficinas/{oficina_id}/usuarios')
    if resp.status_code != 200:
        raise requests.RequestException('falha ao consultar a equipe')
    return any(u['id'] == mecanico_id and u['role'] == 'mecanico' for u in resp.json().get('usuarios', []))


def _recalcular_total(db, os_: OrdemServico) -> None:
    total = db.scalar(select(func.coalesce(func.sum(ItemOS.quantidade * ItemOS.valor_unitario_centavos), 0))
                      .where(ItemOS.os_id == os_.id))
    os_.valor_total_centavos = int(total or 0)
    os_.atualizada_em = agora()


def os_do_mes(db, oficina_id: int) -> int:
    """OS criadas no mês corrente (America/Sao_Paulo), INCLUINDO as excluídas: excluir não devolve cota."""
    return int(db.scalar(select(func.count(OrdemServico.id)).where(
        OrdemServico.oficina_id == oficina_id, OrdemServico.criada_em >= inicio_do_mes(agora()))) or 0)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@bp.get('/api/os')
@require_roles('dono', 'mecanico', 'cliente')
def listar_os():
    user = g.user
    with session_scope() as db:
        where = _filtro_visibilidade(db, user)
        status = request.args.get('status')
        if status:
            where.append(OrdemServico.status == status)
        itens = escopo.listar(db, OrdemServico, user['oficina_id'], *where, order_by=OrdemServico.id.desc())
        return jsonify({'ordens': [_os_dict(db, o) for o in itens]})


@bp.post('/api/os')
@require_roles('dono', 'mecanico')
def criar_os():
    user = g.user
    dados = _json()
    descricao = str(dados.get('descricao', '')).strip()
    if len(descricao) < 3:
        return erro('Descreva o problema ou o serviço (mínimo 3 caracteres).')
    veiculo_id = dados.get('veiculo_id')

    try:
        with session_scope() as db:
            veiculo = escopo.obter(db, Veiculo, veiculo_id, user['oficina_id']) if isinstance(veiculo_id, int) else None
            if not veiculo:
                return negar_nao_encontrado(user, 'veiculo', veiculo_id if isinstance(veiculo_id, int) else 0)

            mecanico_id = user['id'] if user['role'] == 'mecanico' else dados.get('mecanico_id')
            if mecanico_id is not None and not _mecanico_valido(user['oficina_id'], mecanico_id):
                return erro('Mecânico não encontrado nesta oficina.', 404)

            plano = planos.plano_da_oficina(user['oficina_id'])
            lim = planos.limite(plano, 'max_os_mes')
            if lim is not None:
                usadas = os_do_mes(db, user['oficina_id'])
                if usadas >= lim:
                    return resposta_limite(user, plano, 'max_os_mes', lim, usadas, 'os')

            agora_ = agora()
            os_ = OrdemServico(oficina_id=user['oficina_id'], veiculo_id=veiculo.id, mecanico_id=mecanico_id,
                               criada_por=user['id'], status='aberta', descricao=descricao,
                               valor_total_centavos=0, criada_em=agora_, atualizada_em=agora_)
            db.add(os_)
            db.flush()
            resultado = _os_dict(db, os_, detalhado=True)
    except requests.RequestException:
        return erro('Serviço de autenticação indisponível.', 503)
    log_negocio('os.aberta', user, 'os', resultado['id'], {'veiculo_id': resultado['veiculo']['id']})
    return jsonify({'ordem': resultado}), 201


@bp.get('/api/os/<int:os_id>')
@require_roles('dono', 'mecanico', 'cliente')
def detalhar_os(os_id: int):
    with session_scope() as db:
        os_ = os_visivel(db, g.user, os_id)
        if not os_:
            return negar_nao_encontrado(g.user, 'os', os_id)
        return jsonify({'ordem': _os_dict(db, os_, detalhado=True)})


@bp.put('/api/os/<int:os_id>')
@require_roles('dono', 'mecanico')
def editar_os(os_id: int):
    user = g.user
    dados = _json()
    try:
        with session_scope() as db:
            os_ = os_visivel(db, user, os_id)
            if not os_:
                return negar_nao_encontrado(user, 'os', os_id)
            if os_.status in STATUS_FINAIS:
                return erro('Ordem de serviço encerrada não pode ser editada.', 409)
            if 'descricao' in dados:
                descricao = str(dados['descricao']).strip()
                if len(descricao) < 3:
                    return erro('Descreva o problema ou o serviço (mínimo 3 caracteres).')
                os_.descricao = descricao
            if 'mecanico_id' in dados:
                if user['role'] != 'dono':
                    log_negocio('acesso_negado', user, 'os', os_id, {'motivo': 'papel', 'campo': 'mecanico_id'})
                    return erro('Só o dono pode atribuir o mecânico.', 403)
                novo = dados['mecanico_id']
                if novo is not None and not _mecanico_valido(user['oficina_id'], novo):
                    return erro('Mecânico não encontrado nesta oficina.', 404)
                os_.mecanico_id = novo
            os_.atualizada_em = agora()
            resultado = _os_dict(db, os_, detalhado=True)
    except requests.RequestException:
        return erro('Serviço de autenticação indisponível.', 503)
    log_negocio('os.editada', user, 'os', os_id)
    return jsonify({'ordem': resultado})


@bp.delete('/api/os/<int:os_id>')
@require_roles('dono')
def excluir_os(os_id: int):
    with session_scope() as db:
        os_ = escopo.obter(db, OrdemServico, os_id, g.user['oficina_id'])
        if not os_:
            return negar_nao_encontrado(g.user, 'os', os_id)
        os_.excluida_em = agora()  # exclusão lógica: continua contando na cota do mês
    log_negocio('os.excluida', g.user, 'os', os_id)
    return jsonify({'ok': True})


def _validar_item(dados: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    tipo = str(dados.get('tipo', '')).strip().lower()
    if tipo not in ('servico', 'peca'):
        return None, "Tipo do item deve ser 'servico' ou 'peca'."
    descricao = str(dados.get('descricao', '')).strip()
    if not descricao:
        return None, 'Descreva o item.'
    quantidade = dados.get('quantidade', 1)
    valor = dados.get('valor_unitario_centavos')
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or not 1 <= quantidade <= 10000:
        return None, 'Quantidade inválida.'
    if not isinstance(valor, int) or isinstance(valor, bool) or not 0 <= valor <= 100_000_000:
        return None, 'Informe o valor unitário em centavos (inteiro).'
    return {'tipo': tipo, 'descricao': descricao[:255], 'quantidade': quantidade, 'valor_unitario_centavos': valor}, None


@bp.post('/api/os/<int:os_id>/itens')
@require_roles('dono', 'mecanico')
def adicionar_item(os_id: int):
    campos, msg = _validar_item(_json())
    if msg:
        return erro(msg)
    with session_scope() as db:
        os_ = os_visivel(db, g.user, os_id)
        if not os_:
            return negar_nao_encontrado(g.user, 'os', os_id)
        if os_.status not in STATUS_EDITAVEIS_ITENS:
            return erro('Os itens só podem ser alterados até o serviço ficar pronto.', 409)
        item = ItemOS(os_id=os_.id, **campos)
        db.add(item)
        db.flush()
        _recalcular_total(db, os_)
        resultado = _os_dict(db, os_, detalhado=True)
    log_negocio('os.item_adicionado', g.user, 'os', os_id, {'item_id': item.id, 'tipo': campos['tipo']})
    return jsonify({'ordem': resultado}), 201


@bp.delete('/api/os/<int:os_id>/itens/<int:item_id>')
@require_roles('dono', 'mecanico')
def remover_item(os_id: int, item_id: int):
    with session_scope() as db:
        os_ = os_visivel(db, g.user, os_id)
        item = db.get(ItemOS, item_id) if os_ else None
        if not os_ or not item or item.os_id != os_.id:
            return negar_nao_encontrado(g.user, 'os', os_id)
        if os_.status not in STATUS_EDITAVEIS_ITENS:
            return erro('Os itens só podem ser alterados até o serviço ficar pronto.', 409)
        db.delete(item)
        db.flush()
        _recalcular_total(db, os_)
        resultado = _os_dict(db, os_, detalhado=True)
    log_negocio('os.editada', g.user, 'os', os_id, {'item_removido': item_id})
    return jsonify({'ordem': resultado})


@bp.post('/api/os/<int:os_id>/status')
@require_roles('dono', 'mecanico', 'cliente')
def alterar_status(os_id: int):
    user = g.user
    destino = str(_json().get('status', '')).strip().lower()
    with session_scope() as db:
        os_ = os_visivel(db, user, os_id)
        if not os_:
            return negar_nao_encontrado(user, 'os', os_id)
        permitidos = TRANSICOES.get((os_.status, destino))
        if permitidos is None:
            return erro(f"Transição inválida: '{os_.status}' não pode ir para '{destino}'.", 409)
        if user['role'] not in permitidos:
            log_negocio('acesso_negado', user, 'os', os_id, {'motivo': 'papel', 'transicao': f'{os_.status}->{destino}'})
            return erro('Seu papel não pode executar esta mudança de status.', 403)
        if destino == 'orcamento_aprovado' and os_.valor_total_centavos <= 0:
            return erro('O orçamento ainda não tem itens com valor.', 409)
        anterior = os_.status
        os_.status = destino
        os_.atualizada_em = agora()
        resultado = _os_dict(db, os_, detalhado=True)
    detalhe = {'de': anterior, 'para': destino}
    log_negocio('os.status_alterado', user, 'os', os_id, detalhe)
    if destino in EVENTO_POR_DESTINO:
        log_negocio(EVENTO_POR_DESTINO[destino], user, 'os', os_id, detalhe)
    return jsonify({'ordem': resultado})
