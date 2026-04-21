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
SENSIBILIDADE_PADRAO_V_KPA = (4.9 - 1.0) / (3920.0 / 1000.0)  # ~0.9949 V/kPa


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
        "sensorSensibilidadeVPorKPa": SENSIBILIDADE_PADRAO_V_KPA,
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
    config = carregar_config()
    sens = float(config.get("sensorSensibilidadeVPorKPa", SENSIBILIDADE_PADRAO_V_KPA))
    if sens <= 0:
        raise ValueError("sensorSensibilidadeVPorKPa inválido no configs.json")

    # 1) Offset bruto por média aparada em zero pressão.
    offset_bruto = calcular_offset()

    # 2) Refino opcional usando o erro médio de pressão residual (sem clamp forçado).
    leituras_refino = []
    for _ in range(20):
        v = _ler_tensao_com_retry()
        pressao_residual_pa = ((v - offset_bruto) / sens) * 1000.0
        leituras_refino.append(pressao_residual_pa)
        time.sleep(0.05)

    erro_medio_pa = sum(leituras_refino) / len(leituras_refino)
    correcao_offset_v = (erro_medio_pa / 1000.0) * sens
    offset_calculado = offset_bruto + correcao_offset_v

    salvar_offset(offset_calculado)
    print(f"Offset bruto: {offset_bruto}")
    print(f"Erro médio residual: {erro_medio_pa:.4f} Pa")
    print(f"Novo offset calculado: {offset_calculado}")
