from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)

#############################################################################

@app.route('/catalogo', methods=['GET'])
def ler_produtos():
    caminho = 'catalogo.xlsx'
    if not os.path.exists(caminho):
        return jsonify({"erro": "Arquivo catalogo.xlsx não encontrado"}), 404
    try:
        df = pd.read_excel(caminho)
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"erro": "Falha ao ler planilha de produtos"}), 500

#############################################################################

@app.route('/clientes', methods=['POST'])
def buscar_cliente():
    caminho = 'clientes.xlsx'
    if not os.path.exists(caminho):
        return jsonify({"erro": "Arquivo clientes.xlsx não encontrado"}), 404

    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        empresa = str(dados.get("EMPRESA", "")).strip()
        cnpj = str(dados.get("CNPJ", "")).strip()

        if not empresa or not cnpj:
            return jsonify({"erro": "EMPRESA e CNPJ são obrigatórios"}), 400

        df = pd.read_excel(caminho, dtype=str) 

        resultado = df[
            (df['EMPRESA'].str.strip() == empresa) &
            (df['CNPJ'].str.strip() == cnpj)
        ]

        if resultado.empty:
            return jsonify({"cliente": None}), 200

        cliente = resultado.iloc[0].to_dict()
        return jsonify({"cliente": cliente}), 200

    except Exception as e:
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
        return jsonify({"erro": "Imagem não encontrada"}), 404

#############################################################################

@app.route('/consultar', methods=['POST'])
def consultar_auth():
    caminho = 'auth.xlsx'
    if not os.path.exists(caminho):
        return jsonify({"erro": "Arquivo auth.xlsx não encontrado"}), 404

    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400

        number = str(dados.get("number", "")).strip()

        if not number:
            return jsonify({"erro": "number é obrigatório"}), 400

        df = pd.read_excel(caminho, dtype={'number': str})
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        data_atual = datetime.now().date()
        
        resultado = df[
            (df['number'].str.strip() == number) &
            (df['date'].dt.date == data_atual)
        ]

        if resultado.empty:
            return jsonify({"mensagem": "dados nao encontrados"}), 404

        registro = resultado.iloc[0].to_dict()
        
        if 'date' in registro and pd.notna(registro['date']):
            registro['date'] = registro['date'].strftime('%Y-%m-%d')
        
        return jsonify(registro), 200

    except Exception as e:
        print(f"Erro na consulta: {e}")
        return jsonify({"erro": "Falha ao consultar dados"}), 500

#############################################################################

@app.route('/salvar', methods=['POST'])
def salvar_auth():
    caminho = 'auth.xlsx'
    
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Corpo da requisição inválido"}), 400
        
        number = str(dados.get("number", "")).strip()
        session = str(dados.get("session", "")).strip()
        auth = str(dados.get("auth", "")).strip()
        date = str(dados.get("date", "")).strip()
        
        if not number or not session or not auth or not date:
            return jsonify({"erro": "Todos os campos são obrigatórios: number, session, auth, date"}), 400
        
        novo_registro = {
            'number': number,
            'session': session,
            'auth': auth,
            'date': date
        }
        
        if os.path.exists(caminho):
            df = pd.read_excel(caminho)
            df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
        else:
            df = pd.DataFrame([novo_registro])
        
        df.to_excel(caminho, index=False)
        
        return jsonify({"mensagem": "Dados salvos com sucesso", "dados": novo_registro}), 201

    except Exception as e:
        print(f"Erro ao salvar auth: {e}")
        return jsonify({"erro": "Falha ao salvar dados"}), 500

#############################################################################

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)