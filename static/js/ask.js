// Engineer Ask page: machine-scoped question, answer card, grounded source cards.

const machineSelect = document.getElementById("mm-machine");
const machinePill = document.getElementById("mm-machine-pill");
const questionBox = document.getElementById("mm-question");
const askButton = document.getElementById("mm-ask-button");
const answerCard = document.getElementById("mm-answer-card");
const sourcesHost = document.getElementById("mm-sources");
const sourcesHeading = document.getElementById("mm-sources-heading");
const hintBox = document.getElementById("mm-hint");
const timing = document.getElementById("mm-timing");
const pageModal = new bootstrap.Modal(document.getElementById("mm-page-modal"));

function refreshPill() {
  const option = machineSelect.selectedOptions[0];
  machinePill.textContent = option ? option.dataset.model + " selected" : "No machine selected";
}

machineSelect.addEventListener("change", refreshPill);
refreshPill();

document.querySelectorAll(".mm-example-question").forEach(function (button) {
  button.addEventListener("click", function () {
    questionBox.value = button.dataset.question;
    questionBox.focus();
  });
});

mmBindPageModal(sourcesHost, pageModal, "mm-page-modal-image", "mm-page-modal-title");

function renderEscalation(items) {
  const block = document.getElementById("mm-escalation-block");
  const list = document.getElementById("mm-escalation-list");
  block.classList.toggle("d-none", items.length === 0);
  list.innerHTML = items
    .map(function (item) {
      return mmTag(
        "li",
        "form-check",
        '<input class="form-check-input" type="checkbox">' +
          mmTag("span", "form-check-label ms-1", mmEscape(item))
      );
    })
    .join("");
}

function render(result) {
  answerCard.classList.remove("d-none");
  document.getElementById("mm-answer-status").innerHTML = mmStatusBadge(result.status);
  document.getElementById("mm-answer-text").textContent = result.answer_text;

  renderEscalation(result.record_before_escalation || []);

  const citations = result.citations || [];
  sourcesHeading.classList.toggle("d-none", citations.length === 0);
  sourcesHost.innerHTML = citations.map(mmSourceCard).join("");

  hintBox.classList.toggle("d-none", !result.machine_hint);
  hintBox.textContent = result.machine_hint || "";

  const seconds = (result.latency_ms_total || 0) / 1000;
  timing.textContent = "answered in " + seconds.toFixed(1) + "s";
}

askButton.addEventListener("click", async function () {
  const question = questionBox.value.trim();
  if (!machineSelect.value) {
    mmToast("Select a machine first.");
    return;
  }
  if (question.length < 3) {
    mmToast("Enter a question of at least 3 characters.");
    return;
  }
  askButton.disabled = true;
  askButton.textContent = "Searching the manuals...";
  timing.textContent = "";
  try {
    const result = await mmFetch("/api/v1/assistant/ask/", {
      method: "POST",
      body: { machine_id: machineSelect.value, question: question },
    });
    render(result);
  } catch (failure) {
    if (failure.payload && failure.payload.status) {
      render(failure.payload);
    }
    mmToast(failure.message);
  } finally {
    askButton.disabled = false;
    askButton.textContent = "Ask";
  }
});
