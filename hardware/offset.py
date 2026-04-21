import time
import json
import os
from threading import Lock
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1
ads.data_rate = 128
chan = AnalogIn(ads, ADS.P0)
i2c_lock = Lock()

CONFIG_PATH = "configs.json"


def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {
        "cilindroAr": 0.03135,
        "alturaCilindro": 0.05,
        "diametroCilindro": 0.05,
        "pressaoAtmosferica": 95000,
        "offset": 0.0,
        "sensorSensibilidadeVPorKPa": 1.0,
        "pressaoCalibracaoPa": 1150,
        "pressaoInicioMinPa": 1000,
        "pressaoInicioMaxPa": 1100,
        "janelaEstabilidadeSegundos": 5,
        "oscilacaoMaximaPa": 20,
        "timeoutEstabilidadeSegundos": 60
    }


def _ler_tensao_com_retry(tentativas=3, pausa_erro=0.05):
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            with i2c_lock:
                return chan.voltage
        except Exception as e:
            ultimo_erro = e
            time.sleep(pausa_erro)
    raise RuntimeError(f"Falha ao ler tensão no ADS1115 durante calibração de offset: {ultimo_erro}")


def calcular_offset(numero_leituras=30, intervalo_leitura=0.1):
    """
    Calcula o offset pela média de leituras da tensão em repouso.
    Mantém a mesma dinâmica de leitura do sensor principal:
    - ADS1115 com mesmo ganho/data rate;
    - proteção com lock de I2C;
    - retry em cada leitura.
    """
    leituras = []
    for _ in range(numero_leituras):
        leituras.append(_ler_tensao_com_retry())
        time.sleep(intervalo_leitura)

    # Descarte simples de extremos para reduzir ruído eventual.
    leituras.sort()
    corte = max(1, int(len(leituras) * 0.1))
    leituras_filtradas = leituras[corte:-corte] if len(leituras) > 2 * corte else leituras

    return sum(leituras_filtradas) / len(leituras_filtradas)


def salvar_offset(offset):
    config = carregar_config()
    config["offset"] = offset

    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

    print(f"Offset de {offset} salvo com sucesso em 'configs.json'.")


def ajustar_offset():
    print("Ajustando o offset...")
    offset_calculado = calcular_offset()
    salvar_offset(offset_calculado)
    print(f"Novo offset calculado: {offset_calculado}")
