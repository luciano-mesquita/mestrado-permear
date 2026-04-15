import time
import json
import os
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, ADS.P0)

CONFIG_PATH = "configs.json"

def calcular_offset():
    numero_leituras = 10
    soma_leituras = 0.0
    intervalo_leitura = 0.1  # Intervalo de 100 ms entre as leituras

    for _ in range(numero_leituras):
        voltagem = chan.voltage
        soma_leituras += voltagem
        time.sleep(intervalo_leitura)
        
    offset = soma_leituras / numero_leituras
    return offset

def salvar_offset(offset):
    config = carregar_config()
    config["offset"] = offset
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    
    print(f"Offset de {offset} salvo com sucesso em 'configs.json'.")

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    else:
        return {
            "cilindroAr": 0.03135,
            "alturaCilindro": 0.05,
            "diametroCilindro": 0.05,
            "pressaoAtmosferica": 95000,
            "offset": 0.0  # Valor inicial do offset
        }

def ajustar_offset():
    print("Ajustando o offset...")

    offset_calculado = calcular_offset()

    salvar_offset(offset_calculado)

    print(f"Novo offset calculado: {offset_calculado}")
