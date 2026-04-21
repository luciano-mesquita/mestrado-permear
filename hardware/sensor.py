import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import json
import os
from threading import Lock

i2c = busio.I2C(board.SCL, board.SDA)

ads = ADS.ADS1115(i2c)
ads.gain = 1
ads.data_rate = 128

chan = AnalogIn(ads, ADS.P0)
i2c_lock = Lock()

sensibilidade = 1.0

def carregar_offset():
    config = carregar_config()
    return config.get("offset", 0.0)

def carregar_config():
    CONFIG_PATH = "configs.json"
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    else:
        return {
            "cilindroAr": 0.03135,
            "alturaCilindro": 0.05,
            "diametroCilindro": 0.05,
            "pressaoAtmosferica": 95000,
            "offset": 0.0,  # Valor inicial do offset
            "sensorSensibilidadeVPorKPa": 1.0,
            "pressaoCalibracaoPa": 1150,
            "pressaoInicioMinPa": 1000,
            "pressaoInicioMaxPa": 1100,
            "janelaEstabilidadeSegundos": 5,
            "oscilacaoMaximaPa": 20,
            "timeoutEstabilidadeSegundos": 60
        }

def calcular_pressao(voltage, offset, config=None):
    cfg = config or carregar_config()
    sens = float(cfg.get("sensorSensibilidadeVPorKPa", sensibilidade))
    if sens <= 0:
        raise ValueError("sensorSensibilidadeVPorKPa inválido no configs.json")
    return ((voltage - offset) / sens) * 1000

def get_pressure():
    config = carregar_config()
    offset_calibrado = carregar_offset()
    numero_leituras = 7
    intervalo_leitura = 0.01
    leituras = []

    for _ in range(numero_leituras):
        ultimo_erro = None
        for _ in range(3):
            try:
                with i2c_lock:
                    voltagem = chan.voltage
                leituras.append(voltagem)
                break
            except Exception as e:
                ultimo_erro = e
                time.sleep(0.05)
        else:
            raise RuntimeError(f"Falha ao ler pressão no ADS1115: {ultimo_erro}")
        time.sleep(intervalo_leitura)

    leituras.sort()
    leitura_filtrada = sum(leituras[1:-1]) / len(leituras[1:-1])  # remove mínimo e máximo
    pressao = calcular_pressao(leitura_filtrada, offset_calibrado, config=config)
    return round(pressao, 10)


def get_pressure_display():
    return get_pressure()
