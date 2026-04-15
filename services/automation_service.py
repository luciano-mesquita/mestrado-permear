import time
from datetime import datetime
from domain.models import AutomationState

ETAPA_LABEL = {
    AutomationState.IDLE: "Inativo",
    AutomationState.PURGE: "Esvaziamento",
    AutomationState.OFFSET: "Ajuste de offset",
    AutomationState.CALIBRATION: "Calibração",
    AutomationState.STABILIZING: "Estabilização",
    AutomationState.MEASURING: "Medição automática",
    AutomationState.FINALIZING: "Finalização",
    AutomationState.COMPLETED: "Concluído",
    AutomationState.ERROR: "Erro",
}


def executar_sequencia_automatica(
    *,
    atualizar_status,
    ler_pressao_atual,
    carregar_config,
    aguardar_pressao_estavel,
    calcular_permeabilidade,
    salvar_em_aba,
    esvaziar_cilindro,
    ajustar_offset,
    calibrar_cilindro,
    abrir_solenoide,
    fechar_solenoide,
    dados_medicao,
    lock,
    planilha_nome,
    get_medindo,
    set_medindo,
):
    try:
        atualizar_status(ETAPA_LABEL[AutomationState.PURGE], "Esvaziando cilindro para estabilização inicial...", modo="automatico", em_execucao=True)
        esvaziar_cilindro()

        atualizar_status(ETAPA_LABEL[AutomationState.STABILIZING], "Aguardando estabilização da pressão...")
        time.sleep(2)

        atualizar_status(ETAPA_LABEL[AutomationState.OFFSET], "Ajustando offset do sensor...")
        ajustar_offset()
        time.sleep(2)

        atualizar_status(ETAPA_LABEL[AutomationState.STABILIZING], "Offset concluído. Aguardando estabilização...")
        time.sleep(2)

        config = carregar_config()
        pressao_calibracao = float(config.get("pressaoCalibracaoPa", 1150))

        atualizar_status(
            ETAPA_LABEL[AutomationState.CALIBRATION],
            f"Calibrando cilindro até {pressao_calibracao:.0f} Pa...",
            modo="automatico",
            em_execucao=True,
        )
        calibrar_cilindro(pressao_alvo=pressao_calibracao)

        atualizar_status(ETAPA_LABEL[AutomationState.STABILIZING], "Verificando estabilização da pressão antes da medição...")
        media_estavel = aguardar_pressao_estavel(config)
        atualizar_status(
            ETAPA_LABEL[AutomationState.STABILIZING],
            f"Pressão estável em {media_estavel:.2f} Pa. Pronto para iniciar medição.",
            modo="automatico",
            em_execucao=True,
        )

        atualizar_status(ETAPA_LABEL[AutomationState.MEASURING], "Iniciando coleta automática de dados...", modo="automatico", em_execucao=True)
        set_medindo(True)
        abrir_solenoide()

        tempo = 1
        while True:
            pressao = ler_pressao_atual()
            if pressao < 0:
                atualizar_status(
                    ETAPA_LABEL[AutomationState.MEASURING],
                    f"Primeira pressão negativa detectada ({pressao:.2f} Pa). Encerrando coleta.",
                    modo="automatico",
                    em_execucao=True,
                )
                set_medindo(False)
                break

            with lock:
                dados_medicao.append({"tempo": tempo, "pressao": pressao})
            atualizar_status(
                ETAPA_LABEL[AutomationState.MEASURING],
                f"Coletando ponto {tempo} | pressão: {pressao:.2f} Pa",
                modo="automatico",
                em_execucao=True,
            )

            tempo += 1
            time.sleep(1)

        atualizar_status(ETAPA_LABEL[AutomationState.FINALIZING], "Fechando solenoide e calculando permeabilidade...", modo="automatico", em_execucao=True)
        fechar_solenoide()

        with lock:
            k = calcular_permeabilidade(dados_medicao)
            salvar_em_aba(dados_medicao, planilha_nome, permeabilidade=k)

        atualizar_status(
            ETAPA_LABEL[AutomationState.COMPLETED],
            f"Medição automática finalizada em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
            modo="automatico",
            em_execucao=False,
        )

    except Exception as e:
        set_medindo(False)
        atualizar_status(
            ETAPA_LABEL[AutomationState.ERROR],
            f"Ocorreu um erro durante a sequência automática: {str(e)}",
            modo="automatico",
            em_execucao=False,
            erro=True,
        )
