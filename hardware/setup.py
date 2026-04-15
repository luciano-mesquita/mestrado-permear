import RPi.GPIO as GPIO
import time

def configurar_hardware():
    GPIO.setmode(GPIO.BCM)
    
    rele_compressor_pin = 17
    rele_solenoide_pin = 18

    GPIO.setup(rele_compressor_pin, GPIO.OUT)
    GPIO.setup(rele_solenoide_pin, GPIO.OUT)

    GPIO.output(rele_compressor_pin, GPIO.HIGH)
    GPIO.output(rele_solenoide_pin, GPIO.HIGH)

    print("Compressor e solenoide inicializados desligados.")
    
def limpar_gpio():
    GPIO.cleanup()

if __name__ == "__main__":
    configurar_hardware()
    try:
        pass
    finally:
        limpar_gpio()
