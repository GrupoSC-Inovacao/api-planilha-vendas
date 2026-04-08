# =============================================================================
# IMPORTS - Bibliotecas necessárias
# =============================================================================
from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import psycopg
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text
import os
import logging
import sys
import requests

_pharmadb_token = None
_pharmadb_token_expires_at = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# INICIALIZAÇÃO DO FLASK
# =============================================================================
app = Flask(__name__)

# =============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# =============================================================================
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')

if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

if database_url.startswith('postgresql://') and not database_url.startswith('postgresql+psycopg://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

db = SQLAlchemy(app)

# =============================================================================
# MODELS
# =============================================================================

# -----------------------------------------------------------------------------
# TABELA: vendas
# -----------------------------------------------------------------------------
class Venda(db.Model):
    __tablename__ = 'vendas'
    
    id = db.Column(db.Integer, primary_key=True)
    
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    empresa = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(20), nullable=False)
    nome_fantasia = db.Column(db.String(255))
    razao_social = db.Column(db.String(255))
    email_cliente = db.Column(db.String(255))
    
    data_venda = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valor_total = db.Column(db.Numeric(10,2), nullable=False)
    quantidade_itens = db.Column(db.Integer, default=0)
    observacoes = db.Column(db.Text)
    
    itens = db.relationship('VendaItem', backref='venda', lazy=True, cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    
    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'empresa': self.empresa,
            'cnpj': self.cnpj,
            'nome_fantasia': self.nome_fantasia,
            'razao_social': self.razao_social,
            'email_cliente': self.email_cliente,
            'data_venda': self.data_venda.strftime('%Y-%m-%d %H:%M:%S') if self.data_venda else None,
            'valor_total': float(self.valor_total) if self.valor_total else None,
            'quantidade_itens': self.quantidade_itens,
            'observacoes': self.observacoes,
            'itens': [item.to_dict() for item in self.itens]
        }

# -----------------------------------------------------------------------------
# TABELA: venda_itens (itens individuais de cada venda)
# -----------------------------------------------------------------------------
class VendaItem(db.Model):
    __tablename__ = 'venda_itens'
    
    id = db.Column(db.Integer, primary_key=True)
    
    venda_id = db.Column(db.Integer, db.ForeignKey('vendas.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    produto = db.relationship('Produto', backref='venda_itens')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'venda_id': self.venda_id,
            'produto_id': self.produto_id,
            'cod_sap': self.cod_sap,
            'ean': self.ean,
            'descricao_curta': self.descricao_curta,
            'preco_unitario': float(self.preco_unitario) if self.preco_unitario else None,
            'quantidade': self.quantidade,
            'subtotal': float(self.subtotal) if self.subtotal else None
        }

# -----------------------------------------------------------------------------
# TABELA: carrinho_abandonado (itens adicionados, venda não finalizada)
# -----------------------------------------------------------------------------
class CarrinhoAbandonado(db.Model):
    __tablename__ = 'carrinho_abandonado'
    
    id = db.Column(db.Integer, primary_key=True)
    
    telefone = db.Column(db.String(20), nullable=False, index=True)
    empresa = db.Column(db.String(255)) 
    cnpj = db.Column(db.String(20))
    
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    #session_id = db.Column(db.String(100))
    adicionado_em = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    produto = db.relationship('Produto', backref='carrinho_itens')
    
    def to_dict(self):
        return {
            'id': self.id,
            'telefone': self.telefone,
            'empresa': self.empresa,
            'cnpj': self.cnpj,
            'produto_id': self.produto_id,
            'cod_sap': self.cod_sap,
            'ean': self.ean,
            'descricao_curta': self.descricao_curta,
            'preco_unitario': float(self.preco_unitario) if self.preco_unitario else None,
            'quantidade': self.quantidade,
            'subtotal': float(self.subtotal) if self.subtotal else None,
            'adicionado_em': self.adicionado_em.strftime('%Y-%m-%d %H:%M:%S') if self.adicionado_em else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

# -----------------------------------------------------------------------------
# TABELA: cotacoes
# -----------------------------------------------------------------------------
class Cotacao(db.Model):
    __tablename__ = 'cotacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    codigo = db.Column(db.String(50), nullable=False, index=True, unique=True)
    
    telefone = db.Column(db.String(20), nullable=False, index=True)
    empresa = db.Column(db.String(255))
    cnpj = db.Column(db.String(20))
    
    data_cotacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valida_ate = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(20), default='ativa')
    
    itens = db.relationship('CotacaoItem', backref='cotacao', lazy=True, cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def esta_valida(self):
        """
        Verifica se a cotação está válida:
        - Status deve ser 'ativa'
        - Data atual deve ser <= valida_ate (se definida)
        
        Retorna: bool
        """
        if self.status != 'ativa':
            return False
        
        if self.valida_ate and datetime.utcnow() > self.valida_ate:
            return False
        
        return True
    
    def atualizar_status_se_expirada(self):
        """
        Atualiza o status para 'expirada' se passou da data de validade.
        
        Retorna: bool (True se o status foi alterado)
        """
        if self.status == 'ativa' and self.valida_ate and datetime.utcnow() > self.valida_ate:
            self.status = 'expirada'
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'telefone': self.telefone,
            'empresa': self.empresa,
            'cnpj': self.cnpj,
            'data_cotacao': self.data_cotacao.strftime('%Y-%m-%d %H:%M:%S') if self.data_cotacao else None,
            'valida_ate': self.valida_ate.strftime('%Y-%m-%d %H:%M:%S') if self.valida_ate else None,
            'observacoes': self.observacoes,
            'status': self.status,
            'esta_valida': self.esta_valida(),
            'itens': [item.to_dict() for item in self.itens]
        }

# -----------------------------------------------------------------------------
# TABELA: cotacao_itens (itens da cotação)
# -----------------------------------------------------------------------------
class CotacaoItem(db.Model):
    __tablename__ = 'cotacao_itens'
    
    id = db.Column(db.Integer, primary_key=True)
    
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacoes.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    produto = db.relationship('Produto', backref='cotacao_itens')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'cotacao_id': self.cotacao_id,
            'produto_id': self.produto_id,
            'cod_sap': self.cod_sap,
            'ean': self.ean,
            'descricao_curta': self.descricao_curta,
            'preco_unitario': float(self.preco_unitario) if self.preco_unitario else None,
            'quantidade': self.quantidade,
            'subtotal': float(self.subtotal) if self.subtotal else None
        }

# -----------------------------------------------------------------------------
# TABELA: produtos (catálogo de produtos)
# -----------------------------------------------------------------------------
class Produto(db.Model):
    __tablename__ = 'produtos'
    
    id = db.Column(db.Integer, primary_key=True)
    
    forma = db.Column(db.String(100))
    tipo = db.Column(db.String(100))
    fornecedor = db.Column(db.String(255))
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco = db.Column(db.Numeric(10,2))
    descricao_longa = db.Column(db.Text)
    tamanho_volume = db.Column(db.String(100))
    apresentacao = db.Column(db.String(100))
    quantidade_estoque = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'forma': self.forma,
            'tipo': self.tipo,
            'fornecedor': self.fornecedor,
            'cod_sap': self.cod_sap,
            'ean': self.ean,
            'descricao_curta': self.descricao_curta,
            'preco': float(self.preco) if self.preco is not None else None,
            'descricao_longa': self.descricao_longa,
            'tamanho_volume': self.tamanho_volume,
            'apresentacao': self.apresentacao,
            'quantidade_estoque': self.quantidade_estoque
        }

# -----------------------------------------------------------------------------
# TABELA: ofertas
# -----------------------------------------------------------------------------
class Oferta(db.Model):
    __tablename__ = 'ofertas'
    
    id = db.Column(db.Integer, primary_key=True)
    
    nome = db.Column(db.String(255), nullable=False, index=True)
    
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    descricao_longa = db.Column(db.Text)
    quantidade_estoque = db.Column(db.Integer)
    
    preco_original = db.Column(db.Numeric(10,2), nullable=False)
    preco_oferta = db.Column(db.Numeric(10,2), nullable=False)
    desconto_percentual = db.Column(db.Numeric(5,2))
    
    nome_imagem = db.Column(db.String(255), nullable=False)
    url_imagem = db.Column(db.String(500), nullable=False)
    
    cnpj_cliente = db.Column(db.String(20), index=True)
    ddd_regiao = db.Column(db.String(2), index=True)
    
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valida_ate = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='ativa')
    
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    produto = db.relationship('Produto', backref='ofertas')
    
    def esta_valida(self):
        """
        Verifica se a oferta está válida:
        - Status deve ser 'ativa'
        - Data atual deve estar entre data_inicio e valida_ate
        """
        if self.status != 'ativa':
            return False
        
        agora = datetime.utcnow()
        if agora < self.data_inicio:
            return False
        
        if agora > self.valida_ate:
            return False
        
        return True
    
    def atualizar_status_se_expirada(self):
        """
        Atualiza o status para 'expirada' se passou da data de validade.
        Retorna True se o status foi alterado.
        """
        if self.status == 'ativa':
            agora = datetime.utcnow()
            if agora < self.data_inicio or agora > self.valida_ate:
                self.status = 'expirada'
                return True
        return False
    
    def eh_para_cliente(self, cnpj=None, ddd=None):
        """
        Verifica se a oferta é válida para um cliente específico.
        
        Regras:
        - Se cnpj_cliente e ddd_regiao estiverem vazios → vale para todos
        - Se cnpj_cliente preenchido → só vale para aquele CNPJ
        - Se ddd_regiao preenchido → só vale para aquela região
        - Se ambos preenchidos → precisa combinar ambos
        """
        
        if not self.cnpj_cliente and not self.ddd_regiao:
            return True
        
        if self.cnpj_cliente and cnpj:
            if self.cnpj_cliente != cnpj:
                return False
        elif self.cnpj_cliente and not cnpj:
            return False
        
        if self.ddd_regiao and ddd:
            if self.ddd_regiao != ddd:
                return False
        elif self.ddd_regiao and not ddd:
            return False
        
        return True
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'produto_id': self.produto_id,
            'cod_sap': self.cod_sap,
            'ean': self.ean,
            'descricao_curta': self.descricao_curta,
            'descricao_longa': self.descricao_longa,
            'quantidade_estoque': self.quantidade_estoque,
            'preco_original': float(self.preco_original) if self.preco_original else None,
            'preco_oferta': float(self.preco_oferta) if self.preco_oferta else None,
            'desconto_percentual': float(self.desconto_percentual) if self.desconto_percentual else None,
            'nome_imagem': self.nome_imagem,
            'url_imagem': self.url_imagem,
            'cnpj_cliente': self.cnpj_cliente,
            'ddd_regiao': self.ddd_regiao,
            'data_inicio': self.data_inicio.strftime('%Y-%m-%d %H:%M:%S') if self.data_inicio else None,
            'valida_ate': self.valida_ate.strftime('%Y-%m-%d %H:%M:%S') if self.valida_ate else None,
            'status': self.status,
            'esta_valida': self.esta_valida(),
            'observacoes': self.observacoes
        }

# -----------------------------------------------------------------------------
# TABELA: clientes
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# TABELA: auth (autenticação de usuários)
# -----------------------------------------------------------------------------
class Auth(db.Model):
    __tablename__ = 'auth'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), nullable=False)
    auth = db.Column(db.String(10), default='false')   
    cnpj = db.Column(db.String(20))
    empresa = db.Column(db.String(255))
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('number', 'date', name='uq_number_date'),)
    
    def to_dict(self):
        return {
            'number': self.number,
            'auth': self.auth,
            'cnpj': self.cnpj,
            'empresa': self.empresa,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None            
        }

# -----------------------------------------------------------------------------
# TABELA: consultas_bula (log de todas as consultas de bula)
# -----------------------------------------------------------------------------
class ConsultaBula(db.Model):
    __tablename__ = 'consultas_bula'
    
    id = db.Column(db.Integer, primary_key=True)
    
    telefone = db.Column(db.String(20), nullable=False, index=True)
    empresa = db.Column(db.String(255))
    cnpj = db.Column(db.String(20), index=True)
    
    pesquisa = db.Column(db.String(255), nullable=False)
    dados_retornados = db.Column(db.Text)
    status_consulta = db.Column(db.String(20), default='sucesso')
    
    data_consulta = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_origem = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'telefone': self.telefone,
            'empresa': self.empresa,
            'cnpj': self.cnpj,
            'pesquisa': self.pesquisa,
            'dados_retornados': self.dados_retornados,
            'status_consulta': self.status_consulta,
            'data_consulta': self.data_consulta.strftime('%Y-%m-%d %H:%M:%S') if self.data_consulta else None,
            'ip_origem': self.ip_origem,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

# -----------------------------------------------------------------------------
# TABELA: bula_medicamento (dados local de bulas consultadas)
# -----------------------------------------------------------------------------
class BulaMedicamento(db.Model):
    __tablename__ = 'bula_medicamento'
    
    id = db.Column(db.Integer, primary_key=True)
    
    nome = db.Column(db.String(255), nullable=False, index=True)
    nome_comercial = db.Column(db.String(255))
    principio_ativo = db.Column(db.String(255))
    
    laboratorio = db.Column(db.String(255))
    registro_anvisa = db.Column(db.String(50))
    classe_terapeutica = db.Column(db.String(255))
    
    indicacoes = db.Column(db.Text)
    contraindicacoes = db.Column(db.Text)
    posologia = db.Column(db.Text)
    armazenamento = db.Column(db.Text)
    efeitos_colaterais = db.Column(db.Text)
    advertencias = db.Column(db.Text)
    composicao = db.Column(db.Text)
    
    data_consulta = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fonte = db.Column(db.String(50), default='pharmadb')
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('nome', 'principio_ativo', name='uq_nome_principio'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'nome_comercial': self.nome_comercial,
            'principio_ativo': self.principio_ativo,
            'laboratorio': self.laboratorio,
            'registro_anvisa': self.registro_anvisa,
            'classe_terapeutica': self.classe_terapeutica,
            'indicacoes': self.indicacoes,
            'contraindicacoes': self.contraindicacoes,
            'posologia': self.posologia,
            'armazenamento': self.armazenamento,
            'efeitos_colaterais': self.efeitos_colaterais,
            'advertencias': self.advertencias,
            'composicao': self.composicao,
            'data_consulta': self.data_consulta.strftime('%Y-%m-%d %H:%M:%S') if self.data_consulta else None,
            'fonte': self.fonte,
            'ultima_atualizacao': self.ultima_atualizacao.strftime('%Y-%m-%d %H:%M:%S') if self.ultima_atualizacao else None
        }

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES - PHARMADB AUTH (Consulta externa de bulas)
# -----------------------------------------------------------------------------
def get_pharmadb_token():
    """
    Obtém ou renova o token JWT da PharmaDB.
    Usa cache para evitar requisições desnecessárias.
    """
    global _pharmadb_token, _pharmadb_token_expires_at
    
    if _pharmadb_token and _pharmadb_token_expires_at:
        if datetime.utcnow() < _pharmadb_token_expires_at - timedelta(minutes=5):
            logger.debug("Usando token JWT em cache")
            return _pharmadb_token
    
    api_key = os.environ.get('PHARMADB_API_KEY', '')
    
    if not api_key:
        logger.error("PHARMADB_API_KEY não configurada nas variáveis de ambiente")
        return None
    
    try:
        response = requests.post(
            'https://api.pharmadb.com.br/auth/token',
            headers={'x-api-key': api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            _pharmadb_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)  # 3600 segundos = 60 minutos
            
            _pharmadb_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)
            
            logger.info(f"Token JWT obtido com sucesso. Expira em {expires_in}s")
            return _pharmadb_token
        else:
            logger.error(f"Erro ao obter token PharmaDB: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Exceção ao obter token PharmaDB: {str(e)}")
        return None

# =============================================================================
# ROTAS DA API - ENDPOINTS
# =============================================================================

# -----------------------------------------------------------------------------
# POST /vendas - SALVAR UMA NOVA VENDA
# -----------------------------------------------------------------------------
@app.route('/vendas', methods=['POST'])
def salvar_venda():
    """
    Salva uma nova venda com múltiplos itens.
    
    Body esperado:
    {
        "cnpj": "33456789000132",
        "empresa": "SC01",
        "observacoes": "Venda via WhatsApp",
        "itens": [
            {"produto_id": 63, "quantidade": 2},
            {"produto_id": 64, "quantidade": 1}
        ]
    }
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        cnpj = str(dados.get("cnpj", "")).strip()
        empresa = str(dados.get("empresa", "")).strip()
        
        if not cnpj or not empresa:
            return jsonify({"erro": "CNPJ e empresa são obrigatórios"}), 400
        
        cliente = Cliente.query.filter_by(cnpj=cnpj, empresa=empresa).first()
        
        if not cliente:
            return jsonify({"erro": "Cliente não encontrado"}), 404
        
        itens = dados.get("itens", [])
        if not itens:
            return jsonify({"erro": "Pelo menos um item é obrigatório"}), 400
        
        valor_total = 0
        venda_itens = []
        
        for item in itens:
            produto_id = item.get("produto_id")
            quantidade = item.get("quantidade", 1)
            
            if not produto_id:
                return jsonify({"erro": "produto_id é obrigatório para cada item"}), 400
            
            produto = Produto.query.get(produto_id)
            if not produto:
                return jsonify({"erro": f"Produto {produto_id} não encontrado"}), 404
            
            preco_unitario = float(produto.preco) if produto.preco else 0
            subtotal = preco_unitario * quantidade
            valor_total += subtotal
            
            venda_item = VendaItem(
                produto_id=produto.id,
                cod_sap=produto.cod_sap,
                ean=produto.ean,
                descricao_curta=produto.descricao_curta,
                preco_unitario=preco_unitario,
                quantidade=quantidade,
                subtotal=subtotal
            )
            venda_itens.append(venda_item)
            
            if produto.quantidade_estoque is not None:
                produto.quantidade_estoque -= quantidade
        
        nova_venda = Venda(
            cliente_id=cliente.id,
            empresa=cliente.empresa,
            cnpj=cliente.cnpj,
            nome_fantasia=cliente.nome_fantasia,
            razao_social=cliente.razao_social,
            email_cliente=cliente.email,
            data_venda=datetime.utcnow(),
            valor_total=valor_total,
            quantidade_itens=len(itens),
            observacoes=dados.get("observacoes", "")
        )
        
        nova_venda.itens = venda_itens
        
        db.session.add(nova_venda)
        db.session.commit()
        
        return jsonify({
            "mensagem": "Venda salva com sucesso",
            "venda": nova_venda.to_dict()
        }), 201
        
    except Exception as e:
        print(f"Erro ao salvar venda: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao salvar venda"}), 500

# -----------------------------------------------------------------------------
# POST /carrinho - ADICIONAR ITENS NO CARRINHO ABANDONADO
# -----------------------------------------------------------------------------
@app.route('/carrinho', methods=['POST'])
def adicionar_ao_carrinho():
    """
    Adiciona ou acumula itens no carrinho abandonado.
    NUNCA remove itens - apenas adiciona novos ou atualiza quantidades (somando).
    
    Body esperado:
    {
        "telefone": "5511910589650",
        "empresa": "SC01",  // opcional
        "cnpj": "33456789000132",  // opcional
        "itens": [
            {"produto_id": 93, "quantidade": 4},
            {"produto_id": 103, "quantidade": 2}
        ]
    }
    
    Comportamento:
    - Produto novo no carrinho → ADICIONA
    - Produto existente → SOMA quantidade (ex: 5 + 5 = 10)
    - Produto não enviado → MANTÉM no carrinho (não remove)
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        telefone = str(dados.get("telefone", "")).strip()
        empresa = str(dados.get("empresa", "")).strip()
        cnpj = str(dados.get("cnpj", "")).strip()
        
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        itens_enviados = dados.get("itens", [])
        
        if not itens_enviados:
            carrinho_atual = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
            valor_total = sum(float(item.subtotal) for item in carrinho_atual)
            total_itens = sum(item.quantidade for item in carrinho_atual)
            
            return jsonify({
                "mensagem": "Nenhum item enviado para adicionar",
                "carrinho": {
                    "itens": [item.to_dict() for item in carrinho_atual],
                    "total_itens": total_itens,
                    "quantidade_tipos": len(carrinho_atual),
                    "valor_total": valor_total
                }
            }), 200
        
        itens_no_banco = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        
        banco_dict = {item.produto_id: item for item in itens_no_banco}
        
        for item_enviado in itens_enviados:
            produto_id = item_enviado.get("produto_id")
            quantidade_enviada = item_enviado.get("quantidade", 1)
            
            if not produto_id:
                continue
            
            produto = Produto.query.get(produto_id)
            if not produto:
                continue
            
            preco_unitario = float(produto.preco) if produto.preco else 0
            
            if produto_id in banco_dict:              
                item_existente = banco_dict[produto_id]
                nova_quantidade = item_existente.quantidade + quantidade_enviada
                item_existente.quantidade = nova_quantidade
                item_existente.subtotal = preco_unitario * nova_quantidade
                item_existente.preco_unitario = preco_unitario
                item_existente.empresa = empresa if empresa else item_existente.empresa
                item_existente.cnpj = cnpj if cnpj else item_existente.cnpj
                item_existente.updated_at = datetime.utcnow()
                
                banco_dict[produto_id] = item_existente
            else:
                subtotal = preco_unitario * quantidade_enviada
                novo_item = CarrinhoAbandonado(
                    telefone=telefone,
                    empresa=empresa,
                    cnpj=cnpj,
                    produto_id=produto.id,
                    cod_sap=produto.cod_sap,
                    ean=produto.ean,
                    descricao_curta=produto.descricao_curta,
                    preco_unitario=preco_unitario,
                    quantidade=quantidade_enviada,
                    subtotal=subtotal
                )
                db.session.add(novo_item)
                
                banco_dict[produto_id] = novo_item
        
        db.session.commit()
        
        carrinho_atualizado = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        valor_total = sum(float(item.subtotal) for item in carrinho_atualizado)
        total_itens = sum(item.quantidade for item in carrinho_atualizado)
        
        return jsonify({
            "mensagem": "Itens adicionados/acumulados no carrinho com sucesso",
            "carrinho": {
                "itens": [item.to_dict() for item in carrinho_atualizado],
                "total_itens": total_itens,
                "quantidade_tipos": len(carrinho_atualizado),
                "valor_total": valor_total
            }
        }), 200
        
    except Exception as e:
        print(f"Erro ao adicionar ao carrinho: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao adicionar itens ao carrinho"}), 500

# -----------------------------------------------------------------------------
# GET /carrinho/<telefone> - BUSCAR CARRINHO ABANDONADO DO CLIENTE
# -----------------------------------------------------------------------------
@app.route('/carrinho/<telefone>', methods=['GET'])
def buscar_carrinho_abandonado(telefone):
    """
    Retorna todos os itens do carrinho abandonado de um cliente pelo telefone.
    
    Exemplo: GET /carrinho/5511910589650
    """
    try:
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        carrinho = CarrinhoAbandonado.query.filter_by(telefone=telefone).order_by(CarrinhoAbandonado.adicionado_em.desc()).all()
        
        if not carrinho:
            return jsonify({"mensagem": "Carrinho vazio"}), 201
        
        valor_total = sum(float(item.subtotal) for item in carrinho)
        total_itens = sum(item.quantidade for item in carrinho)
        
        return jsonify({
            "carrinho": {
                "itens": [item.to_dict() for item in carrinho],
                "total_itens": total_itens,
                "quantidade_tipos": len(carrinho),
                "valor_total": valor_total
            }
        }), 200
        
    except Exception as e:
        print(f"Erro ao buscar carrinho: {e}")
        return jsonify({"erro": "Falha ao buscar carrinho"}), 500

# -----------------------------------------------------------------------------
# POST /carrinho/remover - REMOVER ITENS DO CARRINHO
# -----------------------------------------------------------------------------
@app.route('/carrinho/remover', methods=['POST'])
def remover_do_carrinho():
    """
    Remove ou subtrai itens do carrinho abandonado.
    
    Lógica:
    - Se quantidade_a_remover < quantidade_no_carrinho → SUBTRAI e mantém o resto
    - Se quantidade_a_remover >= quantidade_no_carrinho → REMOVE o produto inteiro
    
    Body esperado:
    {
        "telefone": "5511910589650",
        "empresa": "SC01",  // opcional
        "cnpj": "33456789000132",  // opcional
        "itens": [
            {"produto_id": 103, "quantidade": 1},
            {"produto_id": 65, "quantidade": 2}
        ]
    }
    
    Exemplos:
    - Carrinho tem 10 Tylenol, remove 5 → Fica com 5 Tylenol
    - Carrinho tem 5 Clavulin, remove 5 → Remove Clavulin do carrinho
    - Carrinho tem 3 Dorflex, remove 10 → Remove Dorflex do carrinho (zera)
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        telefone = str(dados.get("telefone", "")).strip()
        
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        itens_a_remover = dados.get("itens", [])
        
        if not itens_a_remover:
            return jsonify({"erro": "É necessário informar pelo menos um item para remover"}), 400
        
        itens_no_carrinho = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        
        if not itens_no_carrinho:
            return jsonify({
                "mensagem": "Carrinho vazio, nada para remover",
                "carrinho": {
                    "itens": [],
                    "total_itens": 0,
                    "quantidade_tipos": 0,
                    "valor_total": 0
                }
            }), 200
        
        carrinho_dict = {item.produto_id: item for item in itens_no_carrinho}
        
        itens_removidos = []
        itens_atualizados = []
        itens_nao_encontrados = []
        
        for item_remover in itens_a_remover:
            produto_id = item_remover.get("produto_id")
            quantidade_a_remover = item_remover.get("quantidade", 1)
            
            if not produto_id or quantidade_a_remover <= 0:
                continue
            
            if produto_id not in carrinho_dict:
                itens_nao_encontrados.append({
                    "produto_id": produto_id,
                    "mensagem": "Produto não encontrado no carrinho"
                })
                continue
            
            item_no_carrinho = carrinho_dict[produto_id]
            quantidade_atual = item_no_carrinho.quantidade
            
            nova_quantidade = quantidade_atual - quantidade_a_remover
            
            if nova_quantidade > 0:
                item_no_carrinho.quantidade = nova_quantidade
                preco_unitario = float(item_no_carrinho.preco_unitario) if item_no_carrinho.preco_unitario else 0
                item_no_carrinho.subtotal = preco_unitario * nova_quantidade
                item_no_carrinho.updated_at = datetime.utcnow()
                
                itens_atualizados.append({
                    "produto_id": produto_id,
                    "quantidade_anterior": quantidade_atual,
                    "quantidade_removida": quantidade_a_remover,
                    "quantidade_atual": nova_quantidade
                })
            else:
                db.session.delete(item_no_carrinho)
                
                itens_removidos.append({
                    "produto_id": produto_id,
                    "quantidade_anterior": quantidade_atual,
                    "quantidade_removida": quantidade_a_remover,
                    "mensagem": "Produto removido do carrinho"
                })
        
        db.session.commit()
        
        carrinho_atualizado = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        valor_total = sum(float(item.subtotal) for item in carrinho_atualizado)
        total_itens = sum(item.quantidade for item in carrinho_atualizado)
        
        return jsonify({
            "mensagem": "Itens removidos/subtraídos com sucesso",
            "resumo": {
                "itens_removidos": len(itens_removidos),
                "itens_atualizados": len(itens_atualizados),
                "itens_nao_encontrados": len(itens_nao_encontrados)
            },
            "detalhes": {
                "removidos": itens_removidos,
                "atualizados": itens_atualizados,
                "nao_encontrados": itens_nao_encontrados
            },
            "carrinho": {
                "itens": [item.to_dict() for item in carrinho_atualizado],
                "total_itens": total_itens,
                "quantidade_tipos": len(carrinho_atualizado),
                "valor_total": valor_total
            }
        }), 200
        
    except Exception as e:
        print(f"Erro ao remover do carrinho: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao remover itens do carrinho"}), 500

# -----------------------------------------------------------------------------
# DELETE /carrinho/<telefone> - LIMPAR CARRINHO ABANDONADO
# -----------------------------------------------------------------------------
@app.route('/carrinho/<telefone>', methods=['DELETE'])
def limpar_carrinho_abandonado(telefone):
    """
    Remove todos os itens do carrinho abandonado de um cliente pelo telefone.
    Útil após finalizar a venda.
    
    Exemplo: DELETE /carrinho/5511910589650
    """
    try:
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        carrinho = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        
        if not carrinho:
            return jsonify({"mensagem": "Carrinho já está vazio"}), 200
        
        for item in carrinho:
            db.session.delete(item)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Carrinho limpo com sucesso",
            "itens_removidos": len(carrinho)
        }), 200
        
    except Exception as e:
        print(f"Erro ao limpar carrinho: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao limpar carrinho"}), 500

# -----------------------------------------------------------------------------
# POST /cotacoes - SINCRONIZAR COTAÇÃO
# -----------------------------------------------------------------------------
@app.route('/cotacoes', methods=['POST'])
def sincronizar_cotacao():
    """
    Sincroniza uma cotação com o estado enviado.
    - Se código não existe: CRIA nova cotação
    - Se código existe: ATUALIZA itens (adiciona/atualiza/remove)
    
    Body esperado:
    {
        "telefone": "5511910589650",
        "empresa": "SC01",
        "cnpj": "33456789000132",
        "codigo": "COT-2026-001",
        "observacoes": "Cotação via WhatsApp",
        "valida_ate": "2026-03-15",  // opcional
        "itens": [
            {"produto_id": 103, "quantidade": 1},
            {"produto_id": 64, "quantidade": 1}
        ]
    }
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        telefone = str(dados.get("telefone", "")).strip()
        codigo = str(dados.get("codigo", "")).strip()
        
        if not telefone or not codigo:
            return jsonify({"erro": "Telefone e código são obrigatórios"}), 400
        
        empresa = str(dados.get("empresa", "")).strip()
        cnpj = str(dados.get("cnpj", "")).strip()
        observacoes = dados.get("observacoes", "")
        valida_ate_str = dados.get("valida_ate")
        
        itens_enviados = dados.get("itens", [])
        
        valida_ate = None
        if valida_ate_str:
            try:
                valida_ate = datetime.strptime(valida_ate_str, '%Y-%m-%d')
            except:
                return jsonify({"erro": "Formato de valida_ate inválido. Use YYYY-MM-DD"}), 400
        
        cotacao = Cotacao.query.filter_by(codigo=codigo).first()
        
        if not cotacao:
            cotacao = Cotacao(
                codigo=codigo,
                telefone=telefone,
                empresa=empresa,
                cnpj=cnpj,
                observacoes=observacoes,
                valida_ate=valida_ate,
                data_cotacao=datetime.utcnow(),
                status='ativa'
            )
            db.session.add(cotacao)
            db.session.flush()
            acao = "Cotação criada"
        else:
            cotacao.telefone = telefone
            cotacao.empresa = empresa if empresa else cotacao.empresa
            cotacao.cnpj = cnpj if cnpj else cotacao.cnpj
            cotacao.observacoes = observacoes if observacoes else cotacao.observacoes
            cotacao.valida_ate = valida_ate if valida_ate else cotacao.valida_ate
            cotacao.updated_at = datetime.utcnow()
            acao = "Cotação atualizada"
        
        if not itens_enviados:
            db.session.commit()
            return jsonify({
                "mensagem": f"{acao} (sem alteração de itens)",
                "cotacao": cotacao.to_dict()
            }), 200
        
        itens_no_banco = CotacaoItem.query.filter_by(cotacao_id=cotacao.id).all()
        
        banco_dict = {item.produto_id: item for item in itens_no_banco}
        
        produtos_finais = set()
        
        for item_enviado in itens_enviados:
            produto_id = item_enviado.get("produto_id")
            quantidade = item_enviado.get("quantidade", 1)
            
            if not produto_id:
                continue
            
            produtos_finais.add(produto_id)
            
            produto = Produto.query.get(produto_id)
            if not produto:
                continue
            
            preco_unitario = float(produto.preco) if produto.preco else 0
            subtotal = preco_unitario * quantidade
            
            if produto_id in banco_dict:
                item_existente = banco_dict[produto_id]
                item_existente.quantidade = quantidade
                item_existente.subtotal = subtotal
                item_existente.preco_unitario = preco_unitario
            else:
                novo_item = CotacaoItem(
                    cotacao_id=cotacao.id,
                    produto_id=produto.id,
                    cod_sap=produto.cod_sap,
                    ean=produto.ean,
                    descricao_curta=produto.descricao_curta,
                    preco_unitario=preco_unitario,
                    quantidade=quantidade,
                    subtotal=subtotal
                )
                db.session.add(novo_item)
        
        for produto_id, item in banco_dict.items():
            if produto_id not in produtos_finais:
                db.session.delete(item)
        
        db.session.commit()
        
        cotacao_atualizada = Cotacao.query.get(cotacao.id)
        
        valor_total = sum(float(item.subtotal) for item in cotacao_atualizada.itens)
        total_itens = sum(item.quantidade for item in cotacao_atualizada.itens)
        
        return jsonify({
            "mensagem": f"{acao} com sucesso",
            "cotacao": {
                **cotacao_atualizada.to_dict(),
                "total_itens": total_itens,
                "valor_total": valor_total
            }
        }), 200 if acao == "Cotação atualizada" else 201
        
    except Exception as e:
        print(f"Erro ao sincronizar cotação: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao sincronizar cotação"}), 500

# -----------------------------------------------------------------------------
# GET /cotacoes - BUSCAR COTAÇÃO POR TELEFONE E/OU CÓDIGO
# -----------------------------------------------------------------------------
@app.route('/cotacoes', methods=['GET'])
def buscar_cotacao():
    """
    Busca cotações filtrando por telefone e/ou código.
    Verifica e atualiza automaticamente o status de validade.
    
    Query params:
    - telefone: 5511910589650 (opcional)
    - codigo: COT-2026-001 (opcional)
    - status: ativa (opcional)
    - valida: true|false (opcional) - filtra por validade atual
    
    Exemplos:
    GET /cotacoes?telefone=5511910589650
    GET /cotacoes?codigo=COT-2026-001
    GET /cotacoes?telefone=5511910589650&codigo=COT-2026-001
    GET /cotacoes?status=ativa
    GET /cotacoes?valida=true  ← Apenas cotações válidas
    GET /cotacoes?telefone=5511910589650&valida=true
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        codigo = request.args.get('codigo', '').strip()
        status = request.args.get('status', '').strip()
        apenas_validas = request.args.get('valida', '').lower() == 'true'
        
        if not telefone and not codigo and not status and not apenas_validas:
            return jsonify({"erro": "Informe pelo menos: telefone, código, status ou valida"}), 400
        
        query = Cotacao.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if codigo:
            query = query.filter_by(codigo=codigo)
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(Cotacao.data_cotacao.desc())
        
        cotacoes = query.all()
        
        if apenas_validas:
            cotacoes = [cot for cot in cotacoes if cot.esta_valida()]
        
        if not cotacoes:
            return jsonify({"mensagem": "Nenhuma cotação encontrada"}), 201
        
        resultado = []
        cotacoes_alteradas = []
        
        for cot in cotacoes:            
            if cot.atualizar_status_se_expirada():
                cotacoes_alteradas.append(cot)
            
            valor_total = sum(float(item.subtotal) for item in cot.itens)
            total_itens = sum(item.quantidade for item in cot.itens)
            
            resultado.append({
                **cot.to_dict(),
                "total_itens": total_itens,
                "valor_total": valor_total
            })
        
        if cotacoes_alteradas:
            db.session.commit()
            print(f"Status atualizado para 'expirada' em {len(cotacoes_alteradas)} cotação(ões)")
        
        return jsonify({
            "cotacoes": resultado,
            "total_encontrado": len(resultado)
        }), 200
        
    except Exception as e:
        print(f"Erro ao buscar cotação: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao buscar cotação"}), 500

# -----------------------------------------------------------------------------
# DELETE /cotacoes - EXCLUIR COTAÇÃO POR TELEFONE E/OU CÓDIGO
# -----------------------------------------------------------------------------
@app.route('/cotacoes', methods=['DELETE'])
def excluir_cotacao():
    """
    Exclui cotações filtrando por telefone e/ou código.
    
    Query params:
    - telefone: 5511910589650 (opcional)
    - codigo: COT-2026-001 (opcional)
    
    Exemplos:
    DELETE /cotacoes?codigo=COT-2026-001
    DELETE /cotacoes?telefone=5511910589650
    DELETE /cotacoes?telefone=5511910589650&codigo=COT-2026-001
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        codigo = request.args.get('codigo', '').strip()
        
        if not telefone and not codigo:
            return jsonify({"erro": "Informe pelo menos: telefone ou código"}), 400
        
        query = Cotacao.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if codigo:
            query = query.filter_by(codigo=codigo)
        
        cotacoes = query.all()
        
        if not cotacoes:
            return jsonify({"mensagem": "Nenhuma cotação encontrada para excluir"}), 200
        
        for cot in cotacoes:
            for item in cot.itens:
                db.session.delete(item)
            db.session.delete(cot)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Cotação(ões) excluída(s) com sucesso",
            "cotacoes_excluidas": len(cotacoes)
        }), 200
        
    except Exception as e:
        print(f"Erro ao excluir cotação: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao excluir cotação"}), 500

# -----------------------------------------------------------------------------
# POST /ofertas - CADASTRAR NOVA OFERTA
# -----------------------------------------------------------------------------
@app.route('/ofertas', methods=['POST'])
def cadastrar_oferta():
    """
    Cadastra uma nova oferta promocional.
    
    Body esperado:
    {
        "nome": "promocao-natal-2026",
        "produto_id": 63,
        "preco_oferta": 199.90,
        "nome_imagem": "promocao-natal-2026.jpg",
        "valida_ate": "2026-12-31",
        "data_inicio": "2026-12-01",  // opcional, padrão: hoje
        "cnpj_cliente": "33456789000132",  // opcional
        "ddd_regiao": "11",  // opcional
        "observacoes": "Oferta especial de Natal"
    }
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        nome = str(dados.get("nome", "")).strip()
        produto_id = dados.get("produto_id")
        preco_oferta = dados.get("preco_oferta")
        nome_imagem = str(dados.get("nome_imagem", "")).strip()
        valida_ate_str = dados.get("valida_ate")
        
        if not nome or not produto_id or not preco_oferta or not nome_imagem or not valida_ate_str:
            return jsonify({
                "erro": "Campos obrigatórios: nome, produto_id, preco_oferta, nome_imagem, valida_ate"
            }), 400
        
        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({"erro": f"Produto {produto_id} não encontrado"}), 404
        
        quantidade_estoque = produto.quantidade_estoque if produto.quantidade_estoque is not None else 0
        
        try:
            valida_ate = datetime.strptime(valida_ate_str, '%Y-%m-%d')
        except:
            return jsonify({"erro": "Formato de valida_ate inválido. Use YYYY-MM-DD"}), 400
        
        data_inicio = datetime.utcnow()
        if dados.get("data_inicio"):
            try:
                data_inicio = datetime.strptime(dados.get("data_inicio"), '%Y-%m-%d')
            except:
                return jsonify({"erro": "Formato de data_inicio inválido. Use YYYY-MM-DD"}), 400
        
        preco_original = float(produto.preco) if produto.preco else 0
        desconto_percentual = 0
        if preco_original > 0:
            desconto_percentual = ((preco_original - float(preco_oferta)) / preco_original) * 100
        
        base_url = request.url_root.rstrip('/')
        url_imagem = f"{base_url}/imagens-arquivo/{nome_imagem}"
        
        cnpj_cliente = str(dados.get("cnpj_cliente", "")).strip() or None
        ddd_regiao = str(dados.get("ddd_regiao", "")).strip() or None
        observacoes = dados.get("observacoes", "")
        
        oferta_existente = Oferta.query.filter_by(nome=nome).first()
        if oferta_existente:
            return jsonify({
                "erro": f"Já existe uma oferta com o nome '{nome}'. Use um nome único."
            }), 409
        
        nova_oferta = Oferta(
            nome=nome,
            produto_id=produto.id,
            cod_sap=produto.cod_sap,
            ean=produto.ean,
            descricao_curta=produto.descricao_curta,
            descricao_longa=produto.descricao_longa,
            quantidade_estoque=quantidade_estoque,
            preco_original=preco_original,
            preco_oferta=preco_oferta,
            desconto_percentual=desconto_percentual,
            nome_imagem=nome_imagem,
            url_imagem=url_imagem,
            cnpj_cliente=cnpj_cliente,
            ddd_regiao=ddd_regiao,
            data_inicio=data_inicio,
            valida_ate=valida_ate,
            status='ativa',
            observacoes=observacoes
        )
        
        db.session.add(nova_oferta)
        db.session.commit()
        
        return jsonify({
            "mensagem": "Oferta cadastrada com sucesso",
            "oferta": nova_oferta.to_dict()
        }), 201
        
    except Exception as e:
        print(f"Erro ao cadastrar oferta: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao cadastrar oferta"}), 500

# -----------------------------------------------------------------------------
# GET /ofertas - BUSCAR OFERTAS
# -----------------------------------------------------------------------------
@app.route('/ofertas', methods=['GET'])
def buscar_ofertas():
    """
    Busca ofertas filtrando por telefone, CNPJ e/ou DDD.
    Valida automaticamente e exclui ofertas expiradas ou sem estoque.
    
    Query params:
    - telefone: 5511910589650 (opcional, usado para extrair DDD)
    - cnpj: 33456789000132 (opcional)
    - ddd: 11 (opcional, extraído do telefone se não informado)
    - nome: promocao-natal (opcional, busca por nome)
    - ativas: true (opcional, default=true - só traz ofertas válidas)
    - com_estoque: true (opcional, default=true - só traz ofertas com estoque > 0)
    
    Exemplos:
    GET /ofertas?telefone=5511910589650
    GET /ofertas?cnpj=33456789000132
    GET /ofertas?ddd=11
    GET /ofertas?telefone=5511910589650&cnpj=33456789000132
    GET /ofertas?nome=promocao-natal
    GET /ofertas?com_estoque=true
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        cnpj = request.args.get('cnpj', '').strip()
        ddd = request.args.get('ddd', '').strip()
        nome = request.args.get('nome', '').strip()
        apenas_ativas = request.args.get('ativas', 'true').lower() == 'true'
        apenas_com_estoque = request.args.get('com_estoque', 'true').lower() == 'true'
        
        if not ddd and telefone and len(telefone) >= 11:
            ddd = telefone[2:4]
        
        query = Oferta.query
        
        if nome:
            query = query.filter(Oferta.nome.ilike(f'%{nome}%'))
        
        query = query.order_by(Oferta.valida_ate.desc())
        
        ofertas = query.all()
        
        if not ofertas:
            return jsonify({"mensagem": "Nenhuma oferta encontrada"}), 201
        
        resultado = []
        ofertas_alteradas = []
        ofertas_sem_estoque = 0
        
        for oferta in ofertas:
            if oferta.atualizar_status_se_expirada():
                ofertas_alteradas.append(oferta)
            
            if apenas_ativas and not oferta.esta_valida():
                continue
            
            if apenas_com_estoque and (oferta.quantidade_estoque is None or oferta.quantidade_estoque <= 0):
                ofertas_sem_estoque += 1
                continue
            
            if cnpj or ddd:
                if not oferta.eh_para_cliente(cnpj=cnpj, ddd=ddd):
                    continue
            
            resultado.append(oferta.to_dict())
        
        if ofertas_alteradas:
            db.session.commit()
            print(f"Status atualizado para 'expirada' em {len(ofertas_alteradas)} oferta(s)")
        elif ofertas_alteradas:
            db.session.rollback()
        
        if not resultado:
            if ofertas_sem_estoque > 0 and apenas_com_estoque:
                return jsonify({
                    "mensagem": "Nenhuma oferta encontrada",
                    "motivo": "Todas as ofertas estão sem estoque disponível",
                    "ofertas_sem_estoque": ofertas_sem_estoque
                }), 201
            else:
                return jsonify({
                    "mensagem": "Nenhuma oferta encontrada",
                    "motivo": "Nenhuma oferta disponível para este cliente/região"
                }), 201
        
        return jsonify({
            "ofertas": resultado,
            "total_encontrado": len(resultado),
            "filtros_aplicados": {
                "cnpj": cnpj,
                "ddd": ddd,
                "telefone": telefone,
                "apenas_ativas": apenas_ativas,
                "apenas_com_estoque": apenas_com_estoque
            }
        }), 200
        
    except Exception as e:
        print(f"Erro ao buscar ofertas: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao buscar ofertas"}), 500

# -----------------------------------------------------------------------------
# DELETE /ofertas - EXCLUIR OFERTA POR NOME OU ID
# -----------------------------------------------------------------------------
@app.route('/ofertas', methods=['DELETE'])
def excluir_oferta():
    """
    Exclui uma oferta pelo nome ou ID.
    
    Query params (pelo menos um é obrigatório):
    - nome: promocao-natal-2026
    - id: 1
    
    Exemplos:
    DELETE /ofertas?nome=promocao-natal-2026
    DELETE /ofertas?id=1
    """
    try:
        nome = request.args.get('nome', '').strip()
        oferta_id = request.args.get('id', '')
        
        if not nome and not oferta_id:
            return jsonify({"erro": "Informe pelo menos: nome ou id da oferta"}), 400
        
        query = Oferta.query
        
        if nome:
            query = query.filter_by(nome=nome)
        if oferta_id:
            try:
                oferta_id = int(oferta_id)
                query = query.filter_by(id=oferta_id)
            except:
                return jsonify({"erro": "ID deve ser um número inteiro"}), 400
        
        ofertas = query.all()
        
        if not ofertas:
            return jsonify({"mensagem": "Nenhuma oferta encontrada para excluir"}), 200
        
        for oferta in ofertas:
            db.session.delete(oferta)
        
        db.session.commit()
        
        return jsonify({
            "mensagem": "Oferta(s) excluída(s) com sucesso",
            "ofertas_excluidas": len(ofertas),
            "nomes_excluidos": [oferta.nome for oferta in ofertas]
        }), 200
        
    except Exception as e:
        print(f"Erro ao excluir oferta: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao excluir oferta"}), 500

# -----------------------------------------------------------------------------
# GET /vendas/ultima/<cnpj> - BUSCAR ÚLTIMA VENDA DO CLIENTE
# -----------------------------------------------------------------------------
@app.route('/vendas/ultima/<cnpj>', methods=['GET'])
def buscar_ultima_venda(cnpj):
    """
    Retorna a venda mais recente de um cliente pelo CNPJ.
    
    Exemplo: GET /vendas/ultima/33456789000132
    """
    try:
        if not cnpj:
            return jsonify({"erro": "CNPJ é obrigatório"}), 400
        
        venda = Venda.query.filter_by(cnpj=cnpj).order_by(Venda.data_venda.desc()).first()
        
        if not venda:
            return jsonify({"mensagem": "Nenhuma venda encontrada"}), 201
        
        return jsonify({"venda": venda.to_dict()}), 200
        
    except Exception as e:
        print(f"Erro ao buscar última venda: {e}")
        return jsonify({"erro": "Falha ao buscar venda"}), 500

# -----------------------------------------------------------------------------
# GET /vendas/cliente/<cnpj> - BUSCAR TODAS AS VENDAS DO CLIENTE
# -----------------------------------------------------------------------------
@app.route('/vendas/cliente/<cnpj>', methods=['GET'])
def buscar_todas_vendas_cliente(cnpj):
    """
    Retorna o histórico completo de vendas de um cliente.
    
    Exemplo: GET /vendas/cliente/33456789000132
    """
    try:
        if not cnpj:
            return jsonify({"erro": "CNPJ é obrigatório"}), 400
        
        vendas = Venda.query.filter_by(cnpj=cnpj).order_by(Venda.data_venda.desc()).all()
        
        if not vendas:
            return jsonify({"mensagem": "Nenhuma venda encontrada"}), 201
        
        return jsonify({
            "vendas": [venda.to_dict() for venda in vendas],
            "total_vendas": len(vendas)
        }), 200
        
    except Exception as e:
        print(f"Erro ao buscar vendas: {e}")
        return jsonify({"erro": "Falha ao buscar vendas"}), 500

# -----------------------------------------------------------------------------
# GET /vendas/relatorio - RELATÓRIO DE VENDAS COM FILTROS
# -----------------------------------------------------------------------------
@app.route('/vendas/relatorio', methods=['GET'])
def relatorio_vendas():
    """
    Gera relatório de vendas com filtros opcionais por data e CNPJ.
    
    Exemplos:
    GET /vendas/relatorio
    GET /vendas/relatorio?data_inicio=2026-03-01&data_fim=2026-03-05
    GET /vendas/relatorio?cnpj=33456789000132
    """
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        cnpj = request.args.get('cnpj')
        
        query = Venda.query
        
        if data_inicio:
            try:
                data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(Venda.data_venda >= data_inicio_dt)
            except:
                return jsonify({"erro": "Formato de data_inicio inválido. Use YYYY-MM-DD"}), 400
        
        if data_fim:
            try:
                data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_dt = data_fim_dt + timedelta(days=1)
                query = query.filter(Venda.data_venda < data_fim_dt)
            except:
                return jsonify({"erro": "Formato de data_fim inválido. Use YYYY-MM-DD"}), 400
        
        if cnpj:
            query = query.filter_by(cnpj=cnpj)
        
        query = query.order_by(Venda.data_venda.desc())
        vendas = query.all()
        
        total_vendas = len(vendas)
        valor_total = sum(float(v.valor_total) for v in vendas if v.valor_total)
        
        return jsonify({
            "vendas": [venda.to_dict() for venda in vendas],
            "resumo": {
                "total_vendas": total_vendas,
                "valor_total": valor_total,
                "periodo": {
                    "inicio": data_inicio,
                    "fim": data_fim
                }
            }
        }), 200
        
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return jsonify({"erro": "Falha ao gerar relatório"}), 500

# -----------------------------------------------------------------------------
# GET /catalogo - LISTAR TODOS OS PRODUTOS
# -----------------------------------------------------------------------------
@app.route('/catalogo', methods=['GET'])
def ler_produtos():
    """
    Retorna lista completa de produtos com ID (para usar na venda).
    Apenas produtos com estoque disponível (quantidade_estoque > 0).
    
    Exemplo: GET /catalogo
    Resposta: [{"id": 63, "descricao_curta": "...", "preco": 225.36, "quantidade_estoque": 12, ...}, ...]
    """
    try:        
        produtos = Produto.query.filter(Produto.quantidade_estoque > 0).all()
        
        return jsonify([p.to_dict() for p in produtos]), 200
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return jsonify({"erro": "Falha ao ler planilha de produtos"}), 500

# -----------------------------------------------------------------------------
# POST /clientes - BUSCAR CLIENTE POR EMPRESA + CNPJ
# -----------------------------------------------------------------------------
@app.route('/clientes', methods=['POST'])
def buscar_cliente():
    """
    Busca um cliente específico usando EMPRESA e CNPJ.
    
    Body: {"EMPRESA": "SC01", "CNPJ": "33456789000132"}
    """
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

# -----------------------------------------------------------------------------
# GET /imagens/<nome> - LISTAR IMAGENS POR NOME
# -----------------------------------------------------------------------------
@app.route('/imagens/<nome>')
def listar_imagens_por_nome(nome):
    """
    Busca imagens na pasta local que começam com o nome informado.
    
    Exemplo: GET /imagens/produto1 → retorna URLs de produto1.jpg, produto1_2.png, etc.
    """
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

# -----------------------------------------------------------------------------
# GET /imagens-arquivo/<nome> - MOSTRAR ARQUIVO DE IMAGEM
# -----------------------------------------------------------------------------
@app.route('/imagens-arquivo/<nome>')
def servir_arquivo_imagem(nome):
    """
    Serve o arquivo de imagem diretamente para o cliente.
    
    Exemplo: GET /imagens-arquivo/produto1.jpg → retorna a imagem
    """
    if '..' in nome or nome.startswith('/'):
        return jsonify({"erro": "Acesso negado"}), 403
    try:
        return send_from_directory('.', nome)
    except FileNotFoundError:
        return jsonify({"erro": "Imagem não encontrada"}), 404

# -----------------------------------------------------------------------------
# POST /consultar - CONSULTAR AUTENTICAÇÃO (DATA ATUAL)
# -----------------------------------------------------------------------------
@app.route('/consultar', methods=['POST'])
def consultar_auth():
    """
    Verifica se um número está autenticado HOJE.
    
    Body: {"number": "5511910589650"}
    Retorna 201 se não encontrar (para sua lógica de bot)
    """
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

# -----------------------------------------------------------------------------
# POST /salvar - SALVAR/ATUALIZAR AUTENTICAÇÃO
# -----------------------------------------------------------------------------
@app.route('/salvar', methods=['POST'])
def salvar_auth():
    """
    Salva nova autenticação ou atualiza existente (mesmo number + data).
    
    Body: {"number": "5511910589650", "auth": "true", "date": "2026-03-03", "cnpj": "33456789000132", "empresa": "SC01"}
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        number = str(dados.get("number", "")).strip()
        auth = str(dados.get("auth", "")).strip()
        cnpj = str(dados.get("cnpj", "")).strip()
        empresa = str(dados.get("empresa", "")).strip()
        date_str = str(dados.get("date", "")).strip()        
        
        if not number or not auth or not date_str:
            return jsonify({"erro": "Todos os campos são obrigatórios: number, auth, cnpj,empresa, date"}), 400
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD"}), 400
        
        novo_registro = {
            'number': number,
            'auth': auth,            
            'cnpj': cnpj,
            'empresa': empresa,
            'date': date_str
        }
        
        registro = Auth.query.filter_by(number=number, date=date_obj).first()
        
        if registro:
            registro.auth = auth
            registro.cnpj = cnpj
            registro.empresa = empresa
            db.session.commit()
            return jsonify({"mensagem": "Registro atualizado com sucesso", "dados": novo_registro}), 200
        else:
            novo = Auth(number=number, auth=auth, cnpj=cnpj, empresa=empresa, date=date_obj)
            db.session.add(novo)
            db.session.commit()
            return jsonify({"mensagem": "Dados salvos com sucesso", "dados": novo_registro}), 201

    except Exception as e:
        print(f"Erro ao salvar auth: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao salvar dados"}), 500

# -----------------------------------------------------------------------------
# POST /desativar - DESATIVAR AUTENTICAÇÃO (auth = false)
# -----------------------------------------------------------------------------
@app.route('/desativar', methods=['POST'])
def desativar_auth():
    """
    Altera o campo auth para 'false' no registro de hoje.
    
    Body: {"number": "5511910589650"}
    """
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

# -----------------------------------------------------------------------------
# POST /dados/cliente - BUSCAR CLIENTE POR TELEFONE (NA TABELA AUTH)
# -----------------------------------------------------------------------------
@app.route('/dados/cliente', methods=['POST'])
def buscar_cliente_por_telefone():
    """
    Busca o CNPJ e EMPRESA de um cliente pelo número de telefone na tabela auth.
    
    Body: {"number": "5511910589650"}
    Retorna: {"cnpj": "...", "empresa": "..."} ou erro
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        number = str(dados.get("number", "")).strip().replace(" ", "")

        if not number:
            return jsonify({"erro": "number é obrigatório"}), 400

        registro = Auth.query.filter_by(number=number).order_by(Auth.created_at.desc()).first()

        if registro and registro.cnpj and registro.empresa:
            return jsonify({
                "cnpj": registro.cnpj,
                "empresa": registro.empresa,
                "number": registro.number,
                "mensagem": "Cliente encontrado"
            }), 200

        return jsonify({"mensagem": "dados nao encontrados"}), 201

    except Exception as e:
        print(f"Erro ao buscar cliente por telefone: {e}")
        return jsonify({"erro": "Falha ao buscar cliente"}), 500

# -----------------------------------------------------------------------------
# POST /consultas-bula/log - SALVAR DADOS DE CONSULTA DE BULA
# -----------------------------------------------------------------------------
@app.route('/consultas-bula/log', methods=['POST'])
def salvar_log_consulta_bula():
    """
    Salva o log de uma consulta de bula realizada por um usuário.
    Body esperado:
    {
        "telefone": "5511910589650",
        "empresa": "SC01",
        "cnpj": "33456789000132",
        "pesquisa": "tylenol",
        "dados_retornados": "texto com os dados retornados da consulta",
        "status_consulta": "sucesso"
    }
    """
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        telefone = str(dados.get("telefone", "")).strip()
        pesquisa = str(dados.get("pesquisa", "")).strip()
        
        if not telefone:
            return jsonify({"erro": "telefone é obrigatório"}), 400
        
        if not pesquisa:
            return jsonify({"erro": "pesquisa é obrigatório"}), 400
        
        empresa = str(dados.get("empresa", "")).strip() or None
        cnpj = str(dados.get("cnpj", "")).strip() or None
        dados_retornados = dados.get("dados_retornados", "")
        status_consulta = str(dados.get("status_consulta", "sucesso")).strip()
        ip_origem = request.remote_addr
        
        novo_log = ConsultaBula(
            telefone=telefone,
            empresa=empresa,
            cnpj=cnpj,
            pesquisa=pesquisa,
            dados_retornados=dados_retornados,
            status_consulta=status_consulta,
            ip_origem=ip_origem
        )
        
        db.session.add(novo_log)
        db.session.commit()
        
        logger.info(f"Log de consulta salvo: {pesquisa} | Telefone: {telefone}")
        
        return jsonify({
            "mensagem": "Log de consulta salvo com sucesso",
            "consulta": novo_log.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao salvar log de consulta: {str(e)}")
        db.session.rollback()
        return jsonify({
            "erro": "Falha ao salvar log de consulta",
            "detalhe": str(e)
        }), 500

# -----------------------------------------------------------------------------
# GET /consultas-bula - BUSCAR DAODS DE CONSULTAS DE BULA
# -----------------------------------------------------------------------------
@app.route('/consultas-bula', methods=['GET'])
def buscar_logs_consultas_bula():
    """
    Busca logs de consultas de bula com filtros opcionais.
    Query params: telefone, cnpj, pesquisa, status, data_inicio, data_fim, limite
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        cnpj = request.args.get('cnpj', '').strip()
        pesquisa = request.args.get('pesquisa', '').strip()
        status = request.args.get('status', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        limite = request.args.get('limite', '100', type=int)
        
        query = ConsultaBula.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if cnpj:
            query = query.filter_by(cnpj=cnpj)
        if pesquisa:
            query = query.filter(ConsultaBula.pesquisa.ilike(f'%{pesquisa}%'))
        if status:
            query = query.filter_by(status_consulta=status)
        if data_inicio:
            try:
                data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(ConsultaBula.data_consulta >= data_inicio_dt)
            except:
                return jsonify({"erro": "Formato de data_inicio inválido. Use YYYY-MM-DD"}), 400
        if data_fim:
            try:
                data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_dt = data_fim_dt + timedelta(days=1)
                query = query.filter(ConsultaBula.data_consulta < data_fim_dt)
            except:
                return jsonify({"erro": "Formato de data_fim inválido. Use YYYY-MM-DD"}), 400
        
        query = query.order_by(ConsultaBula.data_consulta.desc()).limit(limite)
        consultas = query.all()
        
        if not consultas:
            return jsonify({"mensagem": "Nenhuma consulta encontrada"}), 201
        
        return jsonify({
            "consultas": [consulta.to_dict() for consulta in consultas],
            "total_encontrado": len(consultas),
            "filtros_aplicados": {
                "telefone": telefone, "cnpj": cnpj, "pesquisa": pesquisa,
                "status": status, "data_inicio": data_inicio,
                "data_fim": data_fim, "limite": limite
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs de consultas: {str(e)}")
        return jsonify({
            "erro": "Falha ao buscar logs de consultas",
            "detalhe": str(e)
        }), 500

# -----------------------------------------------------------------------------
# DELETE /consultas-bula - EXCLUIR DADOS DE CONSULTAS
# -----------------------------------------------------------------------------
@app.route('/consultas-bula', methods=['DELETE'])
def excluir_logs_consultas_bula():
    """
    Exclui logs de consultas com filtros.
    Query params: telefone, cnpj, id, mais_antigas_que (pelo menos um obrigatório)
    """
    try:
        telefone = request.args.get('telefone', '').strip()
        cnpj = request.args.get('cnpj', '').strip()
        consulta_id = request.args.get('id', '').strip()
        mais_antigas_que = request.args.get('mais_antigas_que', '').strip()
        
        if not telefone and not cnpj and not consulta_id and not mais_antigas_que:
            return jsonify({"erro": "Informe pelo menos um filtro: telefone, cnpj, id ou mais_antigas_que"}), 400
        
        query = ConsultaBula.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if cnpj:
            query = query.filter_by(cnpj=cnpj)
        if consulta_id:
            try:
                query = query.filter_by(id=int(consulta_id))
            except:
                return jsonify({"erro": "ID deve ser um número inteiro"}), 400
        if mais_antigas_que:
            try:
                data_limite = datetime.strptime(mais_antigas_que, '%Y-%m-%d')
                query = query.filter(ConsultaBula.data_consulta < data_limite)
            except:
                return jsonify({"erro": "Formato de mais_antigas_que inválido. Use YYYY-MM-DD"}), 400
        
        consultas = query.all()
        
        if not consultas:
            return jsonify({"mensagem": "Nenhuma consulta encontrada para excluir"}), 200
        
        for consulta in consultas:
            db.session.delete(consulta)
        
        db.session.commit()
        
        logger.info(f"{len(consultas)} log(s) de consulta excluído(s)")
        
        return jsonify({
            "mensagem": "Log(s) de consulta excluído(s) com sucesso",
            "registros_excluidos": len(consultas)
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao excluir logs de consultas: {str(e)}")
        db.session.rollback()
        return jsonify({
            "erro": "Falha ao excluir logs de consultas",
            "detalhe": str(e)
        }), 500

# -----------------------------------------------------------------------------
# POST /bula - CONSULTAR BULA COMPLETA (PHARMADB COM AUTH + DADOS LOCAL)
# -----------------------------------------------------------------------------
@app.route('/bula', methods=['POST'])
def consultar_bula():
    """
    Consulta a bula completa de um medicamento via PharmaDB.
    Body esperado:
    {
        "telefone": "5511910589650",
        "empresa": "SC01",
        "cnpj": "33456789000132",
        "busca": "tylenol"
    }
    """
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        telefone = str(dados.get("telefone", "")).strip()
        empresa = str(dados.get("empresa", "")).strip() or None
        cnpj = str(dados.get("cnpj", "")).strip() or None
        busca = str(dados.get("busca", "")).strip()
        
        if not busca:
            return jsonify({"erro": "Campo 'busca' é obrigatório"}), 400
        
        status_consulta = 'sucesso'
        dados_retornados = None
        medicamento = None
        fonte_usada = 'local'
        
        medicamento = BulaMedicamento.query.filter(
            db.or_(
                BulaMedicamento.nome.ilike(f'%{busca}%'),
                BulaMedicamento.nome_comercial.ilike(f'%{busca}%'),
                BulaMedicamento.principio_ativo.ilike(f'%{busca}%')
            )
        ).order_by(BulaMedicamento.ultima_atualizacao.desc()).first()
        
        if medicamento:
            logger.info(f"Medicamento encontrado no cache local: {busca}")
            dados_retornados = f"Nome: {medicamento.nome} | Lab: {medicamento.laboratorio}"
        else:
            logger.info(f"Medicamento não encontrado no cache. Consultando PharmaDB: {busca}")
            fonte_usada = 'pharmadb'
            
            token = get_pharmadb_token()
            if not token:
                return jsonify({
                    "erro": "Erro de autenticação com PharmaDB",
                    "sugestao": "Verifique se PHARMADB_API_KEY está configurada"
                }), 503
            
            mapeamento = {
                'tylenol': 'paracetamol',
                'dorflex': 'dorflex',
                'neosaldina': 'neosaldina',
                'buscopan': 'buscopan',
                'novalgina': 'novalgina'
            }
            
            termos_busca = [busca.lower()]
            if busca.lower() in mapeamento:
                termos_busca.append(mapeamento[busca.lower()])
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            medicamento_encontrado = None
            termo_usado = None
            
            for termo in termos_busca:
                try:
                    url = f"https://api.pharmadb.com.br/v1/bulas/busca?q={termo}&page=1&per_page=5"
                    response = requests.get(url, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        
                        if items and len(items) > 0:
                            bula_resumo = items[0]
                            bula_id = bula_resumo.get('id')
                            
                            url_completa = f"https://api.pharmadb.com.br/v1/bulas/{bula_id}"
                            response_completa = requests.get(url_completa, headers=headers, timeout=15)
                            
                            if response_completa.status_code == 200:
                                bula_completa = response_completa.json()
                                medicamento_encontrado = bula_completa
                                termo_usado = termo
                                logger.info(f"Bula encontrada: {bula_completa.get('produto', {}).get('nome', termo)}")
                                break
                                
                except Exception as e:
                    logger.warning(f"Erro ao buscar '{termo}': {str(e)}")
                    continue
            
            if not medicamento_encontrado:
                logger.warning(f"Medicamento não encontrado na PharmaDB: {busca}")
                status_consulta = 'nao_encontrado'
                
                if telefone:
                    try:
                        log = ConsultaBula(
                            telefone=telefone, empresa=empresa, cnpj=cnpj,
                            pesquisa=busca, dados_retornados=None,
                            status_consulta=status_consulta, ip_origem=request.remote_addr
                        )
                        db.session.add(log)
                        db.session.commit()
                    except:
                        db.session.rollback()
                
                return jsonify({
                    "erro": "Medicamento não encontrado na PharmaDB",
                    "nome_pesquisado": busca,
                    "sugestao": "Tente buscar pelo nome genérico"
                }), 404
            
            produto = medicamento_encontrado.get('produto', {})
            
            try:
                medicamento_cache = BulaMedicamento(
                    nome=produto.get('nome', '').upper(),
                    nome_comercial=produto.get('nome', '').upper(),
                    principio_ativo=', '.join(produto.get('principios_ativos', [])).upper(),
                    laboratorio=produto.get('laboratorio'),
                    registro_anvisa=produto.get('registro_anvisa'),
                    indicacoes=medicamento_encontrado.get('texto_indicacoes'),
                    contraindicacoes=medicamento_encontrado.get('texto_contraindicacoes'),
                    posologia=medicamento_encontrado.get('texto_posologia'),
                    armazenamento=None,
                    efeitos_colaterais=medicamento_encontrado.get('texto_reacoes_adversas'),
                    advertencias=None,
                    composicao=None,
                    fonte='pharmadb'
                )
                db.session.add(medicamento_cache)
                db.session.commit()
                logger.info(f"Medicamento salvo no cache local: {produto.get('nome')}")
                
                medicamento = BulaMedicamento.query.filter_by(nome=produto.get('nome', '').upper()).first()
                
            except Exception as e:
                logger.error(f"Erro ao salvar no cache: {str(e)}")
                db.session.rollback()
                medicamento = None
            
            dados_retornados = f"Nome: {produto.get('nome', '')} | Lab: {produto.get('laboratorio', '')}"
        
        if medicamento:
            resposta_dados = medicamento.to_dict()
        else:
            resposta_dados = {
                "nome": produto.get('nome', ''),
                "registro_anvisa": produto.get('registro_anvisa', ''),
                "laboratorio": produto.get('laboratorio', ''),
                "principio_ativo": ', '.join(produto.get('principios_ativos', [])),
                "indicacoes": medicamento_encontrado.get('texto_indicacoes', ''),
                "contraindicacoes": medicamento_encontrado.get('texto_contraindicacoes', ''),
                "posologia": medicamento_encontrado.get('texto_posologia', ''),
                "reacoes_adversas": medicamento_encontrado.get('texto_reacoes_adversas', ''),
                "interacoes": medicamento_encontrado.get('texto_interacoes', ''),
                "extraido_em": medicamento_encontrado.get('extraido_em', '')
            }
        
        logger.info(f"Bula consultada com sucesso: {busca} (fonte: {fonte_usada})")
        resposta = jsonify({
            "status": "success",
            "nome_pesquisado": busca,
            "fonte": fonte_usada,
            "dados": resposta_dados
        }), 200
        
        if telefone:
            try:
                log = ConsultaBula(
                    telefone=telefone,
                    empresa=empresa,
                    cnpj=cnpj,
                    pesquisa=busca,
                    dados_retornados=dados_retornados,
                    status_consulta=status_consulta,
                    ip_origem=request.remote_addr
                )
                db.session.add(log)
                db.session.commit()
            except Exception as log_error:
                logger.warning(f"Não foi possível salvar log: {log_error}")
                db.session.rollback()
        
        return resposta
        
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout ao consultar bula: {dados.get('busca', 'desconhecido') if dados else 'desconhecido'}")
        return jsonify({
            "erro": "Tempo esgotado ao consultar PharmaDB",
            "nome_pesquisado": dados.get('busca', '') if dados else ''
        }), 504
        
    except Exception as e:
        logger.error(f"Erro ao consultar bula: {dados.get('busca', 'desconhecido') if dados else 'desconhecido'} - {str(e)}")
        return jsonify({
            "erro": "Falha ao consultar bula",
            "detalhe": str(e)
        }), 500

# -----------------------------------------------------------------------------
# GET /bulas - LISTAR BULAS DE MEDICAMENTOS NA BASE LOCAL
# -----------------------------------------------------------------------------
@app.route('/bulas', methods=['GET'])
def listar_bulas_cache():
    """
    Lista medicamentos armazenados no cache local.
    Query params:
    - busca: tylenol (opcional)
    - limite: 100 (opcional, default=100)
    """
    try:
        busca = request.args.get('busca', '').strip()
        limite = request.args.get('limite', '100', type=int)
        
        query = BulaMedicamento.query
        
        if busca:
            query = query.filter(
                db.or_(
                    BulaMedicamento.nome.ilike(f'%{busca}%'),
                    BulaMedicamento.nome_comercial.ilike(f'%{busca}%'),
                    BulaMedicamento.principio_ativo.ilike(f'%{busca}%')
                )
            )
        
        medicamentos = query.order_by(BulaMedicamento.nome.asc()).limit(limite).all()
        
        return jsonify({
            "medicamentos": [m.to_dict() for m in medicamentos],
            "total": len(medicamentos),
            "fonte": "cache_local"
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao listar bulas do cache: {str(e)}")
        return jsonify({"erro": str(e)}), 500

# -----------------------------------------------------------------------------
# DELETE /bulas
# -----------------------------------------------------------------------------
@app.route('/bulas', methods=['DELETE'])
def limpar_cache_bulas():
    """
    Limpa medicamentos do cache local.
    Query params (pelo menos um obrigatório):
    - nome: paracetamol
    - mais_antigas_que: 2026-01-01
    - todos: true
    """
    try:
        nome = request.args.get('nome', '').strip()
        mais_antigas_que = request.args.get('mais_antigas_que', '').strip()
        todos = request.args.get('todos', '').lower() == 'true'
        
        if not nome and not mais_antigas_que and not todos:
            return jsonify({"erro": "Informe pelo menos um filtro"}), 400
        
        query = BulaMedicamento.query
        
        if nome:
            query = query.filter(BulaMedicamento.nome.ilike(f'%{nome}%'))
        
        if mais_antigas_que:
            try:
                data_limite = datetime.strptime(mais_antigas_que, '%Y-%m-%d')
                query = query.filter(BulaMedicamento.ultima_atualizacao < data_limite)
            except:
                return jsonify({"erro": "Formato de data inválido"}), 400
        
        medicamentos = query.all()
        
        if not medicamentos:
            return jsonify({"mensagem": "Nenhum medicamento encontrado para excluir"}), 200
        
        for med in medicamentos:
            db.session.delete(med)
        
        db.session.commit()
        
        logger.info(f"{len(medicamentos)} medicamento(s) removido(s) do cache")
        
        return jsonify({
            "mensagem": "Cache limpo com sucesso",
            "medicamentos_removidos": len(medicamentos)
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {str(e)}")
        db.session.rollback()
        return jsonify({"erro": str(e)}), 500

# =============================================================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# =============================================================================

try:
    with app.app_context():
        print("Iniciando conexão com o banco...")
        print(f"DATABASE_URL: {'OK' if os.environ.get('DATABASE_URL') else 'NÃO CONFIGURADA'}")
        db.create_all()
        print("Banco conectado!")
except Exception as e:
    print(f"ERRO CRÍTICO: {e}")
    print(f"Tipo: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    raise

# =============================================================================
# INICIALIZAÇÃO DO SERVIDOR
# =============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    try:        
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        return jsonify({
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)