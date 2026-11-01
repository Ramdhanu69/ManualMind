// Query history table. Clicking a row reopens the stored answer and its citations.

const historyRows = document.getElementById("h-rows");
const historyEmpty = document.getElementById("h-empty");
const historyDetail = document.getElementById("h-detail");
const historyModal = new bootstrap.Modal(document.getElementById("mm-page-modal"));
const showUser = Boolean(window.MM_HISTORY_SHOW_USER);

function historyFilters() {
  const params = new URLSearchParams();
  const machine = document.getElementById("f-machine");
  const search = document.getElementById("f-search");
  const from = document.getElementById("f-from");
  const to = document.getElementById("f-to");
  const state = document.getElementById("f-status");
  if (machine && machine.value) params.set("machine", machine.value);
  if (search && search.value.trim()) params.set("search", search.value.trim());
  if (from && from.value) params.set("date_from", from.value);
  if (to && to.value) params.set("date_to", to.value);
  if (state && state.value) params.set("status", state.value);
  return params;
}

function historyRow(item) {
  const userCell = showUser ? mmTag("td", "", mmEscape(item.username)) : "";
  const seconds = ((item.latency_ms_total || 0) / 1000).toFixed(1) + "s";
  return (
    '<tr style="cursor:pointer" data-query="' + item.id + '">' +
    mmTag("td", "mm-mono-small text-nowrap", mmLocalTime(item.created_at)) +
    mmTag("td", "mm-mono-small", mmEscape(item.machine_id)) +
    userCell +
    mmTag("td", "", mmEscape(item.question)) +
    mmTag("td", "", mmStatusBadge(item.status)) +
    mmTag("td", "text-end mm-mono-small", seconds) +
    "</tr>"
  );
}

async function loadHistory() {
  const params = historyFilters();
  const page = await mmFetch("/api/v1/assistant/history/?" + params.toString());
  const items = page.results || [];
  historyRows.innerHTML = items.map(historyRow).join("");
  historyEmpty.classList.toggle("d-none", items.length > 0);
  historyDetail.innerHTML = "";
}

function detailPanel(item) {
  const meta =
    "Asked " + mmLocalTime(item.created_at) + " on " + mmEscape(item.machine_model) +
    " &middot; retrieval " + item.latency_ms_retrieval + " ms &middot; model " +
    item.latency_ms_llm + " ms &middot; " + mmEscape(item.llm_model || "no model") +
    " &middot; top score " + Number(item.top_score).toFixed(3);

  const citations = item.citations || [];
  const sources = citations.length
    ? mmTag("h2", "h6 mt-4", "Sources") + citations.map(mmSourceCard).join("")
    : "";

  return (
    mmTag(
      "div",
      "card mm-card",
      mmTag(
        "div",
        "card-header d-flex justify-content-between align-items-center",
        mmTag("span", "", mmEscape(item.question)) + mmStatusBadge(item.status)
      ) +
        mmTag(
          "div",
          "card-body",
          mmTag("p", "", mmEscape(item.answer_text)) +
            mmTag("p", "text-body-secondary small mb-0", meta)
        )
    ) + sources
  );
}

historyRows.addEventListener("click", async function (event) {
  const row = event.target.closest("tr[data-query]");
  if (!row) return;
  try {
    const item = await mmFetch("/api/v1/assistant/history/" + row.dataset.query + "/");
    historyDetail.innerHTML = detailPanel(item);
    historyDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (failure) {
    mmToast(failure.message);
  }
});

mmBindPageModal(historyDetail, historyModal, "mm-page-modal-image", "mm-page-modal-title");

const applyButton = document.getElementById("f-apply");
if (applyButton) {
  applyButton.addEventListener("click", function () {
    loadHistory().catch(function (failure) {
      mmToast(failure.message);
    });
  });
}

loadHistory().catch(function (failure) {
  mmToast(failure.message);
});
