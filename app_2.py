import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import urllib3
import os
import pandas as pd
from flask_caching import Cache

def conectar_banco():
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_bd = os.path.join(pasta_atual, 'banco_tcc.db')
    
    conn = sqlite3.connect(caminho_bd)
    conn.row_factory = sqlite3.Row 
    return conn

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 86400})

# ==========================================
# ROTA 1: DESPESAS MUNICIPAIS (SQLITE)
# ==========================================
@app.route('/api/despesas', methods=['GET'])
def listar_despesas():
    ano = request.args.get('ano')
    mes = request.args.get('mes')

    if not ano: 
        return jsonify({"dados": [], "erro": "Selecione o ano"})

    despesas_formatadas = []
    
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        if mes:
            mes_formatado = str(mes).zfill(2) 
            query = """
                SELECT DISTINCT 
                    data_lancamento, 
                    categoria, 
                    fornecedor_origem, 
                    descricao, 
                    valor 
                FROM Despesas 
                WHERE ano = ? AND mes = ?
            """
            cursor.execute(query, (ano, mes_formatado))
            
            for linha in cursor.fetchall():
                despesas_formatadas.append({
                    "data": str(linha['data_lancamento']),
                    "categoria": str(linha['categoria']),
                    "fornecedor": str(linha['fornecedor_origem']),
                    "descricao": str(linha['descricao']),
                    "valor": float(linha['valor'])
                })
        else:
            query = """
                SELECT mes, SUM(valor) as total 
                FROM (
                    SELECT DISTINCT 
                        data_lancamento, 
                        categoria, 
                        fornecedor_origem, 
                        descricao, 
                        valor, 
                        mes 
                    FROM Despesas 
                    WHERE ano = ?
                )
                GROUP BY mes ORDER BY mes
            """
            cursor.execute(query, (ano,))
            
            for linha in cursor.fetchall():
                despesas_formatadas.append({
                    "categoria": "Resumo",
                    "fornecedor": "-",
                    "data": f"{ano}-{linha['mes']}-01",
                    "descricao": f"Total consolidado de {linha['mes']}/{ano}",
                    "valor": float(linha['total'])
                })

        conexao.close()
    except Exception as e:
        print(f"Erro ao buscar dados no banco de dados (Despesas): {e}")

    return jsonify({"dados": despesas_formatadas})


# ==========================================
# ROTA 2: RECEITAS MUNICIPAIS (SQLITE)
# ==========================================
@app.route('/api/receitas', methods=['GET'])
def listar_receitas():
    ano = request.args.get('ano')
    mes = request.args.get('mes')

    if not ano: 
        return jsonify({"dados": [], "erro": "Selecione o ano"})

    receitas_formatadas = []
    
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        if mes:
            mes_formatado = str(mes).zfill(2)
            query = """
                SELECT DISTINCT 
                    data_lancamento, 
                    categoria, 
                    fornecedor_origem, 
                    descricao, 
                    valor 
                FROM Receitas 
                WHERE ano = ? AND mes = ?
            """
            cursor.execute(query, (ano, mes_formatado))
            
            for linha in cursor.fetchall():
                receitas_formatadas.append({
                    "data": str(linha['data_lancamento']),
                    "categoria": str(linha['categoria']),
                    "fornecedor": str(linha['fornecedor_origem']),
                    "descricao": str(linha['descricao']),
                    "valor": float(linha['valor'])
                })
        else:
            query = """
                SELECT mes, SUM(valor) as total 
                FROM (
                    SELECT DISTINCT 
                        data_lancamento, 
                        categoria, 
                        fornecedor_origem, 
                        descricao, 
                        valor, 
                        mes 
                    FROM Receitas 
                    WHERE ano = ?
                )
                GROUP BY mes ORDER BY mes
            """
            cursor.execute(query, (ano,))
            
            for linha in cursor.fetchall():
                receitas_formatadas.append({
                    "categoria": "Resumo",
                    "fornecedor": "-",
                    "data": f"{ano}-{linha['mes']}-01",
                    "descricao": f"Total arrecadado de {linha['mes']}/{ano}",
                    "valor": float(linha['total'])
                })

        conexao.close()
    except Exception as e:
        print(f"Erro ao buscar dados no banco de dados (Receitas): {e}")

    return jsonify({"dados": receitas_formatadas})


# ==========================================
# ROTA 3: BUSCA DE PREFEITOS (SEADE)
# ==========================================
@app.route('/api/prefeito', methods=['GET'])
def buscar_prefeito():
    ano_selecionado = request.args.get('ano')
    if not ano_selecionado:
        return jsonify({"erro": "Ano não informado"}), 400
        
    ano = int(ano_selecionado)
    ano_base = ano - (ano % 4)
    periodo_mandato = f"{ano_base} a {ano_base + 3}"
    nome_prefeito = ""
    
    try:
        url_seade = "https://produtos.seade.gov.br/produtos/eleicoes/candidatos/index.php?page=ele_sel"
        payload = {'ano': ano_base, 'cargo': '11', 'mun': '3505500'}
        
        resposta = requests.post(url_seade, data=payload, verify=False, timeout=3)
        sopa = BeautifulSoup(resposta.text, 'html.parser')
        
        for td in sopa.find_all('td'):
            texto_celula = td.get_text(strip=True)
            if texto_celula.startswith("1") and "-" in texto_celula:
                partes = texto_celula.split('-')
                if len(partes) >= 2:
                    nome_prefeito = partes[1].strip().title()
                    break
    except Exception as e:
        print(f"SEADE falhou ou bloqueou a requisição: {e}")

    if not nome_prefeito or nome_prefeito == "Não localizado":
        prefeitos_barretos = {
            2008: "Emanoel Mariano Carvalho",
            2012: "Guilherme Henrique de Ávila",
            2016: "Guilherme Henrique de Ávila",
            2020: "Paula Lemos",
            2024: "Odair de Moura e Silva" 
        }
        nome_prefeito = prefeitos_barretos.get(ano_base, "Registro Histórico Indisponível")
        
    return jsonify({
        "prefeito": nome_prefeito,
        "periodo": periodo_mandato,
        "ano_eleicao": ano_base
    })


# ==========================================
# ROTA 4: SALÁRIOS DOS SERVIDORES (SQLITE)
# ==========================================
@app.route('/api/servidores', methods=['GET'])
def listar_servidores():
    draw = request.args.get('draw', type=int, default=1)
    start = request.args.get('start', type=int, default=0)
    length = request.args.get('length', type=int, default=25)
    search_value = request.args.get('search[value]', default='')

    coluna_index = request.args.get('order[0][column]', '1') 
    direcao = request.args.get('order[0][dir]', 'asc')       

    mapa_colunas = {
        '0': 'mes',
        '1': 'nome',
        '2': 'cargo',
        '3': 'salario'
    }
    
    coluna_sql = mapa_colunas.get(coluna_index, 'nome')
    if direcao not in ['asc', 'desc']:
        direcao = 'asc'

    ano = request.args.get('ano')
    mes = request.args.get('mes')
    cargo = request.args.get('cargo')

    if not ano:
        return jsonify({"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": [], "erro": "Selecione o ano"})

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        # CORREÇÃO 1: Garante que o ano é tratado como texto (impede erros de tipagem)
        filtros_sql = "CAST(ano AS TEXT) = ?"
        parametros = [str(ano)]

        # CORREÇÃO 2: Força maiúsculas (UPPER) para ignorar diferenças de texto no SQLite
        if mes and mes.lower() != 'todos os meses':
            filtros_sql += " AND UPPER(mes) = UPPER(?)"
            parametros.append(mes)

        if cargo:
            filtros_sql += " AND UPPER(cargo) LIKE UPPER(?)"
            parametros.append(f"%{cargo}%")

        query_total = f"SELECT COUNT(*) FROM (SELECT DISTINCT nome, cargo, salario, mes, ano FROM Servidores WHERE {filtros_sql})"
        cursor.execute(query_total, parametros)
        recordsTotal = cursor.fetchone()[0]

        if search_value:
            filtros_sql += " AND (UPPER(nome) LIKE UPPER(?) OR UPPER(cargo) LIKE UPPER(?))"
            parametros.extend([f"%{search_value}%", f"%{search_value}%"])

        query_filtered = f"SELECT COUNT(*) FROM (SELECT DISTINCT nome, cargo, salario, mes, ano FROM Servidores WHERE {filtros_sql})"
        cursor.execute(query_filtered, parametros)
        recordsFiltered = cursor.fetchone()[0]

        if coluna_sql == 'mes':
            # Ajuste de UPPER também na ordenação
            coluna_ordenacao = """CASE UPPER(mes) 
                WHEN 'JANEIRO' THEN 1 WHEN 'FEVEREIRO' THEN 2 WHEN 'MARÇO' THEN 3 
                WHEN 'ABRIL' THEN 4 WHEN 'MAIO' THEN 5 WHEN 'JUNHO' THEN 6 
                WHEN 'JULHO' THEN 7 WHEN 'AGOSTO' THEN 8 WHEN 'SETEMBRO' THEN 9 
                WHEN 'OUTUBRO' THEN 10 WHEN 'NOVEMBRO' THEN 11 WHEN 'DEZEMBRO' THEN 12 
                ELSE 99 END"""
        else:
            coluna_ordenacao = coluna_sql

        if length == -1:
            query = f"""
                SELECT nome, cargo, salario, mes, ano 
                FROM Servidores 
                WHERE {filtros_sql} 
                GROUP BY nome, cargo, salario, mes, ano
                ORDER BY {coluna_ordenacao} {direcao}, nome ASC
            """
            cursor.execute(query, parametros)
        else:
            query = f"""
                SELECT nome, cargo, salario, mes, ano 
                FROM Servidores 
                WHERE {filtros_sql} 
                GROUP BY nome, cargo, salario, mes, ano
                ORDER BY {coluna_ordenacao} {direcao}, nome ASC 
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, parametros + [length, start])
        
        servidores_formatados = []
        for linha in cursor.fetchall():
            # CORREÇÃO 3: Filtro anti-falha para salários formatados como texto na migração
            valor_salario = linha['salario']
            try:
                if isinstance(valor_salario, str):
                    valor_salario = valor_salario.replace('.', '').replace(',', '.')
                salario_float = float(valor_salario)
            except:
                salario_float = 0.0

            servidores_formatados.append({
                "nome": str(linha['nome']),
                "cargo": str(linha['cargo']),
                "salario": salario_float,
                "mes": str(linha['mes']),
                "ano": str(linha['ano'])
            })

        conexao.close()

        return jsonify({
            "draw": draw,
            "recordsTotal": recordsTotal,
            "recordsFiltered": recordsFiltered,
            "data": servidores_formatados
        })

    except Exception as e:
        print(f"Erro na busca ao banco de dados (Servidores): {e}")
        return jsonify({"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": [], "erro": str(e)})


# ==========================================
# ROTA 5: RAIO-X DO FORNECEDOR / CIDADÃO (SQLITE)
# ==========================================
@app.route('/api/raiox', methods=['GET'])
def buscar_raiox():
    termo = request.args.get('termo')
    
    if not termo or len(termo.strip()) < 3:
        return jsonify({"dados": [], "erro": "Digite pelo menos 3 caracteres."})
        
    termo_busca = f"%{termo.strip()}%"
    historico_completo = []
    
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        query_despesas = """
            SELECT data_lancamento, 
                   categoria, 
                   fornecedor_origem AS fornecedor, 
                   descricao, 
                   valor 
            FROM Despesas 
            WHERE fornecedor_origem LIKE ?
        """
        cursor.execute(query_despesas, (termo_busca,))
        for linha in cursor.fetchall():
            historico_completo.append({
                "data": str(linha['data_lancamento']),
                "tipo": "Recebimento (A Prefeitura pagou)",
                "categoria": str(linha['categoria']),
                "fornecedor": str(linha['fornecedor']),
                "descricao": str(linha['descricao']),
                "valor": float(linha['valor']),
                "natureza": "despesa_publica"
            })

        query_receitas = """
            SELECT data_lancamento, 
                   categoria, 
                   fornecedor_origem AS fornecedor, 
                   descricao, 
                   valor 
            FROM Receitas 
            WHERE fornecedor_origem LIKE ?
        """
        cursor.execute(query_receitas, (termo_busca,))
        for linha in cursor.fetchall():
            historico_completo.append({
                "data": str(linha['data_lancamento']),
                "tipo": "Pagamento (A Prefeitura arrecadou)",
                "categoria": str(linha['categoria']),
                "fornecedor": str(linha['fornecedor']),
                "descricao": str(linha['descricao']),
                "valor": float(linha['valor']),
                "natureza": "receita_publica"
            })

        conexao.close()
        
    except Exception as e:
        print(f"Erro ao buscar dados no banco de dados (Raio-X): {e}")
        return jsonify({"dados": [], "erro": "Falha ao conectar com o banco de dados."})

    return jsonify({"dados": historico_completo})


# ==========================================
# ROTA 6: OBRAS PÚBLICAS (CSV)
# ==========================================
@app.route('/api/obras', methods=['GET'])
@cache.cached(timeout=3600) 
def listar_obras():
    try:
        # ATENÇÃO: Quando for subir para o PythonAnywhere, altere este caminho para './obras.csv'
        caminho_obras = r"C:\Users\gpatr\OneDrive\(#5) Gabriel Patricio Soares - 82317440\Backend\Obras\obras.csv"
        
        if not os.path.exists(caminho_obras):
            return jsonify({"dados": [], "erro": f"O ficheiro obras.csv não foi encontrado."})
            
        df_obras = pd.read_csv(caminho_obras, sep=';', encoding='utf-8', on_bad_lines='skip', dtype=str)
        df_obras.columns = df_obras.columns.str.strip()
        df_obras = df_obras.fillna('-')
        
        obras_formatadas = []
        for index, row in df_obras.iterrows():
            valor_bruto = str(row.get('Valor do Contrato', '0'))
            valor_limpo = valor_bruto.replace('.', '').replace(',', '.')
            try:
                valor_float = float(valor_limpo)
            except:
                valor_float = 0.0
                
            obras_formatadas.append({
                "situacao": str(row.get('Situação', '-')).strip(),
                "ano": str(row.get('Ano do Contrato', '-')).strip(),
                "empresa": str(row.get('Contratada', '-')).strip(),
                "cnpj": str(row.get('CNPJ da Contratada', '-')).strip(),
                "descricao": str(row.get('Descrição da Obra', '-')).strip(),
                "valor": valor_float
            })
            
        return jsonify({"dados": obras_formatadas})
        
    except Exception as e:
        print(f"Erro ao processar obras.csv: {e}")
        return jsonify({"dados": [], "erro": "Erro interno ao ler o arquivo de obras."})


# ==========================================
# ROTA: RAIO-X PAGINADO (SERVER-SIDE DATATABLES - SQLITE)
# ==========================================
@app.route('/api/raiox_paginado', methods=['GET'])
def raiox_paginado():
    try:
        draw = int(request.args.get('draw', 1)) 
        inicio = int(request.args.get('start', 0)) 
        quantidade = int(request.args.get('length', 25)) 
        
        termo = request.args.get('termo', '').strip()

        if len(termo) < 3:
            return jsonify({"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": []})

        conexao = conectar_banco()
        cursor = conexao.cursor()

        query_count = """
            SELECT COUNT(*) 
            FROM Despesas 
            WHERE fornecedor_origem LIKE ? OR cnpj_fornecedor LIKE ?
        """
        termo_sql = f"%{termo}%"
        cursor.execute(query_count, (termo_sql, termo_sql))
        total_registos = cursor.fetchone()[0]

        query_dados = """
            SELECT data_lancamento, fornecedor_origem, categoria, valor, descricao 
            FROM Despesas 
            WHERE fornecedor_origem LIKE ? OR cnpj_fornecedor LIKE ?
            ORDER BY data_lancamento DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_dados, (termo_sql, termo_sql, quantidade, inicio))
        linhas = cursor.fetchall()

        dados_formatados = []
        for linha in linhas:
            dados_formatados.append({
                "data": str(linha['data_lancamento']), 
                "tipo": "Pagamento Efetuado",
                "fornecedor": str(linha['fornecedor_origem']),
                "categoria": str(linha['categoria']),
                "descricao": str(linha['descricao']),
                "valor": float(linha['valor'])
            })

        conexao.close()

        return jsonify({
            "draw": draw,
            "recordsTotal": total_registos, 
            "recordsFiltered": total_registos, 
            "data": dados_formatados 
        })

    except Exception as e:
        print(f"Erro na paginação do Raio-X: {e}")
        return jsonify({"draw": int(request.args.get('draw', 1)), "recordsTotal": 0, "recordsFiltered": 0, "data": []})


# ==========================================
# ROTA: DESPESAS PAGINADAS (SERVER-SIDE - SQLITE)
# ==========================================
@app.route('/api/despesas_paginado', methods=['GET'])
def despesas_paginadas():
    try:
        draw = int(request.args.get('draw', 1))
        inicio = int(request.args.get('start', 0))
        quantidade = int(request.args.get('length', 25))
        
        busca = request.args.get('search[value]', '').strip()
        
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        filtro_sql = ""
        parametros = []
        if busca:
            filtro_sql = " WHERE fornecedor_origem LIKE ? OR categoria LIKE ? OR descricao LIKE ?"
            busca_like = f"%{busca}%"
            parametros = [busca_like, busca_like, busca_like]
            
        cursor.execute(f"SELECT COUNT(*) FROM Despesas {filtro_sql}", parametros)
        total_filtrado = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Despesas")
        total_absoluto = cursor.fetchone()[0]
        
        query_dados = f"""
            SELECT data_lancamento, fornecedor_origem, categoria, valor, descricao 
            FROM Despesas 
            {filtro_sql}
            ORDER BY data_lancamento DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_dados, parametros + [quantidade, inicio])
        linhas = cursor.fetchall()
        
        dados_formatados = []
        for linha in linhas:
            dados_formatados.append({
                "data": str(linha['data_lancamento']),
                "fornecedor": str(linha['fornecedor_origem']),
                "categoria": str(linha['categoria']),
                "descricao": str(linha['descricao']),
                "valor": float(linha['valor'])
            })
            
        conexao.close()
        
        return jsonify({
            "draw": draw,
            "recordsTotal": total_absoluto,
            "recordsFiltered": total_filtrado,
            "data": dados_formatados
        })
        
    except Exception as e:
        print(f"Erro nas despesas paginadas: {e}")
        return jsonify({"draw": int(request.args.get('draw', 1)), "recordsTotal": 0, "recordsFiltered": 0, "data": []})


# ==========================================
# ROTA: RECEITAS PAGINADAS (SERVER-SIDE - SQLITE)
# ==========================================
@app.route('/api/receitas_paginado', methods=['GET'])
def receitas_paginadas():
    try:
        draw = int(request.args.get('draw', 1))
        inicio = int(request.args.get('start', 0))
        quantidade = int(request.args.get('length', 25))
        
        busca = request.args.get('search[value]', '').strip()
        
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        filtro_sql = ""
        parametros = []
        if busca:
            filtro_sql = " WHERE fornecedor_origem LIKE ? OR categoria LIKE ?"
            busca_like = f"%{busca}%"
            parametros = [busca_like, busca_like]
            
        cursor.execute(f"SELECT COUNT(*) FROM Receitas {filtro_sql}", parametros)
        total_filtrado = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Receitas")
        total_absoluto = cursor.fetchone()[0]
        
        query_dados = f"""
            SELECT data_lancamento, fornecedor_origem, categoria, valor 
            FROM Receitas 
            {filtro_sql}
            ORDER BY data_lancamento DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_dados, parametros + [quantidade, inicio])
        linhas = cursor.fetchall()
        
        dados_formatados = []
        for linha in linhas:
            dados_formatados.append({
                "data": str(linha['data_lancamento']),
                "origem": str(linha['fornecedor_origem']),
                "categoria": str(linha['categoria']),
                "valor": float(linha['valor'])
            })
            
        conexao.close()
        
        return jsonify({
            "draw": draw,
            "recordsTotal": total_absoluto,
            "recordsFiltered": total_filtrado,
            "data": dados_formatados
        })
        
    except Exception as e:
        print(f"Erro nas receitas paginadas: {e}")
        return jsonify({"draw": int(request.args.get('draw', 1)), "recordsTotal": 0, "recordsFiltered": 0, "data": []})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)