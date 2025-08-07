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
            reda__Property_Type__c,
            reda__Region__c,
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
        nome = record.get("Name")
        tipo = record.get("reda__Property_Type__c")
        regiao = record.get("reda__Region__c")
        metragem = record.get("reda__Built_Area__c")
        iptu = record.get("PriceIptu__c")
        condominio = record.get("CondoExpenses__c")

        aluguel = None
        rent_setups = record.get("reda__Rent_Charge_Setups__r", {}).get("records", [])
        for rent in rent_setups:
            aluguel = rent.get("reda__New_Lease_Base_Amount__c")
            break

        dados.append({
            "Nome": nome,
            "Tipologia": tipo,
            "Região": regiao,
            "Metragem (m²)": metragem,
            "IPTU (R$)": iptu,
            "Condomínio (R$)": condominio,
            "Aluguel (R$)": aluguel
        })

    df = pd.DataFrame(dados)

    # Cria campo pacote_tab
    df["Pacote_Tab (R$)"] = (
        df["IPTU (R$)"].fillna(0) +
        df["Condomínio (R$)"].fillna(0) +
        df["Aluguel (R$)"].fillna(0)
    )

    # Remove tipologias inválidas
    tipologias_excluir = ["Are", "Chu", "Cow", "Pet", "Ret", "Sal", "Vag"]
    df = df[~df["Tipologia"].isin(tipologias_excluir)]

    # Agrupa e tira o menor valor de pacote por grupo
    agrupado = df.groupby(["Tipologia", "Região"]).agg({
        "Metragem (m²)": "min",
        "Pacote_Tab (R$)": "min"
    }).reset_index()

    # Retorna como JSON
    return jsonify(agrupado.to_dict(orient="records"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)