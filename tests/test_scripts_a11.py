"""T11.10: os scripts de aceite e de evidência da A11 existem, compilam e mantêm as travas de segurança."""
from __future__ import annotations

import py_compile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENARIO = ROOT / 'scripts' / 'cenarios' / 'ativ11.py'
CHECKOUT = ROOT / 'scripts' / 'evidencias' / 'checkout.py'


def test_scripts_compilam(tmp_path):
    for arq in (CENARIO, CHECKOUT):
        py_compile.compile(str(arq), cfile=str(tmp_path / (arq.name + 'c')), doraise=True)


def test_checkout_aborta_se_a_stripe_nao_estiver_em_modo_de_teste():
    codigo = CHECKOUT.read_text()
    assert 'modo de teste' in codigo and 'ABORTADO' in codigo
    # a trava vem ANTES de digitar o cartão
    assert codigo.index('ABORTADO') < codigo.index('preencher_cartao(page)\n        tirar')
    assert '4242 4242 4242 4242' in codigo


def test_cenario_nao_embute_segredos_e_usa_contas_de_demonstracao():
    codigo = CENARIO.read_text()
    assert 'DOMINIO_CONTAS' in codigo
    assert not re.search(r'\b(sk|pk|rk)_(test|live)_[A-Za-z0-9]{8,}|\bwhsec_[A-Za-z0-9]{8,}', codigo)
