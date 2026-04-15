let nomePlanilha = "";
let intervalo;
let modoAutomatico = false;

function setMensagemSistema(mensagem, tipo = "info") {
  const etapaEl = document.getElementById("status-etapa");
  const msgEl = document.getElementById("status-mensagem");
  if (!etapaEl || !msgEl) return;

  if (tipo === "erro") etapaEl.textContent = "Erro";
  if (tipo === "sucesso") etapaEl.textContent = "Sucesso";
  msgEl.textContent = mensagem;
}

async function iniciarMedicao() {
  modoAutomatico = false;
  const res = await fetch("/planilhas");
  const planilhas = await res.json();

  const select = document.getElementById("planilhas-select");
  const input = document.getElementById("nova-planilha");
  const campoNome = document.getElementById("campo-nome-planilha");

  select.innerHTML = '<option value="">-- criar nova --</option>';
  planilhas.forEach(p => {
    const option = document.createElement("option");
    option.value = p;
    option.textContent = p;
    select.appendChild(option);
  });

  input.value = "";
  campoNome.style.display = "block";

  // Limpa campos de metadados
  document.getElementById("responsavel").value = "";
  document.getElementById("coordenadas").value = "";
  document.getElementById("descricao").value = "";

  document.getElementById("modal").style.display = "flex";
}

async function iniciarMedicaoAutomatica() {
  modoAutomatico = true;
  const res = await fetch("/planilhas");
  const planilhas = await res.json();

  const select = document.getElementById("planilhas-select");
  const input = document.getElementById("nova-planilha");
  const campoNome = document.getElementById("campo-nome-planilha");

  select.innerHTML = '<option value="">-- criar nova --</option>';
  planilhas.forEach(p => {
    const option = document.createElement("option");
    option.value = p;
    option.textContent = p;
    select.appendChild(option);
  });

  input.value = "";
  campoNome.style.display = "block";

  // Limpa campos de metadados
  document.getElementById("responsavel").value = "";
  document.getElementById("coordenadas").value = "";
  document.getElementById("descricao").value = "";

  document.getElementById("modal").style.display = "flex";
}

function alternarCampoNome() {
  const select = document.getElementById("planilhas-select");
  const campo = document.getElementById("campo-nome-planilha");

  campo.style.display = select.value ? "none" : "block";
}

function confirmarEscolha() {
  const select = document.getElementById("planilhas-select");
  const input = document.getElementById("nova-planilha");

  nomePlanilha = select.value || (input.value.trim() + ".ods");

  if (!nomePlanilha || nomePlanilha === ".ods") {
    setMensagemSistema("Informe um nome válido para a planilha.", "erro");
    return;
  }

  fecharModal();
  
    if (modoAutomatico) {
        iniciarMedicaoAutomaticaBackend(nomePlanilha);
        console.log("automatica")
    } else {
        iniciarMedicaoBackend(nomePlanilha);
        console.log("manual")
    }
}

function fecharModal() {
  document.getElementById("modal").style.display = "none";
}

async function iniciarMedicaoBackend(planilha) {
  const responsavel = document.getElementById("responsavel").value.trim();
  const coordenadas = document.getElementById("coordenadas").value.trim();
  const descricao = document.getElementById("descricao").value.trim();

  await fetch('/start', {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      planilha,
      responsavel,
      coordenadas,
      descricao
    })
  });

  if (intervalo) clearInterval(intervalo);

  intervalo = setInterval(async () => {
    const res = await fetch("/data");
    const dados = await res.json();

    if (dados.length > 0) {
      const tempo = dados.map(d => d.tempo);
      const pressao = dados.map(d => d.pressao);
    }
  }, 1000);
}

async function iniciarMedicaoAutomaticaBackend(planilha) {
    const responsavel = document.getElementById("responsavel").value.trim();
    const coordenadas = document.getElementById("coordenadas").value.trim();
    const descricao = document.getElementById("descricao").value.trim();

    setMensagemSistema("Iniciando medição automática. Aguarde a sequência de hardware.", "info");

    await fetch('/start_auto', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            planilha, responsavel, coordenadas, descricao
        })
    });
}

async function iniciarMediçãoBackend(planilha) {
  const responsavel = document.getElementById("responsavel").value.trim();
  const coordenadas = document.getElementById("coordenadas").value.trim();
  const descricao = document.getElementById("descricao").value.trim();

  await fetch('/start', {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      planilha,
      responsavel,
      coordenadas,
      descricao
    })
  });

  if (intervalo) clearInterval(intervalo);

  intervalo = setInterval(async () => {
    const res = await fetch("/data");
    const dados = await res.json();

    if (dados.length > 0) {
      const tempo = dados.map(d => d.tempo);
      const pressao = dados.map(d => d.pressao);
    }
  }, 1000);
}

async function finalizarMedicao() {
  const res = await fetch("/stop", { method: "POST" });
  const data = await res.json();
  console.log(data.status);
  setMensagemSistema("Medição finalizada. Planilha salva com sucesso.", "sucesso");
  if (intervalo) clearInterval(intervalo);
}

async function ajustarOffset() {
  fetch("/ajustar_offset", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  })
    .then(response => response.json())
    .then(data => {
      setMensagemSistema(data.status, "info");
    })
    .catch(error => {
      console.log("Erro:", error);
      setMensagemSistema("Ocorreu um erro ao ajustar o offset.", "erro");
    });
}

function calibrarCilindro() {
  // Desabilita o botão para evitar múltiplos cliques enquanto a calibração está em andamento
  document.getElementById("calibrar-btn").disabled = true;

  fetch("/calibrar_cilindro", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  })
    .then(response => response.json())
    .then(data => {
      setMensagemSistema(data.status, "info");
      // Habilita o botão novamente
      document.getElementById("calibrar-btn").disabled = false;
    })
    .catch(error => {
      console.log("Erro:", error);
      setMensagemSistema("Ocorreu um erro ao iniciar a calibração.", "erro");
    });
}

function esvaziarCilindro() {
  // Desabilita o botão para evitar múltiplos cliques enquanto a calibração está em andamento
  document.getElementById("esvaziar-btn").disabled = true;

  fetch("/esvaziar_cilindro", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  })
    .then(response => response.json())
    .then(data => {
      setMensagemSistema(data.status, "info");
      document.getElementById("esvaziar-btn").disabled = false;
    })
    .catch(error => {
      console.log("Erro:", error);
      setMensagemSistema("Ocorreu um erro ao esvaziar cilindro.", "erro");
    });
}

function abrirModalPlanilhas() {
  fetch('/planilhas')
    .then(res => res.json())
    .then(planilhas => {
      const lista = document.getElementById("lista-planilhas");
      lista.innerHTML = "";

      if (planilhas.length === 0) {
        lista.innerHTML = "<li class='lista-vazia'>Nenhuma planilha encontrada.</li>";
      } else {
        planilhas.forEach(p => {
          const item = document.createElement("li");
          item.className = "planilha-item"; // Classe do item

          const link = document.createElement("a");
          link.href = `/download/${encodeURIComponent(p)}`;
          link.textContent = p;
          link.className = "planilha-link"; // Classe do estilo que criamos
          link.target = "_blank";
          
          item.appendChild(link);
          lista.appendChild(item);
        });
      }

      document.getElementById("modal-planilhas").style.display = "flex";
    });
}

function fecharModalPlanilhas() {
  document.getElementById("modal-planilhas").style.display = "none";
}

function abrirModalConfig() {
  // Requisição para carregar valores existentes
  fetch("/config")
    .then(res => res.json())
    .then(config => {
      document.getElementById("config-cilindroAr").value = config.cilindroAr;
      document.getElementById("config-alturaCilindro").value = config.alturaCilindro;
      document.getElementById("config-diametroCilindro").value = config.diametroCilindro;
      document.getElementById("config-pressao").value = config.pressaoAtmosferica;
    });

  document.getElementById("modal-config").style.display = "flex";
}

function fecharModalConfig() {
  document.getElementById("modal-config").style.display = "none";
}

function salvarConfiguracoes() {
  const config = {
    cilindroAr: parseFloat(document.getElementById("config-cilindroAr").value),
    alturaCilindro: parseFloat(document.getElementById("config-alturaCilindro").value),
    diametroCilindro: parseFloat(document.getElementById("config-diametroCilindro").value),
    pressaoAtmosferica: parseFloat(document.getElementById("config-pressao").value)
  };

  fetch("/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config)
  })
    .then(res => res.json())
    .then(data => {
      setMensagemSistema(data.status, "sucesso");
      fecharModalConfig();
    });
}


async function reiniciarEquipamento() {
  try {
    const res = await fetch("/reiniciar_equipamento", { method: "POST" });
    const data = await res.json();
    setMensagemSistema(data.status || "Comando de reinicialização enviado.", "info");
  } catch (error) {
    console.error("Erro ao reiniciar equipamento:", error);
    setMensagemSistema("Não foi possível enviar o comando de reinicialização.", "erro");
  }
}

async function desligarEquipamento() {
  try {
    const res = await fetch("/desligar_equipamento", { method: "POST" });
    const data = await res.json();
    setMensagemSistema(data.status || "Comando de desligamento enviado.", "info");
  } catch (error) {
    console.error("Erro ao desligar equipamento:", error);
    setMensagemSistema("Não foi possível enviar o comando de desligamento.", "erro");
  }
}

function atualizarPressao() {
  fetch("/get_pressure")
    .then(response => response.json())
    .then(data => {
      if (typeof data.pressao !== "number") {
        return;
      }
      // Atualiza o valor da pressão na interface
      document.getElementById("pressure").textContent = data.pressao.toFixed(2);
    })
    .catch(error => {
      console.error("Erro ao obter a pressão:", error);
    });
}

function atualizarStatusTela(status) {
  const etapaEl = document.getElementById("status-etapa");
  const msgEl = document.getElementById("status-mensagem");

  etapaEl.textContent = status.etapa || "Sem etapa";
  msgEl.textContent = status.mensagem || "Sem informações de status.";
}

function atualizarStatusProcesso() {
  fetch("/status_processo")
    .then(response => response.json())
    .then(data => {
      atualizarStatusTela(data);
    })
    .catch(error => {
      console.error("Erro ao obter status do processo:", error);
    });
}

function iniciarStreamTempoReal() {
  // Simplificado: polling estável e previsível.
  iniciarFallbackPolling();
}

function iniciarFallbackPolling() {
  setInterval(atualizarPressao, 1000);
  setInterval(atualizarStatusProcesso, 1000);
  atualizarStatusProcesso();
}

iniciarStreamTempoReal();
