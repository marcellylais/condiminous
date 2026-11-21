-- Banco do serviço de MORADORES (PostgreSQL)
-- Executado automaticamente pelo container apenas na primeira criação do volume.

CREATE TABLE IF NOT EXISTS moradores (
    id    SERIAL       PRIMARY KEY,
    nome  VARCHAR(100) NOT NULL,
    bloco VARCHAR(10)  NOT NULL,
    apto  VARCHAR(10)  NOT NULL
);

-- Dados iniciais (os mesmos que estavam na lista em memória)
INSERT INTO moradores (nome, bloco, apto)
SELECT 'Ana Souza', 'A', '102'
WHERE NOT EXISTS (SELECT 1 FROM moradores);

INSERT INTO moradores (nome, bloco, apto)
SELECT 'Carlos Silva', 'B', '204'
WHERE (SELECT COUNT(*) FROM moradores) = 1;
