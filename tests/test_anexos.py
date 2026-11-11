"""Anexos da OS no MinIO: validação por conteúdo, escopo, limite do Free e bucket privado."""
from __future__ import annotations

import io

import pytest

from backend import ordens
from tests.test_ordens import Cenario

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 64
WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'\x00' * 32


class FakeMinio:
    def __init__(self):
        self.buckets: set[str] = set()
        self.objetos: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.politicas: list = []

    def bucket_exists(self, b):
        return b in self.buckets

    def make_bucket(self, b):
        self.buckets.add(b)

    def set_bucket_policy(self, b, p):
        self.politicas.append((b, p))

    def put_object(self, b, k, data, length, content_type=None):
        self.objetos[(b, k)] = (data.read(), content_type)

    def get_object(self, b, k):
        if (b, k) not in self.objetos:
            raise KeyError(k)
        dados = self.objetos[(b, k)][0]
        return type('R', (), {'read': lambda s: dados, 'close': lambda s: None, 'release_conn': lambda s: None})()

    def remove_object(self, b, k):
        self.objetos.pop((b, k), None)


@pytest.fixture
def c(gw, monkeypatch):
    cen = Cenario(gw)
    cen.minio = FakeMinio()
    monkeypatch.setattr(ordens, 'minio_client', lambda: cen.minio)
    monkeypatch.setattr(ordens, '_bucket_pronto', False)
    return cen


def enviar(c, os_id, uid, conteudo=PNG, nome='foto.png', campo='arquivo'):
    return c.gw.client.post(f'/api/os/{os_id}/anexos', headers={'X-Test-User': str(uid)},
                            data={campo: (io.BytesIO(conteudo), nome)}, content_type='multipart/form-data')


def test_upload_guarda_no_minio_com_chave_da_oficina_e_da_os(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    r = enviar(c, os_['id'], c.mec1, PNG)
    assert r.status_code == 201
    (bucket, chave), (dados, mime) = next(iter(c.minio.objetos.items()))
    assert chave.startswith(f'os/{c.of_a}/{os_["id"]}/') and chave.endswith('.png')
    assert mime == 'image/png' and dados == PNG
    assert 'chave_objeto' not in r.get_json()['anexo']            # a chave não vai para o cliente
    assert any(e['acao'] == 'anexo.enviado' and e['recurso'] == 'anexo' for e in c.gw.eventos)


@pytest.mark.parametrize('conteudo,ext', [(PNG, 'png'), (JPG, 'jpg'), (WEBP, 'webp')])
def test_aceita_png_jpeg_webp_pelo_conteudo(c, conteudo, ext):
    os_ = c.abrir()
    assert enviar(c, os_['id'], c.dono, conteudo, nome='qualquer.bin').status_code == 201
    assert next(iter(c.minio.objetos))[1].endswith('.' + ext)


def test_tipo_invalido_400_mesmo_com_extensao_de_imagem(c):
    os_ = c.abrir()
    assert enviar(c, os_['id'], c.dono, b'<?php echo 1; ?>', nome='foto.png').status_code == 400
    assert enviar(c, os_['id'], c.dono, b'GIF89a' + b'0' * 20, nome='a.gif').status_code == 400
    assert c.minio.objetos == {}


def test_tamanho_maximo_5mb_400(c):
    os_ = c.abrir()
    grande = PNG + b'0' * (5 * 1024 * 1024)
    assert enviar(c, os_['id'], c.dono, grande).status_code == 400
    assert enviar(c, os_['id'], c.dono, PNG + b'0' * (5 * 1024 * 1024 - len(PNG))).status_code == 201


def test_vazio_e_campo_ausente_400(c):
    os_ = c.abrir()
    assert enviar(c, os_['id'], c.dono, b'').status_code == 400
    assert enviar(c, os_['id'], c.dono, PNG, campo='outro').status_code == 400


def test_outra_oficina_404_no_envio_na_lista_e_na_leitura(c):
    os_ = c.abrir()
    anexo = enviar(c, os_['id'], c.dono).get_json()['anexo']
    h = {'headers': {'X-Test-User': str(c.dono_b)}}
    assert enviar(c, os_['id'], c.dono_b).status_code == 404
    assert c.gw.client.get(f'/api/os/{os_["id"]}/anexos', **h).status_code == 404
    assert c.gw.client.get(anexo['url'], **h).status_code == 404
    assert c.gw.client.delete(f'/api/os/{os_["id"]}/anexos/{anexo["id"]}', **h).status_code == 404
    assert len(c.minio.objetos) == 1


def test_mecanico_nao_atribuido_nao_envia_nem_le(c):
    os_ = c.abrir(mecanico_id=c.mec2)
    assert enviar(c, os_['id'], c.mec1).status_code == 404
    anexo = enviar(c, os_['id'], c.mec2).get_json()['anexo']
    assert c.gw.client.get(anexo['url'], headers={'X-Test-User': str(c.mec1)}).status_code == 404


def test_cliente_le_mas_nao_envia(c):
    os_ = c.abrir(veiculo=c.v_cli)
    anexo = enviar(c, os_['id'], c.dono).get_json()['anexo']
    assert enviar(c, os_['id'], c.cli).status_code == 403
    r = c.gw.client.get(anexo['url'], headers={'X-Test-User': str(c.cli)})
    assert r.status_code == 200 and r.data == PNG and r.headers['Content-Type'] == 'image/png'
    assert 'private' in r.headers['Cache-Control'] and r.headers['X-Content-Type-Options'] == 'nosniff'
    outra = c.abrir(veiculo=c.v_out)
    a2 = enviar(c, outra['id'], c.dono).get_json()['anexo']
    assert c.gw.client.get(a2['url'], headers={'X-Test-User': str(c.cli)}).status_code == 404


def test_anexo_de_outra_os_nao_e_acessivel_pela_url_de_uma_os_minha(c):
    a, b = c.abrir(), c.abrir()
    anexo_b = enviar(c, b['id'], c.dono).get_json()['anexo']
    assert c.gw.client.get(f'/api/os/{a["id"]}/anexos/{anexo_b["id"]}/arquivo',
                           headers={'X-Test-User': str(c.dono)}).status_code == 404


def test_free_permite_so_3_anexos_por_os(c):
    os_ = c.abrir()
    for _ in range(3):
        assert enviar(c, os_['id'], c.dono).status_code == 201
    r = enviar(c, os_['id'], c.dono)
    assert r.status_code == 402 and r.get_json()['limite'] == 3 and r.get_json()['codigo'] == 'limite_plano'
    assert len(c.minio.objetos) == 3
    outra = c.abrir()
    assert enviar(c, outra['id'], c.dono).status_code == 201     # o limite é por OS


def test_pro_nao_tem_limite_de_anexos(c, monkeypatch):
    from backend import planos
    monkeypatch.setattr(planos, 'plano_da_oficina', lambda _i: 'pro')
    os_ = c.abrir()
    for _ in range(5):
        assert enviar(c, os_['id'], c.dono).status_code == 201


def test_bucket_de_anexos_e_privado_e_separado_dos_avatares(c, monkeypatch):
    monkeypatch.setenv('MINIO_BUCKET_NAME', 'avatares')
    os_ = c.abrir()
    enviar(c, os_['id'], c.dono)
    assert c.minio.politicas == []                      # nenhuma política (logo, sem leitura pública)
    assert ordens.bucket_anexos() != 'avatares'
    assert all(b == ordens.bucket_anexos() for b, _ in c.minio.objetos)


def test_remover_anexo_so_dono_e_apaga_o_objeto(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    anexo = enviar(c, os_['id'], c.mec1).get_json()['anexo']
    url = f'/api/os/{os_["id"]}/anexos/{anexo["id"]}'
    assert c.gw.client.delete(url, headers={'X-Test-User': str(c.mec1)}).status_code == 403
    assert c.gw.client.delete(url, headers={'X-Test-User': str(c.dono)}).status_code == 200
    assert c.minio.objetos == {}


def test_minio_fora_do_ar_503_sem_registro_orfao(c, monkeypatch):
    def quebrado():
        raise RuntimeError('minio fora')
    monkeypatch.setattr(ordens, 'minio_client', quebrado)
    os_ = c.abrir()
    assert enviar(c, os_['id'], c.dono).status_code == 503
    assert c.gw.client.get(f'/api/os/{os_["id"]}/anexos', headers={'X-Test-User': str(c.dono)}).get_json()['anexos'] == []


def test_os_cancelada_nao_recebe_anexo(c):
    os_ = c.abrir()
    c.status(os_['id'], c.dono, 'cancelada')
    assert enviar(c, os_['id'], c.dono).status_code == 409
