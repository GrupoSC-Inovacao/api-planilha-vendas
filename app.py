from flask import Flask, jsonify
import pandas as pd
import os

app = Flask(__name__)

@app.route('/planilha', methods=['GET'])
def ler_planilha():
    caminho = 'dados.xlsx'
    if not os.path.exists(caminho):
        return jsonify({"erro": "Arquivo dados.xlsx não encontrado"}), 404
    
    try:
        df = pd.read_excel(caminho)
        dados = df.to_dict(orient='records')
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": "Falha ao ler a planilha"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)