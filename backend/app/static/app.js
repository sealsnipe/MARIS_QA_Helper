(() => {
  const boot = window.APP_BOOT || {};
  const page = boot.page || "chat";
  const globalCustomerId = boot.globalCustomerId || "global";
  const customerLabels = boot.customerLabels || {};
  let activeCustomerId = boot.activeCustomerId || "";
  let activeCustomerName = boot.activeCustomerName || "";

  function isGlobalCustomer() {
    return activeCustomerId === globalCustomerId;
  }

  const customerSelect = document.getElementById("customer-select");
  const noCustomerBanner = document.getElementById("no-customer-banner");
  const pageContent = document.getElementById("page-content");
  const adminWorkspace = document.getElementById("admin-workspace");

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      ...options,
    });

    let payload = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      payload = await response.json();
    }

    if (!response.ok) {
      const error = new Error(payload?.error || "request_failed");
      error.code = payload?.error;
      error.detail = payload?.detail;
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function showStatus(el, message, kind = "") {
    if (!el) return;
    el.textContent = message;
    el.className = `status ${kind}`.trim();
  }

  function renderMarkdown(text) {
    const source = String(text || "");
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      return escapeHtml(source);
    }

    marked.setOptions({
      gfm: true,
      breaks: true,
      headerIds: false,
      mangle: false,
    });

    const html = marked.parse(source);
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      ADD_ATTR: ["target"],
    });
  }

  function setBubbleContent(bubble, text) {
    const body = document.createElement("div");
    body.className = "markdown-body";
    body.innerHTML = renderMarkdown(text);
    bubble.appendChild(body);
  }

  function setCustomerUiEnabled(enabled) {
    const needsCustomer = page === "chat" || page === "kb";
    if (!needsCustomer) return;

    if (enabled) {
      noCustomerBanner?.classList.add("hidden");
      pageContent?.classList.remove("disabled");
    } else {
      noCustomerBanner?.classList.remove("hidden");
      pageContent?.classList.add("disabled");
    }

    const kbName = document.getElementById("kb-customer-name");
    const suffix = enabled ? `(${activeCustomerName})` : "";
    if (kbName) kbName.textContent = suffix;
  }

  function syncActiveCustomerFromSelect() {
    if (!customerSelect) return;
    if (customerSelect.tagName === "SELECT") {
      const option = customerSelect.selectedOptions[0];
      activeCustomerId = customerSelect.value || "";
      activeCustomerName = option && option.value ? option.textContent.trim() : "";
    } else {
      activeCustomerId = customerSelect.value || "";
    }
  }

  async function switchCustomer(customerId) {
    await api("/api/session/customer", {
      method: "POST",
      body: JSON.stringify({ customer_id: customerId }),
    });
    const url = new URL(window.location.href);
    url.searchParams.delete("c");
    window.location.assign(url.toString());
  }

  let activeChatId = page === "chat" ? new URLSearchParams(window.location.search).get("c") || "" : "";

  function setActiveChatInUrl(chatId) {
    if (page !== "chat") return;
    const url = new URL(window.location.href);
    if (chatId) {
      url.searchParams.set("c", chatId);
    } else {
      url.searchParams.delete("c");
    }
    window.history.replaceState({}, "", url);
  }

  async function refreshChatHistory() {
    const chatHistoryList = document.getElementById("chat-history-list");
    if (!chatHistoryList) return;

    if (!activeCustomerId) {
      chatHistoryList.innerHTML = '<li class="chat-history-empty">Bitte zuerst einen Kunden wählen.</li>';
      return;
    }

    let data;
    try {
      data = await api("/api/chats");
    } catch (error) {
      chatHistoryList.innerHTML = `<li class="chat-history-error">Chats konnten nicht geladen werden (${escapeHtml(error.code || "Fehler")}).</li>`;
      return;
    }

    chatHistoryList.innerHTML = "";
    const chats = data.chats || [];
    if (!chats.length) {
      chatHistoryList.innerHTML = '<li class="chat-history-empty">Noch keine Chats für diesen Kunden.</li>';
      return;
    }

    for (const chat of chats) {
      const item = document.createElement("li");
      item.className = "chat-history-item";

      const link = document.createElement("a");
      link.href = `/chat?c=${encodeURIComponent(chat.id)}`;
      link.className = "chat-history-link";
      link.title = chat.title;
      link.textContent = chat.title;
      if (chat.id === activeChatId) {
        link.classList.add("active");
      }

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "chat-history-delete";
      delBtn.textContent = "×";
      delBtn.title = "Chat löschen";
      delBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!confirm(`Chat „${chat.title}“ wirklich löschen?`)) return;
        await api(`/api/chats/${chat.id}`, { method: "DELETE" });
        if (activeChatId === chat.id) {
          activeChatId = "";
          setActiveChatInUrl("");
          const chatLog = document.getElementById("chat-log");
          if (chatLog) chatLog.innerHTML = "";
        }
        await refreshChatHistory();
      });

      item.appendChild(link);
      item.appendChild(delBtn);
      chatHistoryList.appendChild(item);
    }
  }

  function initChatSidebar() {
    const newChatBtn = document.getElementById("new-chat-btn");
    newChatBtn?.addEventListener("click", () => {
      if (page === "chat") {
        activeChatId = "";
        setActiveChatInUrl("");
        const chatLog = document.getElementById("chat-log");
        if (chatLog) chatLog.innerHTML = "";
        refreshChatHistory().catch(() => {});
        document.getElementById("chat-input")?.focus();
      } else {
        window.location.href = "/chat";
      }
    });
  }

  if (customerSelect && customerSelect.tagName === "SELECT") {
    customerSelect.addEventListener("change", async () => {
      syncActiveCustomerFromSelect();
      const value = customerSelect.value;
      if (!value) {
        activeChatId = "";
        setCustomerUiEnabled(false);
        refreshChatHistory().catch(() => {});
        return;
      }
      try {
        await switchCustomer(value);
      } catch (_error) {
        showStatus(document.getElementById("chat-status"), "Kundenwechsel fehlgeschlagen.", "error");
      }
    });
  }

  function renderDocuments(documents, listEl, countEl, emptyEl, deletePath, options = {}) {
    const { readOnly = false, showCustomer = false } = options;
    if (!listEl) return;
    listEl.innerHTML = "";
    if (countEl) countEl.textContent = `(${documents.length})`;
    emptyEl?.classList.toggle("hidden", documents.length > 0);

    for (const doc of documents) {
      const item = document.createElement("li");
      item.className = "doc-item";

      const meta = document.createElement("div");
      meta.className = "doc-meta";
      const customerLabel = showCustomer
        ? `<span class="badge">${escapeHtml(customerLabels[doc.customer_id] || doc.customer_id)}</span> · `
        : "";
      meta.innerHTML = `
        <strong>${escapeHtml(doc.title)}</strong>
        <span>
          ${customerLabel}
          <span class="badge ${doc.status === "failed" ? "failed" : ""}">${escapeHtml(doc.source_type)}</span>
          · ${doc.chunk_count} Chunks
          ${doc.status === "failed" ? "· fehlgeschlagen" : ""}
        </span>
      `;

      item.appendChild(meta);
      if (!readOnly) {
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "danger";
        delBtn.textContent = "Löschen";
        delBtn.addEventListener("click", async () => {
          if (!confirm(`Dokument „${doc.title}“ wirklich löschen?`)) return;
          await api(`${deletePath}/${doc.id}`, { method: "DELETE" });
          if (deletePath === "/api/documents") {
            await refreshKbDocuments();
          } else {
            await refreshAdminDocuments();
          }
        });
        item.appendChild(delBtn);
      }
      listEl.appendChild(item);
    }
  }

  function setKbReadOnlyMode(readOnly) {
    const form = document.getElementById("ingest-form");
    const banner = document.getElementById("kb-readonly-banner");
    const emptyEl = document.getElementById("doc-empty");
    form?.classList.toggle("hidden", readOnly);
    banner?.classList.toggle("hidden", !readOnly);
    if (emptyEl && readOnly) {
      emptyEl.textContent = "Noch keine Dokumente in den verfügbaren Wissensdatenbanken.";
    } else if (emptyEl) {
      emptyEl.textContent = "Noch kein Wissen für diesen Kunden.";
    }
  }

  async function refreshKbDocuments() {
    if (!activeCustomerId) return;
    const data = await api("/api/documents");
    const readOnly = Boolean(data.read_only);
    setKbReadOnlyMode(readOnly);
    renderDocuments(
      data.documents || [],
      document.getElementById("doc-list"),
      document.getElementById("doc-count"),
      document.getElementById("doc-empty"),
      "/api/documents",
      { readOnly, showCustomer: readOnly },
    );
  }

  async function refreshAdminDocuments() {
    const data = await api("/api/admin/documents");
    renderDocuments(
      data.documents || [],
      document.getElementById("admin-doc-list"),
      document.getElementById("admin-doc-count"),
      document.getElementById("admin-doc-empty"),
      "/api/admin/documents",
    );
  }

  function setupDropzone(dropzone, fileInput, fileLabel, onSelect) {
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
      }
    });
    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
      const file = event.dataTransfer?.files?.[0];
      if (file) onSelect(file);
    });
    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      onSelect(file || null);
    });
  }

  function bindIngestForm({
    form,
    titleInput,
    textInput,
    submitBtn,
    statusEl,
    fileInput,
    dropzone,
    fileLabel,
    apiPath,
    onSuccess,
  }) {
    let selectedFile = null;

    const setFile = (file) => {
      selectedFile = file;
      if (fileLabel) {
        fileLabel.textContent = file ? file.name : "Datei hierher ziehen oder klicken";
      }
      dropzone?.classList.toggle("has-file", Boolean(file));
    };

    setupDropzone(dropzone, fileInput, fileLabel, setFile);

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const prefixText = textInput?.value.trim() || "";
      if (!prefixText && !selectedFile) {
        showStatus(statusEl, "Bitte Text und/oder Datei angeben.", "error");
        return;
      }

      submitBtn.disabled = true;
      showStatus(statusEl, "Wird indexiert…");

      const formData = new FormData();
      if (titleInput?.value.trim()) formData.append("title", titleInput.value.trim());
      if (prefixText) formData.append("text", prefixText);
      if (selectedFile) formData.append("file", selectedFile);

      try {
        await api(apiPath, { method: "POST", body: formData });
        showStatus(statusEl, "Wissen erfolgreich indexiert.", "ok");
        if (titleInput) titleInput.value = "";
        if (textInput) textInput.value = "";
        if (fileInput) fileInput.value = "";
        setFile(null);
        await onSuccess();
      } catch (error) {
        const messages = {
          empty_text: "Inhalt zu kurz (min. 20 Zeichen gesamt).",
          unsupported_file_type: "Nur .txt, .md, .pdf, .docx erlaubt.",
          file_too_large: "Datei überschreitet 30 MB.",
          extraction_failed: "Text konnte nicht extrahiert werden.",
          forbidden: "Keine Berechtigung.",
        };
        showStatus(statusEl, messages[error.code] || "Einpflegen fehlgeschlagen.", "error");
        await onSuccess();
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function buildSourcesPopover(sources) {
    const wrap = document.createElement("div");
    wrap.className = "sources-popover";

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "sources-trigger";
    trigger.textContent = "Quellen";
    trigger.setAttribute("aria-label", `${sources.length} Quellen anzeigen`);

    const tooltip = document.createElement("div");
    tooltip.className = "sources-tooltip";
    tooltip.setAttribute("role", "tooltip");

    const list = document.createElement("ul");
    list.className = "sources-tooltip-list";
    for (const source of sources) {
      const li = document.createElement("li");
      li.textContent = `[${source.n}] ${source.title} · Textabschnitt ${source.chunk_index + 1}`;
      list.appendChild(li);
    }

    tooltip.appendChild(list);
    wrap.appendChild(trigger);
    wrap.appendChild(tooltip);
    return wrap;
  }

  function initChatPage() {
    const chatLog = document.getElementById("chat-log");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatSubmit = document.getElementById("chat-submit");
    const chatStatus = document.getElementById("chat-status");

    function scrollChatToBottom() {
      if (!chatLog) return;
      requestAnimationFrame(() => {
        chatLog.scrollTop = chatLog.scrollHeight;
      });
    }

    function appendBubble(role, text, sources = null) {
      const bubble = document.createElement("div");
      bubble.className = `bubble ${role}`;

      if (role === "assistant" && text !== "…") {
        setBubbleContent(bubble, text);
      } else {
        bubble.textContent = text;
      }

      if (role === "assistant" && sources && sources.length) {
        bubble.appendChild(buildSourcesPopover(sources));
      }

      chatLog.appendChild(bubble);
      scrollChatToBottom();
      return bubble;
    }

    function renderChatLog(messages) {
      chatLog.innerHTML = "";
      for (const message of messages) {
        if (message.role === "user" || message.role === "assistant") {
          appendBubble(
            message.role,
            message.content,
            message.role === "assistant" && !message.no_context ? message.sources : null,
          );
        }
      }
    }

    async function loadChat(chatId) {
      if (!chatId) {
        chatLog.innerHTML = "";
        return;
      }
      const data = await api(`/api/chats/${chatId}`);
      activeChatId = data.chat.id;
      setActiveChatInUrl(activeChatId);
      renderChatLog(data.messages || []);
      scrollChatToBottom();
      await refreshChatHistory();
    }

    chatForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!activeCustomerId) return;
      const message = chatInput.value.trim();
      if (!message) return;

      appendBubble("user", message);
      chatInput.value = "";
      chatSubmit.disabled = true;
      showStatus(chatStatus, "");
      const loading = appendBubble("assistant loading", "…");

      try {
        const body = { message };
        if (activeChatId) body.chat_id = activeChatId;

        const data = await api("/api/chat", {
          method: "POST",
          body: JSON.stringify(body),
        });

        loading.remove();
        activeChatId = data.chat_id;
        setActiveChatInUrl(activeChatId);
        appendBubble("assistant", data.answer, data.no_context ? [] : data.sources);
        await refreshChatHistory();
      } catch (_error) {
        loading.remove();
        appendBubble("assistant", "Entschuldigung, die Antwort konnte nicht geladen werden.", []);
        showStatus(chatStatus, "Chat fehlgeschlagen.", "error");
      } finally {
        chatSubmit.disabled = false;
      }
    });

    chatInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
      }
    });

    if (activeCustomerId && activeChatId) {
      loadChat(activeChatId).catch(() => {
        activeChatId = "";
        setActiveChatInUrl("");
        showStatus(chatStatus, "Chat-Verlauf konnte nicht geladen werden.", "error");
      });
    }
  }

  function initKbPage() {
    setKbReadOnlyMode(isGlobalCustomer());

    bindIngestForm({
      form: document.getElementById("ingest-form"),
      titleInput: document.getElementById("ingest-title"),
      textInput: document.getElementById("ingest-text"),
      submitBtn: document.getElementById("ingest-submit"),
      statusEl: document.getElementById("ingest-status"),
      fileInput: document.getElementById("file-input"),
      dropzone: document.getElementById("dropzone"),
      fileLabel: document.getElementById("file-label"),
      apiPath: "/api/documents",
      onSuccess: refreshKbDocuments,
    });

    if (activeCustomerId) {
      refreshKbDocuments().catch(() => showStatus(document.getElementById("ingest-status"), "Dokumente konnten nicht geladen werden.", "error"));
    }
  }

  function initAdminPage() {
    const promptScope = document.getElementById("prompt-scope");
    const promptContent = document.getElementById("prompt-content");
    const promptForm = document.getElementById("prompt-form");
    const promptStatus = document.getElementById("prompt-status");

    async function loadPrompt() {
      const scope = promptScope?.value || "global";
      const query = scope === "global" ? "" : `?customer_id=${encodeURIComponent(scope)}`;
      const data = await api(`/api/admin/system-prompt${query}`);
      if (promptContent) promptContent.value = data.content || "";
    }

    promptScope?.addEventListener("change", () => {
      loadPrompt().catch(() => showStatus(promptStatus, "Prompt konnte nicht geladen werden.", "error"));
    });

    promptForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const scope = promptScope?.value || "global";
      showStatus(promptStatus, "Speichern…");
      try {
        await api("/api/admin/system-prompt", {
          method: "PUT",
          body: JSON.stringify({
            customer_id: scope === "global" ? null : scope,
            content: promptContent?.value || "",
          }),
        });
        showStatus(promptStatus, "System-Prompt gespeichert.", "ok");
      } catch (_error) {
        showStatus(promptStatus, "Speichern fehlgeschlagen.", "error");
      }
    });

    bindIngestForm({
      form: document.getElementById("admin-ingest-form"),
      titleInput: document.getElementById("admin-ingest-title"),
      textInput: document.getElementById("admin-ingest-text"),
      submitBtn: document.getElementById("admin-ingest-submit"),
      statusEl: document.getElementById("admin-ingest-status"),
      fileInput: document.getElementById("admin-file-input"),
      dropzone: document.getElementById("admin-dropzone"),
      fileLabel: document.getElementById("admin-file-label"),
      apiPath: "/api/admin/documents",
      onSuccess: refreshAdminDocuments,
    });

    loadPrompt().catch(() => showStatus(promptStatus, "Prompt konnte nicht geladen werden.", "error"));
    refreshAdminDocuments().catch(() => showStatus(document.getElementById("admin-ingest-status"), "Dokumente konnten nicht geladen werden.", "error"));
  }

  function initCustomersPage() {
    const tbody = document.getElementById("customer-table-body");
    const emptyEl = document.getElementById("customer-empty");
    const countEl = document.getElementById("customer-count");
    const listStatus = document.getElementById("customer-list-status");
    const createForm = document.getElementById("customer-create-form");
    const createId = document.getElementById("customer-create-id");
    const createName = document.getElementById("customer-create-name");
    const createStatus = document.getElementById("customer-create-status");

    function renderCustomers(customers) {
      if (!tbody) return;
      tbody.innerHTML = "";
      const rows = customers || [];
      if (countEl) countEl.textContent = `(${rows.length})`;
      if (emptyEl) emptyEl.classList.toggle("hidden", rows.length > 0);

      rows.forEach((customer) => {
        const row = document.createElement("tr");
        row.dataset.customerId = customer.id;
        row.innerHTML = `
          <td><code>${escapeHtml(customer.id)}</code></td>
          <td>
            <span class="customer-name-display">${escapeHtml(customer.name)}</span>
            <input type="text" class="customer-name-input hidden" value="${escapeHtml(customer.name)}" maxlength="200">
          </td>
          <td>
            <div class="customer-actions">
              <button type="button" class="secondary small customer-edit-btn">Bearbeiten</button>
              <button type="button" class="secondary small customer-save-btn hidden">Speichern</button>
              <button type="button" class="secondary small customer-cancel-btn hidden">Abbrechen</button>
              <button type="button" class="danger small customer-delete-btn">Entfernen</button>
            </div>
          </td>
        `;
        tbody.appendChild(row);
      });
    }

    async function loadCustomers() {
      const data = await api("/api/admin/customers");
      renderCustomers(data.customers);
    }

    tbody?.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const row = target.closest("tr");
      if (!row) return;
      const customerId = row.dataset.customerId;
      const nameDisplay = row.querySelector(".customer-name-display");
      const nameInput = row.querySelector(".customer-name-input");
      const editBtn = row.querySelector(".customer-edit-btn");
      const saveBtn = row.querySelector(".customer-save-btn");
      const cancelBtn = row.querySelector(".customer-cancel-btn");

      if (target.classList.contains("customer-edit-btn")) {
        nameDisplay?.classList.add("hidden");
        nameInput?.classList.remove("hidden");
        editBtn?.classList.add("hidden");
        saveBtn?.classList.remove("hidden");
        cancelBtn?.classList.remove("hidden");
        if (nameInput instanceof HTMLInputElement) nameInput.focus();
        return;
      }

      if (target.classList.contains("customer-cancel-btn")) {
        if (nameInput instanceof HTMLInputElement && nameDisplay) {
          nameInput.value = nameDisplay.textContent || "";
        }
        nameDisplay?.classList.remove("hidden");
        nameInput?.classList.add("hidden");
        editBtn?.classList.remove("hidden");
        saveBtn?.classList.add("hidden");
        cancelBtn?.classList.add("hidden");
        return;
      }

      if (target.classList.contains("customer-save-btn")) {
        const nextName = nameInput instanceof HTMLInputElement ? nameInput.value.trim() : "";
        if (!nextName) {
          showStatus(listStatus, "Name darf nicht leer sein.", "error");
          return;
        }
        showStatus(listStatus, "Speichern…");
        try {
          const data = await api(`/api/admin/customers/${encodeURIComponent(customerId)}`, {
            method: "PATCH",
            body: JSON.stringify({ name: nextName }),
          });
          if (nameDisplay) nameDisplay.textContent = data.customer.name;
          nameDisplay?.classList.remove("hidden");
          nameInput?.classList.add("hidden");
          editBtn?.classList.remove("hidden");
          saveBtn?.classList.add("hidden");
          cancelBtn?.classList.add("hidden");
          showStatus(listStatus, "Kunde gespeichert.", "ok");
        } catch (_error) {
          showStatus(listStatus, "Speichern fehlgeschlagen.", "error");
        }
        return;
      }

      if (target.classList.contains("customer-delete-btn")) {
        const label = nameDisplay?.textContent || customerId;
        if (!window.confirm(`Kunde „${label}“ wirklich entfernen?`)) return;
        showStatus(listStatus, "Entfernen…");
        try {
          await api(`/api/admin/customers/${encodeURIComponent(customerId)}`, { method: "DELETE" });
          await loadCustomers();
          showStatus(listStatus, "Kunde entfernt.", "ok");
        } catch (_error) {
          showStatus(listStatus, "Entfernen fehlgeschlagen.", "error");
        }
      }
    });

    createForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const customerId = (createId?.value || "").trim().toLowerCase();
      const name = (createName?.value || "").trim();
      if (!customerId || !name) {
        showStatus(createStatus, "ID und Name sind Pflicht.", "error");
        return;
      }
      showStatus(createStatus, "Anlegen…");
      try {
        await api("/api/admin/customers", {
          method: "POST",
          body: JSON.stringify({ customer_id: customerId, name }),
        });
        if (createId) createId.value = "";
        if (createName) createName.value = "";
        showStatus(createStatus, "Kunde angelegt.", "ok");
        await loadCustomers();
      } catch (error) {
        const message =
          error.code === "customer_exists"
            ? "Kunden-ID existiert bereits."
            : error.code === "invalid_customer_id"
              ? "Ungültige Kunden-ID (nur a-z, 0-9, -, _)."
              : "Anlegen fehlgeschlagen.";
        showStatus(createStatus, message, "error");
      }
    });

    loadCustomers().catch(() => showStatus(listStatus, "Kunden konnten nicht geladen werden.", "error"));
  }

  syncActiveCustomerFromSelect();
  setCustomerUiEnabled(Boolean(activeCustomerId));
  initChatSidebar();
  refreshChatHistory().catch(() => {});

  if (page === "chat") initChatPage();
  if (page === "kb") initKbPage();
  if (page === "admin") {
    adminWorkspace?.classList.remove("disabled");
    initAdminPage();
  }
  if (page === "customers") {
    initCustomersPage();
  }
})();
