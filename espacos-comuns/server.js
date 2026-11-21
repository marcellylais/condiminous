const express = require('express');
const app = express();
const PORT = 8001; // Usamos a porta 8001 para não conflitar com a de moradores (8000)

app.use(express.json());

// "Banco de dados" temporário em memória para espaços comuns
let db_espacos = [
    { id: 1, nome: "Salão de Festas", capacidade: 80, taxa: 150.00 },
    { id: 2, nome: "Churrasqueira Coletiva", capacidade: 20, taxa: 50.00 }
];

// 1. READ (Listar todos os espaços)
app.get('/espacos', (req, res) => {
    res.json(db_espacos);
});

// 1.1 READ (Listar espaço por ID)
app.get('/espacos/:id', (req, res) => {
    const idEspaco = parseInt(req.params.id);
    const espaco = db_espacos.find(e => e.id === idEspaco);

    if (!espaco) {
        return res.status(404).json({ erro: "Espaço comum não encontrado." });
    }

    res.json(espaco);
});

// 2. CREATE (Cadastrar novo espaço)
app.post('/espacos', (req, res) => {
    const { id, nome, capacidade, taxa } = req.body;

    if (!id || !nome || !capacidade) {
        return res.status(400).json({ erro: "Dados incompletos. Informe id, nome e capacidade." });
    }

    // Verifica se já existe
    const existe = db_espacos.find(e => e.id === id);
    if (existe) {
        return res.status(400).json({ erro: "Espaço comum com esse ID já existe." });
    }

    const novoEspaço = { id, nome, capacidade, taxa: taxa || 0.0 };
    db_espacos.push(novoEspaço);
    
    res.status(201).json({ mensagem: "Espaço comum cadastrado com sucesso!", espaco: novoEspaço });
});

// 3. DELETE (Excluir espaço por ID)
app.delete('/espacos/:id', (req, res) => {
    const idEspaco = parseInt(req.params.id);
    const index = db_espacos.findIndex(e => e.id === idEspaco);

    if (index === -1) {
        return res.status(404).json({ erro: "Espaço comum não encontrado." });
    }

    db_espacos.splice(index, 1);
    res.json({ mensagem: "Espaço comum removido com sucesso!" });
});

// 4. UPDATE (Atualizar todos os campos de um espaço por ID)
app.put('/espacos/:id', (req, res) => {
    const idEspaco = parseInt(req.params.id);
    const { nome, capacidade, taxa } = req.body;

    const index = db_espacos.findIndex(e => e.id === idEspaco);
    if (index === -1) {
        return res.status(404).json({ erro: "Espaço comum não encontrado." });
    }

    db_espacos[index] = { ...db_espacos[index], nome, capacidade, taxa };
    res.json({ mensagem: "Espaço comum atualizado com sucesso!", espaco: db_espacos[index] });
});

app.listen(PORT, () => {
    console.log(`Servidor de Espaços Comuns rodando na porta ${PORT}`);
});