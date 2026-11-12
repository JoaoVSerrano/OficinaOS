-- OficinaOS: esquema do domínio (gerado por scripts/export_sql.sh; não edite à mão).
-- Equivale às revisões Alembic 0001_initial, 0002_dominio_oficina e 0003_oficina_v2 do gateway.
-- Atenção: remove as tabelas do domínio antigo (favoritos, comentarios), se existirem.
CREATE TABLE alembic_version_backend (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_backend_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

INSERT INTO alembic_version_backend (version_num) VALUES ('0001_initial');

-- Running upgrade 0001_initial -> 0002_dominio_oficina

DROP TABLE IF EXISTS comentarios;

DROP TABLE IF EXISTS favoritos;

CREATE TABLE oficinas (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    nome VARCHAR(120) NOT NULL, 
    codigo_convite VARCHAR(16) NOT NULL, 
    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    UNIQUE (codigo_convite)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE clientes (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    oficina_id INTEGER NOT NULL, 
    usuario_id INTEGER, 
    nome VARCHAR(120) NOT NULL, 
    telefone VARCHAR(20), 
    email VARCHAR(160), 
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(oficina_id) REFERENCES oficinas (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_clientes_oficina_id ON clientes (oficina_id);

CREATE INDEX ix_clientes_usuario_id ON clientes (usuario_id);

CREATE TABLE veiculos (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    oficina_id INTEGER NOT NULL, 
    cliente_id INTEGER NOT NULL, 
    placa VARCHAR(10) NOT NULL, 
    marca VARCHAR(60) NOT NULL, 
    modelo VARCHAR(60) NOT NULL, 
    ano INTEGER, 
    PRIMARY KEY (id), 
    CONSTRAINT uniq_oficina_placa UNIQUE (oficina_id, placa), 
    FOREIGN KEY(oficina_id) REFERENCES oficinas (id), 
    FOREIGN KEY(cliente_id) REFERENCES clientes (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_veiculos_oficina_id ON veiculos (oficina_id);

CREATE INDEX ix_veiculos_cliente_id ON veiculos (cliente_id);

CREATE TABLE ordens_servico (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    oficina_id INTEGER NOT NULL, 
    veiculo_id INTEGER NOT NULL, 
    mecanico_id INTEGER, 
    criada_por INTEGER NOT NULL, 
    status VARCHAR(24) NOT NULL DEFAULT 'aberta', 
    descricao TEXT NOT NULL, 
    valor_total_centavos BIGINT NOT NULL DEFAULT '0', 
    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    atualizada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    excluida_em TIMESTAMP NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(oficina_id) REFERENCES oficinas (id), 
    FOREIGN KEY(veiculo_id) REFERENCES veiculos (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_ordens_servico_veiculo_id ON ordens_servico (veiculo_id);

CREATE INDEX ix_ordens_servico_mecanico_id ON ordens_servico (mecanico_id);

CREATE INDEX idx_os_oficina_criada ON ordens_servico (oficina_id, criada_em);

CREATE TABLE itens_os (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    os_id INTEGER NOT NULL, 
    tipo VARCHAR(10) NOT NULL, 
    descricao VARCHAR(255) NOT NULL, 
    quantidade INTEGER NOT NULL DEFAULT '1', 
    valor_unitario_centavos BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(os_id) REFERENCES ordens_servico (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_itens_os_os_id ON itens_os (os_id);

CREATE TABLE anexos_os (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    os_id INTEGER NOT NULL, 
    chave_objeto VARCHAR(255) NOT NULL, 
    nome_original VARCHAR(255) NOT NULL, 
    tipo_mime VARCHAR(60) NOT NULL, 
    tamanho_bytes INTEGER NOT NULL, 
    enviado_por INTEGER NOT NULL, 
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(os_id) REFERENCES ordens_servico (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_anexos_os_os_id ON anexos_os (os_id);

UPDATE alembic_version_backend SET version_num='0002_dominio_oficina' WHERE alembic_version_backend.version_num = '0001_initial';

-- Running upgrade 0002_dominio_oficina -> 0003_oficina_v2

ALTER TABLE ordens_servico ADD COLUMN km_entrada INTEGER;

ALTER TABLE ordens_servico ADD COLUMN entregue_em TIMESTAMP NULL;

CREATE TABLE orcamentos (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    os_id INTEGER NOT NULL, 
    versao INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL DEFAULT 'enviado', 
    itens_json TEXT NOT NULL, 
    subtotal_centavos BIGINT NOT NULL, 
    desconto_centavos BIGINT NOT NULL DEFAULT '0', 
    total_centavos BIGINT NOT NULL, 
    validade_ate DATE NOT NULL, 
    observacoes_cliente TEXT, 
    token_hash VARCHAR(64) NOT NULL, 
    enviado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    decidido_em TIMESTAMP NULL, 
    decidido_por_usuario_id INTEGER, 
    decidido_via VARCHAR(8), 
    motivo_recusa VARCHAR(500), 
    criado_por INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uniq_orcamento_versao UNIQUE (os_id, versao), 
    FOREIGN KEY(os_id) REFERENCES ordens_servico (id), 
    UNIQUE (token_hash)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_orcamentos_os_id ON orcamentos (os_id);

CREATE TABLE notas_os (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    os_id INTEGER NOT NULL, 
    autor_id INTEGER NOT NULL, 
    texto TEXT NOT NULL, 
    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(os_id) REFERENCES ordens_servico (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_notas_os_os_id ON notas_os (os_id);

CREATE TABLE catalogo_itens (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    oficina_id INTEGER NOT NULL, 
    tipo VARCHAR(10) NOT NULL, 
    descricao VARCHAR(255) NOT NULL, 
    valor_centavos BIGINT NOT NULL, 
    ativo BOOL NOT NULL DEFAULT 1, 
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(oficina_id) REFERENCES oficinas (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_catalogo_itens_oficina_id ON catalogo_itens (oficina_id);

CREATE TABLE pagamentos_os (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    os_id INTEGER NOT NULL, 
    valor_centavos BIGINT NOT NULL, 
    forma VARCHAR(16) NOT NULL, 
    pago_em DATE NOT NULL, 
    registrado_por INTEGER NOT NULL, 
    observacao VARCHAR(255), 
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(os_id) REFERENCES ordens_servico (id)
)ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_pagamentos_os_os_id ON pagamentos_os (os_id);

UPDATE alembic_version_backend SET version_num='0003_oficina_v2' WHERE alembic_version_backend.version_num = '0002_dominio_oficina';

