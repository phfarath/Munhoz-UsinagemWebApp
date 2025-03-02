from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from dotenv import load_dotenv

# Adicionando logs de depuração
print("Iniciando aplicação Flask...")

try:
    from supabase import create_client, Client
    print("Supabase importado com sucesso!")
except ModuleNotFoundError as e:
    print(f"Erro ao importar Supabase: {e}")


# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = Flask(__name__, template_folder="templates")
app.secret_key = 'sua_chave_secreta_super_segura'
CORS(app)

# Criar usuários iniciais se não existirem
def criar_usuarios(force_recreate=False):
    # Use explicit method specification
    hashed_password_admin = generate_password_hash("admin123", method="pbkdf2:sha256")
    hashed_password_operador = generate_password_hash("senha123", method="pbkdf2:sha256")

    # If force_recreate is True, delete existing users first
    if force_recreate:
        supabase.table("usuario").delete().eq("username", "admin").execute()
        supabase.table("usuario").delete().eq("username", "operador").execute()
        
    # Create admin user
    response = supabase.table("usuario").select("id").eq("username", "admin").execute()
    if not response.data or force_recreate:
        supabase.table("usuario").insert([{
            "username": "admin",
            "password": hashed_password_admin,
            "is_admin": True
        }]).execute()

    # Create operator user
    response = supabase.table("usuario").select("id").eq("username", "operador").execute()
    if not response.data or force_recreate:
        supabase.table("usuario").insert([{
            "username": "operador",
            "password": hashed_password_operador,
            "is_admin": False
        }]).execute()

# Force recreation of users when app starts
criar_usuarios(force_recreate=True)


# Criar usuários caso não existam
criar_usuarios()

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

        # Buscar usuário no banco
        response = supabase.table("usuario").select("username, password, is_admin").eq("username", username).execute()
        
        # Verifica se o usuário foi encontrado
        if not response.data:
            return jsonify({"message": "Usuário não encontrado"}), 401

        user = response.data[0]
        
        # Debug: Print the password hash to see its format
        print(f"Password hash for {username}: {user['password']}")
        
        # Se a senha estiver vazia ou em um formato inválido, retornar erro
        if not user["password"] or not isinstance(user["password"], str):
            return jsonify({"message": "Senha inválida ou corrompida (vazia ou tipo inválido)"}), 500
            
        # Check if the hash has the correct format (should contain method and salt)
        if ":" not in user["password"]:
            return jsonify({"message": "Formato de hash inválido"}), 500

        try:
            # Verifica a senha
            if check_password_hash(user["password"], password):
                session['username'] = user["username"]
                session['is_admin'] = user["is_admin"]
                return redirect(url_for('home'))
        except ValueError as e:
            return jsonify({"message": f"Erro ao verificar senha: {str(e)}"}), 500

        return jsonify({"message": "Usuário ou senha incorretos"}), 401
    return render_template('login.html')

# Rota de Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

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

    try:
        data = request.json
        print(f"Received data: {data}")
        
        if not data or 'numero_op' not in data:
            return jsonify({"message": "Dados inválidos. Número de OP é obrigatório."}), 400

        # Ensure numeric fields are integers
        op_data = {
            "numero_op": data.get("numero_op"),
            "torno": int(data.get("torno", 0)),
            "fresa": int(data.get("fresa", 0)),
            "ajustagem": int(data.get("ajustagem", 0)),
            "minutos_registrados_torno": 0,
            "minutos_registrados_fresa": 0,
            "minutos_registrados_ajustagem": 0
        }
        
        print(f"Prepared data for insertion: {op_data}")
        
        # Try a direct API call with error handling
        import requests
        import json
        
        url = f"{SUPABASE_URL}/rest/v1/op"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        response = requests.post(url, json=op_data, headers=headers)
        
        print(f"Direct API response: Status {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        try:
            print(f"Response body: {response.json()}")
        except:
            print(f"Raw response: {response.text}")
        
        if response.status_code >= 400:
            return jsonify({"message": f"Erro ao cadastrar OP: {response.text}"}), response.status_code
            
        return jsonify({"message": "OP cadastrada com sucesso!"})
    
    except ValueError as e:
        print(f"Value error: {str(e)}")
        return jsonify({"message": f"Erro de valor: {str(e)}"}), 400
    
    except Exception as e:
        error_msg = str(e)
        print(f"Error inserting OP: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Erro ao cadastrar OP: {error_msg}"}), 500

# 👉 2️⃣ Rota para Buscar uma OP Específica
@app.route('/op/<numero_op>', methods=['GET'])
def buscar_op(numero_op):
    try:
        print(f"Buscando OP: {numero_op}")  # Log para verificar a entrada

        # Buscar OP no banco de dados
        response = supabase.table("op").select("*").eq("numero_op", numero_op).execute()

        if not response.data:
            print("OP não encontrada no banco de dados.")  # Log de erro
            return jsonify({"message": "OP não encontrada"}), 404

        op = response.data[0]  # Pega a primeira OP encontrada
        print(f"OP encontrada: {op}")  # Log do resultado

        return jsonify(op)

    except Exception as e:
        print(f"Erro ao buscar OP {numero_op}: {str(e)}")  # Log do erro
        return jsonify({"message": f"Erro ao buscar OP: {str(e)}"}), 500

# 👉 3️⃣ Rota para Registrar Horas em uma OP
@app.route('/op/<numero_op>', methods=['PUT'])
def registrar_horas_op(numero_op):
    try:
        # Buscar a OP no banco de dados
        response = supabase.table("op").select("*").eq("numero_op", numero_op).execute()
        if not response.data:
            return jsonify({"message": "OP não encontrada"}), 404

        op = response.data[0]  # Pega a primeira OP encontrada

        # Capturar dados enviados pelo usuário
        data = request.json
        setor = data.get('setor')

        if setor not in ["torno", "fresa", "ajustagem"]:
            return jsonify({"message": "Setor inválido. Escolha entre torno, fresa ou ajustagem."}), 400

        try:
            # Converter horários para minutos
            inicio = datetime.strptime(data.get('inicio', ''), '%H:%M')
            fim = datetime.strptime(data.get('fim', ''), '%H:%M')
            minutos_trabalhados = int((fim - inicio).total_seconds() / 60)
        except ValueError:
            return jsonify({"message": "Formato de hora inválido. Use HH:MM"}), 400

        # Determinar o campo correto de minutos registrados
        field = f"minutos_registrados_{setor}"

        # Somar os minutos existentes com os novos minutos registrados
        minutos_atuais = op.get(field, 0)  # Se não existir, assume 0
        novos_minutos = minutos_atuais + minutos_trabalhados

        # Atualizar no banco de dados
        update_response = supabase.table("op").update({field: novos_minutos}).eq("numero_op", numero_op).execute()

        # Verificar se a atualização foi bem-sucedida
        if update_response.data:
            return jsonify({"message": f"{minutos_trabalhados} minutos adicionados à OP {numero_op} no setor {setor}!"})
        else:
            return jsonify({"message": "Erro ao atualizar OP."}), 500

    except Exception as e:
        print(f"Erro ao registrar horas: {str(e)}")
        return jsonify({"message": f"Erro ao registrar horas: {str(e)}"}), 500

@app.route('/api/ops', methods=['GET'])
def listar_ops_dropdown():
    try:
        response = supabase.table("op").select("numero_op").execute()
        ops = response.data if response.data else []

        print("OPs encontradas:", ops)  # Log para depuração
        return jsonify(ops)

    except Exception as e:
        print(f"Erro ao buscar OPs: {str(e)}")  # Log do erro no


# 👉 Rota para Listar Todas as OPs
@app.route('/ops', methods=['GET'])
def listar_ops():
    response = supabase.table("op").select("*").execute()
    ops = response.data if response.data else []

    for op in ops:
        op["eficiencia_torno"] = round((op["torno"] / op["minutos_registrados_torno"]) * 100, 2) if op["minutos_registrados_torno"] > 0 else 0
        op["eficiencia_fresa"] = round((op["fresa"] / op["minutos_registrados_fresa"]) * 100, 2) if op["minutos_registrados_fresa"] > 0 else 0
        op["eficiencia_ajustagem"] = round((op["ajustagem"] / op["minutos_registrados_ajustagem"]) * 100, 2) if op["minutos_registrados_ajustagem"] > 0 else 0

    return jsonify(ops)

# 👉 Rota para Deletar uma OP
@app.route('/op/<numero_op>', methods=['DELETE'])
def deletar_op(numero_op):
    try:
        # Verificar se a OP existe antes de excluir
        response = supabase.table("op").select("numero_op").eq("numero_op", numero_op).execute()
        if not response.data:
            return jsonify({"message": "OP não encontrada."}), 404

        # Excluir a OP
        delete_response = supabase.table("op").delete().eq("numero_op", numero_op).execute()

        if delete_response.data:
            return jsonify({"message": f"OP {numero_op} removida com sucesso!"})
        else:
            return jsonify({"message": "Erro ao remover OP."}), 500

    except Exception as e:
        print(f"Erro ao excluir OP: {str(e)}")
        return jsonify({"message": f"Erro ao excluir OP: {str(e)}"}), 500
    

@app.route('/operadores')
def listar_operadores():
    response = supabase.table("operadores").select("id, nome, torno, fresa, ajustagem").execute()
    return jsonify(response.data)


@app.route('/api/operador/<int:id>')
def get_operador(id):
    response = supabase.table("operadores").select("id, nome, torno, fresa, ajustagem").eq("id", id).execute()
    operador = response.data[0] if response.data else None

    if not operador:
        return jsonify({"error": "Operador não encontrado"}), 404  # Retorna erro 404 em JSON

    return jsonify(operador)  # Retorna os dados do operador como JSON

@app.route('/operador/<int:id>')
def painel_operador(id):
    response = supabase.table("operadores").select("id, nome, torno, fresa, ajustagem").eq("id", id).execute()
    operador = response.data[0] if response.data else None

    if not operador:
        return "Operador não encontrado", 404  # Retorna erro 404 se o operador não existir

    return render_template('operador.html', operador=operador)  # Renderiza a interface HTML


@app.route('/registrar_apontamento', methods=['POST'])
def registrar_apontamento():
    try:
        data = request.json
        operador_id = data.get("operador_id")
        numero_op = data.get("numero_op")
        setor = data.get("setor")
        inicio = data.get("inicio")
        fim = data.get("fim")
        currentDay = datetime.now().strftime("%Y-%m-%d")  # Obtém a data atual

        if not operador_id or not numero_op or not setor or not inicio or not fim:
            return jsonify({"error": "Todos os campos são obrigatórios!"}), 400

        # Calcular os minutos trabalhados
        hora_inicio = datetime.strptime(inicio, "%H:%M")
        hora_fim = datetime.strptime(fim, "%H:%M")
        minutos_trabalhados = (hora_fim - hora_inicio).seconds // 60

        if minutos_trabalhados <= 0:
            return jsonify({"error": "Horário inválido!"}), 400

        # Inserir o apontamento no banco com a data atual
        response = supabase.table("apontamentos").insert({
            "operador_id": operador_id,
            "numero_op": numero_op,
            "setor": setor,
            "inicio": inicio,
            "fim": fim,
            "data_apontamento": currentDay
        }).execute()

        print(f"Apontamento registrado ({currentDay}): {minutos_trabalhados} minutos para {setor}")

        # Atualizar os minutos registrados na OP
        coluna_minutos = f"minutos_registrados_{setor}"  # Define qual coluna atualizar
        response = supabase.rpc("incrementar_minutos_op", {
            "numero_op": numero_op,
            "coluna": coluna_minutos,
            "minutos": minutos_trabalhados
        }).execute()

        # Calcular eficiência com base na OP
        eficiencia = calcular_eficiencia(numero_op, setor)

        return jsonify({"message": "Apontamento registrado!", "eficiencia": eficiencia})

    except Exception as e:
        print(f"Erro ao registrar apontamento: {str(e)}")
        return jsonify({"error": "Erro ao registrar apontamento"}), 500

def calcular_eficiencia(numero_op, setor):
    try:
        response = supabase.table("op").select(setor, f"minutos_registrados_{setor}").eq("numero_op", numero_op).execute()
        op_data = response.data[0] if response.data else None

        if not op_data:
            print(f"OP {numero_op} não encontrada.")
            return 0  # Retorna 0% se a OP não existir

        minutos_registrados = op_data[f"minutos_registrados_{setor}"]
        valor_setor = op_data[setor]  # O tempo esperado para esse setor

        eficiencia = round((valor_setor / minutos_registrados) * 100, 2) if minutos_registrados > 0 else 0
        print(f"Eficiência calculada para OP {numero_op} - {setor}: {eficiencia}%")

        return eficiencia

    except Exception as e:
        print(f"Erro ao calcular eficiência: {str(e)}")
        return 0

@app.route('/selecao_operador')
def selecao_operadores():
    return render_template('selecao_operador.html')


# if __name__ == '__main__':
#     app.run(debug=True)
