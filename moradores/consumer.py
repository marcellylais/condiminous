import json
import os
import time
from urllib.parse import quote

import pika


EXCHANGE = "condiminous.events"
FILA = "moradores.espacos"
ROUTING_KEY = "espaco.criado"


def criar_url():
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = os.getenv("RABBITMQ_PORT", "5672")
    usuario = quote(os.getenv("RABBITMQ_USER", "condiminous"), safe="")
    senha = quote(os.getenv("RABBITMQ_PASSWORD", "condiminous_pass"), safe="")

    return f"amqp://{usuario}:{senha}@{host}:{port}/"


def processar_evento(canal, metodo, propriedades, corpo):
    try:
        evento = json.loads(corpo.decode("utf-8"))

        if evento.get("event_type") != ROUTING_KEY:
            print(
                f"Evento ignorado: {evento.get('event_type')}",
                flush=True,
            )
        else:
            espaco = evento.get("data", {})

            print(
                "Evento espaco.criado consumido: "
                f"event_id={evento.get('event_id')}, "
                f"espaco_id={espaco.get('id')}, "
                f"nome={espaco.get('nome')}",
                flush=True,
            )

        canal.basic_ack(delivery_tag=metodo.delivery_tag)

    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        print(f"Mensagem inválida descartada: {erro}", flush=True)

        canal.basic_nack(
            delivery_tag=metodo.delivery_tag,
            requeue=False,
        )

    except Exception as erro:
        print(f"Erro ao processar evento: {erro}", flush=True)

        canal.basic_nack(
            delivery_tag=metodo.delivery_tag,
            requeue=True,
        )


def consumir():
    while True:
        conexao = None

        try:
            parametros = pika.URLParameters(criar_url())
            parametros.heartbeat = 30
            parametros.blocked_connection_timeout = 30

            conexao = pika.BlockingConnection(parametros)
            canal = conexao.channel()

            canal.exchange_declare(
                exchange=EXCHANGE,
                exchange_type="topic",
                durable=True,
            )

            canal.queue_declare(
                queue=FILA,
                durable=True,
            )

            canal.queue_bind(
                queue=FILA,
                exchange=EXCHANGE,
                routing_key=ROUTING_KEY,
            )

            canal.basic_qos(prefetch_count=1)

            canal.basic_consume(
                queue=FILA,
                on_message_callback=processar_evento,
                auto_ack=False,
            )

            print(
                f"Aguardando eventos '{ROUTING_KEY}' na fila '{FILA}'.",
                flush=True,
            )

            canal.start_consuming()

        except KeyboardInterrupt:
            print("Consumidor encerrado.", flush=True)
            break

        except Exception as erro:
            print(
                f"RabbitMQ indisponível: {erro}. "
                "Nova tentativa em 5 segundos.",
                flush=True,
            )
            time.sleep(5)

        finally:
            if conexao is not None and conexao.is_open:
                conexao.close()


if __name__ == "__main__":
    consumir()