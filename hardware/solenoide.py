import time
import RPi.GPIO as GPIO
from hardware.sensor import get_pressure  # Para acessar a leitura de pressão

solenoide_pin = 18 
GPIO.setup(solenoide_pin, GPIO.OUT)

def abrir_solenoide():
    print("Abrindo a válvula solenoide...")
    GPIO.output(solenoide_pin, GPIO.LOW)
    print("Válvula solenoide aberta.")

def fechar_solenoide():
    print("Fechando a válvula solenoide...")
    GPIO.output(solenoide_pin, GPIO.HIGH)
    print("Válvula solenoide fechada.")

def esvaziar_cilindro():
    print("Abrindo a válvula solenoide...")
    abrir_solenoide()
    time.sleep(5)
    fechar_solenoide()

def controlar_solenoide():
    while True:
        pressao = get_pressure()
        print(f"Pressão atual: {pressao} Pa")

        if pressao > 0:
            abrir_solenoide()
        elif pressao <= 0:
            fechar_solenoide()
            break

        time.sleep(1)  # Atualiza a cada 1 segundo
