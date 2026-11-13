"""Catálogo de serviços e peças da oficina (tabela de preços).

Regras:
- `oficina_id` vem sempre do usuário autenticado (`g.user`), nunca do corpo/URL;
- item de outra oficina (ou inexistente) => 404, sem revelar qual dos dois;
- só o dono cria, edita e desativa; o mecânico só lê os itens ativos;
- "remover" desativa o item (OS antigas podem ter usado o preço), nunca apaga.
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request

from backend import escopo
from backend.database import session_scope
from backend.dominio import _json, erro, log_negocio, negar_nao_encontrado, require_roles
from backend.models import CatalogoItem

bp = Blueprint('catalogo', __name__)

TIPOS = ('servico', 'peca')
DESCRICAO_MAX = 255
VALOR_MAX = 100_000_000


def _item_dict(item: CatalogoItem) -> dict[str, Any]:
    return {'id': item.id, 'tipo': item.tipo, 'descricao': item.descricao,
            'valor_centavos': int(item.valor_centavos), 'ativo': bool(item.ativo)}


def _validar(dados: dict[str, Any], parcial: bool) -> tuple[dict[str, Any] | None, str | None]:
    """Valida os campos do item; com `parcial`, só os campos presentes no corpo."""
    limpos: dict[str, Any] = {}
    if not parcial or 'tipo' in dados:
        tipo = dados.get('tipo')
        if tipo not in TIPOS:
            return None, "Informe o tipo: 'servico' ou 'peca'."
        limpos['tipo'] = tipo
    if not parcial or 'descricao' in dados:
        descricao = dados.get('descricao')
        descricao = descricao.strip() if isinstance(descricao, str) else ''
        if not 1 <= len(descricao) <= DESCRICAO_MAX:
            return None, f'Informe a descrição (até {DESCRICAO_MAX} caracteres).'
        limpos['descricao'] = descricao
    if not parcial or 'valor_centavos' in dados:
        valor = dados.get('valor_centavos')
        if not isinstance(valor, int) or isinstance(valor, bool) or not 0 <= valor <= VALOR_MAX:
            return None, 'Informe o valor em centavos (número inteiro de 0 a 100.000.000).'
        limpos['valor_centavos'] = valor
    if parcial and 'ativo' in dados:
        if not isinstance(dados['ativo'], bool):
            return None, "O campo 'ativo' precisa ser verdadeiro ou falso."
        limpos['ativo'] = dados['ativo']
    return limpos, None


@bp.get('/api/catalogo')
@require_roles('dono', 'mecanico')
def listar_catalogo():
    user = g.user
    filtros = []
    # ?todos=1 (inclui inativos) vale só para o dono; para o mecânico o parâmetro é ignorado
    if not (user['role'] == 'dono' and request.args.get('todos') == '1'):
        filtros.append(CatalogoItem.ativo.is_(True))
    tipo = request.args.get('tipo')
    if tipo:
        if tipo not in TIPOS:
            return erro("Filtro de tipo inválido: use 'servico' ou 'peca'.")
        filtros.append(CatalogoItem.tipo == tipo)
    with session_scope() as db:
        stmt = escopo.consulta(CatalogoItem, user['oficina_id'])
        for cond in filtros:
            stmt = stmt.where(cond)
        stmt = stmt.order_by(CatalogoItem.tipo, CatalogoItem.descricao, CatalogoItem.id)
        itens = [_item_dict(i) for i in db.scalars(stmt).all()]
    return jsonify({'itens': itens})


@bp.post('/api/catalogo')
@require_roles('dono')
def criar_item_catalogo():
    dados, msg = _validar(_json(), parcial=False)
    if msg:
        return erro(msg)
    with session_scope() as db:
        item = CatalogoItem(oficina_id=g.user['oficina_id'], ativo=True, **dados)
        db.add(item)
        db.flush()
        resultado = _item_dict(item)
    log_negocio('catalogo.item_criado', g.user, 'catalogo_item', resultado['id'],
                {'tipo': resultado['tipo'], 'valor_centavos': resultado['valor_centavos']})
    return jsonify({'item': resultado}), 201


@bp.put('/api/catalogo/<int:item_id>')
@require_roles('dono')
def editar_item_catalogo(item_id: int):
    dados, msg = _validar(_json(), parcial=True)
    if msg:
        return erro(msg)
    with session_scope() as db:
        item = escopo.obter(db, CatalogoItem, item_id, g.user['oficina_id'])
        if not item:
            return negar_nao_encontrado(g.user, 'catalogo_item', item_id)
        for campo, valor in dados.items():
            setattr(item, campo, valor)
        db.flush()
        resultado = _item_dict(item)
    log_negocio('catalogo.item_editado', g.user, 'catalogo_item', item_id, {'campos': sorted(dados)})
    return jsonify({'item': resultado})


@bp.delete('/api/catalogo/<int:item_id>')
@require_roles('dono')
def desativar_item_catalogo(item_id: int):
    with session_scope() as db:
        item = escopo.obter(db, CatalogoItem, item_id, g.user['oficina_id'])
        if not item:
            return negar_nao_encontrado(g.user, 'catalogo_item', item_id)
        item.ativo = False
        db.flush()
        resultado = _item_dict(item)
    log_negocio('catalogo.item_desativado', g.user, 'catalogo_item', item_id)
    return jsonify({'ok': True, 'item': resultado})
