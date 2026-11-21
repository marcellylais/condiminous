const express = require("express");
const { Pool } = require("pg");
const client = require("prom-client");

const {
    publicarEspacoCriado,
    fecharRabbitMQ
} = require("./rabbitmq");

const app = express();
const PORT = Number(process.env.PORT || 8001);

app.use(express.json());
app.use((req, res, next) => {
    // A coleta do Prometheus não será contabilizada como tráfego da aplicação.
    if (req.path === "/metrics") {
        return next();
    }

    const inicio = process.hrtime.bigint();

    res.on("finish", () => {
        const fim = process.hrtime.bigint();
        const duracao = Number(fim - inicio) / 1_000_000_000;

        const rota = req.route
            ? `${req.baseUrl}${req.route.path}`
            : "rota_inexistente";

        const labels = {
            method: req.method,
            route: rota,
            status: String(res.statusCode),
            service: "espacos-service"
        };

        requisicoesHttp.inc(labels);
        duracaoRequisicoes.observe(labels, duracao);
    });

    next();
});

const pool = new Pool({
    host: process.env.ESPACOS_DB_HOST,
    port: Number(process.env.ESPACOS_DB_PORT || 5432),
    database: process.env.ESPACOS_DB_NAME,
    user: process.env.ESPACOS_DB_USER,
    password: process.env.ESPACOS_DB_PASSWORD
});

// Coleta métricas padrão do processo Node.js, como memória e CPU.
client.collectDefaultMetrics({
    prefix: "espacos_"
});

const requisicoesHttp = new client.Counter({
    name: "http_requests_total",
    help: "Total de requisições HTTP recebidas",
    labelNames: ["method", "route", "status", "service"]
});

const duracaoRequisicoes = new client.Histogram({
    name: "http_request_duration_seconds",
    help: "Duração das requisições HTTP em segundos",
    labelNames: ["method", "route", "status", "service"],
    buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5]
});

function validarEspaco(dados) {
    const nome = typeof dados.nome === "string"
        ? dados.nome.trim()
        : "";

    const capacidade = Number(dados.capacidade);
    const taxa = dados.taxa === undefined
        ? 0
        : Number(dados.taxa);

    if (!nome) {
        return { erro: "O nome é obrigatório." };
    }

    if (!Number.isInteger(capacidade) || capacidade <= 0) {
        return {
            erro: "A capacidade deve ser um número inteiro maior que zero."
        };
    }

    if (!Number.isFinite(taxa) || taxa < 0) {
        return {
            erro: "A taxa deve ser um número maior ou igual a zero."
        };
    }

    return {
        dados: {
            nome,
            capacidade,
            taxa
        }
    };
}

app.get("/metrics", async (req, res) => {
    try {
        res.set("Content-Type", client.register.contentType);
        return res.end(await client.register.metrics());
    } catch (erro) {
        console.error("Erro ao gerar métricas:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível gerar as métricas."
        });
    }
});

// Verifica a saúde do serviço e a conexão com o banco.
app.get("/health", async (req, res) => {
    try {
        await pool.query("SELECT 1");

        return res.status(200).json({
            status: "ok",
            service: "espacos-service",
            database: "connected"
        });
    } catch (erro) {
        console.error("Falha no healthcheck:", erro.message);

        return res.status(503).json({
            status: "error",
            service: "espacos-service",
            database: "disconnected"
        });
    }
});

// Lista todos os espaços.
app.get("/espacos", async (req, res) => {
    try {
        const resultado = await pool.query(`
            SELECT
                id,
                nome,
                capacidade,
                taxa::double precision AS taxa
            FROM espacos
            ORDER BY id
        `);

        return res.status(200).json(resultado.rows);
    } catch (erro) {
        console.error("Erro ao listar espaços:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível listar os espaços."
        });
    }
});

// Busca um espaço pelo ID.
app.get("/espacos/:id", async (req, res) => {
    const id = Number(req.params.id);

    if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({
            erro: "ID inválido."
        });
    }

    try {
        const resultado = await pool.query(
            `SELECT
                id,
                nome,
                capacidade,
                taxa::double precision AS taxa
             FROM espacos
             WHERE id = $1`,
            [id]
        );

        if (resultado.rowCount === 0) {
            return res.status(404).json({
                erro: "Espaço comum não encontrado."
            });
        }

        return res.status(200).json(resultado.rows[0]);
    } catch (erro) {
        console.error("Erro ao buscar espaço:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível buscar o espaço."
        });
    }
});

// Cadastra um espaço.
app.post("/espacos", async (req, res) => {
    const validacao = validarEspaco(req.body || {});

    if (validacao.erro) {
        return res.status(400).json({
            erro: validacao.erro
        });
    }

    const { nome, capacidade, taxa } = validacao.dados;

    try {
        const resultado = await pool.query(
            `INSERT INTO espacos (nome, capacidade, taxa)
             VALUES ($1, $2, $3)
             RETURNING
                id,
                nome,
                capacidade,
                taxa::double precision AS taxa`,
            [nome, capacidade, taxa]
        );

        const espacoCriado = resultado.rows[0];

        const eventoPublicado = await publicarEspacoCriado(
            espacoCriado
        );

        return res.status(201).json({
            mensagem: "Espaço comum cadastrado com sucesso!",
            espaco: espacoCriado,
            evento_publicado: eventoPublicado
        });

    } catch (erro) {
        console.error("Erro ao cadastrar espaço:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível cadastrar o espaço."
        });
    }
});

// Atualiza todos os campos de um espaço.
app.put("/espacos/:id", async (req, res) => {
    const id = Number(req.params.id);

    if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({
            erro: "ID inválido."
        });
    }

    const validacao = validarEspaco(req.body || {});

    if (validacao.erro) {
        return res.status(400).json({
            erro: validacao.erro
        });
    }

    const { nome, capacidade, taxa } = validacao.dados;

    try {
        const resultado = await pool.query(
            `UPDATE espacos
             SET nome = $1,
                 capacidade = $2,
                 taxa = $3
             WHERE id = $4
             RETURNING
                id,
                nome,
                capacidade,
                taxa::double precision AS taxa`,
            [nome, capacidade, taxa, id]
        );

        if (resultado.rowCount === 0) {
            return res.status(404).json({
                erro: "Espaço comum não encontrado."
            });
        }

        return res.status(200).json({
            mensagem: "Espaço comum atualizado com sucesso!",
            espaco: resultado.rows[0]
        });
    } catch (erro) {
        console.error("Erro ao atualizar espaço:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível atualizar o espaço."
        });
    }
});

// Exclui um espaço.
app.delete("/espacos/:id", async (req, res) => {
    const id = Number(req.params.id);

    if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({
            erro: "ID inválido."
        });
    }

    try {
        const resultado = await pool.query(
            `DELETE FROM espacos
             WHERE id = $1
             RETURNING id`,
            [id]
        );

        if (resultado.rowCount === 0) {
            return res.status(404).json({
                erro: "Espaço comum não encontrado."
            });
        }

        return res.status(200).json({
            mensagem: "Espaço comum removido com sucesso!"
        });
    } catch (erro) {
        console.error("Erro ao remover espaço:", erro.message);

        return res.status(500).json({
            erro: "Não foi possível remover o espaço."
        });
    }
});

const servidor = app.listen(PORT, "0.0.0.0", () => {
    console.log(`Servidor de Espaços Comuns rodando na porta ${PORT}`);
});

async function encerrar() {
    console.log("Encerrando o serviço de espaços...");

    servidor.close(async () => {
        await fecharRabbitMQ();
        await pool.end();
        process.exit(0);
    });
}

process.on("SIGTERM", encerrar);
process.on("SIGINT", encerrar);