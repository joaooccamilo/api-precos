from flask import Flask, jsonify
from simple_salesforce import Salesforce
import pandas as pd
import os

app = Flask(__name__)

# Conexão com o Salesforce
sf = Salesforce(
    username=os.environ.get("SF_USERNAME"),
    password=os.environ.get("SF_PASSWORD"),
    security_token=os.environ.get("SF_TOKEN"),
    domain="login"
)

@app.route("/precos", methods=["GET"])
def get_precos():
    query = """
        SELECT 
            Name,
            reda__Property_Type__r.Name,
            reda__Region__r.Name,
            reda__Built_Area__c,
            PriceIptu__c,
            CondoExpenses__c,
            (
                SELECT 
                    reda__New_Lease_Base_Amount__c
                FROM reda__Rent_Charge_Setups__r
            )
        FROM reda__Property__c
        WHERE reda__Leasing_Status__c = 'Vacant - Available'
    """

    results = sf.query_all(query)
    records = results["records"]

    dados = []
    for record in records:
        name = record.get("Name")
        tipo = record.get("reda__Property_Type__r", {}).get("Name")
        regiao = record.get("reda__Region__r", {}).get("Name")
        area = record.get("reda__Built_Area__c")
        iptu = record.get("PriceIptu__c")
        condominio = record.get("CondoExpenses__c")
        
        # Verifica se existe o relacionamento filho antes de acessar
        rent_setups_wrapper = record.get("reda__Rent_Charge_Setups__r")
        if rent_setups_wrapper and "records" in rent_setups_wrapper:
            for rent in rent_setups_wrapper["records"]:
                aluguel = rent.get("reda__New_Lease_Base_Amount__c")
                dados.append({
                    "Nome": name,
                    "Tipo": tipo,
                    "Região": regiao,
                    "Área (m²)": area,
                    "IPTU (R$)": iptu,
                    "Condomínio (R$)": condominio,
                    "Aluguel (R$)": aluguel
                })
        else:
            # Caso não haja setup de aluguel, ainda adiciona o imóvel
            dados.append({
                "Nome": name,
                "Tipo": tipo,
                "Região": regiao,
                "Área (m²)": area,
                "IPTU (R$)": iptu,
                "Condomínio (R$)": condominio,
                "Aluguel (R$)": None
            })

    df = pd.DataFrame(dados)

    df["Pacote_tab"] = (
        df["IPTU (R$)"].fillna(0) +
        df["Condomínio (R$)"].fillna(0) +
        df["Aluguel (R$)"].fillna(0)
    )

    # # Cria a coluna 'regiao' com base nas 3 primeiras letras da unidade
    # df['Nome'] = df['unidade'].str[:3].str.upper().replace({
    #     'BEL': 'Bela Vista',
    #     'ITA': 'Itaim Bibi',
    #     'ITU': 'Alameda Itu',
    #     'MEL': 'Melo Alves',
    #     'PAP': 'Paraiso Paulista',
    #     'PAR': 'Paraiso',
    #     'CAP': 'Capote Valente',
    #     'VMD': 'Vila Madalena',
    #     'PIN': 'Pinheiros',
    #     'VMR': 'Vila Mariana',
    #     'FRE': 'Frei Caneca'
    # })
    
    # Coluna auxiliar para agrupamento: 7 primeiras letras da tipologia
    df['tipologia_resumida'] = df['Tipo'].astype(str).str[:3]
    
    # Converte 'área' para texto sem arredondar
    df['área'] = df['Área (m²)'].astype(str)
    
    # Renomeia a coluna 'pacote_tabela' para 'valor'
    df['valor'] = df['Pacote_tab']

    # Lista de tipologias a excluir
    tipologias_excluir = ["Are", "Chu", "Cow", "Pet", "Ret", "Sal", "Vag"]
    
    # Filtra apenas as colunas relevantes
    df_filtrado = df[['Tipo', 'tipologia_resumida', 'Região', 'área', 'valor']]
    
    # Seleciona a tipologia completa correspondente ao menor valor por grupo
    # Remove linhas com valor nulo em 'valor'
    df_filtrado = df_filtrado.dropna(subset=['valor'])
    
    # Recalcula o índice do menor valor
    idx_min = df_filtrado.groupby(['tipologia_resumida', 'Região'])['valor'].idxmin()
    
    # Seleciona os registros correspondentes
    agrupado = df_filtrado.loc[idx_min].copy()
    
    
    # Aplica substituições para nomes amigáveis
    agrupado['tipologia'] = agrupado['tipologia_resumida'].replace({
        'Stu': 'Studio',
        'stu': 'Studio',
        '1 D': '1 dormitorio',
        '2 D': '2 dormitorios',
        '3 D': '3 dormitorios',
        '4 D': '4 dormitorios',
        '5 D': '5 dormitorios',
        '1 d': '1 dormitorio',
        '2 d': '2 dormitorios',
        '3 d': '3 dormitorios',
        '4 d': '4 dormitorios',
        '5 d': '5 dormitorios',
        'Lof': 'Loft',
        'lof': 'Loft',
        'Cob': 'Cobertura',
        'Dup': 'Duplex'
        # Pode expandir conforme necessário
    }, regex=True)

    # Remove as linhas que têm esses valores na coluna "Tipologia"
    agrupado = agrupado[~agrupado["tipologia"].isin(tipologias_excluir)]
    
    # Remove a coluna auxiliar
    agrupado = agrupado[['tipologia', 'Região', 'área', 'valor']]
    
    # Ordena por valor
    agrupado = agrupado.sort_values(by='valor').reset_index(drop=True)

    # Retorna como JSON
    return jsonify(agrupado.to_dict(orient="records"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)