from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura'
CORS(app)  # Permitir requisições de outros domínios

# Configuração do banco de dados com fallback para SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://munhoz_database_user:IqfoBG8IwciNcF3JXnAEDWEsI7f0sXSX@dpg-cuge219opnds739a38kg-a.oregon-postgres.render.com/munhoz_database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar o banco de dados
db = SQLAlchemy(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Modelo da OP
class OP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_op = db.Column(db.String(50), unique=True, nullable=False)
    torno = db.Column(db.Float, nullable=False)
    fresa = db.Column(db.Float, nullable=False)
    ajustagem = db.Column(db.Float, nullable=False)
    minutos_registrados_torno = db.Column(db.Float, nullable=False, default=0)
    minutos_registrados_fresa = db.Column(db.Float, nullable=False, default=0)
    minutos_registrados_ajustagem = db.Column(db.Float, nullable=False, default=0)

# Criar o banco de dados
with app.app_context():
    db.create_all()

    # Criar usuário admin se não existir
    if not Usuario.query.filter_by(username="admin").first():
        hashed_password = generate_password_hash("admin123", method='pbkdf2:sha256')
        novo_admin = Usuario(username="admin", password=hashed_password, is_admin=True)
        db.session.add(novo_admin)
        db.session.commit()

    # Criar usuário normal se não existir
    if not Usuario.query.filter_by(username="operador").first():
        hashed_password = generate_password_hash("senha123", method='pbkdf2:sha256')
        novo_usuario = Usuario(username="operador", password=hashed_password, is_admin=False)
        db.session.add(novo_usuario)
        db.session.commit()

# 👉 Rota para a Página Principal
@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', is_admin=session.get('is_admin', False))
    return redirect(url_for('login'))

# Rota de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('home'))
        return 'Usuário ou senha incorretos', 401
    return render_template('login.html')

# Rota de Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

# Rota para Registrar Usuários (Apenas para teste, depois pode ser removida)
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    novo_usuario = Usuario(username=data['username'], password=hashed_password, is_admin=data['is_admin'])
    db.session.add(novo_usuario)
    db.session.commit()
    return jsonify({"message": "Usuário cadastrado com sucesso!"})

@app.route('/get_user_role', methods=['GET'])
def get_user_role():
    if 'username' in session:
        return jsonify({"is_admin": session.get('is_admin', False)})
    return jsonify({"is_admin": False})

# 👉 1️⃣ Rota para Cadastrar OPs
@app.route('/op', methods=['POST'])
def cadastrar_op():
    if 'username' not in session or not session.get('is_admin', False):
        return jsonify({"message": "Acesso negado. Apenas administradores podem cadastrar OPs."}), 403

    data = request.json
    if not data or 'numero_op' not in data:
        return jsonify({"message": "Dados inválidos."}), 400

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
    try:
        inicio = datetime.strptime(data.get('inicio', ''), '%H:%M')
        fim = datetime.strptime(data.get('fim', ''), '%H:%M')
        minutos_trabalhados = int((fim - inicio).total_seconds() / 60)
    except ValueError:
        return jsonify({"message": "Formato de hora inválido. Use HH:MM"}), 400

    setor = data.get('setor')

    if setor == "torno":
        op.minutos_registrados_torno += minutos_trabalhados
    elif setor == "fresa":
        op.minutos_registrados_fresa += minutos_trabalhados
    elif setor == "ajustagem":
        op.minutos_registrados_ajustagem += minutos_trabalhados
    else:
        return jsonify({"message": "Setor inválido. Escolha entre torno, fresa ou ajustagem."}), 400

    db.session.commit()
    return jsonify({"message": f"Horas registradas para OP {numero_op}!"})

# 👉 Rota para Listar Todas as OPs
@app.route('/ops', methods=['GET'])
def listar_ops():
    ops = OP.query.all()
    op_list = []

    for op in ops:
        eficiencia_torno = (op.torno / op.minutos_registrados_torno) * 100 if op.minutos_registrados_torno > 0 else 0
        eficiencia_fresa = (op.fresa / op.minutos_registrados_fresa) * 100 if op.minutos_registrados_fresa > 0 else 0
        eficiencia_ajustagem = (op.ajustagem / op.minutos_registrados_ajustagem) * 100 if op.minutos_registrados_ajustagem > 0 else 0

        op_list.append({
            "numero_op": op.numero_op,
            "torno": op.torno,
            "fresa": op.fresa,
            "ajustagem": op.ajustagem,
            "minutos_registrados_torno": op.minutos_registrados_torno,
            "minutos_registrados_fresa": op.minutos_registrados_fresa,
            "minutos_registrados_ajustagem": op.minutos_registrados_ajustagem,
            "eficiencia_torno": round(eficiencia_torno, 2),
            "eficiencia_fresa": round(eficiencia_fresa, 2),
            "eficiencia_ajustagem": round(eficiencia_ajustagem, 2)
        })

    return jsonify(op_list)

@app.route('/op/<numero_op>', methods=['DELETE'])
def deletar_op(numero_op):
    op = OP.query.filter_by(numero_op=numero_op).first()
    if not op:
        return jsonify({"message": "OP não encontrada"}), 404

    db.session.delete(op)
    db.session.commit()
    return jsonify({"message": f"OP {numero_op} removida com sucesso!"})


if __name__ == '__main__':
    app.run(debug=True)
