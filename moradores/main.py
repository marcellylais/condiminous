from flask import Flask, jsonify, request

app = Flask(__name__)

# "Banco de dados" temporário em memória
db_moradores = [
    {"id": 1, "nome": "Ana Souza", "bloco": "A", "apto": "102"},
    {"id": 2, "nome": "Carlos Silva", "bloco": "B", "apto": "204"}
]

# 1. READ (Listar todos)
@app.route("/moradores", methods=["GET"])
def listar_moradores():
    return jsonify(db_moradores)

# 1.1 READ (Listar morador por ID)
@app.route("/moradores/<int:morador_id>", methods=["GET"])
def obter_morador(morador_id):
    morador = next((m for m in db_moradores if m["id"] == morador_id), None)
    if not morador:
        return jsonify({"erro": "Morador não encontrado."}), 404
    return jsonify(morador)

# 2. CREATE (Adicionar novo morador)
@app.route("/moradores", methods=["POST"])
def criar_morador():
    dados = request.get_json()
    
    # Validação simples
    if not dados or "id" not in dados or "nome" not in dados:
        return jsonify({"erro": "Dados incompletos"}), 400
        
    # Verifica se o ID já existe
    for m in db_moradores:
        if m["id"] == dados["id"]:
            return jsonify({"erro": "Morador com esse ID já existe."}), 400
            
    db_moradores.append(dados)
    return jsonify({"mensagem": "Morador cadastrado com sucesso!", "morador": dados}), 201

# 3. DELETE (Excluir morador por ID)
@app.route("/moradores/<int:morador_id>", methods=["DELETE"])
def deletar_morador(morador_id):
    for index, m in enumerate(db_moradores):
        if m["id"] == morador_id:
            db_moradores.pop(index)
            return jsonify({"mensagem": "Morador removido com sucesso!"})
            
    return jsonify({"erro": "Morador não encontrado."}), 404

# 4. UPDATE (Atualizar morador por ID)
@app.route("/moradores/<int:morador_id>", methods=["PUT"])
def atualizar_morador(morador_id):
    dados = request.get_json()
    morador = next((m for m in db_moradores if m["id"] == morador_id), None)
    
    if not morador:
        return jsonify({"erro": "Morador não encontrado."}), 404
    
    # Atualiza os campos fornecidos
    morador.update(dados)
    return jsonify({"mensagem": "Morador atualizado com sucesso!", "morador": morador})

if __name__ == "__main__":
    app.run(debug=True, port=8000)