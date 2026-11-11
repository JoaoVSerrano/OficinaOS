-- OficinaOS: dados fictícios de demonstração. Idempotente (INSERT IGNORE com ids fixos).
-- Não cria logins nem senhas: usuários vivem no auth-service e são criados pelo cadastro.
-- Aplicar depois de db/001_dominio.sql.

INSERT IGNORE INTO oficinas (id, nome, codigo_convite) VALUES
  (1, 'Auto Center Silva (demo)', 'DEMO-SILVA-01'),
  (2, 'Mecânica do Zé (demo)', 'DEMO-ZE-0002');

INSERT IGNORE INTO clientes (id, oficina_id, nome, telefone, email) VALUES
  (1, 1, 'Carlos Pereira', '14 99999-0001', 'carlos@exemplo.invalid'),
  (2, 1, 'Marina Souza',   '14 99999-0002', 'marina@exemplo.invalid'),
  (3, 2, 'Rafael Lima',    '14 99999-0003', 'rafael@exemplo.invalid');

INSERT IGNORE INTO veiculos (id, oficina_id, cliente_id, placa, marca, modelo, ano) VALUES
  (1, 1, 1, 'ABC1D23', 'Fiat',       'Uno',   2014),
  (2, 1, 1, 'DEF4G56', 'Volkswagen', 'Gol',   2018),
  (3, 1, 2, 'HIJ7K89', 'Chevrolet',  'Onix',  2021),
  (4, 2, 3, 'LMN0P12', 'Honda',      'Civic', 2016);

INSERT IGNORE INTO ordens_servico (id, oficina_id, veiculo_id, mecanico_id, criada_por, status, descricao, valor_total_centavos) VALUES
  (1, 1, 1, NULL, 0, 'aberta',             'Barulho na suspensão dianteira',  0),
  (2, 1, 2, NULL, 0, 'orcamento_aprovado', 'Troca de óleo e filtros',         25000),
  (3, 1, 3, NULL, 0, 'em_servico',         'Revisão dos 20 mil km',           48000),
  (4, 1, 1, NULL, 0, 'entregue',           'Troca de pastilhas de freio',     32000),
  (5, 2, 4, NULL, 0, 'pronta',             'Alinhamento e balanceamento',     18000);

INSERT IGNORE INTO itens_os (id, os_id, tipo, descricao, quantidade, valor_unitario_centavos) VALUES
  (1, 2, 'peca',    'Óleo 5W30 (litro)', 4, 4500),
  (2, 2, 'peca',    'Filtro de óleo',    1, 3500),
  (3, 2, 'servico', 'Mão de obra',       1, 3500),
  (4, 3, 'servico', 'Revisão completa',  1, 48000),
  (5, 4, 'peca',    'Jogo de pastilhas', 1, 22000),
  (6, 4, 'servico', 'Mão de obra',       1, 10000),
  (7, 5, 'servico', 'Alinhamento',       1, 9000),
  (8, 5, 'servico', 'Balanceamento',     1, 9000);
