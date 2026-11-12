from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


# ---------------------------------------------------------------------------
# Domínio da oficina (Atividade 10). Tenant = oficina: toda tabela tem oficina_id
# (direto ou via os_id). usuario_id/mecanico_id referenciam usuarios.id do
# auth-service, sem FK entre serviços.
# ---------------------------------------------------------------------------

STATUS_OS = ('aberta', 'orcamento_aprovado', 'em_servico', 'pronta', 'entregue', 'cancelada')


class Oficina(Base):
    __tablename__ = 'oficinas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    codigo_convite: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    criada_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class Cliente(Base):
    __tablename__ = 'clientes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oficina_id: Mapped[int] = mapped_column(ForeignKey('oficinas.id'), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class Veiculo(Base):
    __tablename__ = 'veiculos'
    __table_args__ = (UniqueConstraint('oficina_id', 'placa', name='uniq_oficina_placa'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oficina_id: Mapped[int] = mapped_column(ForeignKey('oficinas.id'), nullable=False, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey('clientes.id'), nullable=False, index=True)
    placa: Mapped[str] = mapped_column(String(10), nullable=False)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OrdemServico(Base):
    __tablename__ = 'ordens_servico'
    __table_args__ = (Index('idx_os_oficina_criada', 'oficina_id', 'criada_em'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oficina_id: Mapped[int] = mapped_column(ForeignKey('oficinas.id'), nullable=False)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey('veiculos.id'), nullable=False, index=True)
    mecanico_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    criada_por: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default='aberta')
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor_total_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default='0')
    criada_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    atualizada_em: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP')
    )
    excluida_em: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    km_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entregue_em: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)


class ItemOS(Base):
    __tablename__ = 'itens_os'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_id: Mapped[int] = mapped_column(ForeignKey('ordens_servico.id'), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # servico | peca
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, server_default='1')
    valor_unitario_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AnexoOS(Base):
    __tablename__ = 'anexos_os'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_id: Mapped[int] = mapped_column(ForeignKey('ordens_servico.id'), nullable=False, index=True)
    chave_objeto: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(60), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    enviado_por: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


# ---------------------------------------------------------------------------
# OficinaOS v2: orçamento com versões, anotações internas, catálogo e pagamentos.
# Filhos da OS chegam à oficina por os_id (ver backend/escopo.py).
# ---------------------------------------------------------------------------

STATUS_ORCAMENTO = ('enviado', 'aprovado', 'recusado', 'substituido')   # "expirado" é calculado pela validade
FORMAS_PAGAMENTO = ('dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'boleto', 'outro')


class Orcamento(Base):
    """Versão enviada ao cliente: snapshot dos itens da OS no momento do envio."""
    __tablename__ = 'orcamentos'
    __table_args__ = (UniqueConstraint('os_id', 'versao', name='uniq_orcamento_versao'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_id: Mapped[int] = mapped_column(ForeignKey('ordens_servico.id'), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default='enviado')
    itens_json: Mapped[str] = mapped_column(Text, nullable=False)
    subtotal_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    desconto_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default='0')
    total_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validade_ate: Mapped[date] = mapped_column(Date, nullable=False)
    observacoes_cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    enviado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    decidido_em: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    decidido_por_usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decidido_via: Mapped[str | None] = mapped_column(String(8), nullable=True)   # app | link
    motivo_recusa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_por: Mapped[int] = mapped_column(Integer, nullable=False)


class NotaOS(Base):
    """Anotação interna da OS (dono e mecânico; o cliente nunca vê)."""
    __tablename__ = 'notas_os'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_id: Mapped[int] = mapped_column(ForeignKey('ordens_servico.id'), nullable=False, index=True)
    autor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    criada_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class CatalogoItem(Base):
    """Tabela de preços da oficina (serviços e peças com valor padrão)."""
    __tablename__ = 'catalogo_itens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oficina_id: Mapped[int] = mapped_column(ForeignKey('oficinas.id'), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # servico | peca
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('1'))
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class PagamentoOS(Base):
    """Pagamento recebido pela oficina numa OS (não é a assinatura do SaaS)."""
    __tablename__ = 'pagamentos_os'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    os_id: Mapped[int] = mapped_column(ForeignKey('ordens_servico.id'), nullable=False, index=True)
    valor_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False)
    forma: Mapped[str] = mapped_column(String(16), nullable=False)
    pago_em: Mapped[date] = mapped_column(Date, nullable=False)
    registrado_por: Mapped[int] = mapped_column(Integer, nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
