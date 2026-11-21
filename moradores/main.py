import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

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