-- Banco do serviço de ESPAÇOS COMUNS (PostgreSQL)
-- Executado automaticamente pelo container apenas na primeira criação do volume.

CREATE TABLE IF NOT EXISTS espacos (
    id         SERIAL        PRIMARY KEY,
    nome       VARCHAR(100)  NOT NULL,
    capacidade INTEGER       NOT NULL CHECK (capacidade > 0),
    taxa       NUMERIC(10,2) NOT NULL DEFAULT 0
);

-- Dados iniciais (os mesmos que estavam na lista em memória)
INSERT INTO espacos (nome, capacidade, taxa)
SELECT 'Salão de Festas', 80, 150.00
WHERE NOT EXISTS (SELECT 1 FROM espacos);

INSERT INTO espacos (nome, capacidade, taxa)
SELECT 'Churrasqueira Coletiva', 20, 50.00
WHERE (SELECT COUNT(*) FROM espacos) = 1;
