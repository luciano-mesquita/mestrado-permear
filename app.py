from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from datetime import datetime
from threading import Thread, Lock
import time
import os
import subprocess
import atexit
from odf.opendocument import OpenDocumentSpreadsheet, load
from odf.table import Table, TableRow, TableCell
from odf.text import P
import json
import math
import copy
from scipy.stats import linregress
from hardware.compressor import calibrar_cilindro
from hardware.offset import ajustar_offset
from hardware.solenoide import esvaziar_cilindro, abrir_solenoide, fechar_solenoide
from hardware.setup import configurar_hardware, limpar_gpio
from services.sensor_service import sensor_service
from services.automation_service import executar_sequencia_automatica

limpar_gpio()
configurar_hardware()
sensor_service.start()
atexit.register(sensor_service.stop)

app = Flask(__name__)

dados_medicao = []
medindo = False
planilha_nome = ""
metadados = {}  # <-- metadados adicionados
lock = Lock()
estado_processo = {
    "etapa": "Sistema pronto",
    "mensagem": "Aguardando comando do usuário.",
    "modo": "idle",
    "em_execucao": False,
    "erro": False,
    "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}


def atualizar_status(etapa, mensagem, modo=None, em_execucao=None, erro=False):
    with lock:
        estado_processo["etapa"] = etapa
        estado_processo["mensagem"] = mensagem
        estado_processo["erro"] = erro
        estado_processo["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if modo is not None:
            estado_processo["modo"] = modo
        if em_execucao is not None:
            estado_processo["em_execucao"] = em_execucao


def ler_pressao_atual():
    """Fonte única de pressão para rotas e automação (cache do SensorService)."""
    return sensor_service.get_latest_pressure()


def aguardar_pressao_estavel(config):
    """
    Considera pressão estável quando:
    - todas as leituras na janela estão no intervalo [min, max]
    - oscilação (máx - mín) é menor/igual ao limite configurado.
    """
    pressao_min = float(config.get("pressaoInicioMinPa", 1000))
    pressao_max = float(config.get("pressaoInicioMaxPa", 1100))
    janela = int(config.get("janelaEstabilidadeSegundos", 5))
    oscilacao_max = float(config.get("oscilacaoMaximaPa", 20))
    timeout = int(config.get("timeoutEstabilidadeSegundos", 60))

    leituras = []
    inicio = time.time()
    while time.time() - inicio < timeout:
        pressao = ler_pressao_atual()
        leituras.append(pressao)
        if len(leituras) > janela:
            leituras.pop(0)

        msg = f"Aguardando estabilização | leitura atual: {pressao:.2f} Pa"
        atualizar_status("Estabilização", msg, modo="automatico", em_execucao=True)

        if len(leituras) == janela:
            p_min = min(leituras)
            p_max = max(leituras)
            oscilacao = p_max - p_min
            dentro_faixa = all(pressao_min <= p <= pressao_max for p in leituras)
            if dentro_faixa and oscilacao <= oscilacao_max:
                media = sum(leituras) / len(leituras)
                return media

        time.sleep(1)

    raise RuntimeError(
        f"Pressão não estabilizou na faixa {pressao_min}-{pressao_max} Pa "
        f"dentro de {timeout}s."
    )

@app.route("/")
def index():
    return render_template("index.html")

# Rota para obter a pressão
@app.route("/get_pressure")
def get_pressure_route():
    try:
        # Exibe exatamente o mesmo valor de pressão utilizado na medição/planilha.
        pressao = ler_pressao_atual()
        return jsonify({"pressao": pressao})
    except Exception as e:
        atualizar_status(
            "Erro de leitura",
            f"Falha ao ler o sensor de pressão: {str(e)}",
            erro=True
        )
        return jsonify({"erro": str(e)}), 503


@app.route("/status_processo", endpoint="status_processo_api")
def obter_status_processo():
    with lock:
        payload = dict(estado_processo)
        payload["medindo"] = medindo
        payload["pontos_coletados"] = len(dados_medicao)
    return jsonify(payload)


@app.route("/health")
def health():
    status_sensor = sensor_service.get_status()
    ok_sensor = status_sensor["running"] and (
        status_sensor["latest_age_s"] is not None and status_sensor["latest_age_s"] <= 2.0
    )
    payload = {
        "status": "ok" if ok_sensor else "degraded",
        "sensor_service": status_sensor
    }
    return jsonify(payload), (200 if ok_sensor else 503)


@app.route("/events")
def events():
    @stream_with_context
    def event_stream():
        while True:
            try:
                pressao = ler_pressao_atual()
            except Exception:
                pressao = None

            with lock:
                status = copy.deepcopy(estado_processo)
                status["medindo"] = medindo
                status["pontos_coletados"] = len(dados_medicao)

            payload = {
                "pressao": pressao,
                "status": status
            }
            yield f"event: telemetry\ndata: {json.dumps(payload)}\n\n"
            time.sleep(1)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(event_stream(), mimetype="text/event-stream", headers=headers)

# Rota para ajustar o offset e salvar no arquivo
@app.route("/ajustar_offset", methods=["POST"])
def ajustar_offset_flask():
    """Rota para ajustar o offset e salvar no arquivo 'configs.json'."""
    try:
        atualizar_status(
            "Ajuste de offset",
            "Ajustando offset do sensor...",
            modo="manual",
            em_execucao=True
        )
        ajustar_offset()  # Chama a função que ajusta e salva o offset
        atualizar_status(
            "Offset ajustado",
            "Offset ajustado e salvo com sucesso.",
            modo="manual",
            em_execucao=False
        )
        return jsonify({"status": "Offset ajustado e salvo com sucesso!"})
    except Exception as e:
        atualizar_status(
            "Erro no offset",
            f"Erro ao ajustar offset: {str(e)}",
            modo="manual",
            em_execucao=False,
            erro=True
        )
        return jsonify({"status": f"Erro ao ajustar o offset: {str(e)}"}), 500

@app.route("/start", methods=["POST"])
def start():
    global medindo, dados_medicao, planilha_nome, metadados

    if medindo:
        return jsonify({"status": "já em execução"})

    req = request.get_json()
    planilha_nome = req.get("planilha", "log_pressao.ods")
    if not planilha_nome.endswith(".ods"):
        planilha_nome += ".ods"

    metadados = {
        "Responsável": req.get("responsavel", ""),
        "Coordenadas": req.get("coordenadas", ""),
        "Descrição": req.get("descricao", ""),
        "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    dados_medicao = []
    medindo = True
    abrir_solenoide()
    atualizar_status(
        "Medição manual",
        "Medição manual iniciada. Solenoide aberta e coletando dados...",
        modo="manual",
        em_execucao=True
    )

    def medir():
        global medindo
        tempo = 1
        while medindo:
            try:
                pressao = ler_pressao_atual()
            except Exception as e:
                atualizar_status(
                    "Erro na medição manual",
                    f"Falha ao coletar pressão: {str(e)}",
                    modo="manual",
                    em_execucao=False,
                    erro=True
                )
                medindo = False
                break
            with lock:
                dados_medicao.append({
                    "tempo": tempo,
                    "pressao": pressao
                })
                estado_processo["mensagem"] = f"Coletando ponto {tempo} | pressão: {pressao:.2f} Pa"
                estado_processo["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tempo += 1
            time.sleep(1)

    Thread(target=medir, daemon=True).start()
    return jsonify({"status": "medição iniciada"})

@app.route("/start_auto", methods=["POST"])
def start_auto():
    global medindo, dados_medicao, planilha_nome, metadados

    if medindo:
        return jsonify({"status": "já em execução"})

    req = request.get_json()
    planilha_nome = req.get("planilha", "log_pressao.ods")
    if not planilha_nome.endswith(".ods"):
        planilha_nome += ".ods"

    metadados = {
        "Responsável": req.get("responsavel", ""),
        "Coordenadas": req.get("coordenadas", ""),
        "Descrição": req.get("descricao", ""),
        "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    dados_medicao = []
    atualizar_status(
        "Automação iniciada",
        "Preparando sequência automática de medição...",
        modo="automatico",
        em_execucao=True
    )

    def set_medindo(valor):
        global medindo
        medindo = valor

    def get_medindo():
        return medindo

    Thread(
        target=executar_sequencia_automatica,
        kwargs={
            "atualizar_status": atualizar_status,
            "ler_pressao_atual": ler_pressao_atual,
            "carregar_config": carregar_config,
            "aguardar_pressao_estavel": aguardar_pressao_estavel,
            "calcular_permeabilidade": calcular_permeabilidade,
            "salvar_em_aba": salvar_em_aba,
            "esvaziar_cilindro": esvaziar_cilindro,
            "ajustar_offset": ajustar_offset,
            "calibrar_cilindro": calibrar_cilindro,
            "abrir_solenoide": abrir_solenoide,
            "fechar_solenoide": fechar_solenoide,
            "dados_medicao": dados_medicao,
            "lock": lock,
            "planilha_nome": planilha_nome,
            "get_medindo": get_medindo,
            "set_medindo": set_medindo,
        },
        daemon=True
    ).start()
    return jsonify({"status": "Automação iniciada"})

def calcular_permeabilidade(dados):
    if len(dados) < 2:
        return None  # não há dados suficientes

    tempos = [d["tempo"] for d in dados if d["pressao"] > 0]
    pressoes = [d["pressao"] for d in dados if d["pressao"] > 0]
    ln_pressoes = [math.log(p) for p in pressoes]

    if len(tempos) != len(ln_pressoes):
        return None

    # Regressão linear ln(P) vs. t
    slope, intercept, *_ = linregress(tempos, ln_pressoes)

    # Carrega configurações
    config = carregar_config()
    altura = float(config["alturaCilindro"])
    diametro = float(config["diametroCilindro"])
    volume = float(config["cilindroAr"])
    pressao_atm = float(config["pressaoAtmosferica"])

    # Área da seção transversal
    area = math.pi * (diametro ** 2) / 4
    viscosidade_ar = 1.81e-5  # Pa·s

    # Fórmula da permeabilidade
    k = (2.3 * altura * viscosidade_ar * volume) / (area * pressao_atm) * abs(slope)
    return k

# Rota para iniciar a calibração do cilindro até atingir a pressão configurada
@app.route("/calibrar_cilindro", methods=["POST"])
def calibrar_cilindro_flask():
    """Rota para iniciar a calibração do cilindro até a pressão configurada."""
    config = carregar_config()
    pressao_calibracao = float(config.get("pressaoCalibracaoPa", 1150))
    # Inicia a calibração em uma thread separada para não bloquear o servidor Flask
    Thread(target=calibrar_cilindro, kwargs={"pressao_alvo": pressao_calibracao}, daemon=True).start()
    atualizar_status(
        "Calibração do cilindro",
        f"Calibração iniciada. Compressor ativo até atingir {pressao_calibracao:.0f} Pa.",
        modo="manual",
        em_execucao=True
    )
    return jsonify({"status": f"Calibração iniciada. O compressor será ativado até atingir {pressao_calibracao:.0f} Pa."})

# Rota para abrir válvula solenóide
@app.route("/esvaziar_cilindro", methods=["POST"])
def esvaziar_cilindro_flask():
    Thread(target=esvaziar_cilindro, daemon=True).start()
    atualizar_status(
        "Esvaziamento do cilindro",
        "Abrindo solenoide para esvaziar o cilindro.",
        modo="manual",
        em_execucao=True
    )
    return jsonify({"status": "Cilindro esvaziado."})

@app.route("/stop", methods=["POST"])
def stop():
    global medindo
    if not medindo:
        return jsonify({"status": "nenhuma medição em andamento"})

    medindo = False
    fechar_solenoide()
    time.sleep(1)

    with lock:
        k = calcular_permeabilidade(dados_medicao)
        salvar_em_aba(dados_medicao, planilha_nome, permeabilidade=k)
    atualizar_status(
        "Medição finalizada",
        "Medição encerrada e planilha salva com sucesso.",
        em_execucao=False
    )

    return jsonify({"status": "medição finalizada e planilha salva"})


@app.route("/desligar_equipamento", methods=["POST"])
def desligar_equipamento():
    try:
        atualizar_status(
            "Desligamento do equipamento",
            "Comando de desligamento enviado ao Raspberry Pi.",
            em_execucao=False
        )
        # Executa em thread para responder ao cliente antes do desligamento.
        Thread(target=lambda: subprocess.run(["sudo", "shutdown", "-h", "now"], check=False), daemon=True).start()
        return jsonify({"status": "Desligamento iniciado. O Raspberry Pi será desligado em instantes."})
    except Exception as e:
        atualizar_status(
            "Erro no desligamento",
            f"Falha ao desligar equipamento: {str(e)}",
            erro=True
        )
        return jsonify({"status": f"Erro ao desligar equipamento: {str(e)}"}), 500

@app.route("/reiniciar_equipamento", methods=["POST"])
def reiniciar_equipamento():
    try:
        atualizar_status(
            "Reinicialização do equipamento",
            "Comando de reinicialização enviado ao Raspberry Pi.",
            em_execucao=False
        )
        # Executa em thread para responder ao cliente antes da reinicialização.
        Thread(target=lambda: subprocess.run(["sudo", "shutdown", "-r", "now"], check=False), daemon=True).start()
        return jsonify({"status": "Reinicialização iniciada. O Raspberry Pi será reiniciado em instantes."})
    except Exception as e:
        atualizar_status(
            "Erro na reinicialização",
            f"Falha ao reiniciar equipamento: {str(e)}",
            erro=True
        )
        return jsonify({"status": f"Erro ao reiniciar equipamento: {str(e)}"}), 500

@app.route("/data")
def data():
    with lock:
        return jsonify(dados_medicao)

@app.route("/planilhas")
def listar_planilhas():
    arquivos = [f for f in os.listdir('.') if f.endswith(".ods")]
    return jsonify(arquivos)

@app.route("/download/<nome>")
def download_planilha(nome):
    caminho = os.path.join('.', nome)
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    return "Arquivo não encontrado", 404

def salvar_em_aba(dados, arquivo, permeabilidade=None):
    if os.path.exists(arquivo):
        doc = load(arquivo)
    else:
        doc = OpenDocumentSpreadsheet()

    nome_aba = "Medição " + datetime.now().strftime("%H:%M:%S")
    table = Table(name=nome_aba)

    # Metadados
    for chave, valor in metadados.items():
        row = TableRow()
        cell_key = TableCell()
        cell_key.addElement(P(text=f"{chave}:"))
        cell_val = TableCell()
        cell_val.addElement(P(text=str(valor)))
        row.addElement(cell_key)
        row.addElement(cell_val)
        table.addElement(row)

    # Linha em branco
    table.addElement(TableRow())

    # Cabeçalho
    header = TableRow()
    for col in ["Tempo (s)", "Pressão (Pa)"]:
        cell = TableCell()
        cell.addElement(P(text=col))
        header.addElement(cell)
    table.addElement(header)

    # Dados
    for row_data in dados:
        row = TableRow()
        for val in [row_data["tempo"], row_data["pressao"]]:
            cell = TableCell()
            cell = TableCell(valuetype="float", value=val)
            row.addElement(cell)
        table.addElement(row)

    # Valor calculado pelo Python
    if permeabilidade is not None:
        # Linha com valor calculado pelo Python
        # row = TableRow()
        # cell_label = TableCell()
        # cell_label.addElement(P(text="Permeabilidade (m²) [Python]:"))
        # cell_val = TableCell()
        # cell_val.addElement(P(text=str(permeabilidade).replace('.', ',')))
        # row.addElement(cell_label)
        # row.addElement(cell_val)
        # table.addElement(row)

        # Linha com fórmula para LibreOffice Calc
        row_formula = TableRow()
        cell_label_formula = TableCell()
        cell_label_formula.addElement(P(text="Permeabilidade (m²)"))

        linha_inicial = 7
        linha_final = len(dados) + 6  # Ex: dados com 10 linhas => linha_final = 16

        formula = (
            'of:=((2.3 * 0.05 * 0.0000181 * 0.03135) / ((PI() * 0.05^2 / 4) * 95000)) * '
            f'ABS(SLOPE(LN([.B{linha_inicial}:.B{linha_final}]); [.A{linha_inicial}:.A{linha_final}]))'
        )

        cell_formula = TableCell(formula=formula, valuetype="float")
        cell_formula.addElement(P(text=""))
        row_formula.addElement(cell_label_formula)
        row_formula.addElement(cell_formula)
        table.addElement(row_formula)

    doc.spreadsheet.addElement(table)
    doc.save(arquivo)
    print(f"Planilha salva: {arquivo}")

CONFIG_PATH = "configs.json"

def salvar_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f)

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            defaults = {
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
            defaults.update(config)
            return defaults
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

@app.route("/config", methods=["POST"])
def configurar_equipamento():
    config_recebida = request.get_json()
    config_atual = carregar_config()
    config_atual.update(config_recebida)
    salvar_config(config_atual)
    return jsonify({"status": "Configuração salva com sucesso"})

@app.route("/config", methods=["GET"])
def obter_configuracoes():
    config = carregar_config()
    return jsonify(config)

from odf.opendocument import load
from odf.table import Table

from odf.table import TableRow, TableCell
from odf.text import P

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
