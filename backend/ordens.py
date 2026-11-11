"""Ordens de serviço: CRUD, itens e máquina de estados (seção 4.3 do plano).

status: aberta -> orcamento_aprovado -> em_servico -> pronta -> entregue   (cancelada só pelo dono, antes de entregue)
Transição inexistente => 409. Transição existente mas sem permissão do papel => 403.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import func, select

from backend import escopo, planos
from backend.database import session_scope
from backend.dominio import (_core, _ids_veiculos_do_cliente_logado, _json, erro, log_negocio, negar_nao_encontrado,
                             require_roles, resposta_limite)
from backend.models import AnexoOS, Cliente, ItemOS, OrdemServico, Veiculo

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


# ---------------------------------------------------------------------------
# Anexos (fotos e comprovantes) no MinIO
#
# Bucket PRIVADO e separado do de avatares (que tem leitura pública): os anexos nunca ganham
# política de leitura anônima. A leitura passa pela rota do gateway, com checagem de papel e oficina.
# ---------------------------------------------------------------------------

TAMANHO_MAX_ANEXO = 5 * 1024 * 1024
_bucket_pronto = False


def bucket_anexos() -> str:
    return os.getenv('MINIO_ANEXOS_BUCKET', 'oficinaos-anexos')


def minio_client():
    from minio import Minio
    endpoint = os.getenv('MINIO_ENDPOINT', 'minio:9000')
    endpoint = endpoint.split('://')[-1]
    return Minio(endpoint, access_key=os.getenv('MINIO_ACCESS_KEY', ''), secret_key=os.getenv('MINIO_SECRET_KEY', ''),
                 secure=False)


def _garantir_bucket(cliente) -> None:
    """Cria o bucket se faltar. Propositalmente NÃO define política: sem política = sem leitura pública."""
    global _bucket_pronto
    if _bucket_pronto:
        return
    if not cliente.bucket_exists(bucket_anexos()):
        cliente.make_bucket(bucket_anexos())
    _bucket_pronto = True


def detectar_imagem(conteudo: bytes) -> tuple[str, str] | None:
    """Tipo pelo CONTEÚDO (bytes mágicos), nunca pelo nome ou pelo Content-Type enviado."""
    if conteudo.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png', 'png'
    if conteudo.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', 'jpg'
    if conteudo[:4] == b'RIFF' and conteudo[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    return None


def _anexo_dict(a: AnexoOS) -> dict[str, Any]:
    return {'id': a.id, 'os_id': a.os_id, 'nome_original': a.nome_original, 'tipo_mime': a.tipo_mime,
            'tamanho_bytes': a.tamanho_bytes, 'enviado_por': a.enviado_por, 'criado_em': _iso(a.criado_em),
            'url': f'/api/os/{a.os_id}/anexos/{a.id}/arquivo'}


@bp.post('/api/os/<int:os_id>/anexos')
@require_roles('dono', 'mecanico')
def enviar_anexo(os_id: int):
    user = g.user
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return erro("Envie o arquivo no campo 'arquivo' (multipart/form-data).")
    conteudo = arquivo.read(TAMANHO_MAX_ANEXO + 1)
    if not conteudo:
        return erro('O arquivo enviado está vazio.')
    if len(conteudo) > TAMANHO_MAX_ANEXO:
        return erro('O arquivo excede o limite de 5 MB.')
    tipo = detectar_imagem(conteudo)
    if not tipo:
        return erro('Formato não aceito. Envie uma imagem PNG, JPEG ou WEBP.')
    mime, ext = tipo

    with session_scope() as db:
        os_ = os_visivel(db, user, os_id)
        if not os_:
            return negar_nao_encontrado(user, 'os', os_id)
        if os_.status == 'cancelada':
            return erro('Ordem de serviço cancelada não aceita anexos.', 409)
        plano = planos.plano_da_oficina(user['oficina_id'])
        lim = planos.limite(plano, 'max_anexos_por_os')
        if lim is not None:
            usados = int(db.scalar(select(func.count(AnexoOS.id)).where(AnexoOS.os_id == os_id)) or 0)
            if usados >= lim:
                return resposta_limite(user, plano, 'max_anexos_por_os', lim, usados, 'anexo')
        chave = f'os/{user["oficina_id"]}/{os_id}/{uuid.uuid4().hex}.{ext}'
        nome = (arquivo.filename or f'foto.{ext}').replace('\\', '/').rsplit('/', 1)[-1][:255]
        try:
            import io
            cliente = minio_client()
            _garantir_bucket(cliente)
            cliente.put_object(bucket_anexos(), chave, io.BytesIO(conteudo), length=len(conteudo), content_type=mime)
        except Exception as exc:  # MinIO fora do ar ou mal configurado
            _core().app.logger.error('Falha ao gravar anexo no MinIO: %s', exc)
            return erro('Serviço de armazenamento indisponível.', 503)
        try:
            anexo = AnexoOS(os_id=os_id, chave_objeto=chave, nome_original=nome, tipo_mime=mime,
                            tamanho_bytes=len(conteudo), enviado_por=user['id'], criado_em=agora())
            db.add(anexo)
            db.flush()
            resultado = _anexo_dict(anexo)
        except Exception:
            try:
                cliente.remove_object(bucket_anexos(), chave)
            finally:
                raise
    log_negocio('anexo.enviado', user, 'anexo', resultado['id'], {'os_id': os_id, 'tamanho_bytes': len(conteudo)})
    return jsonify({'anexo': resultado}), 201


@bp.get('/api/os/<int:os_id>/anexos')
@require_roles('dono', 'mecanico', 'cliente')
def listar_anexos(os_id: int):
    with session_scope() as db:
        if not os_visivel(db, g.user, os_id):
            return negar_nao_encontrado(g.user, 'os', os_id)
        itens = db.scalars(select(AnexoOS).where(AnexoOS.os_id == os_id).order_by(AnexoOS.id)).all()
        return jsonify({'anexos': [_anexo_dict(a) for a in itens]})


@bp.get('/api/os/<int:os_id>/anexos/<int:anexo_id>/arquivo')
@require_roles('dono', 'mecanico', 'cliente')
def baixar_anexo(os_id: int, anexo_id: int):
    """Entrega o arquivo só a quem pode ver a OS (papel + oficina). O bucket não é público."""
    with session_scope() as db:
        os_ = os_visivel(db, g.user, os_id)
        anexo = db.get(AnexoOS, anexo_id) if os_ else None
        if not os_ or not anexo or anexo.os_id != os_.id:
            return negar_nao_encontrado(g.user, 'anexo', anexo_id)
        chave, mime = anexo.chave_objeto, anexo.tipo_mime
    try:
        resp = minio_client().get_object(bucket_anexos(), chave)
        try:
            dados = resp.read()
        finally:
            resp.close()
            resp.release_conn()
    except Exception as exc:
        _core().app.logger.error('Anexo %s ausente no MinIO: %s', chave, exc)
        return erro('Arquivo não encontrado no armazenamento.', 404)
    return Response(dados, content_type=mime, headers={'Cache-Control': 'private, max-age=300',
                                                       'X-Content-Type-Options': 'nosniff',
                                                       'Content-Disposition': 'inline'})


@bp.delete('/api/os/<int:os_id>/anexos/<int:anexo_id>')
@require_roles('dono')
def remover_anexo(os_id: int, anexo_id: int):
    with session_scope() as db:
        os_ = os_visivel(db, g.user, os_id)
        anexo = db.get(AnexoOS, anexo_id) if os_ else None
        if not os_ or not anexo or anexo.os_id != os_.id:
            return negar_nao_encontrado(g.user, 'anexo', anexo_id)
        chave = anexo.chave_objeto
        db.delete(anexo)
    try:
        minio_client().remove_object(bucket_anexos(), chave)
    except Exception as exc:
        _core().app.logger.warning('Não foi possível remover %s do MinIO: %s', chave, exc)
    log_negocio('os.editada', g.user, 'anexo', anexo_id, {'anexo_removido': True, 'os_id': os_id})
    return jsonify({'ok': True})
