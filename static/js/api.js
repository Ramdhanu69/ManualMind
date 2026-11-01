// Shared fetch wrapper: session auth plus CSRF, and one consistent error shape.

async function mmFetch(url, options = {}) {
  const init = {
    method: options.method || "GET",
    headers: { "X-CSRFToken": window.MM_CSRF, ...(options.headers || {}) },
    credentials: "same-origin",
  };
  if (options.body instanceof FormData) {
    init.body = options.body;
  } else if (options.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error(
        (payload && payload.detail) ||
          "Your role is not allowed to perform this action."
      );
    }
    let message = (payload && payload.detail) || `Request failed (${response.status}).`;
    if (payload && payload.errors) {
      const details = Object.entries(payload.errors)
        .map(([field, list]) => `${field}: ${[].concat(list).join(" ")}`)
        .join("; ");
      if (details) message = `${message} ${details}`;
    }
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function mmToast(message, variant = "danger") {
  const host = document.getElementById("mm-toasts");
  if (!host) return;
  const element = document.createElement("div");
  element.className = `toast align-items-center text-bg-${variant} border-0`;
  element.setAttribute("role", "alert");
  element.innerHTML =
    '<div class="d-flex"><div class="toast-body"></div>' +
    '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
  element.querySelector(".toast-body").textContent = message;
  host.appendChild(element);
  const toast = new bootstrap.Toast(element, { delay: 6000 });
  toast.show();
  element.addEventListener("hidden.bs.toast", () => element.remove());
}

function mmEscape(value) {
  const node = document.createElement("span");
  node.textContent = value === null || value === undefined ? "" : String(value);
  return node.innerHTML;
}

function mmStatusBadge(status) {
  const map = {
    ANSWERED: ["text-bg-success", "ANSWERED"],
    INSUFFICIENT_EVIDENCE: ["text-bg-warning", "INSUFFICIENT EVIDENCE"],
    ERROR: ["text-bg-danger", "ERROR"],
    INDEXED: ["text-bg-success", "INDEXED"],
    PENDING: ["text-bg-secondary", "PENDING"],
    FAILED: ["text-bg-danger", "FAILED"],
  };
  const [cls, label] = map[status] || ["text-bg-secondary", status || "UNKNOWN"];
  return `<span class="badge ${cls}">${mmEscape(label)}</span>`;
}

function mmLocalTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("mm-logout");
  if (!button) return;
  button.addEventListener("click", async () => {
    try {
      await mmFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login/";
    }
  });
});

// Small HTML builders. Every caller passes text through mmEscape first, so these
// never interpolate untrusted values directly.
function mmAttr(value) {
  return mmEscape(value).replace(/"/g, "&quot;");
}

function mmTag(name, className, inner) {
  const attribute = className ? ' class="' + mmAttr(className) + '"' : "";
  return "<" + name + attribute + ">" + inner + "</" + name + ">";
}

function mmBadge(className, label) {
  return '<span class="badge ' + mmAttr(className) + '">' + mmEscape(label) + "</span>";
}

function mmLink(href, className, label) {
  return (
    '<a class="' + mmAttr(className) + '" target="_blank" rel="noopener" href="' +
    mmAttr(href) + '">' + mmEscape(label) + "</a>"
  );
}

function mmImage(source, alt, label) {
  return (
    '<img class="mm-page-thumb" loading="lazy" src="' + mmAttr(source) +
    '" alt="' + mmAttr(alt) + '" data-full="' + mmAttr(source) +
    '" data-label="' + mmAttr(label) + '">'
  );
}

function mmPreviewUrl(citation) {
  return "/api/v1/manuals/" + citation.manual_id + "/page/" + citation.page_number + "/preview/";
}

function mmSourceCard(citation) {
  const preview = mmPreviewUrl(citation);
  const pdf = "/api/v1/manuals/" + citation.manual_id + "/pdf/#page=" + citation.page_number;
  const badge = citation.quote_verified
    ? mmBadge("text-bg-success", "verbatim quote")
    : mmBadge("text-bg-secondary", "passage shown");

  const header =
    mmTag("div", "fw-semibold d-inline", mmEscape(citation.document_id)) +
    " " +
    mmTag("span", "text-body-secondary", mmEscape(citation.title)) +
    mmTag(
      "div",
      "mm-mono-small text-body-secondary",
      "Rev " + mmEscape(citation.revision) + " &middot; Page " + citation.page_number
    );

  const quoteColumn =
    mmTag("div", "mm-quote", mmEscape(citation.quote)) +
    mmLink(pdf, "btn btn-sm btn-outline-secondary mt-2", "Open PDF at page " + citation.page_number);

  const imageColumn = mmImage(
    preview,
    "Page " + citation.page_number + " of " + mmEscape(citation.document_id),
    mmEscape(citation.document_id) + " page " + citation.page_number
  );

  return mmTag(
    "div",
    "mm-source-card",
    mmTag(
      "div",
      "card-body p-3",
      mmTag(
        "div",
        "d-flex flex-wrap justify-content-between align-items-start gap-2 mb-2",
        mmTag("div", "", header) + mmTag("div", "", badge)
      ) +
        mmTag(
          "div",
          "row g-3",
          mmTag("div", "col-12 col-md-7", quoteColumn) +
            mmTag("div", "col-12 col-md-5", imageColumn)
        )
    )
  );
}

// Click any rendered page thumbnail to open it full size in a shared modal.
function mmBindPageModal(host, modal, imageId, titleId) {
  host.addEventListener("click", function (event) {
    const image = event.target.closest(".mm-page-thumb");
    if (!image) return;
    document.getElementById(imageId).src = image.dataset.full;
    document.getElementById(titleId).textContent = image.dataset.label;
    modal.show();
  });
}
