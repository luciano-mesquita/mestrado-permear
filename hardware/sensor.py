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
            "sensorVs": 5.0,
            "usarFormulaRatiometrica": True,
            "sensorSensibilidadeVPorKPa": 1.0,
            "fatorDivisorTensaoSensor": 1.0
        }

def calcular_pressao(voltage, offset, config=None):
    cfg = config or carregar_config()
    usar_ratiometrica = cfg.get("usarFormulaRatiometrica", True)

    if usar_ratiometrica:
        vs = float(cfg.get("sensorVs", 5.0))
        fator_divisor = float(cfg.get("fatorDivisorTensaoSensor", 1.0))
        if vs <= 0:
            raise ValueError("sensorVs inválido no configs.json")
        if fator_divisor <= 0:
            raise ValueError("fatorDivisorTensaoSensor inválido no configs.json")

        vout_sensor = voltage * fator_divisor
        voffset_sensor = offset * fator_divisor

        pressao_pa = ((((vout_sensor / vs) - 0.2) / 0.2) * 1000.0)
        pressao_offset_pa = ((((voffset_sensor / vs) - 0.2) / 0.2) * 1000.0)
        return pressao_pa - pressao_offset_pa

    sens = float(cfg.get("sensorSensibilidadeVPorKPa", sensibilidade))
    return ((voltage - offset) / sens) * 1000

def get_pressure():
    global ultima_pressao_valida

    config = carregar_config()
    offset_calibrado = carregar_offset()

    ultimo_erro = None
    for _ in range(3):
        try:
            with i2c_lock:
                voltagem = chan.voltage
            pressao = calcular_pressao(voltagem, offset_calibrado, config=config)
            return round(pressao, 10)
        except Exception as e:
            ultimo_erro = e
            time.sleep(0.05)

    raise RuntimeError(f"Falha ao ler pressão no ADS1115: {ultimo_erro}")


def get_pressure_display():
    return get_pressure()
