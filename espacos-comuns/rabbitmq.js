const amqp = require("amqplib");
const { randomUUID } = require("crypto");

const EXCHANGE = "condiminous.events";
const FILA = "moradores.espacos";
const ROUTING_KEY = "espaco.criado";

let conexao = null;
let canal = null;

function criarUrl() {
    const host = process.env.RABBITMQ_HOST || "rabbitmq";
    const port = process.env.RABBITMQ_PORT || "5672";
    const user = encodeURIComponent(
        process.env.RABBITMQ_USER || "condiminous"
    );
    const password = encodeURIComponent(
        process.env.RABBITMQ_PASSWORD || "condiminous_pass"
    );

    return `amqp://${user}:${password}@${host}:${port}`;
}

function limparConexao() {
    canal = null;
    conexao = null;
}

async function obterCanal() {
    if (canal) {
        return canal;
    }

    conexao = await amqp.connect(criarUrl());

    conexao.on("error", (erro) => {
        console.error("Erro na conexão com RabbitMQ:", erro.message);
    });

    conexao.on("close", () => {
        console.warn("Conexão com RabbitMQ encerrada.");
        limparConexao();
    });

    canal = await conexao.createChannel();

    await canal.assertExchange(EXCHANGE, "topic", {
        durable: true
    });

    await canal.assertQueue(FILA, {
        durable: true
    });

    await canal.bindQueue(FILA, EXCHANGE, ROUTING_KEY);

    console.log("Conexão com RabbitMQ estabelecida.");

    return canal;
}

async function publicarEspacoCriado(espaco) {
    const evento = {
        event_id: randomUUID(),
        event_type: ROUTING_KEY,
        occurred_at: new Date().toISOString(),
        data: espaco
    };

    try {
        const canalAtual = await obterCanal();

        const publicado = canalAtual.publish(
            EXCHANGE,
            ROUTING_KEY,
            Buffer.from(JSON.stringify(evento)),
            {
                persistent: true,
                contentType: "application/json",
                messageId: evento.event_id,
                timestamp: Date.now()
            }
        );

        if (!publicado) {
            console.warn(
                "RabbitMQ aplicou controle de fluxo ao publicar o evento."
            );
        }

        console.log(
            `Evento ${ROUTING_KEY} publicado para o espaço ${espaco.id}.`
        );

        return true;
    } catch (erro) {
        console.error(
            `Não foi possível publicar ${ROUTING_KEY}:`,
            erro.message
        );

        limparConexao();
        return false;
    }
}

async function fecharRabbitMQ() {
    try {
        if (canal) {
            await canal.close();
        }

        if (conexao) {
            await conexao.close();
        }
    } catch (erro) {
        console.error(
            "Erro ao encerrar RabbitMQ:",
            erro.message
        );
    } finally {
        limparConexao();
    }
}

module.exports = {
    publicarEspacoCriado,
    fecharRabbitMQ
};