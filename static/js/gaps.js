// Knowledge gaps: unanswered questions grouped by machine, with run statistics.

const gapsSummary = document.getElementById("gaps-summary");
const gapsGroups = document.getElementById("gaps-groups");
const gapsEmpty = document.getElementById("gaps-empty");
let gapsLoaded = false;

function statTile(label, value) {
  return mmTag(
    "div",
    "col-6 col-lg-3",
    mmTag(
      "div",
      "card mm-card h-100",
      mmTag(
        "div",
        "card-body",
        mmTag("div", "text-body-secondary small", mmEscape(label)) +
          mmTag("div", "h4 mb-0", mmEscape(value))
      )
    )
  );
}

function gapGroup(group) {
  const examples = group.latest
    .map(function (item) {
      return mmTag(
        "li",
        "list-group-item",
        mmTag("div", "", mmEscape(item.question)) +
          mmTag(
            "div",
            "text-body-secondary mm-mono-small",
            mmLocalTime(item.created_at) + " &middot; top score " +
              Number(item.top_score).toFixed(3)
          )
      );
    })
    .join("");

  return mmTag(
    "div",
    "card mm-card mb-3",
    mmTag(
      "div",
      "card-header d-flex justify-content-between align-items-center",
      mmTag(
        "span",
        "",
        mmEscape(group.machine_model) + " (" + mmEscape(group.machine_id) + ")"
      ) + mmBadge("text-bg-warning", group.count + " unanswered")
    ) + mmTag("ul", "list-group list-group-flush", examples)
  );
}

async function loadGaps() {
  if (gapsLoaded) return;
  try {
    const data = await mmFetch("/api/v1/supervisor/knowledge-gaps/");
    const stats = await mmFetch("/api/v1/supervisor/stats/");
    const models = stats.by_model
      .map(function (row) {
        return row.llm_model + " (" + row.count + ")";
      })
      .join(", ");
    gapsSummary.innerHTML =
      statTile("Questions asked", data.queries_total) +
      statTile("Unanswered", data.unanswered_total) +
      statTile("Avg retrieval", data.average_latency_ms_retrieval + " ms") +
      statTile("Models used", models || "none");
    gapsGroups.innerHTML = data.groups.map(gapGroup).join("");
    gapsEmpty.classList.toggle("d-none", data.groups.length > 0);
    gapsLoaded = true;
  } catch (failure) {
    mmToast(failure.message);
  }
}

document.getElementById("gaps-tab").addEventListener("shown.bs.tab", loadGaps);
