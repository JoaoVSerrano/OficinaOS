"""Rotas do domínio da oficina (Atividade 10).

Regras que valem para TODAS as rotas deste módulo:
- papel e oficina vêm do auth-service (`/me`), nunca do corpo/URL da requisição;
- toda consulta passa por `backend.escopo` (registro de outra oficina => 404);
- a permissão é checada aqui, no backend, mesmo que a interface esconda o botão.
"""
from __future__ import annotations

import re
import secrets
from functools import wraps
from typing import Any

import requests
from flask import Blueprint, g, jsonify, request

from backend import escopo, planos
from backend.database import session_scope
from backend.models import Cliente, Oficina, Veiculo

bp = Blueprint('dominio', __name__)

PAPEIS_OFICINA = ('dono', 'mecanico', 'cliente')


# ---------------------------------------------------------------------------
# Acesso ao núcleo do gateway (import tardio: backend.app importa este módulo)
# ---------------------------------------------------------------------------

def _core():
    import sys
    return sys.modules['backend.app']


def erro(mensagem: str, status: int = 400, **extra: Any):
    return jsonify({'error': mensagem, **extra}), status


def log_negocio(evento: str, user: dict[str, Any] | None, recurso: str = '', recurso_id: int | None = None,
                detalhe: dict[str, Any] | None = None) -> None:
    """Evento de negócio no log-service: quem, papel, oficina, recurso e quando (o log carimba a hora)."""
    dados = dict(detalhe or {})
    dados.update({'papel': (user or {}).get('role'), 'oficina_id': (user or {}).get('oficina_id'),
                  'recurso': recurso, 'recurso_id': recurso_id})
    _core().log_event(evento, usuario_id=(user or {}).get('id'), detalhe=dados,
                      oficina_id=(user or {}).get('oficina_id'), papel=(user or {}).get('role'),
                      recurso=recurso, recurso_id=recurso_id)


def _json() -> dict[str, Any]:
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


# ---------------------------------------------------------------------------
# Usuário autenticado e autorização por papel
# ---------------------------------------------------------------------------

def usuario_atual() -> tuple[dict[str, Any] | None, Any]:
    """Consulta o auth-service. Devolve (usuario, None) ou (None, resposta_de_erro)."""
    core = _core()
    try:
        resp = core._forward_to_auth('GET', '/me')
    except requests.RequestException as exc:
        core.app.logger.error('Auth-service indisponível: %s', exc)
        return None, erro('Serviço de autenticação indisponível.', 503)
    if resp.status_code != 200:
        return None, erro('Faça login para continuar.', 401)
    user = resp.json().get('user') or {}
    if not user.get('id'):
        return None, erro('Faça login para continuar.', 401)
    return user, None


def require_roles(*papeis: str, precisa_oficina: bool = True):
    """401 sem login; 403 com papel errado (mesmo chamando a API direto); 409 se o dono ainda não criou a oficina."""

    def decorador(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user, err = usuario_atual()
            if err:
                return err
            if user.get('role') not in papeis:
                log_negocio('acesso_negado', user, 'rota', None, {'caminho': request.path, 'metodo': request.method,
                                                                    'motivo': 'papel'})
                return erro('Seu papel não tem permissão para esta ação.', 403)
            if precisa_oficina and not user.get('oficina_id'):
                return erro('Crie sua oficina para continuar.', 409, codigo='sem_oficina')
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorador


def negar_nao_encontrado(user: dict[str, Any], recurso: str, recurso_id: int):
    """404 para registro inexistente OU de outra oficina (não revela qual dos dois)."""
    log_negocio('acesso_negado', user, recurso, recurso_id, {'motivo': 'nao_encontrado_na_oficina',
                                                              'caminho': request.path})
    return erro('Registro não encontrado.', 404)


# ---------------------------------------------------------------------------
# Cadastro e oficina
# ---------------------------------------------------------------------------

_ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _gerar_codigo(db) -> str:
    for _ in range(20):
        codigo = 'OF-' + ''.join(secrets.choice(_ALFABETO) for _ in range(8))
        if not db.scalar(escopo_codigo(codigo)):
            return codigo
    raise RuntimeError('não foi possível gerar um código de convite único')


def escopo_codigo(codigo: str):
    from sqlalchemy import select
    return select(Oficina.id).where(Oficina.codigo_convite == codigo)


def _resposta_auth(resp: requests.Response, status: int | None = None):
    """Repassa resposta e cookie de sessão do auth-service ao navegador."""
    core = _core()
    response = jsonify(core._auth_response_payload(resp))
    response.status_code = status or resp.status_code
    for header in core._set_cookie_headers(resp):
        response.headers.add('Set-Cookie', header)
    return response


def _serializar_oficina(o: Oficina, incluir_codigo: bool) -> dict[str, Any]:
    dados = {'id': o.id, 'nome': o.nome, 'plano': planos.plano_da_oficina(o.id)}
    if incluir_codigo:
        dados['codigo_convite'] = o.codigo_convite
    return dados


def _contar_mecanicos(oficina_id: int) -> int:
    resp = _core()._forward_to_auth('GET', f'/internal/oficinas/{oficina_id}/usuarios')
    if resp.status_code != 200:
        raise requests.RequestException('falha ao consultar a equipe')
    return sum(1 for u in resp.json().get('usuarios', []) if u.get('role') == 'mecanico')


def resposta_limite(user: dict[str, Any], plano: str, chave: str, limite: int, uso: int, recurso: str):
    """402 padronizado de limite do plano (corpo da seção 4.4) + evento plano.limite_atingido."""
    log_negocio('plano.limite_atingido', user, recurso, None, {'limite': chave, 'uso': uso, 'plano': plano})
    return erro('Limite do plano atingido: ' + _MSG_LIMITE[chave].format(limite=limite) + '. ' + planos.COMO_LIBERAR + '.',
                402, codigo='limite_plano', limite=limite, uso=uso, plano=plano, como_liberar=planos.COMO_LIBERAR)


_MSG_LIMITE = {
    'max_os_mes': 'o plano Free permite {limite} ordens de serviço por mês',
    'max_mecanicos': 'o plano Free permite {limite} mecânico',
    'max_anexos_por_os': 'o plano Free permite {limite} anexos por ordem de serviço',
}


@bp.post('/api/cadastro')
def cadastro():
    """Cadastro orquestrado: dono cria a oficina; mecânico e cliente entram por código de convite."""
    core = _core()
    dados = _json()
    tipo = str(dados.get('tipo', '')).strip().lower()
    nome = str(dados.get('nome', '')).strip()
    email = str(dados.get('email', '')).strip().lower()
    senha = str(dados.get('senha', ''))

    if tipo not in PAPEIS_OFICINA:
        return erro("Informe o tipo de conta: 'dono', 'mecanico' ou 'cliente'.")
    if len(nome) < 2:
        return erro('Informe um nome válido.')
    if '@' not in email or len(email) < 5:
        return erro('Informe um e-mail válido.')
    if len(senha) < 6:
        return erro('A senha precisa ter pelo menos 6 caracteres.')

    try:
        if tipo == 'dono':
            nome_oficina = str(dados.get('nome_oficina', '')).strip()
            if len(nome_oficina) < 2:
                return erro('Informe o nome da oficina.')
            with session_scope() as db:
                oficina = Oficina(nome=nome_oficina, codigo_convite=_gerar_codigo(db))
                db.add(oficina)
                db.flush()
                oficina_id = int(oficina.id)
            resp = core._forward_to_auth('POST', '/internal/register', json={
                'nome': nome, 'email': email, 'senha': senha, 'role': 'dono', 'oficina_id': oficina_id})
            if resp.status_code != 201:
                with session_scope() as db:  # desfaz a oficina se o auth recusou (e-mail repetido etc.)
                    registro = db.get(Oficina, oficina_id)
                    if registro:
                        db.delete(registro)
                return _resposta_auth(resp)
            user = resp.json()['user']
            log_negocio('oficina.criada', user, 'oficina', oficina_id, {'nome': nome_oficina})
            return _resposta_auth(resp)

        codigo = str(dados.get('codigo_convite', '')).strip().upper()
        with session_scope() as db:
            oficina = db.scalar(escopo_codigo(codigo)) if codigo else None
        if not oficina:
            return erro('Código de convite inválido.')
        oficina_id = int(oficina)

        if tipo == 'mecanico':
            plano = planos.plano_da_oficina(oficina_id)
            lim = planos.limite(plano, 'max_mecanicos')
            if lim is not None:
                usados = _contar_mecanicos(oficina_id)
                if usados >= lim:
                    return resposta_limite({'role': 'mecanico', 'oficina_id': oficina_id}, plano, 'max_mecanicos',
                                           lim, usados, 'cadastro')
        resp = core._forward_to_auth('POST', '/internal/register', json={
            'nome': nome, 'email': email, 'senha': senha, 'role': tipo, 'oficina_id': oficina_id})
        if resp.status_code != 201:
            return _resposta_auth(resp)
        user = resp.json()['user']
        if tipo == 'cliente':
            _vincular_ou_criar_cliente(user)
        log_negocio('membro.entrou', user, 'oficina', oficina_id, {'papel_entrada': tipo})
        return _resposta_auth(resp)
    except requests.RequestException as exc:
        core.app.logger.error('Auth-service indisponível no cadastro: %s', exc)
        return erro('Serviço de autenticação indisponível.', 503)


def _vincular_ou_criar_cliente(user: dict[str, Any]) -> None:
    """Cliente que entra por convite: liga ao cadastro feito pelo dono (mesmo e-mail) ou cria um novo."""
    from sqlalchemy import func, select
    with session_scope() as db:
        existente = db.scalar(select(Cliente).where(
            Cliente.oficina_id == user['oficina_id'], Cliente.usuario_id.is_(None),
            func.lower(Cliente.email) == str(user['email']).lower()))
        if existente:
            existente.usuario_id = user['id']
        else:
            db.add(Cliente(oficina_id=user['oficina_id'], usuario_id=user['id'], nome=user['nome'],
                           email=user['email']))


@bp.post('/api/oficinas')
def criar_oficina():
    """Onboarding: dono (ex.: conta antiga ou Google) que ainda não tem oficina."""
    user, err = usuario_atual()
    if err:
        return err
    if user.get('role') != 'dono' or user.get('oficina_id'):
        return erro('Esta conta não pode criar uma oficina.', 403)
    nome = str(_json().get('nome', '')).strip()
    if len(nome) < 2:
        return erro('Informe o nome da oficina.')
    core = _core()
    with session_scope() as db:
        oficina = Oficina(nome=nome, codigo_convite=_gerar_codigo(db))
        db.add(oficina)
        db.flush()
        oficina_id = int(oficina.id)
    try:
        resp = core._forward_to_auth('POST', f'/internal/users/{user["id"]}/oficina', json={'oficina_id': oficina_id})
    except requests.RequestException:
        resp = None
    if resp is None or resp.status_code != 200:
        with session_scope() as db:
            registro = db.get(Oficina, oficina_id)
            if registro:
                db.delete(registro)
        return erro('Não foi possível criar a oficina.', 503 if resp is None else resp.status_code)
    user['oficina_id'] = oficina_id
    log_negocio('oficina.criada', user, 'oficina', oficina_id, {'nome': nome})
    return jsonify({'oficina': {'id': oficina_id, 'nome': nome}}), 201


@bp.get('/api/oficina')
@require_roles('dono', 'mecanico', 'cliente')
def minha_oficina():
    user = g.user
    with session_scope() as db:
        oficina = db.get(Oficina, user['oficina_id'])
        if not oficina:
            return erro('Oficina não encontrada.', 404)
        return jsonify({'oficina': _serializar_oficina(oficina, user['role'] == 'dono')})


@bp.get('/api/equipe')
@require_roles('dono')
def equipe():
    try:
        resp = _core()._forward_to_auth('GET', f'/internal/oficinas/{g.user["oficina_id"]}/usuarios')
    except requests.RequestException:
        return erro('Serviço de autenticação indisponível.', 503)
    if resp.status_code != 200:
        return erro('Não foi possível listar a equipe.', 502)
    return jsonify({'equipe': resp.json().get('usuarios', [])})


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

def _cliente_dict(c: Cliente) -> dict[str, Any]:
    return {'id': c.id, 'nome': c.nome, 'telefone': c.telefone, 'email': c.email,
            'criado_em': c.criado_em.isoformat() if c.criado_em else None}


def _validar_cliente(dados: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    nome = str(dados.get('nome', '')).strip()
    if len(nome) < 2:
        return None, 'Informe o nome do cliente.'
    email = str(dados.get('email') or '').strip().lower() or None
    if email and '@' not in email:
        return None, 'Informe um e-mail válido.'
    telefone = str(dados.get('telefone') or '').strip()[:20] or None
    return {'nome': nome[:120], 'telefone': telefone, 'email': email}, None


@bp.get('/api/clientes')
@require_roles('dono', 'mecanico')
def listar_clientes():
    with session_scope() as db:
        itens = escopo.listar(db, Cliente, g.user['oficina_id'], order_by=Cliente.nome)
        return jsonify({'clientes': [_cliente_dict(c) for c in itens]})


@bp.post('/api/clientes')
@require_roles('dono')
def criar_cliente():
    dados, msg = _validar_cliente(_json())
    if msg:
        return erro(msg)
    with session_scope() as db:
        cliente = Cliente(oficina_id=g.user['oficina_id'], **dados)
        db.add(cliente)
        db.flush()
        resultado = _cliente_dict(cliente)
    log_negocio('cliente.criado', g.user, 'cliente', resultado['id'])
    return jsonify({'cliente': resultado}), 201


@bp.get('/api/clientes/<int:cliente_id>')
@require_roles('dono', 'mecanico')
def detalhar_cliente(cliente_id: int):
    with session_scope() as db:
        cliente = escopo.obter(db, Cliente, cliente_id, g.user['oficina_id'])
        if not cliente:
            return negar_nao_encontrado(g.user, 'cliente', cliente_id)
        return jsonify({'cliente': _cliente_dict(cliente)})


@bp.put('/api/clientes/<int:cliente_id>')
@require_roles('dono')
def editar_cliente(cliente_id: int):
    dados, msg = _validar_cliente(_json())
    if msg:
        return erro(msg)
    with session_scope() as db:
        cliente = escopo.obter(db, Cliente, cliente_id, g.user['oficina_id'])
        if not cliente:
            return negar_nao_encontrado(g.user, 'cliente', cliente_id)
        for campo, valor in dados.items():
            setattr(cliente, campo, valor)
        return jsonify({'cliente': _cliente_dict(cliente)})


@bp.delete('/api/clientes/<int:cliente_id>')
@require_roles('dono')
def remover_cliente(cliente_id: int):
    with session_scope() as db:
        cliente = escopo.obter(db, Cliente, cliente_id, g.user['oficina_id'])
        if not cliente:
            return negar_nao_encontrado(g.user, 'cliente', cliente_id)
        if escopo.listar(db, Veiculo, g.user['oficina_id'], Veiculo.cliente_id == cliente_id):
            return erro('O cliente ainda tem veículos cadastrados. Remova os veículos primeiro.', 409)
        db.delete(cliente)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Veículos
# ---------------------------------------------------------------------------

_PLACA = re.compile(r'^[A-Z0-9]{7}$')


def _veiculo_dict(v: Veiculo) -> dict[str, Any]:
    return {'id': v.id, 'cliente_id': v.cliente_id, 'placa': v.placa, 'marca': v.marca, 'modelo': v.modelo,
            'ano': v.ano}


def _validar_veiculo(dados: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    placa = re.sub(r'[\s-]', '', str(dados.get('placa', ''))).upper()
    if not _PLACA.match(placa):
        return None, 'Informe uma placa válida (7 caracteres, ex.: ABC1D23).'
    marca = str(dados.get('marca', '')).strip()
    modelo = str(dados.get('modelo', '')).strip()
    if not marca or not modelo:
        return None, 'Informe marca e modelo.'
    ano = dados.get('ano')
    if ano in ('', None):
        ano = None
    else:
        try:
            ano = int(ano)
        except (TypeError, ValueError):
            return None, 'Ano inválido.'
        if not 1900 <= ano <= 2100:
            return None, 'Ano inválido.'
    return {'placa': placa, 'marca': marca[:60], 'modelo': modelo[:60], 'ano': ano}, None


def _ids_veiculos_do_cliente_logado(db, user: dict[str, Any]) -> list[int]:
    ids_clientes = [c.id for c in escopo.listar(db, Cliente, user['oficina_id'], Cliente.usuario_id == user['id'])]
    if not ids_clientes:
        return []
    return [v.id for v in escopo.listar(db, Veiculo, user['oficina_id'], Veiculo.cliente_id.in_(ids_clientes))]


@bp.get('/api/veiculos')
@require_roles('dono', 'mecanico', 'cliente')
def listar_veiculos():
    user = g.user
    with session_scope() as db:
        where = []
        if user['role'] == 'cliente':
            ids = _ids_veiculos_do_cliente_logado(db, user)
            where.append(Veiculo.id.in_(ids or [0]))
        cliente_id = request.args.get('cliente_id', type=int)
        if cliente_id:
            where.append(Veiculo.cliente_id == cliente_id)
        itens = escopo.listar(db, Veiculo, user['oficina_id'], *where, order_by=Veiculo.placa)
        return jsonify({'veiculos': [_veiculo_dict(v) for v in itens]})


@bp.post('/api/veiculos')
@require_roles('dono')
def criar_veiculo():
    dados = _json()
    campos, msg = _validar_veiculo(dados)
    if msg:
        return erro(msg)
    cliente_id = dados.get('cliente_id')
    with session_scope() as db:
        cliente = escopo.obter(db, Cliente, cliente_id, g.user['oficina_id']) if isinstance(cliente_id, int) else None
        if not cliente:
            return erro('Cliente não encontrado.', 404)
        if escopo.listar(db, Veiculo, g.user['oficina_id'], Veiculo.placa == campos['placa']):
            return erro('Já existe um veículo com essa placa nesta oficina.', 409)
        veiculo = Veiculo(oficina_id=g.user['oficina_id'], cliente_id=cliente.id, **campos)
        db.add(veiculo)
        db.flush()
        resultado = _veiculo_dict(veiculo)
    log_negocio('veiculo.criado', g.user, 'veiculo', resultado['id'])
    return jsonify({'veiculo': resultado}), 201


def _veiculo_visivel(db, user: dict[str, Any], veiculo_id: int) -> Veiculo | None:
    veiculo = escopo.obter(db, Veiculo, veiculo_id, user['oficina_id'])
    if veiculo and user['role'] == 'cliente' and veiculo.id not in _ids_veiculos_do_cliente_logado(db, user):
        return None
    return veiculo


@bp.get('/api/veiculos/<int:veiculo_id>')
@require_roles('dono', 'mecanico', 'cliente')
def detalhar_veiculo(veiculo_id: int):
    with session_scope() as db:
        veiculo = _veiculo_visivel(db, g.user, veiculo_id)
        if not veiculo:
            return negar_nao_encontrado(g.user, 'veiculo', veiculo_id)
        return jsonify({'veiculo': _veiculo_dict(veiculo)})


@bp.put('/api/veiculos/<int:veiculo_id>')
@require_roles('dono')
def editar_veiculo(veiculo_id: int):
    campos, msg = _validar_veiculo(_json())
    if msg:
        return erro(msg)
    with session_scope() as db:
        veiculo = escopo.obter(db, Veiculo, veiculo_id, g.user['oficina_id'])
        if not veiculo:
            return negar_nao_encontrado(g.user, 'veiculo', veiculo_id)
        outro = escopo.listar(db, Veiculo, g.user['oficina_id'], Veiculo.placa == campos['placa'],
                              Veiculo.id != veiculo_id)
        if outro:
            return erro('Já existe um veículo com essa placa nesta oficina.', 409)
        for campo, valor in campos.items():
            setattr(veiculo, campo, valor)
        return jsonify({'veiculo': _veiculo_dict(veiculo)})


@bp.delete('/api/veiculos/<int:veiculo_id>')
@require_roles('dono')
def remover_veiculo(veiculo_id: int):
    from sqlalchemy import select
    from backend.models import OrdemServico
    with session_scope() as db:
        veiculo = escopo.obter(db, Veiculo, veiculo_id, g.user['oficina_id'])
        if not veiculo:
            return negar_nao_encontrado(g.user, 'veiculo', veiculo_id)
        # inclui OS excluídas logicamente: a FK ainda as referencia
        tem_os = db.scalar(select(OrdemServico.id).where(OrdemServico.veiculo_id == veiculo_id).limit(1))
        if tem_os:
            return erro('O veículo tem ordens de serviço e não pode ser removido.', 409)
        db.delete(veiculo)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Auditoria da oficina (dono vê só os eventos da própria oficina)
# ---------------------------------------------------------------------------

@bp.get('/api/auditoria')
@require_roles('dono')
def auditoria_da_oficina():
    """Eventos de negócio da oficina. `oficina_id` é FORÇADO pelo servidor (nunca vem da requisição)."""
    core = _core()
    params: dict[str, Any] = {'oficina_id': g.user['oficina_id'], 'n': request.args.get('n', '50')}
    for chave in ('acao', 'cursor', 'usuario_id'):
        if request.args.get(chave):
            params[chave] = request.args[chave]
    try:
        resp = requests.get(f'{core.log_service_url()}/logs', params=params,
                            headers={'X-Internal-Token': core.internal_token()}, timeout=10)
        resp.raise_for_status()
        dados = resp.json()
    except requests.RequestException as exc:
        core.app.logger.error('log-service indisponível na auditoria: %s', exc)
        return erro('Serviço de log indisponível.', 503)
    nomes: dict[str, str] = {}
    try:
        equipe_resp = core._forward_to_auth('GET', f'/internal/oficinas/{g.user["oficina_id"]}/usuarios')
        if equipe_resp.status_code == 200:
            nomes = {str(u['id']): u['nome'] for u in equipe_resp.json().get('usuarios', [])}
    except requests.RequestException:
        pass
    for evento in dados.get('logs', []):
        evento['usuario_nome'] = nomes.get(str(evento.get('usuario_id') or ''))
    return jsonify(dados)


# ---------------------------------------------------------------------------
# Assinatura (Atividade 11): só o dono da oficina assina; oficina e usuário vêm da sessão
# ---------------------------------------------------------------------------

@bp.post('/api/payment/checkout')
@require_roles('dono')
def payment_checkout():
    core = _core()
    user = g.user
    if not core.check_rate_limit(f'checkout:{user["id"]}', max_requests=5, window_seconds=60):
        return erro('Muitas tentativas de checkout. Por favor, aguarde um minuto.', 429)
    try:
        resp = core._forward_to_payment('POST', '/checkout', json={
            'oficina_id': user['oficina_id'], 'usuario_id': user['id'], 'email': user.get('email', '')})
        corpo, status = resp.json(), resp.status_code
    except requests.RequestException as exc:
        core.app.logger.error('payment-service indisponível em checkout: %s', exc)
        return erro('Serviço de pagamentos indisponível.', 503)
    if status == 201:
        log_negocio('assinatura.checkout_iniciado', user, 'assinatura', user['oficina_id'])
    return jsonify(corpo), status


@bp.post('/api/payment/portal')
@require_roles('dono')
def payment_portal():
    core = _core()
    user = g.user
    try:
        resp = core._forward_to_payment('POST', '/portal', json={'oficina_id': user['oficina_id']})
        corpo, status = resp.json(), resp.status_code
    except requests.RequestException as exc:
        core.app.logger.error('payment-service indisponível em portal: %s', exc)
        return erro('Serviço de pagamentos indisponível.', 503)
    if status == 200:
        log_negocio('assinatura.portal_aberto', user, 'assinatura', user['oficina_id'])
    return jsonify(corpo), status


# ---------------------------------------------------------------------------
# Painel admin da plataforma (Atividade 11): planos, assinaturas ativas, MRR de teste e eventos
# ---------------------------------------------------------------------------

def _eventos_recentes(n: int) -> list[dict[str, Any]]:
    """Últimos eventos do log-service; o log é acessório, então falha vira lista vazia."""
    core = _core()
    try:
        resp = requests.get(f'{core.log_service_url()}/logs', params={'n': n},
                            headers={'X-Internal-Token': core.internal_token()}, timeout=5)
        resp.raise_for_status()
        return resp.json().get('logs', [])
    except Exception as exc:
        core.app.logger.warning('log-service indisponível no painel: %s', exc)
        return []


@bp.get('/api/admin/painel')
@require_roles('admin', precisa_oficina=False)
def admin_painel():
    from sqlalchemy import select
    core = _core()
    try:
        resumo = core._forward_to_payment('GET', '/internal/resumo')
        contagem = core._forward_to_auth('GET', '/internal/usuarios/contagem')
        if resumo.status_code != 200 or contagem.status_code != 200:
            raise requests.RequestException('resposta inesperada')
        resumo, contagem = resumo.json(), contagem.json()
    except requests.RequestException as exc:
        core.app.logger.error('Painel admin sem dados de pagamento/usuários: %s', exc)
        return erro('Não foi possível reunir os dados do painel agora. Tente novamente.', 503)

    with session_scope() as db:
        ids = set(db.scalars(select(Oficina.id)).all())
    pro = {i for i in resumo.get('oficinas_pro', []) if i in ids}     # Pro de oficina que não existe é ignorado
    por_oficina = {int(k): v for k, v in (contagem.get('por_oficina') or {}).items() if int(k) in ids}
    return jsonify({
        'oficinas_por_plano': {'free': len(ids) - len(pro), 'pro': len(pro)},
        'usuarios_por_plano': {
            'free': sum(v for k, v in por_oficina.items() if k not in pro),
            'pro': sum(v for k, v in por_oficina.items() if k in pro),
            'sem_oficina': contagem.get('sem_oficina', 0),
        },
        'assinaturas_ativas': resumo.get('assinaturas_ativas', 0),
        'inadimplentes': resumo.get('inadimplentes', 0),
        'mrr_centavos': resumo.get('mrr_centavos', 0),
        'moeda': resumo.get('moeda', 'brl'),
        'eventos': _eventos_recentes(20),
    })
