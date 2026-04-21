# Permear

Sistema para medição de permeabilidade intrínseca do solo ao ar, executado em Raspberry Pi 3 com interface web em Flask.

## Componentes de hardware

- Sensor de pressão MPXV5004DP
- Conversor ADS1115 (16 bits)
- Minicompressor 12 V / 0,5 A
- Válvula solenoide 12 V / 0,5 A
- Módulo relé optoacoplado de 2 canais
- Cilindro de ar
- Raspberry Pi 3

## Pilha de software

- Python
- Flask
- Serviços de controle de hardware em `hardware/`
- Automação e aquisição de dados em `services/`

## Fluxo de medição

1. O usuário inicia a medição pela interface web.
2. O cilindro é calibrado para **1,15 kPa** (`pressaoCalibracaoPa = 1150` Pa), para compensar a redução durante a estabilização.
3. A válvula solenoide é aberta para forçar passagem de ar pela amostra de solo.
4. A pressão é lida em intervalos de 1 segundo.
5. Os dados são salvos em planilha `.ods` com a fórmula para cálculo da permeabilidade.

## Modos disponíveis

### Modo manual

Sequência típica na interface:

1. **Ajustar Offset**
2. **Calibrar Cilindro**
3. **Iniciar Medição**
4. **Finalizar Medição**

### Modo automático

A aplicação executa a sequência completa automaticamente:

- esvaziamento inicial;
- ajuste de offset;
- calibração de pressão;
- estabilização;
- coleta de dados;
- cálculo da permeabilidade e gravação na planilha.

## Execução

```bash
pip install -r requirements.txt
python app.py
```

A interface ficará disponível no host configurado para o Flask.
