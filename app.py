from flask import Flask, render_template, request, jsonify, make_response
import pandas as pd
import io
import matplotlib

matplotlib.use('Agg')  # Configuração importante para evitar problemas de thread
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import base64
from collections import Counter
import numpy as np
import json

app = Flask(__name__)


# Custom JSON encoder para lidar com tipos numpy/pandas
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if pd.isna(obj):
            return None
        if isinstance(obj, (np.integer, np.floating)):
            return int(obj) if isinstance(obj, np.integer) else float(obj)
        return super().default(obj)


app.json_encoder = CustomJSONEncoder


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    try:
        # Determinar o tipo de arquivo
        filename = file.filename.lower()
        has_headers = request.form.get('hasHeaders') == 'true'

        if filename.endswith('.csv'):
            # Ler CSV
            df = pd.read_csv(file, header=0 if has_headers else None)
        elif filename.endswith(('.xls', '.xlsx')):
            # Ler Excel
            df = pd.read_excel(file, header=0 if has_headers else None)
        else:
            return jsonify({'error': 'Tipo de arquivo não suportado'}), 400

        # Processar os dados
        processed_data = process_data(df)

        # Gerar visualizações
        charts = generate_charts(processed_data)

        # Preparar resposta
        response_data = {
            'preview': df.head(5).replace({np.nan: None}).to_dict(orient='records'),
            'total_records': len(df),
            'analysis': processed_data,
            'charts': charts
        }

        # Criar resposta com o encoder customizado
        response = make_response(json.dumps(response_data, cls=CustomJSONEncoder))
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


def clean_numeric(value):
    """Função para limpar e converter valores numéricos"""
    if pd.isna(value):
        return 0
    try:
        # Remove caracteres não numéricos (exceto ponto decimal e sinal negativo)
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c in '.-')
        return float(cleaned) if cleaned else 0
    except:
        return 0


def process_data(df):
    """Processa os dados do DataFrame"""
    processed = []

    # Verifica se o DataFrame tem pelo menos 4 colunas
    if len(df.columns) < 4:
        raise ValueError("O arquivo deve conter pelo menos 4 colunas")

    for _, row in df.iterrows():
        try:
            # Limpa e converte o valor numérico
            valor = clean_numeric(row[3])

            item = {
                'localidade': str(row[0]) if pd.notna(row[0]) else 'N/A',
                'dimensao': 'Negativo' if 'neg' in str(row[1]).lower() else 'Positivo',
                'indicador': str(row[2]) if pd.notna(row[2]) else 'N/A',
                'valor': valor
            }
            processed.append(item)
        except Exception as e:
            print(f"Erro ao processar linha: {row}. Erro: {str(e)}")
            continue

    return processed


def generate_charts(data):
    """Gera gráficos baseados nos dados processados"""
    charts = {}

    try:
        # Gráfico de distribuição de dimensões
        dimension_counts = Counter([item['dimensao'] for item in data])

        fig, ax = plt.subplots()
        ax.pie(
            [dimension_counts['Positivo'], dimension_counts['Negativo']],
            labels=['Positivo', 'Negativo'],
            colors=['#4ade80', '#f87171'],
            autopct='%1.1f%%'
        )
        ax.axis('equal')

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        charts['dimension_chart'] = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)

        # Gráfico de distribuição de valores
        positive_values = [item['valor'] for item in data if item['dimensao'] == 'Positivo']
        negative_values = [abs(item['valor']) for item in data if item['dimensao'] == 'Negativo']

        fig, ax = plt.subplots()
        categories = ['Valores Positivos', 'Valores Negativos']

        avg_values = [
            sum(positive_values) / len(positive_values) if positive_values else 0,
            sum(negative_values) / len(negative_values) if negative_values else 0
        ]

        max_values = [
            max(positive_values) if positive_values else 0,
            max(negative_values) if negative_values else 0
        ]

        bar_width = 0.35
        x = range(len(categories))

        ax.bar(x, avg_values, bar_width, label='Valor Médio', color=['#4ade80', '#f87171'])
        ax.bar([i + bar_width for i in x], max_values, bar_width, label='Valor Máximo', color=['#86efac', '#fca5a5'])

        ax.set_xticks([i + bar_width / 2 for i in x])
        ax.set_xticklabels(categories)
        ax.legend()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        charts['value_chart'] = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)

    except Exception as e:
        print(f"Erro ao gerar gráficos: {str(e)}")
        charts = {
            'dimension_chart': '',
            'value_chart': ''
        }

    return charts


if __name__ == '__main__':
    app.run(debug=True)