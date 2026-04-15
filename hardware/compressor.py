import time
import RPi.GPIO as GPIO
import json
import os
from hardware.sensor import get_pressure  # Usamos get_pressure para obter a pressão com o offset carregado de configs.json

rele_pin = 17
GPIO.setup(rele_pin, GPIO.OUT)
CONFIG_PATH = "configs.json"

def ativar_compressor():
    """Ativa o mini compressor (abre o relé)."""
    print("Ativando o mini compressor...")
    GPIO.output(rele_pin, GPIO.LOW)  # Envia sinal LOW para ligar o compressor (relé fechado)
    print("Compressor ativado.")

def desativar_compressor():
    """Desativa o mini compressor (fecha o relé)."""
    print("Desligando o mini compressor...")
    GPIO.output(rele_pin, GPIO.HIGH)  # Envia sinal HIGH para desligar o compressor (relé aberto)
    print("Compressor desativado.")

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "pressaoCalibracaoPa": 1150
    }


def calibrar_cilindro(pressao_alvo=None):
    """Calibra o cilindro em operação contínua do compressor até a pressão alvo."""
    config = carregar_config()
    alvo = pressao_alvo if pressao_alvo is not None else float(config.get("pressaoCalibracaoPa", 1150))
    print(f"Iniciando calibração do cilindro (alvo: {alvo} Pa)...")

    ativar_compressor()
    try:
        while True:
            pressao = get_pressure()
            print(f"Pressão Atual: {pressao} Pa")
            if pressao >= alvo:
                print(f"Pressão calibrada. Alvo de {alvo} Pa atingido.")
                break
            time.sleep(0.2)
    finally:
        desativar_compressor()
