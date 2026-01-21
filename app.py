from flask import Flask, jsonify, request
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)