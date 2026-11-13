"""Orçamento com versões, anotações internas e link público para o cliente aprovar ou recusar.

- Cada envio é uma versão nova (snapshot dos itens da OS); a versão `enviado` anterior vira `substituido`.
- O link público carrega um token aleatório; o banco guarda SÓ o sha256 dele. Quem tem o link decide sem login,
  e a decisão entra na auditoria da oficina com um ator sintético (cliente sem id).
- A resposta pública não leva ids, e-mail, telefone nem notas, e nunca vai para cache (`Cache-Control: no-store`).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, timedelta
from typing import Any

import requests
from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, select

from backend.database import session_scope  # noqa: F401  (substituído nos testes; usar sempre por este nome)
from backend.dominio import _core, _json, erro, log_negocio, negar_nao_encontrado, require_roles
from backend.models import Cliente, ItemOS, NotaOS, Oficina, Orcamento, OrdemServico, Veiculo
from backend.ordens import agora, log_transicao, os_visivel, transicionar

bp = Blueprint('orcamentos', __name__)

VALIDADE_MIN, VALIDADE_MAX = 1, 90
OBS_MAX = 2000
MOTIVO_MIN, MOTIVO_MAX = 3, 500
NOTA_MAX = 2000


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _int(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hoje() -> date:
    return agora().date()


def _iso(d: Any) -> str | None:
    return d.isoformat() if d else None


def _expirado(o: Orcamento) -> bool:
    return o.status == 'enviado' and o.validade_ate < _hoje()


def _itens(o: Orcamento) -> list[dict[str, Any]]:
    try:
        itens = json.loads(o.itens_json or '[]')
    except ValueError:
        return []
    return itens if isinstance(itens, list) else []


def _orc_publico(o: Orcamento) -> dict[str, Any]:
    """Campos que o cliente pode ver (sem id, sem token/hash, sem quem decidiu)."""
    return {
        'versao': o.versao, 'status': o.status, 'expirado': _expirado(o), 'itens': _itens(o),
        'subtotal_centavos': o.subtotal_centavos, 'desconto_centavos': o.desconto_centavos,
        'total_centavos': o.total_centavos, 'validade_ate': _iso(o.validade_ate),
        'observacoes_cliente': o.observacoes_cliente, 'enviado_em': _iso(o.enviado_em),
        'decidido_em': _iso(o.decidido_em), 'motivo_recusa': o.motivo_recusa,
    }


def _orc_dict(o: Orcamento) -> dict[str, Any]:
    return {'id': o.id, **_orc_publico(o), 'decidido_via': o.decidido_via}


def _ultima_versao(db, os_id: int) -> int:
    return int(db.scalar(select(func.max(Orcamento.versao)).where(Orcamento.os_id == os_id)) or 0)


def _decidir(db, os_: OrdemServico, orc: Orcamento, dados: dict[str, Any], ator: dict[str, Any],
             via: str) -> tuple[str, int] | None:
    """Regras comuns da decisão (app e link). Grava na sessão; devolve (mensagem, status) em caso de erro."""
    acao = str(dados.get('acao', '')).strip().lower()
    if acao not in ('aprovar', 'recusar'):
        return "Ação inválida: use 'aprovar' ou 'recusar'.", 400
    if orc.status != 'enviado':
        if orc.status == 'substituido':
            return 'Este orçamento foi substituído por uma versão mais nova. Peça o link novo à oficina.', 409
        return 'Este orçamento já foi decidido.', 409
    if orc.versao != _ultima_versao(db, os_.id):
        return 'Este orçamento foi substituído por uma versão mais nova.', 409
    if _expirado(orc):
        return 'Este orçamento expirou. Peça um orçamento atualizado à oficina.', 410
    if os_.status != 'aberta':
        return 'A ordem de serviço não está mais aguardando orçamento.', 409

    if acao == 'recusar':
        motivo = str(dados.get('motivo') or '').strip()
        if not MOTIVO_MIN <= len(motivo) <= MOTIVO_MAX:
            return f'Informe o motivo da recusa ({MOTIVO_MIN} a {MOTIVO_MAX} caracteres).', 400
        orc.status = 'recusado'
        orc.motivo_recusa = motivo
    else:
        if int(orc.subtotal_centavos) != int(os_.valor_total_centavos):
            return 'Orçamento desatualizado: reenvie', 409
        falha = transicionar(db, os_, 'orcamento_aprovado', ator, via_orcamento=True)
        if falha:
            return falha
        orc.status = 'aprovado'
    orc.decidido_em = agora()
    orc.decidido_por_usuario_id = ator.get('id')
    orc.decidido_via = via
    return None


def _logar_decisao(ator: dict[str, Any], os_id: int, orc: dict[str, Any], via: str) -> None:
    """Eventos da decisão (chamar DEPOIS de fechar a sessão)."""
    detalhe: dict[str, Any] = {'os_id': os_id, 'versao': orc['versao'], 'via': via,
                               'total_centavos': orc['total_centavos']}
    if orc['status'] == 'recusado':
        detalhe['motivo'] = orc['motivo_recusa']
        log_negocio('orcamento.recusado', ator, 'orcamento', orc.get('id'), detalhe)
        return
    log_negocio('orcamento.aprovado', ator, 'orcamento', orc.get('id'), detalhe)
    log_transicao(ator, os_id, 'aberta', 'orcamento_aprovado', via='orcamento')


# ---------------------------------------------------------------------------
# Rotas autenticadas: versões do orçamento
# ---------------------------------------------------------------------------

@bp.get('/api/os/<int:os_id>/orcamentos')
@require_roles('dono', 'mecanico', 'cliente')
def listar_orcamentos(os_id: int):
    with session_scope() as db:
        if not os_visivel(db, g.user, os_id):
            return negar_nao_encontrado(g.user, 'os', os_id)
        versoes = db.scalars(select(Orcamento).where(Orcamento.os_id == os_id)
                             .order_by(Orcamento.versao.desc())).all()
        return jsonify({'orcamentos': [_orc_dict(o) for o in versoes]})


@bp.post('/api/os/<int:os_id>/orcamentos')
@require_roles('dono')
def enviar_orcamento(os_id: int):
    user = g.user
    dados = _json()
    desconto = dados.get('desconto_centavos', 0)
    validade = dados.get('validade_dias', 7)
    obs = dados.get('observacoes_cliente')
    obs = '' if obs is None else obs
    if not _int(desconto) or desconto < 0:
        return erro('Desconto inválido (inteiro em centavos, a partir de 0).')
    if not _int(validade) or not VALIDADE_MIN <= validade <= VALIDADE_MAX:
        return erro(f'Validade inválida (de {VALIDADE_MIN} a {VALIDADE_MAX} dias).')
    if not isinstance(obs, str) or len(obs.strip()) > OBS_MAX:
        return erro(f'Observações para o cliente: até {OBS_MAX} caracteres.')
    obs = obs.strip()

    token = secrets.token_urlsafe(32)
    with session_scope() as db:
        os_ = os_visivel(db, user, os_id)
        if not os_:
            return negar_nao_encontrado(user, 'os', os_id)
        if os_.status != 'aberta':
            return erro('Só é possível enviar orçamento com a OS aberta.', 409)
        subtotal = int(os_.valor_total_centavos)
        if subtotal <= 0:
            return erro('Adicione itens com valor antes de enviar o orçamento.', 409)
        if desconto > subtotal:
            return erro('O desconto não pode ser maior que o subtotal.')

        itens = db.scalars(select(ItemOS).where(ItemOS.os_id == os_id).order_by(ItemOS.id)).all()
        snapshot = [{'tipo': i.tipo, 'descricao': i.descricao, 'quantidade': i.quantidade,
                     'valor_unitario_centavos': i.valor_unitario_centavos,
                     'subtotal_centavos': i.quantidade * i.valor_unitario_centavos} for i in itens]
        for anterior in db.scalars(select(Orcamento).where(Orcamento.os_id == os_id,
                                                           Orcamento.status == 'enviado')).all():
            anterior.status = 'substituido'
        agora_ = agora()
        orc = Orcamento(os_id=os_id, versao=_ultima_versao(db, os_id) + 1, status='enviado',
                        itens_json=json.dumps(snapshot, ensure_ascii=False), subtotal_centavos=subtotal,
                        desconto_centavos=desconto, total_centavos=subtotal - desconto,
                        validade_ate=agora_.date() + timedelta(days=validade), observacoes_cliente=obs or None,
                        token_hash=_hash(token), enviado_em=agora_, criado_por=user['id'])
        db.add(orc)
        db.flush()
        resultado = _orc_dict(orc)
    log_negocio('orcamento.enviado', user, 'orcamento', resultado['id'],
                {'os_id': os_id, 'versao': resultado['versao'], 'total_centavos': resultado['total_centavos']})
    # caminho RELATIVO: o front monta a URL com a própria origem (nunca confiar no Host da requisição)
    return jsonify({'orcamento': resultado, 'link': f'/orcamento/{token}'}), 201


@bp.post('/api/os/<int:os_id>/orcamentos/<int:orcamento_id>/decisao')
@require_roles('dono', 'cliente')
def decidir_orcamento(os_id: int, orcamento_id: int):
    user = g.user
    dados = _json()
    with session_scope() as db:
        os_ = os_visivel(db, user, os_id)
        orc = db.scalar(select(Orcamento).where(Orcamento.id == orcamento_id, Orcamento.os_id == os_id)
                        .with_for_update()) if os_ else None
        if not os_ or not orc:
            return negar_nao_encontrado(user, 'orcamento', orcamento_id)
        falha = _decidir(db, os_, orc, dados, user, 'app')
        if falha:
            return erro(*falha)
        resultado = _orc_dict(orc)
        status_os = os_.status
    _logar_decisao(user, os_id, resultado, 'app')
    return jsonify({'orcamento': resultado, 'os_status': status_os})


# ---------------------------------------------------------------------------
# Rotas públicas (sem login): o token do link é a credencial
# ---------------------------------------------------------------------------

@bp.after_request
def _sem_cache_no_publico(response):
    if request.path.startswith('/api/publico/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


def _limite_publico(token_hash: str):
    """Limite por IP E por token: o IP sozinho é falsificável (X-Forwarded-For)."""
    core = _core()
    ip_ok = core.check_rate_limit(f'pub:ip:{core.get_client_ip()}', 30, 60)
    tok_ok = core.check_rate_limit(f'pub:tok:{token_hash[:16]}', 10, 60)
    if not (ip_ok and tok_ok):
        return erro('Muitas tentativas. Aguarde um minuto e tente de novo.', 429)
    return None


def _buscar_publico(db, token_hash: str, travar: bool = False):
    stmt = select(Orcamento).where(Orcamento.token_hash == token_hash)
    if travar:
        stmt = stmt.with_for_update()
    orc = db.scalar(stmt)
    os_ = db.get(OrdemServico, orc.os_id) if orc else None
    if not orc or not os_ or os_.excluida_em is not None:
        return None, None
    return orc, os_


def _payload_publico(db, orc: Orcamento, os_: OrdemServico) -> dict[str, Any]:
    oficina = db.get(Oficina, os_.oficina_id)
    veiculo = db.get(Veiculo, os_.veiculo_id)
    cliente = db.get(Cliente, veiculo.cliente_id) if veiculo else None
    return {
        'oficina': {'nome': oficina.nome if oficina else ''},
        'cliente': {'nome': cliente.nome if cliente else ''},
        'veiculo': {'placa': veiculo.placa, 'marca': veiculo.marca, 'modelo': veiculo.modelo, 'ano': veiculo.ano}
        if veiculo else {'placa': '', 'marca': '', 'modelo': '', 'ano': None},
        'os': {'descricao': os_.descricao, 'km_entrada': os_.km_entrada},
        'orcamento': _orc_publico(orc),
    }


_LINK_INVALIDO = 'Link de orçamento inválido.'


@bp.get('/api/publico/orcamentos/<token>')
def ver_orcamento_publico(token: str):
    token_hash = _hash(token)
    bloqueio = _limite_publico(token_hash)
    if bloqueio:
        return bloqueio
    with session_scope() as db:
        orc, os_ = _buscar_publico(db, token_hash)
        if not orc:
            return erro(_LINK_INVALIDO, 404)
        return jsonify(_payload_publico(db, orc, os_))


@bp.post('/api/publico/orcamentos/<token>/decisao')
def decidir_orcamento_publico(token: str):
    token_hash = _hash(token)
    bloqueio = _limite_publico(token_hash)
    if bloqueio:
        return bloqueio
    dados = _json()
    with session_scope() as db:
        orc, os_ = _buscar_publico(db, token_hash, travar=True)
        if not orc:
            return erro(_LINK_INVALIDO, 404)
        ator = {'id': None, 'role': 'cliente', 'oficina_id': os_.oficina_id}
        falha = _decidir(db, os_, orc, dados, ator, 'link')
        if falha:
            return erro(*falha)
        os_id = os_.id
        para_log = _orc_dict(orc)
        resultado = _payload_publico(db, orc, os_)
    _logar_decisao(ator, os_id, para_log, 'link')
    return jsonify(resultado)


# ---------------------------------------------------------------------------
# Anotações internas (dono e mecânico; o cliente nunca vê)
# ---------------------------------------------------------------------------

def _nomes_da_equipe(oficina_id: int) -> dict[int, str]:
    try:
        resp = _core()._forward_to_auth('GET', f'/internal/oficinas/{oficina_id}/usuarios')
        if resp.status_code == 200:
            return {int(u['id']): u.get('nome') for u in resp.json().get('usuarios', [])}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass
    return {}


def _nota_dict(n: NotaOS, nomes: dict[int, str]) -> dict[str, Any]:
    return {'id': n.id, 'autor_id': n.autor_id, 'autor_nome': nomes.get(n.autor_id), 'texto': n.texto,
            'criada_em': _iso(n.criada_em)}


@bp.get('/api/os/<int:os_id>/notas')
@require_roles('dono', 'mecanico')
def listar_notas(os_id: int):
    with session_scope() as db:
        if not os_visivel(db, g.user, os_id):
            return negar_nao_encontrado(g.user, 'os', os_id)
        notas = db.scalars(select(NotaOS).where(NotaOS.os_id == os_id)
                           .order_by(NotaOS.criada_em.desc(), NotaOS.id.desc())).all()
        notas = list(notas)
    nomes = _nomes_da_equipe(g.user['oficina_id']) if notas else {}
    return jsonify({'notas': [_nota_dict(n, nomes) for n in notas]})


@bp.post('/api/os/<int:os_id>/notas')
@require_roles('dono', 'mecanico')
def adicionar_nota(os_id: int):
    user = g.user
    texto = _json().get('texto')
    texto = texto.strip() if isinstance(texto, str) else ''
    if not 1 <= len(texto) <= NOTA_MAX:
        return erro(f'Escreva a anotação (1 a {NOTA_MAX} caracteres).')
    with session_scope() as db:
        if not os_visivel(db, user, os_id):
            return negar_nao_encontrado(user, 'os', os_id)
        nota = NotaOS(os_id=os_id, autor_id=user['id'], texto=texto, criada_em=agora())
        db.add(nota)
        db.flush()
        resultado = _nota_dict(nota, {user['id']: user.get('nome')})
    log_negocio('os.nota_adicionada', user, 'os', os_id, {'nota_id': resultado['id']})
    return jsonify({'nota': resultado}), 201
