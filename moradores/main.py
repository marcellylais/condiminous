import os
import re
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# ---------------------------------------------------------------
# Configuração do banco (vem do ambiente; padrões = rodar local)
# ---------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("MORADORES_DB_HOST", "localhost"),
    "port": int(os.getenv("MORADORES_DB_PORT", "5433")),
    "dbname": os.getenv("MORADORES_DB_NAME", "moradores_db"),
    "user": os.getenv("MORADORES_DB_USER", "moradores_user"),
    "password": os.getenv("MORADORES_DB_PASSWORD", "moradores_pass"),
}


@contextmanager
def conectar():
    """Abre conexão, entrega um cursor, faz commit/rollback e SEMPRE fecha."""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    try:
        with conn:                      # commit se der certo, rollback se der erro
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()                    # o "with conn" do psycopg2 NÃO fecha a conexão


app = Flask(__name__)
app.json.ensure_ascii = False           # devolve "João" em vez de "João"


# ---------------------------------------------------------------
# Métricas (Prometheus) - mesmos nomes e rótulos do espacos-service
# ---------------------------------------------------------------
SERVICE_NAME = "moradores-service"
ROTULOS = ["method", "route", "status", "service"]

REQUISICOES = Counter(
    "http_requests_total",
    "Total de requisições HTTP recebidas",
    ROTULOS,
)
DURACAO = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos",
    ROTULOS,
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5],
)


def rota_atual():
    """Devolve o MOLDE da rota (/moradores/:id), nunca o caminho real (/moradores/57)."""
    if request.url_rule is None:
        return "rota_inexistente"
    return re.sub(r"<[^>]+>", ":id", request.url_rule.rule)


@app.before_request
def iniciar_cronometro():
    g.inicio = time.perf_counter()


@app.after_request
def registrar_metricas(response):
    if request.path != "/metrics" and hasattr(g, "inicio"):
        rotulos = {
            "method": request.method,
            "route": rota_atual(),
            "status": str(response.status_code),
            "service": SERVICE_NAME,
        }
        REQUISICOES.labels(**rotulos).inc()
        DURACAO.labels(**rotulos).observe(time.perf_counter() - g.inicio)
    return response


@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------
# Validação
# ---------------------------------------------------------------
CAMPOS_OBRIGATORIOS = ("nome", "bloco", "apto")


def validar(dados):
    """Retorna a mensagem de erro, ou None se estiver tudo certo."""
    if not isinstance(dados, dict):
        return "JSON ausente ou inválido"
    for campo in CAMPOS_OBRIGATORIOS:
        valor = dados.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            return f"O campo '{campo}' é obrigatório"
    return None


# ---------------------------------------------------------------
# Tratamento de erros do banco (sem expor detalhes internos)
# ---------------------------------------------------------------
@app.errorhandler(psycopg2.OperationalError)
def banco_indisponivel(e):
    return jsonify({"erro": "Banco de dados indisponível"}), 503


@app.errorhandler(psycopg2.DataError)
def dado_invalido(e):
    return jsonify({"erro": "Valor inválido ou muito longo"}), 400


@app.errorhandler(psycopg2.Error)
def erro_banco(e):
    return jsonify({"erro": "Erro interno"}), 500


# ---------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    try:
        with conectar() as cur:
            cur.execute("SELECT 1")
        return jsonify({
            "status": "ok",
            "service": "moradores-service",
            "database": "connected",
        }), 200
    except psycopg2.Error as e:
        app.logger.error("Falha no healthcheck: %s", e)
        return jsonify({
            "status": "error",
            "service": "moradores-service",
            "database": "disconnected",
        }), 503


# ---------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------
@app.route("/moradores", methods=["GET"])
def listar_moradores():
    with conectar() as cur:
        cur.execute("SELECT id, nome, bloco, apto FROM moradores ORDER BY id")
        moradores = cur.fetchall()
    return jsonify(moradores)


@app.route("/moradores/<int:morador_id>", methods=["GET"])
def obter_morador(morador_id):
    with conectar() as cur:
        cur.execute(
            "SELECT id, nome, bloco, apto FROM moradores WHERE id = %s",
            (morador_id,),
        )
        morador = cur.fetchone()
    if morador is None:
        return jsonify({"erro": "Morador não encontrado"}), 404
    return jsonify(morador)


@app.route("/moradores", methods=["POST"])
def criar_morador():
    dados = request.get_json(silent=True)
    erro = validar(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    with conectar() as cur:
        cur.execute(
            "INSERT INTO moradores (nome, bloco, apto) VALUES (%s, %s, %s) "
            "RETURNING id, nome, bloco, apto",
            (dados["nome"].strip(), dados["bloco"].strip(), dados["apto"].strip()),
        )
        morador = cur.fetchone()
    return jsonify(morador), 201


@app.route("/moradores/<int:morador_id>", methods=["PUT"])
def atualizar_morador(morador_id):
    dados = request.get_json(silent=True)
    erro = validar(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    with conectar() as cur:
        cur.execute(
            "UPDATE moradores SET nome = %s, bloco = %s, apto = %s WHERE id = %s "
            "RETURNING id, nome, bloco, apto",
            (dados["nome"].strip(), dados["bloco"].strip(), dados["apto"].strip(), morador_id),
        )
        morador = cur.fetchone()
    if morador is None:
        return jsonify({"erro": "Morador não encontrado"}), 404
    return jsonify(morador)


@app.route("/moradores/<int:morador_id>", methods=["DELETE"])
def deletar_morador(morador_id):
    with conectar() as cur:
        cur.execute("DELETE FROM moradores WHERE id = %s RETURNING id", (morador_id,))
        apagado = cur.fetchone()
    if apagado is None:
        return jsonify({"erro": "Morador não encontrado"}), 404
    return jsonify({"mensagem": "Morador removido com sucesso"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)