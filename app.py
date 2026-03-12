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

# Configurar logging para mostrar erros no console
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
# Pega a DATABASE_URL e corrige o prefixo
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')

# Corrige postgres:// para postgresql://
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Força o uso do driver psycopg (versão 3) em vez de psycopg2
if database_url.startswith('postgresql://') and not database_url.startswith('postgresql+psycopg://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

db = SQLAlchemy(app)

# =============================================================================
# MODELS - CLASSES QUE REPRESENTAM AS TABELAS DO BANCO
# =============================================================================

# -----------------------------------------------------------------------------
# TABELA: vendas
# -----------------------------------------------------------------------------
class Venda(db.Model):
    __tablename__ = 'vendas'
    
    # Campos da tabela
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados do cliente no momento da venda
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    empresa = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(20), nullable=False)
    nome_fantasia = db.Column(db.String(255))
    razao_social = db.Column(db.String(255))
    email_cliente = db.Column(db.String(255))
    
    # Dados da venda
    data_venda = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valor_total = db.Column(db.Numeric(10,2), nullable=False)
    quantidade_itens = db.Column(db.Integer, default=0)
    observacoes = db.Column(db.Text)
    
    # Relacionamento: uma venda tem vários itens
    itens = db.relationship('VendaItem', backref='venda', lazy=True, cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    
    # Converte para JSON
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
    
    # Chaves estrangeiras: relaciona com venda e produto
    venda_id = db.Column(db.Integer, db.ForeignKey('vendas.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    # Dados do produto no momento da venda
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    # Relacionamento com Produto
    produto = db.relationship('Produto', backref='venda_itens')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Converte para JSON
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
# TABELA: carrinho_abandonado (itens adicionados mas venda não finalizada)
# -----------------------------------------------------------------------------
class CarrinhoAbandonado(db.Model):
    __tablename__ = 'carrinho_abandonado'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados do cliente
    telefone = db.Column(db.String(20), nullable=False, index=True)
    empresa = db.Column(db.String(255)) 
    cnpj = db.Column(db.String(20))
    
    # Dados do produto
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    # Metadados
    #session_id = db.Column(db.String(100))
    adicionado_em = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com produto
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
# TABELA: cotacoes (cabeçalho da cotação)
# -----------------------------------------------------------------------------
class Cotacao(db.Model):
    __tablename__ = 'cotacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Código único da cotação (gerado pelo bot)
    codigo = db.Column(db.String(50), nullable=False, index=True, unique=True)
    
    # Dados do cliente
    telefone = db.Column(db.String(20), nullable=False, index=True)
    empresa = db.Column(db.String(255))
    cnpj = db.Column(db.String(20))
    
    # Dados da cotação
    data_cotacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valida_ate = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(20), default='ativa')
    
    # Relacionamento com itens
    itens = db.relationship('CotacaoItem', backref='cotacao', lazy=True, cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Verificação de validade    
    def esta_valida(self):
        """
        Verifica se a cotação está válida:
        - Status deve ser 'ativa'
        - Data atual deve ser <= valida_ate (se definida)
        
        Retorna: bool
        """
        # Se não está com status 'ativa', já está inválida
        if self.status != 'ativa':
            return False
        
        # Se tem data de validade e já passou, está expirada
        if self.valida_ate and datetime.utcnow() > self.valida_ate:
            return False
        
        # Caso contrário, está válida
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

    # Conversão para JSON

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
    
    # Dados do produto
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    preco_unitario = db.Column(db.Numeric(10,2), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)
    
    # Relacionamento com produto
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
    
    # Campos do produto
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
    
    # Converte para JSON
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
    
    # Identificação da oferta
    nome = db.Column(db.String(255), nullable=False, index=True)
    
    # Vínculo com produto
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    
    # Dados do produto (snapshot no momento da oferta)
    cod_sap = db.Column(db.String(100))
    ean = db.Column(db.String(50))
    descricao_curta = db.Column(db.String(255))
    descricao_longa = db.Column(db.Text)
    quantidade_estoque = db.Column(db.Integer)
    
    # Preços
    preco_original = db.Column(db.Numeric(10,2), nullable=False)
    preco_oferta = db.Column(db.Numeric(10,2), nullable=False)
    desconto_percentual = db.Column(db.Numeric(5,2))
    
    # Imagem da oferta (URL construída a partir do nome)
    nome_imagem = db.Column(db.String(255), nullable=False)
    url_imagem = db.Column(db.String(500), nullable=False)
    
    # Segmentação (opcional - se vazio, vale para todos)
    cnpj_cliente = db.Column(db.String(20), index=True)
    ddd_regiao = db.Column(db.String(2), index=True)
    
    # Validade
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    valida_ate = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='ativa')
    
    # Metadados
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento com produto
    produto = db.relationship('Produto', backref='ofertas')
    
    # Verificação de validade      
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
        
        # Se não tem segmentação, vale para todos
        if not self.cnpj_cliente and not self.ddd_regiao:
            return True
        
        # Verifica CNPJ
        if self.cnpj_cliente and cnpj:
            if self.cnpj_cliente != cnpj:
                return False
        elif self.cnpj_cliente and not cnpj:
            return False
        
        # Verifica DDD
        if self.ddd_regiao and ddd:
            if self.ddd_regiao != ddd:
                return False
        elif self.ddd_regiao and not ddd:
            return False
        
        return True
    
    # Conversão para JSON    
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
    
    # Garante que não tenha cliente duplicado com mesmo EMPRESA + CNPJ
    __table_args__ = (db.UniqueConstraint('empresa', 'cnpj', name='uq_empresa_cnpj'),)
    
    # Converte para JSON
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
    
    # Garante um registro único por number + data (evita duplicatas no mesmo dia)
    __table_args__ = (db.UniqueConstraint('number', 'date', name='uq_number_date'),)
    
    # Converte para JSON
    def to_dict(self):
        return {
            'number': self.number,
            'auth': self.auth,
            'cnpj': self.cnpj,
            'empresa': self.empresa,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None            
        }

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
        # Pega os dados JSON enviados na requisição
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        # Extrai e valida dados do cliente
        cnpj = str(dados.get("cnpj", "")).strip()
        empresa = str(dados.get("empresa", "")).strip()
        
        if not cnpj or not empresa:
            return jsonify({"erro": "CNPJ e empresa são obrigatórios"}), 400
        
        # Busca o cliente no banco pelo CNPJ + empresa
        cliente = Cliente.query.filter_by(cnpj=cnpj, empresa=empresa).first()
        
        if not cliente:
            return jsonify({"erro": "Cliente não encontrado"}), 404
        
        # Extrai lista de itens da venda
        itens = dados.get("itens", [])
        if not itens:
            return jsonify({"erro": "Pelo menos um item é obrigatório"}), 400
        
        # Variáveis para calcular o total e armazenar os itens
        valor_total = 0
        venda_itens = []
        
        # Loop para processar cada item da venda
        for item in itens:
            produto_id = item.get("produto_id")
            quantidade = item.get("quantidade", 1)
            
            if not produto_id:
                return jsonify({"erro": "produto_id é obrigatório para cada item"}), 400
            
            # Busca o produto pelo ID
            produto = Produto.query.get(produto_id)
            if not produto:
                return jsonify({"erro": f"Produto {produto_id} não encontrado"}), 404
            
            # Calcula subtotal: preço × quantidade
            preco_unitario = float(produto.preco) if produto.preco else 0
            subtotal = preco_unitario * quantidade
            valor_total += subtotal
            
            # Cria o objeto VendaItem com os dados do produto (snapshot)
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
            
            # Atualiza estoque do produto
            if produto.quantidade_estoque is not None:
                produto.quantidade_estoque -= quantidade
        
        # Cria o registro da venda
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
        
        # Associa os itens à venda
        nova_venda.itens = venda_itens
        
        # Salva tudo no banco de dados
        db.session.add(nova_venda)
        db.session.commit()
        
        # Retorna sucesso com os dados da venda criada
        return jsonify({
            "mensagem": "Venda salva com sucesso",
            "venda": nova_venda.to_dict()
        }), 201
        
    except Exception as e:
        print(f"Erro ao salvar venda: {e}")
        db.session.rollback()
        return jsonify({"erro": "Falha ao salvar venda"}), 500

# -----------------------------------------------------------------------------
# POST /carrinho - ADICIONAR/ACUMULAR ITENS NO CARRINHO ABANDONADO
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
        
        # Identificador do cliente
        telefone = str(dados.get("telefone", "")).strip()
        empresa = str(dados.get("empresa", "")).strip()
        cnpj = str(dados.get("cnpj", "")).strip()
        
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        # Itens a serem adicionados/acumulados
        itens_enviados = dados.get("itens", [])
        
        if not itens_enviados:
            # Se não veio nenhum item, apenas retorna o carrinho atual
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
        
        # Buscar itens atuais no banco
        itens_no_banco = CarrinhoAbandonado.query.filter_by(telefone=telefone).all()
        
        # Criar dicionário para busca rápida (produto_id -> item)
        banco_dict = {item.produto_id: item for item in itens_no_banco}
        
        # Processar cada item enviado
        for item_enviado in itens_enviados:
            produto_id = item_enviado.get("produto_id")
            quantidade_enviada = item_enviado.get("quantidade", 1)
            
            if not produto_id:
                continue
            
            # Buscar produto para pegar dados completos
            produto = Produto.query.get(produto_id)
            if not produto:
                continue
            
            # Calcular preço unitário
            preco_unitario = float(produto.preco) if produto.preco else 0
            
            # Verificar se já existe no carrinho
            if produto_id in banco_dict:              
                item_existente = banco_dict[produto_id]
                nova_quantidade = item_existente.quantidade + quantidade_enviada
                item_existente.quantidade = nova_quantidade
                item_existente.subtotal = preco_unitario * nova_quantidade
                item_existente.preco_unitario = preco_unitario
                item_existente.empresa = empresa if empresa else item_existente.empresa
                item_existente.cnpj = cnpj if cnpj else item_existente.cnpj
                item_existente.updated_at = datetime.utcnow()
                
                # Atualiza dicionário para próxima iteração
                banco_dict[produto_id] = item_existente
            else:
                # ✅ ADICIONAR: novo item no carrinho
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
                
                # Adiciona ao dicionário para futuras atualizações
                banco_dict[produto_id] = novo_item
        
        # Salvar todas as alterações
        db.session.commit()
        
        # Retornar carrinho atualizado
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
        
        # Buscar todos os itens do carrinho abandonado do cliente
        carrinho = CarrinhoAbandonado.query.filter_by(telefone=telefone).order_by(CarrinhoAbandonado.adicionado_em.desc()).all()
        
        if not carrinho:
            return jsonify({"mensagem": "Carrinho vazio"}), 201
        
        # Calcular totais
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
# POST /carrinho/remover - REMOVER/SUBTRAIR ITENS DO CARRINHO
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
        
        # Identificador do cliente
        telefone = str(dados.get("telefone", "")).strip()
        
        if not telefone:
            return jsonify({"erro": "Telefone é obrigatório"}), 400
        
        # Itens a serem removidos/subtraídos
        itens_a_remover = dados.get("itens", [])
        
        if not itens_a_remover:
            return jsonify({"erro": "É necessário informar pelo menos um item para remover"}), 400
        
        # Buscar itens atuais no carrinho do cliente
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
        
        # Criar dicionário para busca rápida (produto_id -> item)
        carrinho_dict = {item.produto_id: item for item in itens_no_carrinho}
        
        # Controlar o que foi processado
        itens_removidos = []
        itens_atualizados = []
        itens_nao_encontrados = []
        
        # Processar cada item da solicitação de remoção
        for item_remover in itens_a_remover:
            produto_id = item_remover.get("produto_id")
            quantidade_a_remover = item_remover.get("quantidade", 1)
            
            if not produto_id or quantidade_a_remover <= 0:
                continue
            
            # Verificar se o produto existe no carrinho
            if produto_id not in carrinho_dict:
                itens_nao_encontrados.append({
                    "produto_id": produto_id,
                    "mensagem": "Produto não encontrado no carrinho"
                })
                continue
            
            item_no_carrinho = carrinho_dict[produto_id]
            quantidade_atual = item_no_carrinho.quantidade
            
            # Calcular nova quantidade
            nova_quantidade = quantidade_atual - quantidade_a_remover
            
            if nova_quantidade > 0:
                # SUBTRAIR: mantém o produto com quantidade reduzida
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
                # REMOVER: quantidade zerou ou ficou negativa, exclui do carrinho
                db.session.delete(item_no_carrinho)
                
                itens_removidos.append({
                    "produto_id": produto_id,
                    "quantidade_anterior": quantidade_atual,
                    "quantidade_removida": quantidade_a_remover,
                    "mensagem": "Produto removido do carrinho"
                })
        
        # Salvar alterações no banco
        db.session.commit()
        
        # Retornar carrinho atualizado
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
        
        # Buscar e deletar itens
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
        
        # Dados obrigatórios
        telefone = str(dados.get("telefone", "")).strip()
        codigo = str(dados.get("codigo", "")).strip()
        
        if not telefone or not codigo:
            return jsonify({"erro": "Telefone e código são obrigatórios"}), 400
        
        # Dados opcionais do cliente
        empresa = str(dados.get("empresa", "")).strip()
        cnpj = str(dados.get("cnpj", "")).strip()
        observacoes = dados.get("observacoes", "")
        valida_ate_str = dados.get("valida_ate")
        
        # Itens da cotação
        itens_enviados = dados.get("itens", [])
        
        # Validar data de validade (se informada)
        valida_ate = None
        if valida_ate_str:
            try:
                valida_ate = datetime.strptime(valida_ate_str, '%Y-%m-%d')
            except:
                return jsonify({"erro": "Formato de valida_ate inválido. Use YYYY-MM-DD"}), 400
        
        # Buscar cotação existente pelo código
        cotacao = Cotacao.query.filter_by(codigo=codigo).first()
        
        if not cotacao:
            # CRIAR nova cotação
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
            # ATUALIZAR dados da cotação existente
            cotacao.telefone = telefone
            cotacao.empresa = empresa if empresa else cotacao.empresa
            cotacao.cnpj = cnpj if cnpj else cotacao.cnpj
            cotacao.observacoes = observacoes if observacoes else cotacao.observacoes
            cotacao.valida_ate = valida_ate if valida_ate else cotacao.valida_ate
            cotacao.updated_at = datetime.utcnow()
            acao = "Cotação atualizada"
        
        # Se não veio itens, apenas retorna a cotação (sem alterar itens)
        if not itens_enviados:
            db.session.commit()
            return jsonify({
                "mensagem": f"{acao} (sem alteração de itens)",
                "cotacao": cotacao.to_dict()
            }), 200
        
        # Buscar itens atuais da cotação no banco
        itens_no_banco = CotacaoItem.query.filter_by(cotacao_id=cotacao.id).all()
        
        # Criar dicionário para comparação rápida (produto_id -> item)
        banco_dict = {item.produto_id: item for item in itens_no_banco}
        
        # Lista de produtos que devem permanecer na cotação
        produtos_finais = set()
        
        # Processar cada item enviado
        for item_enviado in itens_enviados:
            produto_id = item_enviado.get("produto_id")
            quantidade = item_enviado.get("quantidade", 1)
            
            if not produto_id:
                continue
            
            produtos_finais.add(produto_id)
            
            # Buscar produto para pegar dados completos
            produto = Produto.query.get(produto_id)
            if not produto:
                continue
            
            # Calcular valores
            preco_unitario = float(produto.preco) if produto.preco else 0
            subtotal = preco_unitario * quantidade
            
            # Verificar se já existe na cotação
            if produto_id in banco_dict:
                # ATUALIZAR item existente
                item_existente = banco_dict[produto_id]
                item_existente.quantidade = quantidade
                item_existente.subtotal = subtotal
                item_existente.preco_unitario = preco_unitario
            else:
                # ADICIONAR novo item
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
        
        # REMOVER itens que estão na cotação mas não foram enviados
        for produto_id, item in banco_dict.items():
            if produto_id not in produtos_finais:
                db.session.delete(item)
        
        # Salvar todas as alterações
        db.session.commit()
        
        # Recarregar a cotação com os itens atualizados
        cotacao_atualizada = Cotacao.query.get(cotacao.id)
        
        # Calcular totais
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
        # Pegar parâmetros da query string
        telefone = request.args.get('telefone', '').strip()
        codigo = request.args.get('codigo', '').strip()
        status = request.args.get('status', '').strip()
        apenas_validas = request.args.get('valida', '').lower() == 'true'  # ← NOVO!
        
        # Pelo menos um filtro é obrigatório
        if not telefone and not codigo and not status and not apenas_validas:
            return jsonify({"erro": "Informe pelo menos: telefone, código, status ou valida"}), 400
        
        # Construir query dinâmica
        query = Cotacao.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if codigo:
            query = query.filter_by(codigo=codigo)
        if status:
            query = query.filter_by(status=status)
        
        # Ordenar por data decrescente
        query = query.order_by(Cotacao.data_cotacao.desc())
        
        # Executar consulta
        cotacoes = query.all()
        
        # Filtrar apenas válidas se solicitado (após buscar do banco)
        if apenas_validas:
            cotacoes = [cot for cot in cotacoes if cot.esta_valida()]
        
        if not cotacoes:
            return jsonify({"mensagem": "Nenhuma cotação encontrada"}), 201
        
        # Formatar resposta com verificação e atualização de validade
        resultado = []
        cotacoes_alteradas = []  # Trackear quais foram alteradas para commit
        
        for cot in cotacoes:            
            if cot.atualizar_status_se_expirada():
                cotacoes_alteradas.append(cot)
            
            # Calcular totais
            valor_total = sum(float(item.subtotal) for item in cot.itens)
            total_itens = sum(item.quantidade for item in cot.itens)
            
            # Montar resposta
            resultado.append({
                **cot.to_dict(),
                "total_itens": total_itens,
                "valor_total": valor_total
            })
        
        #Salvar alterações de status no banco (apenas se alguma mudou)
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
        
        # Pelo menos um filtro é obrigatório
        if not telefone and not codigo:
            return jsonify({"erro": "Informe pelo menos: telefone ou código"}), 400
        
        # Construir query dinâmica
        query = Cotacao.query
        
        if telefone:
            query = query.filter_by(telefone=telefone)
        if codigo:
            query = query.filter_by(codigo=codigo)
        
        # Buscar cotações para excluir
        cotacoes = query.all()
        
        if not cotacoes:
            return jsonify({"mensagem": "Nenhuma cotação encontrada para excluir"}), 200
        
        # Excluir itens primeiro
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
        
        # Campos obrigatórios
        nome = str(dados.get("nome", "")).strip()
        produto_id = dados.get("produto_id")
        preco_oferta = dados.get("preco_oferta")
        nome_imagem = str(dados.get("nome_imagem", "")).strip()
        valida_ate_str = dados.get("valida_ate")
        
        if not nome or not produto_id or not preco_oferta or not nome_imagem or not valida_ate_str:
            return jsonify({
                "erro": "Campos obrigatórios: nome, produto_id, preco_oferta, nome_imagem, valida_ate"
            }), 400
        
        # Buscar produto para pegar dados completos
        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({"erro": f"Produto {produto_id} não encontrado"}), 404
        
        # Capturar estoque atual do produto
        quantidade_estoque = produto.quantidade_estoque if produto.quantidade_estoque is not None else 0
        
        # Validar datas
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
        
        # Calcular desconto percentual
        preco_original = float(produto.preco) if produto.preco else 0
        desconto_percentual = 0
        if preco_original > 0:
            desconto_percentual = ((preco_original - float(preco_oferta)) / preco_original) * 100
        
        # Construir URL da imagem
        base_url = request.url_root.rstrip('/')
        url_imagem = f"{base_url}/imagens-arquivo/{nome_imagem}"
        
        # Campos opcionais
        cnpj_cliente = str(dados.get("cnpj_cliente", "")).strip() or None
        ddd_regiao = str(dados.get("ddd_regiao", "")).strip() or None
        observacoes = dados.get("observacoes", "")
        
        # Verificar se já existe oferta com mesmo nome
        oferta_existente = Oferta.query.filter_by(nome=nome).first()
        if oferta_existente:
            return jsonify({
                "erro": f"Já existe uma oferta com o nome '{nome}'. Use um nome único."
            }), 409
        
        # Criar nova oferta
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
        # Pegar parâmetros da query string
        telefone = request.args.get('telefone', '').strip()
        cnpj = request.args.get('cnpj', '').strip()
        ddd = request.args.get('ddd', '').strip()
        nome = request.args.get('nome', '').strip()
        apenas_ativas = request.args.get('ativas', 'true').lower() == 'true'
        apenas_com_estoque = request.args.get('com_estoque', 'true').lower() == 'true'  # ← NOVO!
        
        # Extrair DDD do telefone se não informado
        if not ddd and telefone and len(telefone) >= 11:
            ddd = telefone[2:4]
        
        # Construir query dinâmica
        query = Oferta.query
        
        # Filtro por nome (se informado)
        if nome:
            query = query.filter(Oferta.nome.ilike(f'%{nome}%'))
        
        # Ordenar por data de validade
        query = query.order_by(Oferta.valida_ate.desc())
        
        # Executar consulta
        ofertas = query.all()
        
        if not ofertas:
            return jsonify({"mensagem": "Nenhuma oferta encontrada"}), 201
        
        # Filtrar e atualizar status
        resultado = []
        ofertas_alteradas = []
        ofertas_sem_estoque = 0
        
        for oferta in ofertas:
            # Atualizar status se estiver expirada
            if oferta.atualizar_status_se_expirada():
                ofertas_alteradas.append(oferta)
            
            # Se quiser apenas ativas, pular as inválidas
            if apenas_ativas and not oferta.esta_valida():
                continue
            
            # ← NOVO: Verificar estoque
            if apenas_com_estoque and (oferta.quantidade_estoque is None or oferta.quantidade_estoque <= 0):
                ofertas_sem_estoque += 1
                continue
            
            # Verificar segmentação (CNPJ e DDD)
            if cnpj or ddd:
                if not oferta.eh_para_cliente(cnpj=cnpj, ddd=ddd):
                    continue
            
            # Adicionar ao resultado
            resultado.append(oferta.to_dict())
        
        # Salvar alterações de status no banco
        if ofertas_alteradas:
            db.session.commit()
            print(f"Status atualizado para 'expirada' em {len(ofertas_alteradas)} oferta(s)")
        elif ofertas_alteradas:
            db.session.rollback()
        
        # Verificar se não sobrou nenhuma oferta após filtros
        if not resultado:
            # Determinar mensagem adequada
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
        
        # Pelo menos um filtro é obrigatório
        if not nome and not oferta_id:
            return jsonify({"erro": "Informe pelo menos: nome ou id da oferta"}), 400
        
        # Construir query
        query = Oferta.query
        
        if nome:
            query = query.filter_by(nome=nome)
        if oferta_id:
            try:
                oferta_id = int(oferta_id)
                query = query.filter_by(id=oferta_id)
            except:
                return jsonify({"erro": "ID deve ser um número inteiro"}), 400
        
        # Buscar oferta(s)
        ofertas = query.all()
        
        if not ofertas:
            return jsonify({"mensagem": "Nenhuma oferta encontrada para excluir"}), 200
        
        # Excluir ofertas
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
        
        # Busca vendas do CNPJ, ordena por data decrescente e pega a primeira
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
        
        # Busca todas as vendas do CNPJ, da mais recente para a mais antiga
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
        # Pega parâmetros da URL (query strings)
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        cnpj = request.args.get('cnpj')
        
        # Começa com todas as vendas
        query = Venda.query
        
        # Aplica filtro de data inicial (se informado)
        if data_inicio:
            try:
                data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(Venda.data_venda >= data_inicio_dt)
            except:
                return jsonify({"erro": "Formato de data_inicio inválido. Use YYYY-MM-DD"}), 400
        
        # Aplica filtro de data final (se informado)
        if data_fim:
            try:
                data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
        # Inclui todo o dia final (até 23:59:59)            
                data_fim_dt = data_fim_dt + timedelta(days=1)
                query = query.filter(Venda.data_venda < data_fim_dt)
            except:
                return jsonify({"erro": "Formato de data_fim inválido. Use YYYY-MM-DD"}), 400
        
        # Aplica filtro de CNPJ (se informado)
        if cnpj:
            query = query.filter_by(cnpj=cnpj)
        
        # Ordena por data decrescente e executa a consulta
        query = query.order_by(Venda.data_venda.desc())
        vendas = query.all()
        
        # Calcula totais para o resumo
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

        # Busca cliente com EXACT MATCH em empresa e cnpj
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
    # Proteção contra acesso a arquivos fora da pasta
    if '..' in nome or nome.startswith('/'):
        return jsonify({"erro": "Acesso negado"}), 403

    base_url = request.url_root.rstrip('/')
    pasta = '.'  # Pasta atual
    extensoes_validas = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    arquivos_encontrados = []

    try:
        # Varre todos os arquivos da pasta
        for arquivo in os.listdir(pasta):
            caminho_completo = os.path.join(pasta, arquivo)
            if not os.path.isfile(caminho_completo):
                continue
            nome_arquivo, ext = os.path.splitext(arquivo)
            if ext.lower() not in extensoes_validas:
                continue
            # Compara ignorando maiúsculas/minúsculas
            if nome_arquivo.lower().startswith(nome.lower()):
                url_completa = f"{base_url}/imagens-arquivo/{arquivo}"
                arquivos_encontrados.append(url_completa)
    except Exception:
        return jsonify({"erro": "Falha ao listar imagens"}), 500

    return jsonify({"imagens": arquivos_encontrados})

# -----------------------------------------------------------------------------
# GET /imagens-arquivo/<nome> - SERVIR ARQUIVO DE IMAGEM
# -----------------------------------------------------------------------------
@app.route('/imagens-arquivo/<nome>')
def servir_arquivo_imagem(nome):
    """
    Serve o arquivo de imagem diretamente para o cliente.
    
    Exemplo: GET /imagens-arquivo/produto1.jpg → retorna a imagem
    """
    # Proteção contra acesso a arquivos fora da pasta
    if '..' in nome or nome.startswith('/'):
        return jsonify({"erro": "Acesso negado"}), 403
    try:
        # Envia o arquivo da pasta atual
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
        
        # Busca registro com number + data EXATAMENTE de hoje
        registro = Auth.query.filter_by(number=number, date=data_atual).first()

        if not registro:
            return jsonify({"mensagem": "dados nao encontrados"}), 201

        return jsonify(registro.to_dict()), 200

    except Exception as e:
        print(f"Erro na consulta auth: {e}")
        return jsonify({"erro": "Falha ao consultar dados"}), 500

# -----------------------------------------------------------------------------
# POST /salvar - SALVAR/ATUALIZAR AUTENTICAÇÃO (UPSERT)
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
        
        # Converte string "YYYY-MM-DD" para objeto date do Python
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
        
        # Busca se já existe registro com esse number + data
        registro = Auth.query.filter_by(number=number, date=date_obj).first()
        
        if registro:
            # ATUALIZA registro existente
            registro.auth = auth
            registro.cnpj = cnpj
            registro.empresa = empresa
            db.session.commit()
            return jsonify({"mensagem": "Registro atualizado com sucesso", "dados": novo_registro}), 200
        else:
            # CRIA novo registro
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
        
        # Busca registro de hoje
        registro = Auth.query.filter_by(number=number, date=data_atual).first()

        if not registro:
            return jsonify({"mensagem": "dados nao encontrados"}), 201
        
        # Altera apenas o campo auth
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

        # Pega e limpa o número recebido
        number = str(dados.get("number", "")).strip().replace(" ", "")

        if not number:
            return jsonify({"erro": "number é obrigatório"}), 400

        # Busca na tabela auth pelo número (traz o registro mais recente)
        registro = Auth.query.filter_by(number=number).order_by(Auth.created_at.desc()).first()

        if registro and registro.cnpj and registro.empresa:
            # Encontrou: Retorna CNPJ e EMPRESA
            return jsonify({
                "cnpj": registro.cnpj,
                "empresa": registro.empresa,
                "number": registro.number,
                "mensagem": "Cliente encontrado"
            }), 200

        # Não encontrou ou não tem CNPJ/EMPRESA cadastrado
        return jsonify({"mensagem": "dados nao encontrados"}), 201

    except Exception as e:
        print(f"Erro ao buscar cliente por telefone: {e}")
        return jsonify({"erro": "Falha ao buscar cliente"}), 500

# =============================================================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# =============================================================================

# Criar tabelas se não existirem (com tratamento de erro)
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

# Rota simples para testar se a app está rodando
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