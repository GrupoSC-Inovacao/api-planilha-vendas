from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import os

app = Flask(__name__)

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)