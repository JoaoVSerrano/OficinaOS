"""Utilitários dos cenários de aceite (requests + PASS/FAIL por passo)."""
from __future__ import annotations

import re
import struct
import sys
import time
import zlib

import requests

DOMINIO_CONTAS = '@oficinaos.example'     # contas de demonstração: nunca o e-mail real de ninguém
SENHA_DEMO = 'demo-123456'


class Relatorio:
    def __init__(self) -> None:
        self.falhas = 0
        self.total = 0

    def passo(self, nome: str, condicao: bool, detalhe: str = '') -> bool:
        self.total += 1
        if not condicao:
            self.falhas += 1
        print(f"[{'PASS' if condicao else 'FAIL'}] {nome}" + (f'  ({detalhe})' if detalhe and not condicao else ''))
        return condicao

    def pular(self, nome: str, motivo: str) -> None:
        print(f'[SKIP] {nome}  ({motivo})')

    def concluir(self) -> int:
        print(f'\n{self.total - self.falhas}/{self.total} passos OK' + ('' if not self.falhas else f', {self.falhas} FALHA(S)'))
        return 1 if self.falhas else 0


def sufixo() -> str:
    return str(int(time.time()))


def sessao(base: str) -> requests.Session:
    s = requests.Session()
    s.base = base.rstrip('/')          # type: ignore[attr-defined]
    s.headers['User-Agent'] = 'oficinaos-cenario/1.0'
    return s


def chamar(s: requests.Session, metodo: str, caminho: str, **kw) -> requests.Response:
    return s.request(metodo, s.base + caminho, timeout=30, **kw)   # type: ignore[attr-defined]


def png_minimo(cor: tuple[int, int, int] = (217, 72, 15), lado: int = 32) -> bytes:
    """PNG válido gerado na hora (sem Pillow): usado como 'foto' de teste."""
    def pedaco(tipo: bytes, dados: bytes) -> bytes:
        corpo = tipo + dados
        return struct.pack('>I', len(dados)) + corpo + struct.pack('>I', zlib.crc32(corpo) & 0xFFFFFFFF)
    linha = b'\x00' + bytes(cor) * lado
    return (b'\x89PNG\r\n\x1a\n' + pedaco(b'IHDR', struct.pack('>IIBBBBB', lado, lado, 8, 2, 0, 0, 0))
            + pedaco(b'IDAT', zlib.compress(linha * lado)) + pedaco(b'IEND', b''))


def baixar_bundles(s: requests.Session) -> tuple[str, str]:
    """Devolve (index.html, texto de todos os .js referenciados e importados dinamicamente)."""
    index = chamar(s, 'GET', '/').content.decode('utf-8', 'replace')
    vistos: set[str] = set()
    fila = re.findall(r'(?:src|href)="(?:/)?([^"]+\.js)"', index)
    texto = ''
    while fila:
        arq = fila.pop()
        if arq in vistos:
            continue
        vistos.add(arq)
        r = chamar(s, 'GET', '/' + arq)
        if r.status_code != 200:
            continue
        corpo = r.content.decode('utf-8', 'replace')   # o Flask não informa o charset do .js
        texto += corpo
        fila += [m for m in re.findall(r'["\'`]\./(chunk-[A-Z0-9]+\.js)["\'`]', corpo) if m not in vistos]
    # o build escreve acentos como \xE7 / \u00e7 dentro dos literais; desfaz para poder procurar texto da tela
    texto = re.sub(r'\\x([0-9A-Fa-f]{2})|\\u([0-9A-Fa-f]{4})',
                   lambda m: chr(int(m.group(1) or m.group(2), 16)), texto)
    return index, texto


def main_seguro(fn) -> None:
    try:
        sys.exit(fn())
    except requests.RequestException as exc:
        print(f'[ERRO] não foi possível falar com o sistema: {exc}')
        sys.exit(2)
