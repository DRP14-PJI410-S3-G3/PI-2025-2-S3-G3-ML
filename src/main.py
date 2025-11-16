import joblib
import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import Error
import sys
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text

load_dotenv() 

DB_HOST = os.getenv("DB_HOST")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SOCKET = os.getenv("DB_SOCKET")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

db_url = None

if DB_SOCKET:
    db_url = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@/{DB_DATABASE}"
        f"?unix_socket={DB_SOCKET}"
    )
elif DB_HOST:
    db_url = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_DATABASE}"
    )
else:
    sys.exit()

try:
    engine = create_engine(
        db_url,
        pool_size=DB_POOL_SIZE
    )
    
except Exception as e:
    sys.exit()

# --- Queries ---
# A query de SELECT pode ser uma string normal
select_query = """
SELECT `id`, `mp10`, `mp25`, `co`, `nox`, `vehicles`, `created_at` 
FROM `cetesb_emissions_vehicles_osasco` 
WHERE `created_at` < %s 
ORDER BY `created_at` DESC 
LIMIT 25;
"""

# Para o INSERT, é boa prática envolvê-la na função text()
insert_query = text("""
INSERT INTO previsoes_poluicao 
(id_registro_base, previsao_co_t1, previsao_co_t2, previsao_co_t3, data_previsao) 
VALUES (:id_base, :p_t1, :p_t2, :p_t3, :p_date)
""")

# --- 2. Carregar Modelos na Inicialização ---
try:
    model_co = joblib.load('./models/co/model.joblib')
    scaler_co_x = joblib.load('./models/co/scaler_x.joblib')
    scaler_co_y = joblib.load('./models/co/scaler_y.joblib')
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit()

try:
    model_mp10 = joblib.load('./models/mp10/model.joblib')
    scaler_mp10_x = joblib.load('./models/mp10/scaler_x.joblib')
    scaler_mp10_y = joblib.load('./models/mp10/scaler_y.joblib')
except FileNotFoundError as e:
    print(f"Error : {e}")
    sys.exit()

try:
    model_nox = joblib.load('./models/nox/model.joblib')
    scaler_nox_x = joblib.load('./models/nox/scaler_x.joblib')
    scaler_nox_y = joblib.load('./models/nox/scaler_y.joblib')
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit()

try:
    model_mp25 = joblib.load('./models/mp25/model.joblib')
    #scaler_mp25_x = joblib.load('./models/mp25/scaler_x.pkl')
    #scaler_mp25_y = joblib.load('./models/mp25/scaler_y.pkl')
except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit()

# --- 3. Inicializar FastAPI ---
app = FastAPI(
    title="API de Previsão de Poluição",
    description=""
)

def get_prediction_from_db(base_timestamp: str):
    with engine.connect() as connection:
        try:
            df_entrada = pd.read_sql(select_query, connection, params=(base_timestamp,))
            
            if len(df_entrada) < 25:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Dados insuficientes. A query retornou {len(df_entrada)} linhas. Necessário: 25."
                )

            df_entrada['created_at'] = pd.to_datetime(df_entrada['created_at'])
            df_entrada = df_entrada.sort_values(by='created_at', ascending=False)
            
            if 'vehicles' in df_entrada.columns:
                df_entrada = df_entrada.rename(columns={'vehicles': 'Fluxo_Veiculos'})

            registro_t = df_entrada.iloc[0]
            id_base = int(registro_t['id'])
            date_base = registro_t['created_at'].isoformat()

            base_features = [
                registro_t['id'], registro_t['mp10'], registro_t['mp25'],
                registro_t['co'], registro_t['nox'], registro_t['Fluxo_Veiculos'],
                registro_t['created_at'].hour, registro_t['created_at'].weekday()
            ]
            lag_co_features = list(df_entrada['co'].iloc[1:25])
            lag_fluxo_features = list(df_entrada['Fluxo_Veiculos'].iloc[0:25])
            
            novos_dados_lista = base_features + lag_co_features + lag_fluxo_features
            
            if len(novos_dados_lista) != 57:
                raise HTTPException(status_code=500, detail="Erro interno: Vetor de features incompleto.")
                
            novos_dados_np = np.array([novos_dados_lista])

            dados_normalizados = scaler_co_x.transform(novos_dados_np)
            predicao_normalizada = model_co.predict(dados_normalizados)
            predicao_real = scaler_co_y.inverse_transform(predicao_normalizada)
            
            pred_t1, pred_t2, pred_t3 = predicao_real[0]

            dados_para_inserir = {
                "id_base": id_base, 
                "p_t1": float(pred_t1),
                "p_t2": float(pred_t2),
                "p_t3": float(pred_t3),
                "p_date": date_base,
            }
            
            connection.execute(insert_query, dados_para_inserir)
            connection.commit()
            
            return {
                "status": "sucesso",
                "mensagem": "Predição realizada e salva no banco.",
                "dados": {
                    "id_registro_base": id_base,
                    "timestamp_base": registro_t['created_at'].isoformat(),
                    "previsao_co_t1": float(pred_t1),
                    "previsao_co_t2": float(pred_t2),
                    "previsao_co_t3": float(pred_t3)
                }
            }
        
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Erro na execução da predição: {str(e)}")

@app.get("/predict/")
async def create_prediction(timestamp: str):
    return get_prediction_from_db(timestamp)

@app.get("/")
def read_root():
    return {"status": "API Online", "mode": "GET"}