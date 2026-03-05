from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#############################################################################
# MODELS - TABELAS DO BANCO
#############################################################################

class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255))
    descricao = db.Column(db.Text)
    preco = db.Column(db.Numeric(10,2))
    estoque = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'preco': float(self.preco) if self.preco else None,
            'estoque': self.estoque,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    empresa = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(20), nullable=False)
    nome_fantasia = db.Column(db.String(255))
    razao_social = db.Column(db.String(255))
    email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('empresa', 'cnpj', name='uq_empresa_cnpj'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'EMPRESA': self.empresa,
            'CNPJ': self.cnpj,
            'NOME FANTASIA': self.nome_fantasia,
            'RAZAO SOCIAL': self.razao_social,
            'EMAIL': self.email
        }

class Auth(db.Model):
    __tablename__ = 'auth'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False)
    auth = db.Column(db.String(10), default='false')
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('number', 'date', name='uq_number_date'),)
    
    def to_dict(self):
        return {
            'number': self.number,
            'auth': self.auth,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None
        }

#############################################################################
# ROTAS
#############################################################################

@app.route('/catalogo', methods=['GET'])
def ler_produtos():
    try:
        produtos = Produto.query.all()
        return jsonify([p.to_dict() for p in produtos]), 200
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return jsonify({"erro": "Falha ao ler planilha de produtos"}), 500

#############################################################################

@app.route('/clientes', methods=['POST'])
def buscar_cliente():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        empresa = str(dados.get("EMPRESA", "")).strip()
        cnpj = str(dados.get("CNPJ", "")).strip()

        if not empresa or not cnpj:
            return jsonify({"erro": "EMPRESA e CNPJ são obrigatórios"}), 400

        cliente = Cliente.query.filter_by(empresa=empresa, cnpj=cnpj).first()

        if not cliente:
            return jsonify({"cliente": None}), 200

        return jsonify({"cliente": cliente.to_dict()}), 200

    except Exception as e:
        print(f"Erro ao buscar cliente: {e}")
        return jsonify({"erro": "Falha ao buscar cliente"}), 500

#############################################################################

@app.route('/imagens/<nome>')
def listar_imagens_por_nome(nome):
    if '..' in nome or nome.startswith('/'):
        return jsonify({"erro": "Acesso negado"}), 403

    base_url = request.url_root.rstrip('/')
    pasta = '.'
    extensoes_validas = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    arquivos_encontrados = []

    try:
        for arquivo in os.listdir(pasta):
            caminho_completo = os.path.join(pasta, arquivo)
            if not os.path.isfile(caminho_completo):
                continue
            nome_arquivo, ext = os.path.splitext(arquivo)
            if ext.lower() not in extensoes_validas:
                continue
            if nome_arquivo.lower().startswith(nome.lower()):
                url_completa = f"{base_url}/imagens-arquivo/{arquivo}"
                arquivos_encontrados.append(url_completa)
    except Exception:
        return jsonify({"erro": "Falha ao listar imagens"}), 500

    return jsonify({"imagens": arquivos_encontrados})

@app.route('/imagens-arquivo/<nome>')
def servir_arquivo_imagem(nome):
    if '..' in nome or nome.startswith('/'):
        return jsonify({"erro": "Acesso negado"}), 403
    try:
        return send_from_directory('.', nome)
    except FileNotFoundError:
        return jsonify({"erro": "Imagem não encontrada"}), 201

#############################################################################

@app.route('/consultar', methods=['POST'])
def consultar_auth():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        number = str(dados.get("number", "")).strip()

        if not number:
            return jsonify({"erro": "number é obrigatório"}), 400

        data_atual = datetime.now().date()
        
        registro = Auth.query.filter_by(number=number, date=data_atual).first()

        if not registro:
            return jsonify({"mensagem": "dados nao encontrados"}), 201

        return jsonify(registro.to_dict()), 200

    except Exception as e:
        print(f"Erro na consulta auth: {e}")
        return jsonify({"erro": "Falha ao consultar dados"}), 500

#############################################################################

@app.route('/salvar', methods=['POST'])
def salvar_auth():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        number = str(dados.get("number", "")).strip()
        auth = str(dados.get("auth", "")).strip()
        date_str = str(dados.get("date", "")).strip()
        
        if not number or not auth or not date_str:
            return jsonify({"erro": "Todos os campos são obrigatórios: number, auth, date"}), 400
        
        # Converte string para date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400
        
        novo_registro = {
            'number': number,
            'auth': auth,
            'date': date_str
        }
        
        # Tenta encontrar registro existente
        registro = Auth.query.filter_by(number=number, date=date_obj).first()
        
        if registro:
            # ATUALIZA existente
            registro.auth = auth
            db.session.commit()
            return jsonify({"mensagem": "Registro atualizado com sucesso", "dados": novo_registro}), 200
        else:
            # CRIA novo
            novo = Auth(number=number, auth=auth, date=date_obj)
            db.session.add(novo)
            db.session.commit()
            return jsonify({"mensagem": "Dados salvos com sucesso", "dados": novo_registro}), 201

    except Exception as e:
        print(f"Erro ao salvar auth: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao salvar dados"}), 500

#############################################################################

@app.route('/desativar', methods=['POST'])
def desativar_auth():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        number = str(dados.get("number", "")).strip()
        if not number:
            return jsonify({"erro": "number é obrigatório"}), 400

        data_atual = datetime.now().date()
        
        registro = Auth.query.filter_by(number=number, date=data_atual).first()

        if not registro:
            return jsonify({"mensagem": "dados nao encontrados"}), 201
        
        registro.auth = 'false'
        db.session.commit()
        
        return jsonify({"mensagem": "Auth desativado com sucesso"}), 200

    except Exception as e:
        print(f"Erro ao desativar auth: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao desativar auth"}), 500

#############################################################################

# Criar tabelas se não existirem
with app.app_context():
    db.create_all()

#############################################################################

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)