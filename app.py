from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Permitir requisições de outros domínios

# Configuração do PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://munhoz_database_user:IqfoBG8IwciNcF3JXnAEDWEsI7f0sXSX@dpg-cuge219opnds739a38kg-a/munhoz_database'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar o banco de dados
db = SQLAlchemy(app)

# Modelo da OP
class OP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_op = db.Column(db.String(50), unique=True, nullable=False)
    torno = db.Column(db.Float, nullable=False)
    fresa = db.Column(db.Float, nullable=False)
    ajustagem = db.Column(db.Float, nullable=False)

# Criar o banco de dados
with app.app_context():
    db.create_all()

# 👉 Rota para a Página Principal
@app.route('/')
def home():
    return render_template('index.html')

# 👉 1️⃣ Rota para Cadastrar OPs
@app.route('/op', methods=['POST'])
def cadastrar_op():
    data = request.json
    nova_op = OP(
        numero_op=data['numero_op'],
        torno=data['torno'],
        fresa=data['fresa'],
        ajustagem=data['ajustagem']
    )
    db.session.add(nova_op)
    db.session.commit()
    return jsonify({"message": "OP cadastrada com sucesso!"})

# 👉 2️⃣ Rota para Buscar uma OP Específica
@app.route('/op/<numero_op>', methods=['GET'])
def buscar_op(numero_op):
    op = OP.query.filter_by(numero_op=numero_op).first()
    if op:
        return jsonify({
            "numero_op": op.numero_op,
            "torno": op.torno,
            "fresa": op.fresa,
            "ajustagem": op.ajustagem
        })
    return jsonify({"message": "OP não encontrada"}), 404

# 👉 3️⃣ Rota para Registrar Horas em uma OP
@app.route('/op/<numero_op>', methods=['PUT'])
def registrar_horas_op(numero_op):
    op = OP.query.filter_by(numero_op=numero_op).first()
    if not op:
        return jsonify({"message": "OP não encontrada"}), 404

    data = request.json
    op.torno = max(0, op.torno - data.get('torno', 0))
    op.fresa = max(0, op.fresa - data.get('fresa', 0))
    op.ajustagem = max(0, op.ajustagem - data.get('ajustagem', 0))

    db.session.commit()
    return jsonify({"message": f"OP {numero_op} atualizada com sucesso!"})

# 👉 Rota para Listar Todas as OPs
@app.route('/ops', methods=['GET'])
def listar_ops():
    ops = OP.query.all()
    return jsonify([{
        "numero_op": op.numero_op,
        "torno": op.torno,
        "fresa": op.fresa,
        "ajustagem": op.ajustagem
    } for op in ops])

if __name__ == '__main__':
    app.run(debug=True)
