(() => {
  const boot = window.APP_BOOT || {};
  const page = boot.page || "chat";
  const customerNavMode = boot.customerNavMode || "scoped";
  const globalCustomerId = boot.globalCustomerId || "global";
  const customerLabels = boot.customerLabels || {};
  const isAdmin = Boolean(boot.isAdmin);
  let activeCustomerId = boot.activeCustomerId || "";
  let activeCustomerName = boot.activeCustomerName || "";

  function pageNeedsCustomer() {
    return customerNavMode === "scoped";
  }

  function adminScopeFromCustomerId(customerId) {
    if (!customerId || customerId === globalCustomerId) return "global";
    return customerId;
  }

  async function persistCustomerSession(customerId) {
    if (!customerId) return;
    await api("/api/session/customer", {
      method: "POST",
      body: JSON.stringify({ customer_id: customerId }),
    });
  }

  let refreshAdminKnowledgeDocuments = null;
  let refreshAdminPromptsPage = null;

  function syncAdminPageScopeFromSidebar(customerId) {
    if (page === "admin_knowledge") {
      syncActiveCustomerFromSelect();
      refreshAdminKnowledgeDocuments?.().catch(() => {});
      return;
    }
    if (page === "admin_prompts") {
      syncActiveCustomerFromSelect();
      refreshAdminPromptsPage?.().catch(() => {});
    }
  }

  function isGlobalCustomer() {
    return activeCustomerId === globalCustomerId;
  }

  const customerSelect = document.getElementById("customer-select");
  const noCustomerBanner = document.getElementById("no-customer-banner");
  const pageContent = document.getElementById("page-content");

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
      let detail = payload?.detail;
      if (Array.isArray(detail)) {
        detail = detail.map((item) => item.msg || item.type || String(item)).join("; ");
      } else if (detail && typeof detail === "object") {
        detail = JSON.stringify(detail);
      }
      const error = new Error(payload?.error || detail || "request_failed");
      error.code = payload?.error;
      error.detail = detail;
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

  function escapeAttr(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
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
    if (!pageNeedsCustomer()) return;

    if (enabled) {
      noCustomerBanner?.classList.add("hidden");
      pageContent?.classList.remove("disabled");
    } else {
      noCustomerBanner?.classList.remove("hidden");
      pageContent?.classList.add("disabled");
    }
  }

  function syncActiveCustomerFromSelect() {
    if (!customerSelect) return;
    if (customerSelect.tagName === "SELECT") {
      let value = customerSelect.value || "";
      if (!value && boot.activeCustomerId) {
        const match = customerSelect.querySelector(`option[value="${boot.activeCustomerId}"]`);
        if (match) {
          customerSelect.value = boot.activeCustomerId;
          value = boot.activeCustomerId;
        }
      }
      activeCustomerId = value;
      const option = customerSelect.selectedOptions[0];
      activeCustomerName =
        option && option.value
          ? option.textContent.trim()
          : customerLabels[activeCustomerId] || boot.activeCustomerName || "";
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

      if (customerNavMode === "global") {
        if (value) {
          try {
            await persistCustomerSession(value);
          } catch (_error) {
            /* session optional on global admin pages */
          }
        }
        return;
      }

      if (customerNavMode === "admin_scoped") {
        if (!value) {
          refreshChatHistory().catch(() => {});
          return;
        }
        try {
          await persistCustomerSession(value);
          syncAdminPageScopeFromSidebar(value);
        } catch (_error) {
          showStatus(document.getElementById("prompt-status"), "Kundenwechsel fehlgeschlagen.", "error");
        }
        return;
      }

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
    const { readOnly = false, showCustomer = false, adminEdit = null, searchActive = false } = options;
    if (!listEl) return;
    listEl.innerHTML = "";
    if (countEl) countEl.textContent = `(${documents.length})`;
    emptyEl?.classList.toggle("hidden", documents.length > 0);
    if (emptyEl && documents.length === 0) {
      emptyEl.textContent = searchActive
        ? "Keine Treffer für die aktuelle Suche."
        : readOnly
          ? "Noch keine Dokumente in den verfügbaren Wissensdatenbanken."
          : "Noch kein Wissen für diesen Kunden.";
    }

    for (const doc of documents) {
      const item = document.createElement("li");
      item.className = "doc-item";
      item.dataset.docId = doc.id;

      const meta = document.createElement("div");
      meta.className = "doc-meta";
      meta.innerHTML = `
        <strong class="doc-title" title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</strong>
        <div class="doc-meta-badges">${renderDocumentBadges(doc, { showCustomer })}</div>
      `;

      item.appendChild(meta);
      if (!readOnly) {
        const actions = document.createElement("div");
        actions.className = "row-actions doc-actions";

        if (adminEdit) {
          const editBtn = document.createElement("button");
          editBtn.type = "button";
          editBtn.className = "icon-btn secondary doc-edit-btn";
          editBtn.setAttribute("aria-label", "Bearbeiten");
          editBtn.innerHTML = ICON_EDIT;
          editBtn.addEventListener("click", () => {
            openAdminDocumentEditor(doc.id, adminEdit.basePath, listEl, adminEdit.onRefresh);
          });
          actions.appendChild(editBtn);
        }

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = adminEdit ? "icon-btn danger" : "danger";
        if (adminEdit) {
          delBtn.setAttribute("aria-label", "Löschen");
          delBtn.innerHTML = ICON_TRASH;
        } else {
          delBtn.textContent = "Löschen";
        }
        delBtn.addEventListener("click", async () => {
          if (!confirm(`Dokument „${doc.title}“ wirklich löschen?`)) return;
          await api(`${deletePath}/${doc.id}`, { method: "DELETE" });
          if (deletePath === "/api/documents") {
            await refreshKbDocuments();
          } else if (adminEdit?.onRefresh) {
            await adminEdit.onRefresh();
          } else if (deletePath.startsWith("/api/admin/customers/")) {
            const match = deletePath.match(/\/api\/admin\/customers\/([^/]+)\/documents/);
            await refreshAdminDocuments(match ? match[1] : "global");
          } else {
            await refreshAdminDocuments("global");
          }
        });
        actions.appendChild(delBtn);
        item.appendChild(actions);
      }
      listEl.appendChild(item);
    }
  }

  function closeAllDocEditPanels(listEl) {
    if (!listEl) return;
    listEl.querySelectorAll(".doc-edit-row").forEach((el) => el.remove());
  }

  async function openAdminDocumentEditor(docId, basePath, listEl, onRefresh) {
    closeAllDocEditPanels(listEl);
    const row = listEl?.querySelector(`.doc-item[data-doc-id="${docId}"]`);
    if (!row || !listEl) return;

    const editRow = document.createElement("li");
    editRow.className = "doc-edit-row";
    editRow.innerHTML = `
      <div class="doc-edit-panel ingest-form">
        <p class="status" data-role="load">Lade Inhalt…</p>
      </div>
    `;
    row.insertAdjacentElement("afterend", editRow);
    const panel = editRow.querySelector(".doc-edit-panel");
    const loadStatus = panel?.querySelector('[data-role="load"]');

    try {
      const data = await api(`${basePath}/${docId}`);
      if (!panel) return;
      const fromFileHint = data.from_file
        ? `<p class="muted doc-edit-hint">Text stammt aus einer Datei. Speichern ersetzt den indexierten Inhalt; die Originaldatei bleibt archiviert.</p>`
        : "";
      const images = Array.isArray(data.images) ? data.images : [];
      const imagesHtml = images.length
        ? `<div class="doc-edit-images"><p class="doc-edit-images-title">Extrahierte Bilder — klicken für Vollbild</p><div class="doc-edit-image-grid">${images
            .map((image) => {
              const base = image.page ? `Seite ${image.page}` : image.id;
              const label = image.transcribed ? `${base} · OCR` : `${base} · Vorschau`;
              return `<button type="button" class="doc-edit-image-item" title="Vollbild anzeigen"><img src="${escapeHtml(image.url)}" alt="${escapeHtml(label)}" loading="lazy"><span class="doc-edit-image-label">${escapeHtml(label)}</span></button>`;
            })
            .join("")}</div></div>`
        : "";
      panel.innerHTML = `
        <label>Titel<input type="text" class="doc-edit-title" maxlength="200" value="${escapeHtml(data.document.title)}"></label>
        <label>Inhalt<textarea class="doc-edit-text" rows="12" spellcheck="true"></textarea></label>
        ${fromFileHint}
        ${imagesHtml}
        <div class="doc-edit-actions">
          <button type="button" class="secondary small doc-edit-save">Speichern</button>
          <button type="button" class="secondary small doc-edit-cancel">Abbrechen</button>
        </div>
        <p class="status doc-edit-status" aria-live="polite"></p>
      `;
      const textArea = panel.querySelector(".doc-edit-text");
      if (textArea) textArea.value = data.text || "";
      bindDocumentImagePreviews(panel);

      panel.querySelector(".doc-edit-cancel")?.addEventListener("click", () => editRow.remove());
      panel.querySelector(".doc-edit-save")?.addEventListener("click", async () => {
        const title = panel.querySelector(".doc-edit-title")?.value.trim() || "";
        const text = panel.querySelector(".doc-edit-text")?.value || "";
        const statusEl = panel.querySelector(".doc-edit-status");
        if (!title) {
          showStatus(statusEl, "Titel ist Pflicht.", "error");
          return;
        }
        showStatus(statusEl, "Speichern…");
        try {
          await api(`${basePath}/${docId}`, {
            method: "PUT",
            body: JSON.stringify({ title, text }),
          });
          editRow.remove();
          await onRefresh();
        } catch (error) {
          const msg =
            error.code === "not_found"
              ? "Dokument nicht gefunden oder falscher Mandant."
              : error.code === "empty_text"
                ? "Text ist zu kurz (mind. 20 Zeichen)."
                : "Speichern fehlgeschlagen.";
          showStatus(statusEl, msg, "error");
        }
      });
    } catch (error) {
      console.error("Failed to load admin document editor content", error);
      let msg = "Inhalt konnte nicht geladen werden.";
      if (error && error.code) {
        if (error.code === "not_found") {
          msg = "Dokument nicht gefunden oder falscher Mandant.";
        } else if (error.code === "forbidden" || error.code === "not_authenticated") {
          msg = "Keine Berechtigung oder Sitzung abgelaufen. Bitte neu anmelden / Seite neu laden.";
        } else {
          msg = `Inhalt konnte nicht geladen werden (${error.code}).`;
        }
      }
      if (loadStatus) showStatus(loadStatus, msg, "error");
    }
  }

  function setupDocSearch(inputId, onSearch) {
    const input = document.getElementById(inputId);
    if (!input) return;
    let timer = null;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        onSearch().catch(() => {});
      }, 250);
    });
  }

  function documentsApiQuery(searchValue) {
    const search = (searchValue || "").trim();
    if (!search) return "";
    return `?search=${encodeURIComponent(search)}`;
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
    const searchInput = document.getElementById("kb-doc-search");
    const listStatus = document.getElementById("kb-doc-list-status");
    const search = searchInput?.value || "";
    showStatus(listStatus, search ? "Suche…" : "", "");
    try {
      const data = await api(`/api/documents${documentsApiQuery(search)}`);
      const readOnly = Boolean(data.read_only);
      setKbReadOnlyMode(readOnly);
      renderDocuments(
        data.documents || [],
        document.getElementById("doc-list"),
        document.getElementById("doc-count"),
        document.getElementById("doc-empty"),
        "/api/documents",
        { readOnly, showCustomer: readOnly, searchActive: Boolean(search.trim()) },
      );
      showStatus(
        listStatus,
        search && !(data.documents || []).length ? "Keine Treffer für die Suche." : "",
        search && !(data.documents || []).length ? "error" : "",
      );
    } catch (error) {
      showStatus(listStatus, "Dokumente konnten nicht geladen werden.", "error");
      throw error;
    }
  }

  async function refreshAdminDocuments(scope = "global", search = "") {
    const base =
      scope === "global"
        ? "/api/admin/documents"
        : `/api/admin/customers/${encodeURIComponent(scope)}/documents`;
    const listStatus = document.getElementById("admin-doc-list-status");
    showStatus(listStatus, search ? "Suche…" : "", "");
    try {
      const data = await api(`${base}${documentsApiQuery(search)}`);
      const listEl = document.getElementById("admin-doc-list");
      closeAllDocEditPanels(listEl);
      renderDocuments(
        data.documents || [],
        listEl,
        document.getElementById("admin-doc-count"),
        document.getElementById("admin-doc-empty"),
        base,
        {
          adminEdit: {
            basePath: base.replace(/\?.*$/, ""),
            onRefresh: () => refreshAdminDocuments(scope, search),
          },
          searchActive: Boolean(search.trim()),
        },
      );
      showStatus(
        listStatus,
        search && !(data.documents || []).length ? "Keine Treffer für die Suche." : "",
        search && !(data.documents || []).length ? "error" : "",
      );
    } catch (error) {
      showStatus(listStatus, "Dokumente konnten nicht geladen werden.", "error");
      throw error;
    }
  }

  function knowledgeScopeLabel(scope) {
    if (scope === "global") return "Global";
    return customerLabels[scope] || scope;
  }

  function initCollapsibleNav() {
    document.querySelectorAll(".nav-group-toggle").forEach((toggle) => {
      const group = toggle.closest(".nav-group");
      if (!group) return;
      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        group.classList.toggle("expanded");
        toggle.setAttribute("aria-expanded", group.classList.contains("expanded") ? "true" : "false");
      });
    });
  }

  function initSidebarNavScroll() {
    const nav = document.querySelector(".sidebar-nav");
    if (!nav) return;
    const storageKey = "sidebar-nav-scroll";
    const saved = sessionStorage.getItem(storageKey);
    if (saved !== null) {
      requestAnimationFrame(() => {
        nav.scrollTop = Number(saved) || 0;
      });
    }
    nav.addEventListener("scroll", () => {
      sessionStorage.setItem(storageKey, String(nav.scrollTop));
    });
    nav.querySelectorAll('a[href]').forEach((link) => {
      link.addEventListener("click", () => {
        sessionStorage.setItem(storageKey, String(nav.scrollTop));
      });
    });
  }

  const INSPECTABLE_FILE_PATTERN = /\.(txt|md|pdf|docx|png|jpe?g|webp|gif)$/i;

  function fileFromClipboard(clipboardData) {
    const items = clipboardData?.items;
    if (!items) return null;
    for (const item of items) {
      if (item.kind !== "file") continue;
      const file = item.getAsFile();
      if (!file) continue;
      if (file.type.startsWith("image/")) {
        const ext = file.type === "image/jpeg" ? "jpg" : file.type === "image/webp" ? "webp" : file.type === "image/gif" ? "gif" : "png";
        return new File([file], `eingefuegtes-bild-${Date.now()}.${ext}`, { type: file.type });
      }
      return file;
    }
    return null;
  }

  function setupDropzone(dropzone, fileInput, fileLabel, onSelect, isFileSelected) {
    if (!dropzone || !fileInput) return;

    const clearSelectedFile = () => {
      fileInput.value = "";
      onSelect(null);
    };

    dropzone.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (isFileSelected?.()) {
        clearSelectedFile();
        return;
      }
      fileInput.click();
    });
    dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (isFileSelected?.()) {
          clearSelectedFile();
          return;
        }
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
    dropzone.addEventListener("paste", (event) => {
      const file = fileFromClipboard(event.clipboardData);
      if (!file) return;
      event.preventDefault();
      onSelect(file);
    });
  }

  function formatDocSourceType(sourceType) {
    if (!sourceType) return "—";
    const raw = String(sourceType);
    if (raw.startsWith("kc:")) return raw.slice(3);
    return raw;
  }

  function renderExtractionBadges(extractionMeta) {
    if (!extractionMeta || typeof extractionMeta !== "object") return "";
    const parts = [];
    if (extractionMeta.coverage === "partial" && extractionMeta.image_count > 0) {
      const missing = Math.max(0, extractionMeta.image_count - (extractionMeta.images_processed || 0));
      if (missing > 0) {
        parts.push(`<span class="badge partial">${missing} Bild(er) offen</span>`);
      }
    }
    if (extractionMeta.vision_used) {
      parts.push('<span class="badge vision">Vision-OCR</span>');
    }
    return parts.join("");
  }

  function renderDocumentBadges(doc, { showCustomer = false } = {}) {
    const badges = [];
    if (showCustomer) {
      badges.push(`<span class="badge">${escapeHtml(customerLabels[doc.customer_id] || doc.customer_id)}</span>`);
    }
    badges.push(
      `<span class="badge ${doc.status === "failed" ? "failed" : ""}">${escapeHtml(formatDocSourceType(doc.source_type))}</span>`,
    );
    badges.push(`<span class="badge">${doc.chunk_count} Chunks</span>`);
    if (doc.status === "failed") {
      badges.push('<span class="badge failed">fehlgeschlagen</span>');
    }
    badges.push(renderExtractionBadges(doc.extraction_meta));
    return badges.filter(Boolean).join("");
  }

  function resolveInspectPath(apiPath) {
    const uploadPath = typeof apiPath === "function" ? apiPath() : apiPath;
    return `${uploadPath}/inspect`;
  }

  function resolveInspectTextPath(apiPath) {
    const uploadPath = typeof apiPath === "function" ? apiPath() : apiPath;
    return `${uploadPath}/inspect-text`;
  }

  function resolveMergePaths(apiPath, targetDocumentId) {
    const uploadPath = typeof apiPath === "function" ? apiPath() : apiPath;
    return {
      preview: `${uploadPath}/merge-preview`,
      apply: `${uploadPath}/${encodeURIComponent(targetDocumentId)}/merge`,
    };
  }

  function parseDuplicateDetail(detail) {
    if (!detail) return null;
    try {
      const parsed = JSON.parse(detail);
      if (parsed && parsed.title) return parsed;
    } catch (_error) {
      return null;
    }
    return null;
  }

  function applyInspectWarnings(inspection, warningEl, mergeActionsEl) {
    if (!warningEl) return;
    const parts = [];
    if (inspection?.duplicate?.title) {
      parts.push(`Identischer Inhalt bereits vorhanden: „${inspection.duplicate.title}"`);
    } else if (Array.isArray(inspection?.similar) && inspection.similar.length) {
      const labels = inspection.similar.map((item) => {
        const pct = Math.round((item.score || 0) * 100);
        return `„${item.title}" (${pct} %)`;
      });
      parts.push(`Sehr ähnlich zu: ${labels.join(", ")}`);
    }
    if (inspection?.has_images) {
      const count = inspection.image_count || 0;
      if (inspection.image_only) {
        parts.push(`${count} Bild(er), kein extrahierbarer Text — Vision-OCR erforderlich.`);
      } else {
        parts.push(`${count} Bild(er) erkannt — ohne Vision-OCR fehlt ggf. Inhalt.`);
      }
    }
    if (parts.length) {
      warningEl.textContent = parts.join(" · ");
      warningEl.classList.remove("hidden");
    } else {
      warningEl.textContent = "";
      warningEl.classList.add("hidden");
    }

    if (!mergeActionsEl) return;
    mergeActionsEl.innerHTML = "";
    if (!inspection?.duplicate && Array.isArray(inspection?.similar) && inspection.similar.length) {
      const top = inspection.similar[0];
      const pct = Math.round((top.score || 0) * 100);
      mergeActionsEl.className = "merge-actions";
      mergeActionsEl.innerHTML = `
        <div class="merge-suggestion-card">
          <div class="merge-suggestion-copy">
            <strong>Ähnlicher Eintrag (${pct}&nbsp;%)</strong>
            <p>„${escapeHtml(top.title)}" — statt einen Duplikat-Eintrag anzulegen, kannst du deine Änderungen direkt einarbeiten.</p>
          </div>
          <button type="button" class="merge-into-btn">Änderungen einarbeiten</button>
        </div>
      `;
      const btn = mergeActionsEl.querySelector(".merge-into-btn");
      if (btn) {
        btn.dataset.targetId = top.document_id;
        btn.dataset.targetTitle = top.title;
        btn.dataset.targetScore = String(top.score || 0);
      }
    } else {
      mergeActionsEl.className = "merge-actions hidden";
    }
  }

  async function askDuplicateProceed(duplicate) {
    const title = duplicate?.title || "Bestehendes Dokument";
    return window.confirm(`Identischer Inhalt existiert bereits als „${title}". Trotzdem einpflegen?`);
  }

  function ensureImageLightbox() {
    let lightbox = document.getElementById("image-lightbox");
    if (lightbox) return lightbox;

    lightbox = document.createElement("div");
    lightbox.id = "image-lightbox";
    lightbox.className = "image-lightbox hidden";
    lightbox.innerHTML = `
      <button type="button" class="image-lightbox-backdrop" aria-label="Vollbild schließen"></button>
      <div class="image-lightbox-content" role="dialog" aria-modal="true" aria-label="Bildvorschau">
        <button type="button" class="image-lightbox-close" aria-label="Schließen">×</button>
        <img class="image-lightbox-img" src="" alt="">
        <p class="image-lightbox-caption"></p>
      </div>
    `;
    document.body.appendChild(lightbox);

    const close = () => lightbox.classList.add("hidden");
    lightbox.querySelector(".image-lightbox-backdrop")?.addEventListener("click", close);
    lightbox.querySelector(".image-lightbox-close")?.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !lightbox.classList.contains("hidden")) close();
    });

    return lightbox;
  }

  function openImageLightbox(url, label = "") {
    const lightbox = ensureImageLightbox();
    const img = lightbox.querySelector(".image-lightbox-img");
    const caption = lightbox.querySelector(".image-lightbox-caption");
    if (img) {
      img.src = url;
      img.alt = label || "Extrahiertes Bild";
    }
    if (caption) caption.textContent = label || "";
    lightbox.classList.remove("hidden");
  }

  function bindDocumentImagePreviews(container) {
    if (!container) return;
    container.querySelectorAll(".doc-edit-image-item").forEach((item) => {
      item.addEventListener("click", () => {
        const img = item.querySelector("img");
        const label = item.querySelector(".doc-edit-image-label")?.textContent?.trim() || "";
        if (img?.src) openImageLightbox(img.src, label);
      });
    });
  }

  function ensureImageVisionModal() {
    let modal = document.getElementById("image-vision-modal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "image-vision-modal";
    modal.className = "image-vision-modal hidden";
    modal.innerHTML = `
      <div class="image-vision-dialog" role="dialog" aria-modal="true" aria-labelledby="image-vision-title">
        <div class="image-vision-header">
          <h3 id="image-vision-title">Bilder in der Datei erkannt</h3>
          <div class="image-vision-select-actions">
            <button type="button" class="secondary small modal-select-all">Alle markieren</button>
            <button type="button" class="secondary small modal-unselect-all">Alle abwählen</button>
          </div>
        </div>
        <p class="image-vision-text">
          <span class="modal-count">0</span> Bild(er) gefunden. Wähle, welche per Vision-OCR transkribiert werden.
          Alle Bilder werden im Eintrag als klickbare Vorschau gespeichert.
        </p>
        <div class="image-vision-grid" aria-label="Bilder für OCR auswählen"></div>
        <div class="image-vision-actions">
          <button type="button" class="modal-vision">Ausgewählte transkribieren</button>
          <button type="button" class="secondary modal-text">Ohne OCR einpflegen</button>
          <button type="button" class="secondary modal-cancel">Abbrechen</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    // Attach permanent "mark all / unmark all" listeners (once, on modal creation)
    const selectAllBtn = modal.querySelector(".modal-select-all");
    const unselectAllBtn = modal.querySelector(".modal-unselect-all");
    const attachToggle = (btn, checked) => {
      if (!btn) return;
      btn.addEventListener("click", () => {
        const grid = modal.querySelector(".image-vision-grid");
        if (!grid) return;
        grid.querySelectorAll('input[name="transcribe-image"]').forEach((cb) => {
          cb.checked = checked;
        });
      });
    };
    attachToggle(selectAllBtn, true);
    attachToggle(unselectAllBtn, false);

    return modal;
  }

  function askImageVisionChoice(inspection) {
    return new Promise((resolve) => {
      const modal = ensureImageVisionModal();
      const countEl = modal.querySelector(".modal-count");
      const grid = modal.querySelector(".image-vision-grid");
      const images = Array.isArray(inspection?.images) ? inspection.images : [];
      const imageCount = inspection?.image_count || images.length || 0;
      if (countEl) countEl.textContent = String(imageCount);

      if (grid) {
        grid.innerHTML = images.length
          ? images
              .map((image) => {
                const label = image.label || image.id || "Bild";
                const preview = image.preview_data_url || "";
                return `
                  <label class="image-vision-option">
                    <input type="checkbox" name="transcribe-image" value="${escapeHtml(image.id || "")}">
                    <span class="image-vision-thumb-wrap">
                      <img src="${preview}" alt="${escapeHtml(label)}" loading="lazy">
                    </span>
                    <span class="image-vision-option-label">${escapeHtml(label)}</span>
                  </label>
                `;
              })
              .join("")
          : `<p class="image-vision-empty">Keine Vorschau verfügbar — alle Bilder werden gespeichert.</p>`;
      }

      modal.classList.remove("hidden");

      const finish = (result) => {
        modal.classList.add("hidden");
        resolve(result);
      };

      const selectedIds = () =>
        Array.from(modal.querySelectorAll('input[name="transcribe-image"]:checked'))
          .map((input) => input.value)
          .filter(Boolean);

      modal.querySelector(".modal-vision")?.addEventListener(
        "click",
        () => finish({ action: "transcribe", selectedIds: selectedIds() }),
        { once: true },
      );
      modal.querySelector(".modal-text")?.addEventListener(
        "click",
        () => finish({ action: "text", selectedIds: [] }),
        { once: true },
      );
      modal.querySelector(".modal-cancel")?.addEventListener(
        "click",
        () => finish({ action: "cancel", selectedIds: [] }),
        { once: true },
      );
    });
  }

  function mergeBlockLabel(kind) {
    const labels = {
      unchanged: "Unverändert",
      modified: "Geändert",
      added: "Neu",
      removed: "Entfernt",
    };
    return labels[kind] || kind;
  }

  function mergeBlockCheckboxLabel(kind) {
    if (kind === "modified") return "Neue Version übernehmen";
    if (kind === "added") return "Einfügen";
    if (kind === "removed") return "Abschnitt entfernen";
    return "";
  }

  function setMergeWizardStep(modal, step) {
    modal.dataset.mergeStep = String(step);
    modal.querySelectorAll(".merge-step").forEach((el) => {
      const active = el.dataset.step === String(step);
      el.classList.toggle("merge-step-active", active);
      el.classList.toggle("merge-step-done", Number(el.dataset.step) < step);
    });
    modal.querySelector('[data-panel="review"]')?.classList.toggle("hidden", step !== 1);
    modal.querySelector('[data-panel="confirm"]')?.classList.toggle("hidden", step !== 2);
    const backBtn = modal.querySelector(".modal-merge-back");
    const nextBtn = modal.querySelector(".modal-merge-next");
    const applyBtn = modal.querySelector(".modal-merge-apply");
    if (backBtn) backBtn.classList.toggle("hidden", step === 1);
    if (nextBtn) nextBtn.classList.toggle("hidden", step !== 1);
    if (applyBtn) applyBtn.classList.toggle("hidden", step !== 2);
  }

  function renderMergeGuidance(modal, preview) {
    const guidanceEl = modal.querySelector(".document-merge-guidance");
    if (!guidanceEl) return;

    const needsLlm = Boolean(preview?.needs_llm_assist);
    const isLlm = preview?.source === "llm";
    let tone = "info";
    if (needsLlm && !isLlm) tone = "warn";
    if (isLlm) tone = "success";

    const summary = preview?.llm_summary
      ? `<p class="document-merge-llm-summary">${escapeHtml(preview.llm_summary)}</p>`
      : "";

    guidanceEl.className = `document-merge-guidance merge-guidance-${tone}`;
    guidanceEl.innerHTML = `
      <p class="document-merge-guidance-text">${escapeHtml(preview?.guidance || "")}</p>
      ${summary}
    `;
    guidanceEl.classList.remove("hidden");

    const llmBtn = modal.querySelector(".modal-merge-llm");
    const resetBtn = modal.querySelector(".modal-merge-reset");
    if (llmBtn) {
      llmBtn.classList.toggle("hidden", !preview?.llm_available || isLlm);
      llmBtn.disabled = false;
    }
    if (resetBtn) {
      resetBtn.classList.toggle("hidden", !isLlm);
    }
  }

  function ensureDocumentMergeModal() {
    let modal = document.getElementById("document-merge-modal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "document-merge-modal";
    modal.className = "document-merge-modal hidden";
    modal.innerHTML = `
      <div class="document-merge-dialog" role="dialog" aria-modal="true" aria-labelledby="document-merge-title">
        <div class="document-merge-header">
          <div class="document-merge-steps" aria-label="Fortschritt">
            <span class="merge-step merge-step-active" data-step="1">1 · Abschnitte prüfen</span>
            <span class="merge-step-sep" aria-hidden="true">→</span>
            <span class="merge-step" data-step="2">2 · Vorschau &amp; Übernehmen</span>
          </div>
          <h3 id="document-merge-title">In bestehendes Dokument einarbeiten</h3>
          <p class="document-merge-subtitle"></p>
        </div>
        <div class="document-merge-guidance hidden"></div>
        <div class="document-merge-panel" data-panel="review">
          <div class="document-merge-toolbar">
            <button type="button" class="secondary small modal-merge-select-all">Alle Änderungen übernehmen</button>
            <button type="button" class="secondary small modal-merge-select-none">Alle abweisen</button>
          </div>
          <p class="document-merge-stats"></p>
          <div class="document-merge-blocks" aria-label="Abschnittsvergleich"></div>
          <div class="document-merge-assist-actions">
            <button type="button" class="modal-merge-llm">KI-Vorschlag laden</button>
            <button type="button" class="secondary modal-merge-reset hidden">Automatischen Vergleich wiederherstellen</button>
          </div>
        </div>
        <div class="document-merge-panel hidden" data-panel="confirm">
          <p class="document-merge-confirm-lead">So sieht der Eintrag nach der Zusammenführung aus. Du kannst den Text noch anpassen.</p>
          <label class="document-merge-preview-label" for="document-merge-preview-field">Finale Vorschau</label>
          <textarea id="document-merge-preview-field" class="document-merge-preview" rows="10"></textarea>
        </div>
        <div class="document-merge-actions">
          <button type="button" class="secondary modal-merge-back hidden">Zurück</button>
          <button type="button" class="modal-merge-next">Weiter zur Vorschau</button>
          <button type="button" class="modal-merge-apply hidden">Übernehmen &amp; Re-Index</button>
          <button type="button" class="secondary modal-merge-cancel">Abbrechen</button>
        </div>
        <p class="document-merge-status" role="status"></p>
      </div>
    `;
    document.body.appendChild(modal);
    return modal;
  }

  function collectMergePreviewText(modal, preview) {
    const parts = [];
    for (const block of preview?.blocks || []) {
      const item = modal.querySelector(`[data-block-id="${block.id}"]`);
      const checkbox = item?.querySelector('input[type="checkbox"]');
      const include = block.kind === "unchanged" ? true : Boolean(checkbox?.checked);
      if (block.kind === "unchanged" && block.old_text) {
        parts.push(block.old_text);
      } else if (block.kind === "modified") {
        parts.push(include ? block.new_text : block.old_text);
      } else if (block.kind === "added" && include && block.new_text) {
        parts.push(block.new_text);
      } else if (block.kind === "removed" && !include && block.old_text) {
        parts.push(block.old_text);
      }
    }
    return parts.filter(Boolean).join("\n\n");
  }

  function collectMergeBlockPayload(modal, preview) {
    return (preview?.blocks || []).map((block) => {
      const item = modal.querySelector(`[data-block-id="${block.id}"]`);
      const checkbox = item?.querySelector('input[type="checkbox"]');
      const include = block.kind === "unchanged" ? null : Boolean(checkbox?.checked);
      return {
        id: block.id,
        kind: block.kind,
        old_text: block.old_text ?? null,
        new_text: block.new_text ?? null,
        include,
        hint: block.hint ?? null,
        source: block.source ?? preview?.source ?? null,
      };
    });
  }

  function renderMergeBlocks(modal, preview) {
    const blocksEl = modal.querySelector(".document-merge-blocks");
    const statsEl = modal.querySelector(".document-merge-stats");
    if (!blocksEl) return;

    const stats = preview.stats || {};
    if (statsEl) {
      const sourceLabel = preview.source === "llm" ? " · KI-Vorschlag" : "";
      statsEl.textContent = [
        stats.modified ? `${stats.modified} geändert` : null,
        stats.added ? `${stats.added} neu` : null,
        stats.removed ? `${stats.removed} entfernt` : null,
        stats.unchanged ? `${stats.unchanged} unverändert` : null,
        sourceLabel,
      ]
        .filter(Boolean)
        .join(" · ");
    }

    blocksEl.innerHTML = (preview.blocks || [])
      .map((block) => {
        const kind = block.kind || "unchanged";
        const label = mergeBlockLabel(kind);
        const checkboxLabel = mergeBlockCheckboxLabel(kind);
        const score =
          typeof block.score === "number" ? ` · ${Math.round(block.score * 100)} % Ähnlichkeit` : "";
        const defaultInclude = block.include === true;
        const hint = block.hint
          ? `<p class="merge-block-hint">${escapeHtml(block.hint)}</p>`
          : "";
        const checkbox =
          kind === "unchanged"
            ? `<span class="merge-block-note">wird beibehalten</span>`
            : `<label class="merge-block-toggle">
                <input type="checkbox" ${defaultInclude ? "checked" : ""}>
                ${escapeHtml(checkboxLabel)}
              </label>`;

        const oldPart = block.old_text
          ? `<div class="merge-block-old"><span class="merge-block-side-label">Bestehend</span><pre>${escapeHtml(block.old_text)}</pre></div>`
          : "";
        const newPart = block.new_text
          ? `<div class="merge-block-new"><span class="merge-block-side-label">Neu</span><pre>${escapeHtml(block.new_text)}</pre></div>`
          : "";

        return `
          <article class="merge-block-item merge-block-${kind}" data-block-id="${escapeHtml(block.id)}" data-block-kind="${kind}" data-default-include="${defaultInclude}">
            <header class="merge-block-header">
              <span class="merge-block-kind">${escapeHtml(label)}${score}</span>
              ${checkbox}
            </header>
            ${hint}
            <div class="merge-block-body">${oldPart}${newPart}</div>
          </article>
        `;
      })
      .join("");

    blocksEl.querySelectorAll('input[type="checkbox"]').forEach((input) => {
      input.addEventListener("change", () => {
        const previewEl = modal.querySelector(".document-merge-preview");
        if (previewEl && modal.dataset.mergeStep === "2") {
          previewEl.value = collectMergePreviewText(modal, modal._mergePreview);
        }
      });
    });

    renderMergeGuidance(modal, preview);
  }

  async function loadMergePreview(modal, { paths, getSourcePayload, useLlm = false, statusEl }) {
    const mergeStatus = modal.querySelector(".document-merge-status");
    if (mergeStatus) {
      mergeStatus.textContent = useLlm
        ? "KI analysiert die Texte…"
        : "Automatischer Vergleich wird geladen…";
    }

    const formData = getSourcePayload();
    if (useLlm) formData.append("use_llm", "true");

    try {
      const preview = await api(paths.preview, { method: "POST", body: formData });
      modal._mergePreview = preview;
      renderMergeBlocks(modal, preview);
      if (mergeStatus) mergeStatus.textContent = "";
      return preview;
    } catch (_error) {
      if (mergeStatus) {
        mergeStatus.textContent = useLlm
          ? "KI-Vorschlag fehlgeschlagen — automatischer Vergleich bleibt aktiv."
          : "Vergleich konnte nicht geladen werden.";
      }
      if (statusEl && !useLlm) showStatus(statusEl, "Merge-Vorschau fehlgeschlagen.", "error");
      throw _error;
    }
  }

  async function openDocumentMergeModal({
    targetDocumentId,
    targetTitle,
    targetScore,
    apiPath,
    getSourcePayload,
    onSuccess,
    statusEl,
  }) {
    const modal = ensureDocumentMergeModal();
    const subtitle = modal.querySelector(".document-merge-subtitle");
    const mergeStatus = modal.querySelector(".document-merge-status");
    const applyBtn = modal.querySelector(".modal-merge-apply");
    const cancelBtn = modal.querySelector(".modal-merge-cancel");
    const nextBtn = modal.querySelector(".modal-merge-next");
    const backBtn = modal.querySelector(".modal-merge-back");
    const llmBtn = modal.querySelector(".modal-merge-llm");
    const resetBtn = modal.querySelector(".modal-merge-reset");
    const selectAllBtn = modal.querySelector(".modal-merge-select-all");
    const selectNoneBtn = modal.querySelector(".modal-merge-select-none");
    const previewField = modal.querySelector(".document-merge-preview");

    const scorePct = targetScore ? Math.round(Number(targetScore) * 100) : null;
    if (subtitle) {
      const scorePart = scorePct ? ` (${scorePct} % ähnlich)` : "";
      subtitle.textContent = `Ziel: „${targetTitle || "Bestehendes Dokument"}"${scorePart}`;
    }

    setMergeWizardStep(modal, 1);
    modal.classList.remove("hidden");

    const paths = resolveMergePaths(apiPath, targetDocumentId);
    modal._getSourcePayload = getSourcePayload;

    try {
      await loadMergePreview(modal, { paths, getSourcePayload, useLlm: false, statusEl });
    } catch (_error) {
      modal.classList.add("hidden");
      return;
    }

    if (applyBtn) applyBtn.disabled = false;

    return new Promise((resolve) => {
      const controller = new AbortController();
      const { signal } = controller;

      const finish = (result) => {
        controller.abort();
        modal.classList.add("hidden");
        modal._mergePreview = null;
        modal._getSourcePayload = null;
        resolve(result);
      };

      const goToConfirm = () => {
        const preview = modal._mergePreview;
        if (previewField) {
          previewField.value = collectMergePreviewText(modal, preview);
          previewField.readOnly = false;
        }
        setMergeWizardStep(modal, 2);
      };

      cancelBtn?.addEventListener("click", () => finish({ action: "cancel" }), { signal });

      backBtn?.addEventListener("click", () => setMergeWizardStep(modal, 1), { signal });

      nextBtn?.addEventListener("click", goToConfirm, { signal });

      selectAllBtn?.addEventListener(
        "click",
        () => {
          modal.querySelectorAll('.merge-block-item input[type="checkbox"]').forEach((cb) => {
            cb.checked = true;
          });
        },
        { signal },
      );

      selectNoneBtn?.addEventListener(
        "click",
        () => {
          modal.querySelectorAll('.merge-block-item input[type="checkbox"]').forEach((cb) => {
            cb.checked = false;
          });
        },
        { signal },
      );

      llmBtn?.addEventListener(
        "click",
        async () => {
          if (llmBtn.disabled) return;
          llmBtn.disabled = true;
          try {
            await loadMergePreview(modal, { paths, getSourcePayload, useLlm: true, statusEl });
          } catch (_error) {
            llmBtn.disabled = false;
          }
        },
        { signal },
      );

      resetBtn?.addEventListener(
        "click",
        async () => {
          if (resetBtn.disabled) return;
          resetBtn.disabled = true;
          try {
            await loadMergePreview(modal, { paths, getSourcePayload, useLlm: false, statusEl });
          } finally {
            resetBtn.disabled = false;
          }
        },
        { signal },
      );

      applyBtn?.addEventListener(
        "click",
        async () => {
          if (applyBtn.disabled) return;
          applyBtn.disabled = true;
          if (mergeStatus) mergeStatus.textContent = "Wird zusammengeführt und neu indexiert…";

          const preview = modal._mergePreview;
          const blockPayload = collectMergeBlockPayload(modal, preview);
          const formData = getSourcePayload();
          formData.append("blocks", JSON.stringify(blockPayload));
          const editedPreview = previewField?.value?.trim();
          if (editedPreview) formData.append("merged_text", editedPreview);

          try {
            await api(paths.apply, { method: "POST", body: formData });
            if (statusEl) showStatus(statusEl, `In „${targetTitle}" eingearbeitet und neu indexiert.`, "ok");
            await onSuccess?.();
            finish({ action: "applied" });
          } catch (_error) {
            if (mergeStatus) mergeStatus.textContent = "Zusammenführung fehlgeschlagen.";
            if (statusEl) showStatus(statusEl, "Zusammenführung fehlgeschlagen.", "error");
            applyBtn.disabled = false;
          }
        },
        { signal },
      );
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
    let fileInspection = null;
    let pendingInspection = false;

    function updateSubmitEnabled() {
      if (!submitBtn) return;
      const hasContent = !!(textInput?.value.trim() || selectedFile);
      submitBtn.disabled = !hasContent || pendingInspection;
    }

    const warningEl = document.createElement("p");
    warningEl.className = "image-warning-banner hidden";
    warningEl.setAttribute("role", "status");

    const mergeActionsEl = document.createElement("div");
    mergeActionsEl.className = "merge-actions hidden";

    if (submitBtn?.parentNode === form) {
      form.insertBefore(warningEl, submitBtn);
      form.insertBefore(mergeActionsEl, submitBtn);
    } else if (form) {
      form.appendChild(warningEl);
      form.appendChild(mergeActionsEl);
    }

    let textInspectTimer = null;

    const runTextInspect = async (prefixText) => {
      if (selectedFile || !prefixText || prefixText.length < 20) {
        if (!selectedFile && !prefixText) {
          fileInspection = null;
          applyInspectWarnings(null, warningEl, mergeActionsEl);
        }
        return;
      }
      try {
        const inspectTextPath = resolveInspectTextPath(apiPath);
        const textInspection = await api(inspectTextPath, {
          method: "POST",
          body: (() => {
            const fd = new FormData();
            fd.append("text", prefixText);
            return fd;
          })(),
        });
        fileInspection = { ...(fileInspection || {}), ...textInspection };
        applyInspectWarnings(fileInspection, warningEl, mergeActionsEl);
      } catch (_error) {
        /* ignore debounced text inspect errors */
      }
    };

    const setFile = async (file) => {
      selectedFile = file;
      fileInspection = null;
      warningEl.textContent = "";
      warningEl.classList.add("hidden");
      mergeActionsEl.innerHTML = "";
      mergeActionsEl.classList.add("hidden");

      if (fileLabel) {
        fileLabel.textContent = file
          ? `${file.name} — klicken zum Entfernen`
          : "Datei hierher ziehen oder klicken";
      }
      dropzone?.classList.toggle("has-file", Boolean(file));
      dropzone?.setAttribute("aria-label", file ? "Ausgewählte Datei entfernen" : "Datei auswählen");

      if (!file) {
        pendingInspection = false;
        updateSubmitEnabled();
        return;
      }

      const lowerName = file.name.toLowerCase();
      if (!INSPECTABLE_FILE_PATTERN.test(lowerName)) {
        updateSubmitEnabled();
        return;
      }

      pendingInspection = true;
      if (submitBtn) submitBtn.disabled = true;

      const formData = new FormData();
      formData.append("file", file);
      const prefixForInspect = textInput?.value.trim() || "";
      if (prefixForInspect) formData.append("text", prefixForInspect);
      try {
        const inspectPath = resolveInspectPath(apiPath);
        fileInspection = await api(inspectPath, { method: "POST", body: formData });
        applyInspectWarnings(fileInspection, warningEl, mergeActionsEl);
      } catch (_error) {
        warningEl.textContent = "Datei konnte nicht geprüft werden.";
        warningEl.classList.remove("hidden");
      } finally {
        pendingInspection = false;
        updateSubmitEnabled();
      }
    };

    setupDropzone(dropzone, fileInput, fileLabel, (file) => {
      setFile(file).catch(() => {});
    }, () => Boolean(selectedFile));

    textInput?.addEventListener("input", () => {
      updateSubmitEnabled();
      if (textInspectTimer) window.clearTimeout(textInspectTimer);
      textInspectTimer = window.setTimeout(() => {
        runTextInspect(textInput.value.trim()).catch(() => {});
      }, 450);
    });

    mergeActionsEl.addEventListener("click", async (event) => {
      const button = event.target.closest(".merge-into-btn");
      if (!button) return;
      const targetDocumentId = button.dataset.targetId;
      const targetTitle = button.dataset.targetTitle || "Bestehendes Dokument";
      const prefixText = textInput?.value.trim() || "";
      if (!prefixText && !selectedFile) {
        showStatus(statusEl, "Bitte Text und/oder Datei für den Merge angeben.", "error");
        return;
      }

      await openDocumentMergeModal({
        targetDocumentId,
        targetTitle,
        targetScore: button.dataset.targetScore,
        apiPath,
        getSourcePayload: () => {
          const formData = new FormData();
          formData.append("target_document_id", targetDocumentId);
          if (prefixText) formData.append("text", prefixText);
          if (selectedFile) formData.append("file", selectedFile);
          return formData;
        },
        onSuccess: async () => {
          if (titleInput) titleInput.value = "";
          if (textInput) textInput.value = "";
          if (fileInput) fileInput.value = "";
          await setFile(null);
          await onSuccess();
        },
        statusEl,
      });
    });

    form?.addEventListener("paste", (event) => {
      const file = fileFromClipboard(event.clipboardData);
      if (!file) return;
      event.preventDefault();
      setFile(file).catch(() => {}).finally(() => updateSubmitEnabled());
    });

    updateSubmitEnabled();

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const prefixText = textInput?.value.trim() || "";
      if (!prefixText && !selectedFile) {
        showStatus(statusEl, "Bitte Text und/oder Datei angeben.", "error");
        return;
      }

      let processImages = false;
      let transcribeImageIds = [];
      if (fileInspection?.has_images) {
        const choice = await askImageVisionChoice(fileInspection);
        if (choice.action === "cancel") return;
        if (choice.action === "text" && fileInspection.image_only) {
          showStatus(statusEl, "Enthält nur Bilder — bitte Vision-OCR wählen oder Text im Formular ergänzen.", "error");
          return;
        }
        processImages = choice.action === "transcribe";
        transcribeImageIds = choice.selectedIds || [];
        if (processImages && transcribeImageIds.length === 0) {
          showStatus(statusEl, "Bitte mindestens ein Bild für Vision-OCR auswählen.", "error");
          return;
        }
      }

      submitBtn.disabled = true;
      showStatus(
        statusEl,
        processImages
          ? `Vision-OCR läuft (${transcribeImageIds.length} Bild(er))…`
          : "Wird indexiert…",
      );

      const submitIngest = async (allowDuplicate = false) => {
        const formData = new FormData();
        if (titleInput?.value.trim()) formData.append("title", titleInput.value.trim());
        if (prefixText) formData.append("text", prefixText);
        if (selectedFile) formData.append("file", selectedFile);
        if (processImages) {
          formData.append("process_images", "true");
          formData.append("transcribe_image_ids", JSON.stringify(transcribeImageIds));
        }
        if (allowDuplicate) formData.append("allow_duplicate", "true");
        const resolvedPath = typeof apiPath === "function" ? apiPath() : apiPath;
        await api(resolvedPath, { method: "POST", body: formData });
      };

      try {
        try {
          await submitIngest(false);
        } catch (error) {
          if (error.code !== "duplicate_document") throw error;
          const duplicate =
            parseDuplicateDetail(error.detail) || fileInspection?.duplicate || null;
          if (!(await askDuplicateProceed(duplicate))) {
            showStatus(statusEl, "Einpflegen abgebrochen — Duplikat.", "error");
            return;
          }
          await submitIngest(true);
        }
        showStatus(statusEl, "Wissen erfolgreich indexiert.", "ok");
        if (titleInput) titleInput.value = "";
        if (textInput) textInput.value = "";
        if (fileInput) fileInput.value = "";
        await setFile(null);
        await onSuccess();
      } catch (error) {
        const messages = {
          empty_text: "Inhalt zu kurz (min. 20 Zeichen gesamt).",
          unsupported_file_type: "Nur .txt, .md, .pdf, .docx und Bildformate (.png, .jpg, …) erlaubt.",
          file_too_large: "Datei überschreitet 30 MB.",
          extraction_failed: "Text konnte nicht extrahiert werden.",
          inspection_failed: "Datei konnte nicht auf Bilder geprüft werden.",
          images_only_requires_vision: "Enthält nur Bilder — Vision-OCR wählen oder Begleittext ergänzen.",
          vision_failed: "Vision-OCR fehlgeschlagen — bitte erneut versuchen oder API/Token prüfen.",
          duplicate_document: "Identischer Inhalt existiert bereits in der Wissensdatenbank.",
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

    setupDocSearch("kb-doc-search", refreshKbDocuments);

    if (activeCustomerId) {
      refreshKbDocuments().catch(() =>
        showStatus(document.getElementById("ingest-status"), "Dokumente konnten nicht geladen werden.", "error"),
      );
    }
  }

  function initImageToTextTool() {
    const zone = document.getElementById("image-paste-zone");
    const zoneEmpty = document.getElementById("image-dropzone-empty");
    const inlinePreview = document.getElementById("image-preview-inline");
    const fileInput = document.getElementById("image-file-input");
    const transcribeBtn = document.getElementById("transcribe-btn");
    const clearBtn = document.getElementById("clear-images-btn");
    const statusEl = document.getElementById("tool-status");
    const resultsEl = document.getElementById("transcribe-results");

    let images = []; // {id, file: File, url: string}
    let mermaidReady = false;

    function ensureMermaid() {
      if (mermaidReady || typeof window.mermaid === "undefined") return;
      window.mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        securityLevel: "strict",
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
      });
      mermaidReady = true;
    }

    function updateDropzoneState() {
      const hasImages = images.length > 0;
      zone?.classList.toggle("has-images", hasImages);
      zoneEmpty?.classList.toggle("hidden", hasImages);
      inlinePreview?.classList.toggle("hidden", !hasImages);
      if (transcribeBtn) transcribeBtn.disabled = !hasImages;
    }

    function renderInlinePreview() {
      if (!inlinePreview) return;
      inlinePreview.innerHTML = "";
      images.forEach((img) => {
        const item = document.createElement("div");
        item.className = "bild-tool-thumb";
        item.innerHTML = `
          <img src="${img.url}" alt="">
          <button type="button" class="bild-tool-thumb-remove" data-id="${img.id}" title="Entfernen">×</button>
          <div class="bild-tool-thumb-meta">${escapeHtml(img.file.name || "Bild")}</div>
          <label class="bild-tool-thumb-check">
            <input type="checkbox" class="select-img" data-id="${img.id}" checked> OCR
          </label>
        `;
        inlinePreview.appendChild(item);
      });
      updateDropzoneState();
    }

    inlinePreview?.addEventListener("click", (e) => {
      const removeBtn = e.target.closest(".bild-tool-thumb-remove");
      if (!removeBtn) return;
      e.stopPropagation();
      const id = removeBtn.dataset.id;
      const entry = images.find((i) => i.id === id);
      if (entry) URL.revokeObjectURL(entry.url);
      images = images.filter((i) => i.id !== id);
      renderInlinePreview();
      if (images.length === 0 && resultsEl) resultsEl.classList.add("hidden");
    });

    function addImage(file) {
      if (!file || !file.type.startsWith("image/")) return;
      const id = "img_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
      const url = URL.createObjectURL(file);
      images.push({ id, file, url });
      renderInlinePreview();
      if (resultsEl) resultsEl.classList.add("hidden");
      showStatus(statusEl, "");
    }

    function handlePaste(ev) {
      if (ev.defaultPrevented) return;
      let added = false;
      if (typeof fileFromClipboard === "function") {
        const f = fileFromClipboard(ev.clipboardData);
        if (f) {
          ev.preventDefault();
          addImage(f);
          added = true;
        }
      }
      if (!added && ev.clipboardData?.files?.length) {
        ev.preventDefault();
        Array.from(ev.clipboardData.files).forEach(addImage);
      }
    }

    if (zone && fileInput) {
      zone.addEventListener("click", (ev) => {
        if (ev.target.closest(".bild-tool-thumb-remove, .select-img, label")) return;
        fileInput.click();
        zone.focus();
      });
      zone.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          fileInput.click();
        }
      });
      fileInput.addEventListener("change", () => {
        Array.from(fileInput.files || []).forEach(addImage);
        fileInput.value = "";
      });
      zone.addEventListener("paste", handlePaste);
      document.getElementById("image-tool-form")?.addEventListener("paste", handlePaste);
      document.addEventListener("paste", handlePaste);
      zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
      zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
      zone.addEventListener("drop", (e) => {
        e.preventDefault();
        zone.classList.remove("dragover");
        Array.from(e.dataTransfer.files || []).forEach(addImage);
      });
    }

    clearBtn?.addEventListener("click", () => {
      images.forEach((i) => URL.revokeObjectURL(i.url));
      images = [];
      renderInlinePreview();
      if (resultsEl) {
        resultsEl.innerHTML = "";
        resultsEl.classList.add("hidden");
      }
      showStatus(statusEl, "");
    });

    function buildClipboardPayload(text, mermaid) {
      const body = (text || "").trim();
      if (!mermaid) return body;
      return `${body}\n\n\`\`\`mermaid\n${mermaid.trim()}\n\`\`\``;
    }

    async function flashButton(btn, label = "Kopiert!") {
      if (!btn) return;
      const old = btn.textContent;
      btn.textContent = label;
      setTimeout(() => { btn.textContent = old; }, 1200);
    }

    async function renderMermaidDiagram(container, code) {
      ensureMermaid();
      if (!container || !code || typeof window.mermaid === "undefined") return;
      const renderId = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      try {
        const { svg } = await window.mermaid.render(renderId, code);
        container.innerHTML = svg;
      } catch (_err) {
        container.innerHTML = `<p class="muted">Diagramm konnte nicht gerendert werden — Code-Ansicht nutzen.</p>`;
      }
    }

    function createMermaidPanel(mermaidCode) {
      const panel = document.createElement("div");
      panel.className = "bild-mermaid-panel";
      panel.innerHTML = `
        <div class="bild-mermaid-toolbar">
          <span class="bild-mermaid-label">Mermaid</span>
          <div class="bild-mermaid-toggle" role="tablist" aria-label="Mermaid-Ansicht">
            <button type="button" class="active" data-mode="diagram">Diagramm</button>
            <button type="button" data-mode="code">Code</button>
          </div>
          <button type="button" class="secondary small copy-mermaid-code-btn">Code kopieren</button>
        </div>
        <div class="bild-mermaid-view">
          <div class="bild-mermaid-diagram" aria-label="Mermaid-Diagramm"></div>
          <pre class="bild-mermaid-code hidden"></pre>
        </div>
      `;
      const diagramEl = panel.querySelector(".bild-mermaid-diagram");
      const codeEl = panel.querySelector(".bild-mermaid-code");
      if (codeEl) codeEl.textContent = mermaidCode;
      renderMermaidDiagram(diagramEl, mermaidCode);

      const toggle = panel.querySelector(".bild-mermaid-toggle");
      toggle?.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-mode]");
        if (!btn) return;
        toggle.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        const showCode = btn.dataset.mode === "code";
        diagramEl?.classList.toggle("hidden", showCode);
        codeEl?.classList.toggle("hidden", !showCode);
      });

      panel.querySelector(".copy-mermaid-code-btn")?.addEventListener("click", async (ev) => {
        const btn = ev.currentTarget;
        try {
          await navigator.clipboard.writeText(mermaidCode);
          await flashButton(btn);
        } catch (_err) {}
      });

      return panel;
    }

    function renderResults(results) {
      if (!resultsEl) return;
      resultsEl.innerHTML = "";

      results.forEach((r, idx) => {
        const card = document.createElement("article");
        card.className = "bild-result-card";

        const head = document.createElement("div");
        head.className = "bild-result-head";
        head.innerHTML = `<h3 class="bild-result-title">${escapeHtml(r.filename || `Bild ${idx + 1}`)}</h3>`;
        card.appendChild(head);

        if (r.error) {
          const err = document.createElement("p");
          err.className = "bild-result-error";
          err.textContent = r.error + (r.detail ? ` (${r.detail})` : "");
          card.appendChild(err);
          resultsEl.appendChild(card);
          return;
        }

        const text = r.text || "";
        const mermaid = r.mermaid || "";
        const copyPayload = buildClipboardPayload(text, mermaid);

        const actions = document.createElement("div");
        actions.className = "bild-result-actions";
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "secondary small";
        copyBtn.textContent = mermaid ? "Text + Mermaid kopieren" : "Text kopieren";
        copyBtn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(copyPayload);
            await flashButton(copyBtn);
          } catch (_err) {}
        });
        actions.appendChild(copyBtn);
        head.appendChild(actions);

        const body = document.createElement("div");
        body.className = "bild-result-body";

        const ta = document.createElement("textarea");
        ta.className = "bild-result-text";
        ta.value = text;
        ta.readOnly = true;
        ta.rows = Math.min(14, Math.max(4, text.split("\n").length + 1));
        body.appendChild(ta);

        if (mermaid) {
          body.appendChild(createMermaidPanel(mermaid));
        }

        card.appendChild(body);
        resultsEl.appendChild(card);
      });

      resultsEl.classList.toggle("hidden", results.length === 0);
    }

    transcribeBtn?.addEventListener("click", async () => {
      const selected = [];
      inlinePreview?.querySelectorAll(".select-img:checked").forEach((cb) => {
        const id = cb.dataset.id;
        const entry = images.find((i) => i.id === id);
        if (entry) selected.push(entry);
      });
      if (selected.length === 0) {
        showStatus(statusEl, "Bitte mindestens ein Bild auswählen.", "error");
        return;
      }

      showStatus(statusEl, `Vision-OCR läuft (${selected.length} Bild(er))…`);
      transcribeBtn.disabled = true;

      const formData = new FormData();
      selected.forEach((entry) => {
        formData.append("files", entry.file, entry.file.name || "image.png");
      });

      try {
        const res = await api("/api/tools/transcribe", { method: "POST", body: formData });
        renderResults(res.results || []);
        showStatus(statusEl, "Fertig — Ergebnis kann kopiert werden.", "ok");
      } catch (err) {
        const msg = (err && err.code) ? `Fehler: ${err.code}` : "Transkription fehlgeschlagen.";
        showStatus(statusEl, msg, "error");
      } finally {
        transcribeBtn.disabled = images.length === 0;
      }
    });

    renderInlinePreview();
    if (resultsEl) resultsEl.classList.add("hidden");
  }

  function initAdminKnowledgePage() {
    const statusEl = document.getElementById("admin-ingest-status");

    function currentScope() {
      return adminScopeFromCustomerId(activeCustomerId || globalCustomerId);
    }

    async function refreshScopeDocuments() {
      const search = document.getElementById("admin-doc-search")?.value || "";
      await refreshAdminDocuments(currentScope(), search);
    }
    refreshAdminKnowledgeDocuments = refreshScopeDocuments;

    bindIngestForm({
      form: document.getElementById("admin-ingest-form"),
      titleInput: document.getElementById("admin-ingest-title"),
      textInput: document.getElementById("admin-ingest-text"),
      submitBtn: document.getElementById("admin-ingest-submit"),
      statusEl,
      fileInput: document.getElementById("admin-file-input"),
      dropzone: document.getElementById("admin-dropzone"),
      fileLabel: document.getElementById("admin-file-label"),
      apiPath: () => {
        const scope = currentScope();
        return scope === "global"
          ? "/api/admin/documents"
          : `/api/admin/customers/${encodeURIComponent(scope)}/documents`;
      },
      onSuccess: refreshScopeDocuments,
    });

    setupDocSearch("admin-doc-search", refreshScopeDocuments);
    refreshScopeDocuments().catch(() =>
      showStatus(statusEl, "Dokumente konnten nicht geladen werden.", "error"),
    );
  }

  function initAdminPromptsPage() {
    const promptContent = document.getElementById("prompt-content");
    const promptForm = document.getElementById("prompt-form");
    const promptStatus = document.getElementById("prompt-status");

    function currentScope() {
      return adminScopeFromCustomerId(activeCustomerId || globalCustomerId);
    }

    async function loadPrompt() {
      const scope = currentScope();
      const query = scope === "global" ? "" : `?customer_id=${encodeURIComponent(scope)}`;
      const data = await api(`/api/admin/system-prompt${query}`);
      if (promptContent) promptContent.value = data.content || "";
    }
    refreshAdminPromptsPage = loadPrompt;

    promptForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const scope = currentScope();
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

    loadPrompt().catch(() => showStatus(promptStatus, "Prompt konnte nicht geladen werden.", "error"));
  }

  function renderCustomerCheckboxes(container, customers, selectedIds, namePrefix) {
    if (!container) return;
    const selected = new Set(selectedIds || []);
    container.innerHTML = "";
    (customers || []).forEach((customer) => {
      const row = document.createElement("label");
      row.className = "user-customer-row";
      row.innerHTML = `
        <input type="checkbox" name="${escapeHtml(namePrefix)}" value="${escapeHtml(customer.id)}" ${selected.has(customer.id) ? "checked" : ""}>
        <span class="user-customer-row-body">
          <code class="user-customer-slug">${escapeHtml(customer.id)}</code>
          <span class="user-customer-name">${escapeHtml(customer.name)}</span>
        </span>
      `;
      container.appendChild(row);
    });
  }

  const ICON_EDIT =
    '<svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
  const ICON_TRASH =
    '<svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
  const ICON_SAVE =
    '<svg class="icon-btn-svg" viewBox="0 0 24 24" aria-hidden="true" style="color:#2e7d32"><path fill="currentColor" d="M17 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm0 16H7v-2h10v2zm-2-8H7V5h8v2H9v2h6v2z"/></svg>';

  function readCheckboxValues(container, namePrefix) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(`input[name="${namePrefix}"]:checked`)).map(
      (el) => el.value,
    );
  }

  function roleOptionsPanelMarkup({ nameValue = "", nameInputClass = "", nameInputId = "", isAdmin = false, autoCustomers = false } = {}) {
    const nameAttrs = [
      nameInputId ? `id="${escapeHtml(nameInputId)}"` : "",
      nameInputClass ? `class="${escapeHtml(nameInputClass)}"` : "",
      !nameInputClass && !nameInputId ? "" : "",
    ].filter(Boolean).join(" ");
    const adminActive = isAdmin ? "is-active" : "is-inactive";
    const autoActive = autoCustomers ? "is-active" : "is-inactive";
    return `
      <div class="role-options-panel">
        <label class="role-name-field">
          <span class="ingest-field-label">Name</span>
          <input type="text" maxlength="120" placeholder="z. B. Support BG Frankfurt" ${nameAttrs} value="${escapeHtml(nameValue)}" required>
        </label>
        <div class="role-toggle-group" role="group" aria-label="Rollenoptionen">
          <button type="button" class="role-toggle-btn ${adminActive}" data-toggle="admin" aria-pressed="${isAdmin ? "true" : "false"}" title="Administrator — voller Systemzugriff">ADM</button>
          <button type="button" class="role-toggle-btn ${autoActive}" data-toggle="auto-customers" aria-pressed="${autoCustomers ? "true" : "false"}" title="Neue Kunden automatisch zuweisen">AK</button>
        </div>
      </div>
    `;
  }

  function bindRoleToggleButtons(panel, options = {}) {
    if (!panel) return;
    const { customersContainer = null } = options;
    panel.querySelectorAll(".role-toggle-btn[data-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = btn.getAttribute("aria-pressed") !== "true";
        btn.setAttribute("aria-pressed", next ? "true" : "false");
        btn.classList.toggle("is-active", next);
        btn.classList.toggle("is-inactive", !next);
        if (btn.dataset.toggle === "auto-customers" && next && customersContainer) {
          customersContainer.querySelectorAll('input[type="checkbox"]').forEach((el) => {
            el.checked = true;
          });
        }
      });
    });
  }

  function readRoleOption(panel, key) {
    const btn = panel?.querySelector(`.role-toggle-btn[data-toggle="${key}"]`);
    return btn?.getAttribute("aria-pressed") === "true";
  }

  function resetRoleToggleButtons(panel) {
    panel?.querySelectorAll(".role-toggle-btn[data-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", "false");
      btn.classList.remove("is-active");
      btn.classList.add("is-inactive");
    });
  }

  function readCustomerCheckboxValues(container, namePrefix) {
    return readCheckboxValues(container, namePrefix);
  }

  function renderRoleCheckboxes(container, roles, selectedIds, namePrefix, onChange) {
    if (!container) return;
    const selected = new Set(selectedIds || []);
    container.innerHTML = "";
    (roles || []).forEach((role) => {
      const row = document.createElement("label");
      row.className = "user-customer-row";
      row.innerHTML = `
        <input type="checkbox" name="${escapeHtml(namePrefix)}" value="${escapeHtml(role.id)}" ${selected.has(role.id) ? "checked" : ""}>
        <span class="user-customer-row-body">
          <span class="user-customer-name">${escapeHtml(role.name)}</span>
          <span class="muted">${role.is_admin ? "Admin" : "Benutzer"}${role.auto_add_new_customers ? " · Auto-Kunden" : ""}</span>
        </span>
      `;
      const input = row.querySelector("input");
      input?.addEventListener("change", () => onChange?.());
      container.appendChild(row);
    });
  }

  function initRolesPage() {
    const roleTbody = document.getElementById("role-table-body");
    const roleEmptyEl = document.getElementById("role-empty");
    const roleCountEl = document.getElementById("role-count");
    const roleListStatus = document.getElementById("role-list-status");
    const roleCreateForm = document.getElementById("role-create-form");
    const roleCreateName = document.getElementById("role-create-name");
    const roleCreateOptions = document.getElementById("role-create-options");
    const roleCreateCustomers = document.getElementById("role-create-customers");
    const roleCreateStatus = document.getElementById("role-create-status");
    let assignableCustomers = [];
    let customerNameById = {};

    bindRoleToggleButtons(roleCreateOptions, { customersContainer: roleCreateCustomers });

    function customerBadges(ids) {
      const slugs = ids || [];
      if (!slugs.length) return '<span class="muted">—</span>';
      return `<span class="user-badge-list">${slugs
        .map((slug) => {
          const title = customerNameById[slug] || slug;
          return `<span class="badge user-slug-badge" title="${escapeHtml(title)}">${escapeHtml(slug)}</span>`;
        })
        .join("")}</span>`;
    }

    function renderRoles(roles) {
      if (!roleTbody) return;
      roleTbody.innerHTML = "";
      const rows = roles || [];
      if (roleCountEl) roleCountEl.textContent = `(${rows.length})`;
      if (roleEmptyEl) roleEmptyEl.classList.toggle("hidden", rows.length > 0);

      rows.forEach((role) => {
        const row = document.createElement("tr");
        row.dataset.roleId = role.id;
        row.innerHTML = `
          <td><span class="role-name-display">${escapeHtml(role.name)}</span></td>
          <td class="user-customers-cell">${customerBadges(role.customer_ids)}</td>
          <td>${role.is_admin ? "Ja" : "Nein"}</td>
          <td>${role.auto_add_new_customers ? "Ja" : "Nein"}</td>
          <td class="user-actions-cell">
            <div class="row-actions">
              <button type="button" class="icon-btn secondary role-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
              <button type="button" class="icon-btn danger role-delete-btn" aria-label="Entfernen">${ICON_TRASH}</button>
            </div>
          </td>
        `;
        roleTbody.appendChild(row);

        const editRow = document.createElement("tr");
        editRow.className = "role-edit-row hidden";
        editRow.dataset.roleId = role.id;
        editRow.innerHTML = `
          <td colspan="5">
            <div class="ingest-form">
              ${roleOptionsPanelMarkup({
                nameValue: role.name,
                nameInputClass: "role-edit-name",
                isAdmin: role.is_admin,
                autoCustomers: role.auto_add_new_customers,
              })}
              <fieldset class="user-customers-fieldset">
                <legend>Kunden (Preset)</legend>
                <div class="role-edit-customers user-customer-checkboxes"></div>
              </fieldset>
              <div class="customer-actions">
                <button type="button" class="secondary small role-save-btn">Speichern</button>
                <button type="button" class="secondary small role-cancel-btn">Abbrechen</button>
              </div>
            </div>
          </td>
        `;
        roleTbody.appendChild(editRow);
        bindRoleToggleButtons(editRow.querySelector(".role-options-panel"), {
          customersContainer: editRow.querySelector(".role-edit-customers"),
        });
        renderCustomerCheckboxes(
          editRow.querySelector(".role-edit-customers"),
          assignableCustomers,
          role.customer_ids,
          `role-edit-${role.id}`,
        );
      });
    }

    async function loadRoles() {
      const data = await api("/api/admin/roles");
      assignableCustomers = data.customers || [];
      customerNameById = Object.fromEntries(assignableCustomers.map((c) => [c.id, c.name]));
      renderCustomerCheckboxes(roleCreateCustomers, assignableCustomers, [], "role-create");
      renderRoles(data.roles || []);
    }

    roleTbody?.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      if (target.closest(".role-edit-btn")) {
        const row = target.closest("tr:not(.role-edit-row)");
        if (!row) return;
        const roleId = row.dataset.roleId;
        const editRow = roleTbody.querySelector(`tr.role-edit-row[data-role-id="${roleId}"]`);
        roleTbody.querySelectorAll(".role-edit-row").forEach((el) => el.classList.add("hidden"));
        editRow?.classList.remove("hidden");
        return;
      }

      if (target.closest(".role-cancel-btn")) {
        target.closest("tr.role-edit-row")?.classList.add("hidden");
        return;
      }

      if (target.closest(".role-save-btn")) {
        const editRow = target.closest("tr.role-edit-row");
        if (!editRow) return;
        const roleId = editRow.dataset.roleId;
        const name = editRow.querySelector(".role-edit-name")?.value.trim() || "";
        const optionsPanel = editRow.querySelector(".role-options-panel");
        const isAdmin = readRoleOption(optionsPanel, "admin");
        const autoCustomers = readRoleOption(optionsPanel, "auto-customers");
        const customerIds = readCustomerCheckboxValues(
          editRow.querySelector(".role-edit-customers"),
          `role-edit-${roleId}`,
        );
        if (!name) {
          showStatus(roleListStatus, "Rollenname ist Pflicht.", "error");
          return;
        }
        showStatus(roleListStatus, "Speichern…");
        try {
          await api(`/api/admin/roles/${encodeURIComponent(roleId)}`, {
            method: "PATCH",
            body: JSON.stringify({
              name,
              customer_ids: customerIds,
              is_admin: isAdmin,
              auto_add_new_customers: autoCustomers,
            }),
          });
          editRow.classList.add("hidden");
          await loadRoles();
          showStatus(roleListStatus, "Rolle gespeichert.", "ok");
        } catch (err) {
          const msg = err?.code === "role_exists" ? "Rollenname existiert bereits." : "Speichern fehlgeschlagen.";
          showStatus(roleListStatus, msg, "error");
        }
        return;
      }

      if (target.closest(".role-delete-btn")) {
        const row = target.closest("tr:not(.role-edit-row)");
        if (!row) return;
        const roleId = row.dataset.roleId;
        const name = row.querySelector(".role-name-display")?.textContent || roleId;
        if (!window.confirm(`Rolle „${name}“ wirklich löschen?`)) return;
        showStatus(roleListStatus, "Entfernen…");
        try {
          await api(`/api/admin/roles/${encodeURIComponent(roleId)}`, { method: "DELETE" });
          await loadRoles();
          showStatus(roleListStatus, "Rolle gelöscht.", "ok");
        } catch {
          showStatus(roleListStatus, "Entfernen fehlgeschlagen.", "error");
        }
      }
    });

    roleCreateForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = (roleCreateName?.value || "").trim();
      const isAdmin = readRoleOption(roleCreateOptions, "admin");
      const autoCustomers = readRoleOption(roleCreateOptions, "auto-customers");
      const customerIds = readCustomerCheckboxValues(roleCreateCustomers, "role-create");
      if (!name) {
        showStatus(roleCreateStatus, "Rollenname ist Pflicht.", "error");
        return;
      }
      showStatus(roleCreateStatus, "Anlegen…");
      try {
        await api("/api/admin/roles", {
          method: "POST",
          body: JSON.stringify({
            name,
            customer_ids: customerIds,
            is_admin: isAdmin,
            auto_add_new_customers: autoCustomers,
          }),
        });
        if (roleCreateName) roleCreateName.value = "";
        resetRoleToggleButtons(roleCreateOptions);
        roleCreateCustomers?.querySelectorAll("input[type=checkbox]").forEach((el) => {
          el.checked = false;
        });
        showStatus(roleCreateStatus, "Rolle angelegt.", "ok");
        await loadRoles();
      } catch (err) {
        const msg = err?.code === "role_exists" ? "Rollenname existiert bereits." : "Anlegen fehlgeschlagen.";
        showStatus(roleCreateStatus, msg, "error");
      }
    });

    loadRoles().catch(() => showStatus(roleListStatus, "Rollen konnten nicht geladen werden.", "error"));
  }

  function initUsersPage() {
    const tbody = document.getElementById("user-table-body");
    const emptyEl = document.getElementById("user-empty");
    const countEl = document.getElementById("user-count");
    const listStatus = document.getElementById("user-list-status");
    const createForm = document.getElementById("user-create-form");
    const createEmail = document.getElementById("user-create-email");
    const createPassword = document.getElementById("user-create-password");
    const createAdmin = document.getElementById("user-create-admin");
    const createRoles = document.getElementById("user-create-roles");
    const createCustomers = document.getElementById("user-create-customers");
    const createStatus = document.getElementById("user-create-status");
    let assignableCustomers = [];
    let assignableRoles = [];
    let customerNameById = {};
    let roleNameById = {};

    function applyRolePreset(rolesContainer, rolePrefix, adminEl, customersEl, customerPrefix) {
      const selectedRoleIds = readCheckboxValues(rolesContainer, rolePrefix);
      let isAdmin = false;
      const customerSet = new Set();
      selectedRoleIds.forEach((roleId) => {
        const role = assignableRoles.find((item) => item.id === roleId);
        if (!role) return;
        if (role.is_admin) isAdmin = true;
        (role.customer_ids || []).forEach((customerId) => customerSet.add(customerId));
      });
      if (adminEl) adminEl.checked = isAdmin;
      renderCustomerCheckboxes(customersEl, assignableCustomers, Array.from(customerSet), customerPrefix);
    }

    function customerBadges(ids) {
      const slugs = ids || [];
      if (!slugs.length) return '<span class="muted">—</span>';
      return `<span class="user-badge-list">${slugs
        .map((slug) => {
          const title = customerNameById[slug] || slug;
          return `<span class="badge user-slug-badge" title="${escapeHtml(title)}">${escapeHtml(slug)}</span>`;
        })
        .join("")}</span>`;
    }

    function roleBadges(ids) {
      const roleIds = ids || [];
      if (!roleIds.length) return '<span class="muted">—</span>';
      return `<span class="user-badge-list">${roleIds
        .map((roleId) => {
          const title = roleNameById[roleId] || roleId;
          return `<span class="badge user-role-badge" title="${escapeHtml(title)}">${escapeHtml(title)}</span>`;
        })
        .join("")}</span>`;
    }

    function renderUsers(users) {
      if (!tbody) return;
      tbody.innerHTML = "";
      const rows = users || [];
      if (countEl) countEl.textContent = `(${rows.length})`;
      if (emptyEl) emptyEl.classList.toggle("hidden", rows.length > 0);

      rows.forEach((user) => {
        const row = document.createElement("tr");
        row.dataset.userId = user.id;
        row.innerHTML = `
          <td><span class="user-email-display">${escapeHtml(user.email)}</span></td>
          <td class="user-customers-cell">${roleBadges(user.role_ids)}</td>
          <td class="user-customers-cell">${customerBadges(user.customer_ids)}</td>
          <td>${user.is_admin ? "Admin" : "Benutzer"}</td>
          <td>${user.is_active ? "Aktiv" : "Inaktiv"}</td>
          <td class="user-actions-cell">
            <div class="row-actions">
              <button type="button" class="icon-btn secondary user-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
              <button type="button" class="icon-btn danger user-delete-btn" aria-label="Entfernen">${ICON_TRASH}</button>
            </div>
          </td>
        `;
        tbody.appendChild(row);

        const editRow = document.createElement("tr");
        editRow.className = "user-edit-row hidden";
        editRow.dataset.userId = user.id;
        editRow.innerHTML = `
          <td colspan="6">
            <div class="ingest-form">
              <div class="customer-form-row user-form-row">
                <label>E-Mail<input type="email" class="user-edit-email" value="${escapeHtml(user.email)}" maxlength="200"></label>
                <label>Neues Passwort (optional)<input type="password" class="user-edit-password" minlength="8" placeholder="leer = unverändert"></label>
                <label class="user-admin-checkbox"><input type="checkbox" class="user-edit-admin" ${user.is_admin ? "checked" : ""}> Administrator</label>
                <label class="user-admin-checkbox"><input type="checkbox" class="user-edit-active" ${user.is_active ? "checked" : ""}> Aktiv</label>
              </div>
              <fieldset class="user-customers-fieldset">
                <legend>Rollen (Preset anwenden)</legend>
                <div class="user-edit-roles user-customer-checkboxes"></div>
              </fieldset>
              <fieldset class="user-customers-fieldset">
                <legend>Kunden</legend>
                <div class="user-edit-customers user-customer-checkboxes"></div>
              </fieldset>
              <div class="customer-actions">
                <button type="button" class="secondary small user-save-btn">Speichern</button>
                <button type="button" class="secondary small user-cancel-btn">Abbrechen</button>
              </div>
            </div>
          </td>
        `;
        tbody.appendChild(editRow);
        const rolesEl = editRow.querySelector(".user-edit-roles");
        const customersEl = editRow.querySelector(".user-edit-customers");
        const adminEl = editRow.querySelector(".user-edit-admin");
        renderRoleCheckboxes(rolesEl, assignableRoles, user.role_ids, `user-roles-${user.id}`, () =>
          applyRolePreset(rolesEl, `user-roles-${user.id}`, adminEl, customersEl, `edit-${user.id}`),
        );
        renderCustomerCheckboxes(customersEl, assignableCustomers, user.customer_ids, `edit-${user.id}`);
      });
    }

    async function loadUsers() {
      const data = await api("/api/admin/users");
      assignableCustomers = data.customers || [];
      assignableRoles = data.roles || [];
      customerNameById = Object.fromEntries(assignableCustomers.map((c) => [c.id, c.name]));
      roleNameById = Object.fromEntries(assignableRoles.map((r) => [r.id, r.name]));
      renderRoleCheckboxes(createRoles, assignableRoles, [], "user-create-roles", () =>
        applyRolePreset(createRoles, "user-create-roles", createAdmin, createCustomers, "create"),
      );
      renderCustomerCheckboxes(createCustomers, assignableCustomers, [], "create");
      renderUsers(data.users || []);
    }

    tbody?.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      if (target.closest(".user-edit-btn")) {
        const row = target.closest("tr:not(.user-edit-row)");
        if (!row) return;
        const userId = row.dataset.userId;
        const editRow = tbody.querySelector(`tr.user-edit-row[data-user-id="${userId}"]`);
        tbody.querySelectorAll(".user-edit-row").forEach((el) => el.classList.add("hidden"));
        editRow?.classList.remove("hidden");
        return;
      }

      if (target.closest(".user-cancel-btn")) {
        const editRow = target.closest("tr.user-edit-row");
        editRow?.classList.add("hidden");
        return;
      }

      if (target.closest(".user-save-btn")) {
        const editRow = target.closest("tr.user-edit-row");
        if (!editRow) return;
        const userId = editRow.dataset.userId;
        const email = editRow?.querySelector(".user-edit-email")?.value.trim() || "";
        const password = editRow?.querySelector(".user-edit-password")?.value || "";
        const isAdmin = Boolean(editRow?.querySelector(".user-edit-admin")?.checked);
        const isActive = Boolean(editRow?.querySelector(".user-edit-active")?.checked);
        const roleIds = readCheckboxValues(editRow?.querySelector(".user-edit-roles"), `user-roles-${userId}`);
        const customerIds = readCustomerCheckboxValues(editRow?.querySelector(".user-edit-customers"), `edit-${userId}`);
        if (!email) {
          showStatus(listStatus, "E-Mail ist Pflicht.", "error");
          return;
        }
        showStatus(listStatus, "Speichern…");
        try {
          const body = {
            email,
            customer_ids: customerIds,
            role_ids: roleIds,
            is_admin: isAdmin,
            is_active: isActive,
          };
          if (password) body.password = password;
          await api(`/api/admin/users/${encodeURIComponent(userId)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          editRow?.classList.add("hidden");
          await loadUsers();
          showStatus(listStatus, "Benutzer gespeichert.", "ok");
        } catch (err) {
          const msg =
            err?.code === "user_exists"
              ? "E-Mail existiert bereits."
              : err?.code === "cannot_demote_self"
                ? "Eigenes Admin-Recht kann nicht entzogen werden."
                : err?.code === "cannot_deactivate_self"
                  ? "Eigenes Konto kann nicht deaktiviert werden."
                  : "Speichern fehlgeschlagen.";
          showStatus(listStatus, msg, "error");
        }
        return;
      }

      if (target.closest(".user-delete-btn")) {
        const row = target.closest("tr:not(.user-edit-row)");
        if (!row) return;
        const userId = row.dataset.userId;
        const email = row.querySelector(".user-email-display")?.textContent || userId;
        if (!window.confirm(`Benutzer „${email}“ wirklich deaktivieren?`)) return;
        showStatus(listStatus, "Entfernen…");
        try {
          await api(`/api/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
          await loadUsers();
          showStatus(listStatus, "Benutzer deaktiviert.", "ok");
        } catch (err) {
          const msg = err?.code === "cannot_deactivate_self" ? "Eigenes Konto kann nicht deaktiviert werden." : "Entfernen fehlgeschlagen.";
          showStatus(listStatus, msg, "error");
        }
      }
    });

    createForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = (createEmail?.value || "").trim();
      const password = createPassword?.value || "";
      const isAdmin = Boolean(createAdmin?.checked);
      const roleIds = readCheckboxValues(createRoles, "user-create-roles");
      const customerIds = readCustomerCheckboxValues(createCustomers, "create");
      if (!email || !password) {
        showStatus(createStatus, "E-Mail und Passwort sind Pflicht.", "error");
        return;
      }
      showStatus(createStatus, "Anlegen…");
      try {
        await api("/api/admin/users", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            customer_ids: customerIds,
            role_ids: roleIds,
            is_admin: isAdmin,
          }),
        });
        if (createEmail) createEmail.value = "";
        if (createPassword) createPassword.value = "";
        if (createAdmin) createAdmin.checked = false;
        createRoles?.querySelectorAll("input[type=checkbox]").forEach((el) => {
          el.checked = false;
        });
        createCustomers?.querySelectorAll("input[type=checkbox]").forEach((el) => {
          el.checked = false;
        });
        showStatus(createStatus, "Benutzer angelegt.", "ok");
        await loadUsers();
      } catch (err) {
        const msg =
          err?.code === "user_exists"
            ? "E-Mail existiert bereits."
            : err?.code === "invalid_password"
              ? "Passwort zu kurz (mind. 8 Zeichen)."
              : "Anlegen fehlgeschlagen.";
        showStatus(createStatus, msg, "error");
      }
    });

    loadUsers().catch(() => showStatus(listStatus, "Benutzer konnten nicht geladen werden.", "error"));
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
        const created = customer.created_at ? new Date(customer.created_at).toLocaleDateString('de-DE') : '';
        row.innerHTML = `
          <td>
            <div class="customer-id-cell">
              <code class="customer-id-display">${escapeHtml(customer.id)}</code>
              ${created ? `<span class="customer-meta">${created}</span>` : ''}
            </div>
            <input type="text" class="customer-id-input hidden" value="${escapeHtml(customer.id)}" maxlength="64" placeholder="neue slug">
          </td>
          <td>
            <span class="customer-name-display">${escapeHtml(customer.name)}</span>
            <input type="text" class="customer-name-input hidden" value="${escapeHtml(customer.name)}" maxlength="200">
          </td>
          <td>
            <div class="row-actions">
              <button type="button" class="icon-btn secondary customer-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
              <button type="button" class="icon-btn save customer-save-btn hidden" aria-label="Speichern" title="Speichern (ID-Änderung migriert Qdrant etc.)">${ICON_SAVE}</button>
              <button type="button" class="icon-btn secondary customer-cancel-btn hidden" aria-label="Abbrechen">Abbrechen</button>
              <button type="button" class="icon-btn danger customer-delete-btn" aria-label="Entfernen">${ICON_TRASH}</button>
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
      const idDisplay = row.querySelector(".customer-id-display");
      const idInput = row.querySelector(".customer-id-input");
      const nameDisplay = row.querySelector(".customer-name-display");
      const nameInput = row.querySelector(".customer-name-input");
      const editBtn = row.querySelector(".customer-edit-btn");
      const saveBtn = row.querySelector(".customer-save-btn");
      const cancelBtn = row.querySelector(".customer-cancel-btn");

      if (target.classList.contains("customer-edit-btn")) {
        row.classList.add('editing');
        idDisplay?.classList.add("hidden");
        idInput?.classList.remove("hidden");
        nameDisplay?.classList.add("hidden");
        nameInput?.classList.remove("hidden");
        editBtn?.classList.add("hidden");
        saveBtn?.classList.remove("hidden");
        cancelBtn?.classList.remove("hidden");
        if (idInput instanceof HTMLInputElement) idInput.focus();
        else if (nameInput instanceof HTMLInputElement) nameInput.focus();
        return;
      }

      if (target.classList.contains("customer-cancel-btn")) {
        row.classList.remove('editing');
        if (idInput instanceof HTMLInputElement && idDisplay) {
          idInput.value = idDisplay.textContent || "";
        }
        if (nameInput instanceof HTMLInputElement && nameDisplay) {
          nameInput.value = nameDisplay.textContent || "";
        }
        idDisplay?.classList.remove("hidden");
        idInput?.classList.add("hidden");
        nameDisplay?.classList.remove("hidden");
        nameInput?.classList.add("hidden");
        editBtn?.classList.remove("hidden");
        saveBtn?.classList.add("hidden");
        cancelBtn?.classList.add("hidden");
        return;
      }

      if (target.classList.contains("customer-save-btn")) {
        const nextIdRaw = idInput instanceof HTMLInputElement ? idInput.value.trim() : "";
        const nextId = (nextIdRaw || customerId).toLowerCase();
        const nextName = nameInput instanceof HTMLInputElement ? nameInput.value.trim() : "";
        if (!nextId || !nextName) {
          showStatus(listStatus, "ID und Name sind Pflicht.", "error");
          return;
        }
        if (!/^[a-z0-9_-]+$/.test(nextId)) {
          showStatus(listStatus, "Ungültige Kunden-ID (nur a-z, 0-9, -, _).", "error");
          return;
        }
        const isSlugChange = nextId !== customerId;
        const progressMsg = isSlugChange
          ? "Speichern + migriere KB (Qdrant) … kann bei großen KBs etwas dauern."
          : "Speichern…";
        showStatus(listStatus, progressMsg);
        try {
          const body = { name: nextName };
          if (isSlugChange) body.id = nextId;
          const data = await api(`/api/admin/customers/${encodeURIComponent(customerId)}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
          const returned = data.customer;
          let okMsg = "Kunde gespeichert.";
          if (isSlugChange) {
            okMsg = `Kunde umbenannt zu „${returned.id}“. KB (Qdrant-Collection kb_${returned.id}) erfolgreich migriert.`;
          }
          showStatus(listStatus, okMsg, "ok");
          row.classList.remove('editing');
          // Full refresh so the updated list (new slug, new name) is visible — clear visual confirmation.
          await loadCustomers();
        } catch (err) {
          const code = err && err.code;
          let msg = "Speichern fehlgeschlagen.";
          if (code === "customer_exists") {
            msg = "Kunden-ID existiert bereits.";
          } else if (code === "invalid_customer_id") {
            msg = "Ungültige Kunden-ID (nur a-z, 0-9, -, _).";
          } else if (code === "vector_store_failed") {
            msg = "KB-Migration (Qdrant) fehlgeschlagen." + (err.detail ? " " + err.detail : " Siehe Logs / Qdrant.");
          } else if (code === "rename_failed") {
            msg = "Daten-Migration fehlgeschlagen." + (err.detail ? " " + err.detail : "");
          } else if (err && err.detail) {
            msg = "Speichern fehlgeschlagen: " + err.detail;
          }
          showStatus(listStatus, msg, "error");
          // leave edit mode open on error so the user can see/correct the attempted values
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
        let message = "Anlegen fehlgeschlagen.";
        if (error.code === "customer_exists") {
          message = "Kunden-ID existiert bereits.";
        } else if (error.code === "invalid_customer_id") {
          message = "Ungültige Kunden-ID (nur a-z, 0-9, -, _).";
        } else if (error.detail) {
          message = `Anlegen fehlgeschlagen: ${error.detail}`;
        } else if (error.status) {
          message = `Anlegen fehlgeschlagen (Status ${error.status}). Siehe Server-Logs für Details.`;
        }
        showStatus(createStatus, message, "error");
      }
    });

    loadCustomers().catch(() => showStatus(listStatus, "Kunden konnten nicht geladen werden.", "error"));
  }

  // Global handler for all info-tip icons (hover tooltip + click to focus + optional hint)
  document.querySelectorAll('.info-tip').forEach((tip) => {
    tip.setAttribute('tabindex', '0');
    tip.addEventListener('click', () => {
      tip.focus();
      // If there's a status element nearby in common admin pages, flash a hint
      const statusEl = document.querySelector('#customer-list-status, #user-list-status, #role-list-status, #prompt-status, #kc-source-list-status');
      if (statusEl) {
        const original = statusEl.textContent;
        statusEl.textContent = 'Mehr Infos im Tooltip (Hover oder Fokus).';
        setTimeout(() => {
          if (statusEl.textContent.includes('Tooltip')) {
            statusEl.textContent = original;
          }
        }, 2800);
      }
    });
  });


  function initKeysPage() {
    const tbody = document.getElementById("keys-table-body");
    const emptyEl = document.getElementById("keys-empty");
    const countEl = document.getElementById("keys-count");
    const listStatus = document.getElementById("keys-list-status");
    const oauthDialog = document.getElementById("oauth-dialog");
    const oauthUrl = document.getElementById("oauth-verify-url");
    const oauthCode = document.getElementById("oauth-user-code");
    const oauthCheck = document.getElementById("oauth-check");
    const oauthCancel = document.getElementById("oauth-cancel");
    const oauthStatus = document.getElementById("oauth-status");

    let currentStatus = null;
    let currentOAuth = null; // {device_auth_id, user_code, interval}

    function areaLabel(area) {
      if (area === "chat") return "Chat (LLM)";
      if (area === "embedding") return "Embeddings";
      if (area === "similarity") return "Similarity Agent";
      if (area === "integration") return "Integration API";
      return area;
    }

    function renderValue(area, data) {
      if (area === "chat" || area === "similarity") {
        const mode = data.auth_mode || "api_key";
        const keyM = data.api_key_masked || "";
        const oauth = data.oauth || {};
        if (mode === "chatgpt_oauth") {
          const acc = oauth.account_id ? ` (Account ${escapeHtml(oauth.account_id)})` : "";
          const cfg = oauth.configured ? "OAuth aktiv" : "OAuth (nicht eingeloggt)";
          const loginBtn = `<button type="button" class="secondary small keys-oauth-btn" style="margin-left:0.5rem">Neu anmelden</button>`;
          return `<span class="keys-mode">chatgpt_oauth</span> <span class="keys-val">${escapeHtml(cfg)}${acc}</span>${loginBtn}`;
        }
        return `<span class="keys-mode">api_key</span> <code class="keys-val">${escapeHtml(keyM || "—")}</code>`;
      }
      if (area === "embedding") {
        return `<code class="keys-val">${escapeHtml(data.api_key_masked || "—")}</code>`;
      }
      if (area === "integration") {
        const en = data.enabled ? "" : " (deaktiviert)";
        return `<code class="keys-val">${escapeHtml(data.api_key_masked || "—")}</code>${escapeHtml(en)}`;
      }
      return "";
    }

    function renderRow(area, data) {
      const tr = document.createElement("tr");
      tr.dataset.area = area;
      tr.innerHTML = `
        <td><strong>${escapeHtml(areaLabel(area))}</strong></td>
        <td class="keys-value-cell">${renderValue(area, data)}</td>
        <td class="keys-actions-cell">
          <div class="row-actions">
            <button type="button" class="icon-btn secondary keys-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
          </div>
        </td>
      `;
      return tr;
    }

    function setEditing(row, area, data, onSave, onCancel) {
      const valCell = row.querySelector(".keys-value-cell");
      const actCell = row.querySelector(".keys-actions-cell");
      if (!valCell || !actCell) return;

      row.classList.add("editing");

      let html = "";
      if (area === "chat" || area === "similarity") {
        const curMode = data.auth_mode || "api_key";
        const curKey = (area === "chat" ? (currentStatus?.chat?.api_key_masked || "") : (currentStatus?.similarity?.api_key_masked || ""));
        const simExtra = area === "similarity" ? `
          <label style="margin-left:0.5rem">Modus
            <select class="keys-sim-mode">
              <option value="same_as_chat" ${data.mode === "same_as_chat" ? "selected" : ""}>Same as chat</option>
              <option value="custom" ${data.mode === "custom" ? "selected" : ""}>Custom</option>
            </select>
          </label>
        ` : "";
        html = `
          <div class="keys-edit-row">
            <label>Auth
              <select class="keys-auth-mode">
                <option value="api_key" ${curMode === "api_key" ? "selected" : ""}>API Key</option>
                <option value="chatgpt_oauth" ${curMode === "chatgpt_oauth" ? "selected" : ""}>ChatGPT OAuth</option>
              </select>
            </label>
            ${simExtra}
            <label class="keys-key-label" style="margin-left:0.5rem">Key
              <input type="password" class="keys-key-input" value="" placeholder="neuer Key (optional)">
            </label>
          </div>
        `;
      } else if (area === "embedding" || area === "integration") {
        html = `
          <div class="keys-edit-row">
            <label>Key
              <input type="password" class="keys-key-input" value="" placeholder="${area === "integration" ? "Token (leer = deaktiviert)" : "neuer Key"}">
            </label>
          </div>
        `;
      }
      valCell.innerHTML = html;

      actCell.innerHTML = `
        <div class="row-actions">
          <button type="button" class="icon-btn save keys-save-btn" aria-label="Speichern" title="Speichern">${ICON_SAVE}</button>
          <button type="button" class="icon-btn secondary keys-cancel-btn" aria-label="Abbrechen">Abbrechen</button>
        </div>
      `;

      const saveBtn = actCell.querySelector(".keys-save-btn");
      const cancelBtn = actCell.querySelector(".keys-cancel-btn");
      const authSel = valCell.querySelector(".keys-auth-mode");
      const keyInput = valCell.querySelector(".keys-key-input");
      const simModeSel = valCell.querySelector(".keys-sim-mode");

      function revert() {
        row.classList.remove("editing");
        valCell.innerHTML = renderValue(area, data);
        actCell.innerHTML = `<div class="row-actions"><button type="button" class="icon-btn secondary keys-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button></div>`;
        // rebind edit
        const newEdit = actCell.querySelector(".keys-edit-btn");
        if (newEdit) newEdit.addEventListener("click", () => startEdit(row, area, data));
      }

      cancelBtn?.addEventListener("click", () => {
        revert();
        onCancel && onCancel();
      });

      saveBtn?.addEventListener("click", async () => {
        const payload = {};
        if (authSel) payload.auth_mode = authSel.value;
        if (keyInput) payload.api_key = keyInput.value; // may be empty
        if (simModeSel) payload.mode = simModeSel.value;
        try {
          saveBtn.disabled = true;
          const endpoint = area === "chat" ? "/api/admin/keys/chat"
            : area === "embedding" ? "/api/admin/keys/embedding"
            : area === "similarity" ? "/api/admin/keys/similarity"
            : "/api/admin/keys/integration";
          await api(endpoint, { method: "PATCH", body: JSON.stringify(payload) });
          // refresh all
          await loadAndRender();
          showStatus(listStatus, "Gespeichert.", "ok");
        } catch (e) {
          showStatus(listStatus, e?.detail || e?.code || "Speichern fehlgeschlagen.", "error");
          saveBtn.disabled = false;
        }
      });

      // if blur the inputs without save? we keep editing until explicit cancel/save.
      // per request: leaving the field (blur) without save -> revert. So on blur of key input:
      if (keyInput) {
        keyInput.addEventListener("blur", () => {
          // if still editing and no save happened, but to detect "without saving", we can revert only if value not "dirty" or always let user cancel.
          // simple: do nothing on blur; user must cancel explicitly or save. The "verlässt das feld" can be handled by cancel.
        });
      }
    }

    function startEdit(row, area, data) {
      setEditing(row, area, data, null, null);
    }

    async function loadAndRender() {
      if (!tbody) return;
      tbody.innerHTML = "";
      if (listStatus) listStatus.textContent = "Lade …";
      try {
        currentStatus = await api("/api/admin/keys");
        const entries = [
          ["chat", currentStatus.chat],
          ["embedding", currentStatus.embedding],
          ["similarity", currentStatus.similarity],
          ["integration", currentStatus.integration],
        ];
        if (countEl) countEl.textContent = `(${entries.length})`;
        if (emptyEl) emptyEl.classList.toggle("hidden", true);
        entries.forEach(([area, data]) => {
          const row = renderRow(area, data || {});
          tbody.appendChild(row);
          const editBtn = row.querySelector(".keys-edit-btn");
          if (editBtn) {
            editBtn.addEventListener("click", () => startEdit(row, area, data || {}));
          }
        });
        if (listStatus) listStatus.textContent = "";
      } catch (e) {
        if (listStatus) showStatus(listStatus, "Konnte Keys nicht laden.", "error");
      }
    }

    // OAuth dialog helpers
    function closeOAuth() {
      if (oauthDialog) oauthDialog.classList.add("hidden");
      if (oauthStatus) oauthStatus.textContent = "";
      currentOAuth = null;
    }

    async function openOAuth() {
      if (!oauthDialog) return;
      try {
        const info = await api("/api/admin/keys/oauth/start", { method: "POST" });
        currentOAuth = {
          device_auth_id: info.device_auth_id,
          user_code: info.user_code,
          interval: info.interval || 5,
        };
        if (oauthUrl) oauthUrl.href = info.verification_url || "https://auth.openai.com/codex/device";
        if (oauthUrl) oauthUrl.textContent = info.verification_url || "https://auth.openai.com/codex/device";
        if (oauthCode) oauthCode.textContent = info.user_code || "";
        if (oauthStatus) oauthStatus.textContent = "";
        oauthDialog.classList.remove("hidden");
      } catch (e) {
        showStatus(listStatus, "OAuth-Start fehlgeschlagen: " + (e?.detail || e?.code || ""), "error");
      }
    }

    async function checkOAuth() {
      if (!currentOAuth || !oauthStatus) return;
      oauthStatus.textContent = "Prüfe …";
      try {
        const res = await api(
          `/api/admin/keys/oauth/poll?device_auth_id=${encodeURIComponent(currentOAuth.device_auth_id)}&user_code=${encodeURIComponent(currentOAuth.user_code)}&interval=${currentOAuth.interval}`,
          { method: "POST" }
        );
        if (res.status === "complete") {
          oauthStatus.textContent = "Erfolgreich — Tokens gespeichert.";
          closeOAuth();
          await loadAndRender();
          showStatus(listStatus, "OAuth Login abgeschlossen.", "ok");
        } else if (res.status === "pending") {
          oauthStatus.textContent = "Noch nicht bestätigt. Warte kurz und prüfe erneut.";
        } else {
          oauthStatus.textContent = "Fehler: " + (res.detail || res.status);
        }
      } catch (e) {
        oauthStatus.textContent = "Fehler: " + (e?.detail || e?.code || "unbekannt");
      }
    }

    if (oauthCancel) oauthCancel.addEventListener("click", closeOAuth);
    if (oauthCheck) oauthCheck.addEventListener("click", checkOAuth);

    // bind global "oauth login" buttons inside rows (for chat and sim)
    // we delegate on tbody clicks for .keys-oauth-btn if we render them
    if (tbody) {
      tbody.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".keys-oauth-btn");
        if (btn) {
          ev.preventDefault();
          openOAuth();
        }
      });
    }

    // initial load
    loadAndRender().catch(() => {});

    // also expose a refresh for after oauth
    window.__refreshKeys = loadAndRender;
  }

  function initKeysPresetsPage() {
    const grid = document.getElementById("preset-grid");
    const emptyEl = document.getElementById("preset-empty");
    const statusEl = document.getElementById("preset-status");
    const createBtn = document.getElementById("preset-create-btn");
    const formModal = document.getElementById("preset-form-modal");
    const form = document.getElementById("preset-form");
    const formTitle = document.getElementById("preset-form-title");
    const nameInput = document.getElementById("preset-name");
    const providerSelect = document.getElementById("preset-provider");
    const modelSelect = document.getElementById("preset-model");
    const oauthModal = document.getElementById("oauth-wizard-modal");
    const oauthUrl = document.getElementById("oauth-verify-url");
    const oauthCode = document.getElementById("oauth-user-code");
    const oauthHint = document.getElementById("oauth-wizard-hint");
    const oauthStatus = document.getElementById("oauth-wizard-status");
    const oauthWizardBody = document.getElementById("oauth-wizard-body");
    const oauthWizardCancel = document.getElementById("oauth-wizard-cancel");
    const oauthWizardDone = document.getElementById("oauth-wizard-done");

    let catalog = { providers: [] };
    let presets = [];
    let oauthSession = null;
    let oauthPollTimer = null;
    let oauthPollInFlight = false;
    let oauthDone = false;
    let editingPresetId = null;

    function providerLabel(id) {
      const row = catalog.providers.find((p) => p.id === id);
      return row?.label || id;
    }

    function modelLabel(provider, modelId) {
      const row = catalog.providers.find((p) => p.id === provider);
      return row?.models?.find((m) => m.id === modelId)?.label || modelId;
    }

    function fillProviderSelect() {
      if (!providerSelect) return;
      providerSelect.innerHTML = "";
      catalog.providers.forEach((provider) => {
        const opt = document.createElement("option");
        opt.value = provider.id;
        opt.textContent = provider.enabled ? provider.label : `${provider.label} (demnächst)`;
        opt.disabled = !provider.enabled;
        providerSelect.appendChild(opt);
      });
      fillModelSelect();
    }

    function fillModelSelect() {
      if (!modelSelect || !providerSelect) return;
      const provider = catalog.providers.find((p) => p.id === providerSelect.value);
      modelSelect.innerHTML = "";
      (provider?.models || []).forEach((model) => {
        const opt = document.createElement("option");
        opt.value = model.id;
        opt.textContent = model.label;
        modelSelect.appendChild(opt);
      });
    }

    function closeFormModal() {
      formModal?.classList.add("hidden");
      editingPresetId = null;
    }

    function stopOAuthPoll() {
      if (oauthPollTimer) {
        clearInterval(oauthPollTimer);
        oauthPollTimer = null;
      }
    }

    function setOAuthWizardActions(mode) {
      const done = mode === "done";
      oauthWizardCancel?.classList.toggle("hidden", done);
      oauthWizardDone?.classList.toggle("hidden", !done);
      oauthWizardBody?.classList.toggle("hidden", done);
    }

    function closeOAuthModal() {
      stopOAuthPoll();
      oauthDone = false;
      oauthPollInFlight = false;
      oauthModal?.classList.add("hidden");
      oauthSession = null;
      if (oauthStatus) oauthStatus.textContent = "";
      setOAuthWizardActions("pending");
    }

    async function finishOAuthSuccess() {
      if (oauthDone) return;
      oauthDone = true;
      stopOAuthPoll();
      setOAuthStep(3);
      if (oauthHint) oauthHint.textContent = "Anmeldung erfolgreich.";
      if (oauthStatus) oauthStatus.textContent = "OAuth gespeichert.";
      setOAuthWizardActions("done");
      await loadPresets();
    }

    async function oauthAlreadyConfigured(presetId) {
      try {
        const data = await api("/api/admin/llm-presets");
        return (data.presets || []).some((row) => row.id === presetId && row.oauth_configured);
      } catch {
        return false;
      }
    }

    function setOAuthStep(step) {
      oauthModal?.querySelectorAll(".oauth-step").forEach((el) => {
        el.classList.toggle("active", el.dataset.step === String(step));
      });
    }

    async function pollOAuthOnce() {
      if (!oauthSession?.presetId || oauthDone) return;
      if (oauthPollInFlight) return;
      oauthPollInFlight = true;
      const presetId = oauthSession.presetId;
      const params = new URLSearchParams({
        provider: oauthSession.provider,
        interval: String(oauthSession.interval || 5),
      });
      if (oauthSession.provider === "grok") {
        params.set("device_code", oauthSession.device_code || "");
      } else {
        params.set("device_auth_id", oauthSession.device_auth_id || "");
        params.set("user_code", oauthSession.user_code || "");
      }
      try {
        const res = await api(`/api/admin/llm-presets/${presetId}/oauth/poll?${params}`, { method: "POST" });
        if (oauthDone) return;
        if (res.status === "complete") {
          await finishOAuthSuccess();
          return;
        }
        if (res.status === "error") {
          const detail = String(res.detail || res.status || "");
          if (detail === "invalid_grant" && (await oauthAlreadyConfigured(presetId))) {
            await finishOAuthSuccess();
            return;
          }
          stopOAuthPoll();
          if (oauthStatus) oauthStatus.textContent = `Fehler: ${detail || res.status}`;
        }
      } catch (e) {
        if (oauthDone) return;
        const detail = String(e?.detail || e?.message || "unbekannt");
        if (detail.includes("invalid_grant") && (await oauthAlreadyConfigured(presetId))) {
          await finishOAuthSuccess();
          return;
        }
        if (oauthStatus) oauthStatus.textContent = `Fehler: ${detail}`;
      } finally {
        oauthPollInFlight = false;
      }
    }

    function startOAuthPoll() {
      stopOAuthPoll();
      oauthDone = false;
      oauthPollInFlight = false;
      oauthPollTimer = setInterval(() => {
        pollOAuthOnce().catch(() => {});
      }, Math.max((oauthSession?.interval || 5) * 1000, 4000));
      pollOAuthOnce().catch(() => {});
    }

    async function openOAuthWizard(presetId, startInfo) {
      oauthSession = { presetId, ...startInfo };
      oauthDone = false;
      oauthPollInFlight = false;
      setOAuthStep(2);
      if (oauthUrl) {
        oauthUrl.href = startInfo.verification_url || "#";
        oauthUrl.textContent = startInfo.verification_url || "—";
      }
      if (oauthCode) oauthCode.textContent = startInfo.user_code || "—";
      if (oauthHint) oauthHint.textContent = "Warte auf Bestätigung im Browser …";
      if (oauthStatus) oauthStatus.textContent = "";
      setOAuthWizardActions("pending");
      oauthModal?.classList.remove("hidden");
      startOAuthPoll();
    }

    function providerLogoMeta(provider) {
      if (provider === "openai") {
        return { src: "/static/providers/openai.svg", alt: "OpenAI" };
      }
      if (provider === "grok") {
        return { src: "/static/providers/grok.svg", alt: "Grok" };
      }
      return null;
    }

    function renderGrid() {
      if (!grid) return;
      grid.innerHTML = "";
      if (emptyEl) emptyEl.classList.toggle("hidden", presets.length > 0);
      presets.forEach((preset) => {
        const card = document.createElement("article");
        card.className = "preset-card";
        const dotClass = preset.oauth_configured ? "ok" : "warn";
        const logo = providerLogoMeta(preset.provider);
        const invalidModel = preset.model_id === "composer-2.5";
        card.innerHTML = `
          <div class="preset-card-head">
            <h3 class="preset-card-title">${escapeHtml(preset.name)}</h3>
            ${logo ? `<img class="preset-provider-logo" src="${logo.src}" alt="${escapeHtml(logo.alt)}" title="${escapeHtml(logo.alt)}">` : ""}
          </div>
          <div class="preset-card-meta">
            <span>${escapeHtml(modelLabel(preset.provider, preset.model_id))}</span>
            <span class="preset-status-wrap" title="${preset.oauth_configured ? "OAuth verbunden" : "OAuth ausstehend"}"><span class="preset-status-dot ${dotClass}"></span></span>
            ${invalidModel ? `<span class="muted">Modell nicht über API verfügbar — bitte Preset neu anlegen (z. B. Grok Build 0.1)</span>` : ""}
            ${preset.oauth_account_label ? `<span>${escapeHtml(preset.oauth_account_label)}</span>` : ""}
          </div>
          <div class="preset-card-actions">
            <button type="button" class="secondary small preset-oauth-btn">OAuth</button>
            <button type="button" class="secondary small preset-delete-btn">Löschen</button>
          </div>
        `;
        card.querySelector(".preset-oauth-btn")?.addEventListener("click", async () => {
          try {
            showStatus(statusEl, "OAuth wird gestartet …", "");
            const info = await api(`/api/admin/llm-presets/${preset.id}/oauth/start`, { method: "POST" });
            showStatus(statusEl, "", "");
            await openOAuthWizard(preset.id, info);
          } catch (e) {
            showStatus(statusEl, `OAuth-Start fehlgeschlagen: ${e?.detail || e?.message}`, "error");
          }
        });
        card.querySelector(".preset-delete-btn")?.addEventListener("click", async () => {
          if (!window.confirm(`Preset „${preset.name}" löschen?`)) return;
          try {
            await api(`/api/admin/llm-presets/${preset.id}`, { method: "DELETE" });
            await loadPresets();
            showStatus(statusEl, "Preset gelöscht.", "success");
          } catch (e) {
            showStatus(statusEl, e?.detail || e?.message || "Löschen fehlgeschlagen", "error");
          }
        });
        grid.appendChild(card);
      });
    }

    async function loadCatalog() {
      catalog = await api("/api/admin/llm-presets/catalog");
      fillProviderSelect();
      const noteEl = document.getElementById("preset-catalog-note");
      const note = catalog.notes?.composer_cli_only;
      if (noteEl && note) {
        noteEl.textContent = ` Hinweis: ${note}`;
        noteEl.classList.remove("hidden");
      }
    }

    async function loadPresets() {
      const data = await api("/api/admin/llm-presets");
      presets = data.presets || [];
      renderGrid();
    }

    createBtn?.addEventListener("click", () => {
      if (formTitle) formTitle.textContent = "Preset anlegen";
      if (nameInput) nameInput.value = "";
      fillProviderSelect();
      formModal?.classList.remove("hidden");
    });
    document.getElementById("preset-form-close")?.addEventListener("click", closeFormModal);
    document.getElementById("preset-form-cancel")?.addEventListener("click", closeFormModal);
    document.getElementById("oauth-wizard-close")?.addEventListener("click", closeOAuthModal);
    document.getElementById("oauth-wizard-cancel")?.addEventListener("click", closeOAuthModal);
    document.getElementById("oauth-wizard-done")?.addEventListener("click", closeOAuthModal);
    document.getElementById("oauth-copy-code")?.addEventListener("click", async () => {
      const code = oauthCode?.textContent || "";
      try {
        await navigator.clipboard.writeText(code);
        if (oauthStatus) oauthStatus.textContent = "Code kopiert.";
      } catch {
        if (oauthStatus) oauthStatus.textContent = "Kopieren nicht möglich.";
      }
    });
    providerSelect?.addEventListener("change", fillModelSelect);

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = nameInput?.value?.trim() || "";
      const provider = providerSelect?.value || "";
      const model_id = modelSelect?.value || "";
      if (!name || !provider || !model_id) return;
      try {
        showStatus(statusEl, "Preset wird angelegt …", "");
        const created = await api("/api/admin/llm-presets", {
          method: "POST",
          body: JSON.stringify({ name, provider, model_id }),
        });
        closeFormModal();
        showStatus(statusEl, "", "");
        const info = await api(`/api/admin/llm-presets/${created.preset.id}/oauth/start`, { method: "POST" });
        await loadPresets();
        await openOAuthWizard(created.preset.id, info);
      } catch (e) {
        showStatus(statusEl, e?.detail || e?.message || "Speichern fehlgeschlagen", "error");
      }
    });

    Promise.all([loadCatalog(), loadPresets()]).catch(() => {
      showStatus(statusEl, "Presets konnten nicht geladen werden.", "error");
    });
  }

  function initKeysAssignmentsPage() {
    const bindingsBody = document.getElementById("bindings-table-body");
    const secretsBody = document.getElementById("secrets-table-body");
    const statusEl = document.getElementById("assign-status");

    let state = null;

    function presetOptions(selectedId, { allowInherit }) {
      const opts = [];
      if (allowInherit) {
        opts.push(`<option value="inherit" ${!selectedId ? "selected" : ""}>— wie Chat —</option>`);
      }
      (state?.presets || []).forEach((preset) => {
        opts.push(
          `<option value="${escapeHtml(preset.id)}" ${preset.id === selectedId ? "selected" : ""}>${escapeHtml(preset.name)} (${escapeHtml(preset.model_id)})</option>`,
        );
      });
      return opts.join("");
    }

    function bindingStatus(binding) {
      if (binding.binding_type === "inherit") return "Erbt Chat-Preset";
      const preset = binding.preset;
      if (!preset) return "Kein Preset gewählt";
      if (!preset.oauth_configured) return "OAuth ausstehend";
      return `Aktiv · ${preset.provider} / ${preset.model_id}`;
    }

    function renderBindings() {
      if (!bindingsBody) return;
      bindingsBody.innerHTML = "";
      (state?.bindings || []).forEach((binding) => {
        const tr = document.createElement("tr");
        const selected = binding.binding_type === "inherit" ? "inherit" : binding.preset_id || "";
        tr.innerHTML = `
          <td>
            <strong>${escapeHtml(binding.label)}</strong>
            <div class="muted" style="font-size:0.85rem">${escapeHtml(binding.description || "")}</div>
          </td>
          <td>
            <select class="binding-preset-select" data-slot="${escapeHtml(binding.slot)}">
              ${binding.slot === "chat"
                ? `<option value="">— Preset wählen —</option>${(state?.presets || [])
                    .map(
                      (preset) =>
                        `<option value="${escapeHtml(preset.id)}" ${preset.id === binding.preset_id ? "selected" : ""}>${escapeHtml(preset.name)} (${escapeHtml(preset.model_id)})</option>`,
                    )
                    .join("")}`
                : presetOptions(selected, { allowInherit: binding.allow_inherit })}
            </select>
          </td>
          <td class="muted">${escapeHtml(bindingStatus(binding))}</td>
        `;
        const select = tr.querySelector(".binding-preset-select");
        select?.addEventListener("change", async () => {
          const slot = select.dataset.slot;
          const value = select.value;
          if (slot === "chat" && !value) return;
          const payload =
            value === "inherit"
              ? { binding_type: "inherit", preset_id: null }
              : { binding_type: "preset", preset_id: value };
          try {
            await api(`/api/admin/llm-bindings/${slot}`, { method: "PATCH", body: JSON.stringify(payload) });
            await load();
            showStatus(statusEl, "Zuordnung gespeichert.", "success");
          } catch (e) {
            showStatus(statusEl, e?.detail || e?.message || "Speichern fehlgeschlagen", "error");
          }
        });
        bindingsBody.appendChild(tr);
      });
    }

    function renderSecretRow(area, label, masked, onSave) {
      const tr = document.createElement("tr");
      tr.dataset.area = area;
      tr.innerHTML = `
        <td><strong>${escapeHtml(label)}</strong></td>
        <td class="keys-value-cell"><code class="keys-val">${escapeHtml(masked || "—")}</code></td>
        <td class="keys-actions-cell">
          <div class="row-actions">
            <button type="button" class="icon-btn secondary secret-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
          </div>
        </td>
      `;
      tr.querySelector(".secret-edit-btn")?.addEventListener("click", () => {
        const valCell = tr.querySelector(".keys-value-cell");
        const actCell = tr.querySelector(".keys-actions-cell");
        if (!valCell || !actCell) return;
        tr.classList.add("editing");
        valCell.innerHTML = `
          <div class="keys-edit-row">
            <label>Key
              <input type="password" class="secret-key-input" placeholder="neuer Key (leer = deaktivieren)">
            </label>
          </div>
        `;
        actCell.innerHTML = `
          <div class="row-actions">
            <button type="button" class="icon-btn save secret-save-btn" aria-label="Speichern">${ICON_SAVE}</button>
            <button type="button" class="icon-btn secondary secret-cancel-btn" aria-label="Abbrechen">Abbrechen</button>
          </div>
        `;
        tr.querySelector(".secret-save-btn")?.addEventListener("click", async () => {
          const value = tr.querySelector(".secret-key-input")?.value ?? "";
          try {
            await onSave(value);
            await load();
            showStatus(statusEl, "Gespeichert.", "success");
          } catch (e) {
            showStatus(statusEl, e?.detail || e?.message || "Speichern fehlgeschlagen", "error");
          }
        });
        tr.querySelector(".secret-cancel-btn")?.addEventListener("click", () => renderSecrets());
      });
      return tr;
    }

    function renderSecrets() {
      if (!secretsBody) return;
      secretsBody.innerHTML = "";
      secretsBody.appendChild(
        renderSecretRow("embedding", "Embeddings", state?.embedding?.api_key_masked, (api_key) =>
          api("/api/admin/keys/embedding", { method: "PATCH", body: JSON.stringify({ api_key }) }),
        ),
      );
      secretsBody.appendChild(
        renderSecretRow("integration", "Integration API", state?.integration?.api_key_masked, (api_key) =>
          api("/api/admin/keys/integration", { method: "PATCH", body: JSON.stringify({ api_key }) }),
        ),
      );
    }

    async function load() {
      state = await api("/api/admin/keys");
      renderBindings();
      renderSecrets();
    }

    load().catch(() => showStatus(statusEl, "Zuordnung konnte nicht geladen werden.", "error"));
  }

  function kcStatusLabel(status) {
    if (status === "pending") return "Offen";
    if (status === "adopted") return "Übernommen";
    if (status === "rejected") return "Abgelehnt";
    return status || "";
  }

  function kcChangeKindLabel(kind) {
    if (kind === "split") return "Split";
    if (kind === "merge") return "Merge";
    if (kind === "insert") return "Neu";
    if (kind === "delete") return "Entfernt";
    return "Ersetzt";
  }

  function normalizeForMatch(text) {
    return String(text)
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/[ \t]+/g, " ")
      .replace(/ *\n */g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function findSnippetRange(haystack, snippet) {
    if (!haystack || !snippet) return null;
    let idx = haystack.indexOf(snippet);
    if (idx >= 0) return { start: idx, end: idx + snippet.length };

    const normHay = normalizeForMatch(haystack);
    const normNeedle = normalizeForMatch(snippet);
    idx = normHay.indexOf(normNeedle);
    if (idx < 0) {
      const anchor = snippet.slice(0, Math.min(Math.max(12, snippet.length), 80)).trim();
      if (!anchor) return null;
      idx = haystack.indexOf(anchor);
      if (idx >= 0) return { start: idx, end: Math.min(haystack.length, idx + snippet.length) };
      return null;
    }

    let normPos = 0;
    let origStart = -1;
    for (let i = 0; i <= haystack.length && normPos <= idx; i += 1) {
      if (normPos === idx) {
        origStart = i;
        break;
      }
      const ch = haystack[i];
      if (ch === undefined) break;
      if (ch === "\r" && haystack[i + 1] === "\n") {
        normPos += 1;
        i += 1;
      } else if (ch === " " || ch === "\t") {
        while (haystack[i + 1] === " " || haystack[i + 1] === "\t") i += 1;
        normPos += 1;
      } else {
        normPos += 1;
      }
    }
    if (origStart < 0) return null;

    let consumed = 0;
    let origEnd = origStart;
    while (origEnd < haystack.length && consumed < normNeedle.length) {
      const ch = haystack[origEnd];
      if (ch === "\r" && haystack[origEnd + 1] === "\n") {
        consumed += 1;
        origEnd += 2;
      } else if (ch === " " || ch === "\t") {
        while (haystack[origEnd + 1] === " " || haystack[origEnd + 1] === "\t") origEnd += 1;
        consumed += 1;
        origEnd += 1;
      } else {
        consumed += 1;
        origEnd += 1;
      }
    }
    return { start: origStart, end: origEnd };
  }

  function buildRevisionMarkup(content, revision) {
    if (!content) return "";
    if (!revision?.changes?.length) {
      return escapeHtml(content).replace(/\n/g, "<br>");
    }

    const spans = [];
    revision.changes.forEach((change) => {
      const snippet = change.target || change.anchor;
      if (!snippet) return;
      let range = findSnippetRange(content, snippet);
      if (!range && change.anchor && change.anchor !== snippet) {
        range = findSnippetRange(content, change.anchor);
      }
      if (!range) return;
      spans.push({ ...range, change });
    });

    spans.sort((a, b) => a.start - b.start);
    const merged = [];
    spans.forEach((span) => {
      const last = merged[merged.length - 1];
      if (last && span.start < last.end) return;
      merged.push(span);
    });

    const segments = [];
    let cursor = 0;
    merged.forEach(({ start, end, change }) => {
      if (cursor < start) {
        segments.push({ type: "text", text: content.slice(cursor, start) });
      }
      segments.push({ type: "mark", text: content.slice(start, end), change });
      cursor = end;
    });
    if (cursor < content.length) {
      segments.push({ type: "text", text: content.slice(cursor) });
    }

    return segments
      .map((seg) => {
        const escaped = escapeHtml(seg.text).replace(/\n/g, "<br>");
        if (seg.type === "text") return escaped;
        const kind = escapeHtml(seg.change.kind || "replace");
        const id = escapeHtml(seg.change.id || "");
        return `<mark class="kc-rev kc-rev-${kind}" data-change-id="${id}" tabindex="0">${escaped}</mark>`;
      })
      .join("");
  }

  function renderKcChangeItem(change) {
    const sources = (change.sources || [])
      .map((src) => `<li>${escapeHtml(src)}</li>`)
      .join("");
    const stageLabel = change.step
      ? `<span class="badge">Stufe ${escapeHtml(String(change.step))}${change.preset_label ? ` · ${escapeHtml(change.preset_label)}` : ""}</span>`
      : "";
    return `
      <article class="kc-change-item">
        <div class="kc-change-item-head">
          <span class="badge kc-rev-badge kc-rev-${escapeHtml(change.kind || "replace")}">${escapeHtml(kcChangeKindLabel(change.kind))}</span>
          ${stageLabel}
          ${change.note ? `<span class="muted">${escapeHtml(change.note)}</span>` : ""}
        </div>
        ${sources ? `<div><strong>Quelle:</strong><ul class="kc-change-sources">${sources}</ul></div>` : ""}
        ${change.target ? `<div><strong>Neu:</strong><p>${escapeHtml(change.target)}</p></div>` : ""}
      </article>
    `;
  }

  function renderKcChangesList(container, revision) {
    if (!container) return;
    const changes = revision?.changes || [];
    if (!changes.length) {
      container.innerHTML = '<p class="muted">Keine strukturierten Änderungen — reiner Textvergleich.</p>';
      return;
    }
    if (revision?.version === 2 && changes.some((row) => row.step)) {
      const steps = [...new Set(changes.map((row) => row.step))].sort((a, b) => a - b);
      container.innerHTML = steps
        .map((step) => {
          const stepChanges = changes.filter((row) => row.step === step);
          const label = stepChanges[0]?.preset_label || `Stufe ${step}`;
          return `
            <h3 class="kc-change-step-heading">${escapeHtml(label)}</h3>
            ${stepChanges.map((change) => renderKcChangeItem(change)).join("")}
          `;
        })
        .join("");
      return;
    }
    container.innerHTML = changes.map((change) => renderKcChangeItem(change)).join("");
  }

  function isKcPipelineRevision(revision) {
    return revision?.version === 2 && Array.isArray(revision.pipeline) && revision.pipeline.length > 0;
  }

  function bindKcRevisionPopover(container) {
    if (!container || container.dataset.kcPopoverBound) return;
    container.dataset.kcPopoverBound = "1";
    let popover = document.getElementById("kc-revision-popover");
    if (!popover) {
      popover = document.createElement("div");
      popover.id = "kc-revision-popover";
      popover.className = "kc-revision-popover hidden";
      document.body.appendChild(popover);
    }

    const hide = () => popover.classList.add("hidden");

    container.addEventListener("mouseover", (event) => {
      const mark = event.target.closest(".kc-rev");
      if (!mark || !container.contains(mark)) return;
      const changeId = mark.dataset.changeId;
      const item = (window.__kcActiveRevisionChanges || []).find((row) => row.id === changeId);
      if (!item) return;
      const sources = (item.sources || [])
        .map((src) => `<li>${escapeHtml(src)}</li>`)
        .join("");
      const stageInfo = item.step
        ? `<p class="muted">Stufe ${escapeHtml(String(item.step))}${item.preset_label ? ` · ${escapeHtml(item.preset_label)}` : ""}</p>`
        : "";
      popover.innerHTML = `
        <strong>${escapeHtml(kcChangeKindLabel(item.kind))}</strong>
        ${stageInfo}
        ${sources ? `<ul>${sources}</ul>` : "<p class='muted'>Neu hinzugefügt</p>"}
        ${item.note ? `<p class="muted">${escapeHtml(item.note)}</p>` : ""}
      `;
      const rect = mark.getBoundingClientRect();
      popover.style.left = `${Math.min(rect.left, window.innerWidth - 320)}px`;
      popover.style.top = `${rect.bottom + 8}px`;
      popover.classList.remove("hidden");
    });
    container.addEventListener("mouseout", (event) => {
      if (event.relatedTarget && popover.contains(event.relatedTarget)) return;
      hide();
    });
    popover.addEventListener("mouseleave", hide);
  }

  function formatKcDate(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  function ensureKcDetailModal() {
    let modal = document.getElementById("kc-detail-modal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "kc-detail-modal";
    modal.className = "kc-detail-modal hidden";
    modal.innerHTML = `
      <div class="kc-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="kc-detail-title">
        <div class="kc-detail-header">
          <h2 id="kc-detail-title"></h2>
          <button type="button" class="kc-detail-close" aria-label="Schließen">×</button>
        </div>
        <div class="kc-detail-meta" id="kc-detail-meta"></div>
        <div class="kc-detail-keywords kc-card-keywords" id="kc-detail-keywords"></div>
        <div class="kc-detail-summary hidden" id="kc-detail-summary"></div>
        <div class="kc-detail-tabs" id="kc-detail-tabs">
          <button type="button" class="secondary small kc-tab-btn active" data-kc-tab="revised">Überarbeitet</button>
          <button type="button" class="secondary small kc-tab-btn" data-kc-tab="original">Original</button>
          <button type="button" class="secondary small kc-tab-btn" data-kc-tab="changes">Änderungen</button>
        </div>
        <div class="kc-detail-panes">
          <div class="kc-detail-body" id="kc-detail-body"></div>
          <div class="kc-detail-body hidden" id="kc-detail-original"></div>
          <div class="kc-detail-changes hidden" id="kc-detail-changes"></div>
        </div>
        <p id="kc-detail-status" class="status" aria-live="polite"></p>
        <div class="kc-detail-actions" id="kc-detail-actions">
          <p class="kc-adopt-scope muted">KB-Ziel: aktiver Kunde aus der Sidebar (oben links).</p>
          <div class="kc-detail-buttons">
            <button type="button" class="primary" id="kc-adopt-btn">In KB übernehmen</button>
            <button type="button" class="secondary danger" id="kc-reject-btn">Ablehnen</button>
            <button type="button" class="secondary" id="kc-detail-cancel-btn">Schließen</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const close = () => modal.classList.add("hidden");
    modal.querySelector(".kc-detail-close")?.addEventListener("click", close);
    modal.querySelector("#kc-detail-cancel-btn")?.addEventListener("click", close);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) close();
    });
    return modal;
  }

  function initKnowledgeCenterContentPage() {
    const grid = document.getElementById("kc-content-grid");
    const emptyEl = document.getElementById("kc-empty");
    const listStatus = document.getElementById("kc-list-status");
    const statusFilter = document.getElementById("kc-status-filter");
    const sourceFilter = document.getElementById("kc-source-filter");
    const searchInput = document.getElementById("kc-search-input");
    const refreshBtn = document.getElementById("kc-refresh-btn");
    const loadMoreWrap = document.getElementById("kc-load-more-wrap");
    const loadMoreBtn = document.getElementById("kc-load-more-btn");

    const modal = ensureKcDetailModal();
    const detailTitle = modal.querySelector("#kc-detail-title");
    const detailMeta = modal.querySelector("#kc-detail-meta");
    const detailKeywords = modal.querySelector("#kc-detail-keywords");
    const detailSummary = modal.querySelector("#kc-detail-summary");
    const detailBody = modal.querySelector("#kc-detail-body");
    const detailOriginal = modal.querySelector("#kc-detail-original");
    const detailChanges = modal.querySelector("#kc-detail-changes");
    const detailTabs = modal.querySelector("#kc-detail-tabs");
    const detailStatus = modal.querySelector("#kc-detail-status");
    const detailActions = modal.querySelector("#kc-detail-actions");
    const adoptBtn = modal.querySelector("#kc-adopt-btn");
    const rejectBtn = modal.querySelector("#kc-reject-btn");

    let customers = [];
    let sources = [];
    let contents = [];
    let total = 0;
    let offset = 0;
    const pageSize = 50;
    let activeContent = null;
    let searchTimer = null;

    function renderSourceFilterOptions() {
      if (!sourceFilter) return;
      const current = sourceFilter.value;
      sourceFilter.innerHTML = '<option value="">Alle Quellen</option>';
      sources.forEach((source) => {
        const opt = document.createElement("option");
        opt.value = source.id;
        opt.textContent = `${source.name} (${source.host_code})`;
        sourceFilter.appendChild(opt);
      });
      sourceFilter.value = current;
    }

    function renderCustomerOptions(_selectedId) {
      /* KB target comes from sidebar session — no per-modal customer dropdown. */
    }

    function renderGrid() {
      if (!grid) return;
      grid.innerHTML = "";
      if (emptyEl) emptyEl.classList.toggle("hidden", contents.length > 0);
      if (loadMoreWrap) loadMoreWrap.classList.toggle("hidden", offset + contents.length >= total);

      contents.forEach((item) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "kc-content-card";
        card.dataset.contentId = item.id;
        const keywords = (item.keywords || [])
          .slice(0, 4)
          .map((kw) => `<span class="kc-keyword-badge">${escapeHtml(kw)}</span>`)
          .join("");
        card.innerHTML = `
          <div class="kc-card-title">${escapeHtml(item.title)}</div>
          <div class="kc-card-summary">${escapeHtml(item.summary || "—")}</div>
          <div class="kc-card-keywords">${keywords}</div>
          <div class="kc-card-meta">
            <span class="badge">${escapeHtml(item.source_name || item.host_code || "Quelle")}</span>
            ${item.suggested_customer_name ? `<span class="badge user-slug-badge">${escapeHtml(item.suggested_customer_id)}</span>` : ""}
            ${item.submitted_by_email ? `<span class="muted">${escapeHtml(item.submitted_by_email)}</span>` : ""}
            ${item.has_revision ? `<span class="badge">${item.pipeline_step_count > 1 ? `KI-Pipeline (${item.pipeline_step_count})` : "KI-Diff"}</span>` : ""}
            <span class="muted">${escapeHtml(formatKcDate(item.received_at))}</span>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    function setKcDetailTab(tab) {
      detailTabs?.querySelectorAll(".kc-tab-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.kcTab === tab);
      });
      const view = window.__kcDetailView || {};
      detailOriginal?.classList.toggle("hidden", tab !== "original");
      detailChanges?.classList.toggle("hidden", tab !== "changes");
      if (tab === "original" || tab === "changes") {
        detailBody?.classList.add("hidden");
        return;
      }
      detailBody?.classList.remove("hidden");
      if (!detailBody) return;
      if (tab === "revised") {
        if (view.finalMarkup) {
          detailBody.innerHTML = view.finalMarkup;
          bindKcRevisionPopover(detailBody);
        } else {
          detailBody.textContent = view.finalContent || "";
        }
        window.__kcActiveRevisionChanges = view.finalChanges || [];
        return;
      }
      const stageMatch = /^stage-(\d+)$/.exec(tab);
      if (stageMatch && view.stages) {
        const stage = view.stages[Number(stageMatch[1]) - 1];
        if (stage) {
          detailBody.innerHTML = buildRevisionMarkup(stage.content || "", { changes: stage.revision?.changes || [] });
          bindKcRevisionPopover(detailBody);
          window.__kcActiveRevisionChanges = (stage.revision?.changes || []).map((change) => ({
            ...change,
            step: stage.step,
            preset_label: stage.preset_label,
          }));
        }
      }
    }

    function buildKcDetailTabs(item) {
      if (!detailTabs) return;
      const revision = item.revision;
      if (!item.has_revision || !revision) {
        detailTabs.classList.add("hidden");
        detailTabs.innerHTML = "";
        return;
      }
      detailTabs.classList.remove("hidden");
      const tabs = ['<button type="button" class="secondary small kc-tab-btn active" data-kc-tab="revised">Endergebnis</button>'];
      if (isKcPipelineRevision(revision)) {
        revision.pipeline.forEach((stage) => {
          tabs.push(
            `<button type="button" class="secondary small kc-tab-btn" data-kc-tab="stage-${stage.step}">Stufe ${stage.step}: ${escapeHtml(stage.preset_label || stage.preset || "")}</button>`,
          );
        });
      } else {
        tabs[0] = '<button type="button" class="secondary small kc-tab-btn active" data-kc-tab="revised">Überarbeitet</button>';
      }
      tabs.push(
        '<button type="button" class="secondary small kc-tab-btn" data-kc-tab="original">Original</button>',
        '<button type="button" class="secondary small kc-tab-btn" data-kc-tab="changes">Änderungen</button>',
      );
      detailTabs.innerHTML = tabs.join("");
    }

    detailTabs?.addEventListener("click", (event) => {
      const btn = event.target.closest(".kc-tab-btn");
      if (!btn) return;
      setKcDetailTab(btn.dataset.kcTab || "revised");
    });

    function buildKcDetailView(item) {
      const content = item.content || "";
      const revision = item.revision;
      const hasRevision = Boolean(item.has_revision && revision);
      return {
        finalContent: content,
        finalMarkup: hasRevision ? buildRevisionMarkup(content, revision) : "",
        finalChanges: revision?.changes || [],
        stages: isKcPipelineRevision(revision)
          ? (revision.pipeline || []).map((stage) => ({
              step: stage.step,
              preset_label: stage.preset_label,
              content: stage.content || "",
              revision: stage.revision,
            }))
          : [],
      };
    }

    function openDetail(item) {
      activeContent = item;
      window.__kcDetailView = buildKcDetailView(item);
      window.__kcActiveRevisionChanges = item.revision?.changes || [];
      if (detailTitle) detailTitle.textContent = item.title;
      if (detailMeta) {
        detailMeta.innerHTML = `
          <span class="badge">${escapeHtml(item.source_name || "")}</span>
          <span class="muted">Host: ${escapeHtml(item.host_code || "")}</span>
          ${item.submitted_by_email ? `<span>Eingereicht von ${escapeHtml(item.submitted_by_email)}</span>` : ""}
          ${item.source_ref ? `<a href="${escapeAttr(item.source_ref)}" target="_blank" rel="noopener">Referenz</a>` : ""}
          ${item.suggested_customer_name ? `<span>Vorschlag: ${escapeHtml(item.suggested_customer_name)}</span>` : ""}
          ${item.revision?.stats?.change_ratio != null ? `<span>Änderung: ${Math.round(item.revision.stats.change_ratio * 100)}%</span>` : ""}
          <span class="muted">${escapeHtml(formatKcDate(item.received_at))}</span>
        `;
      }
      if (detailKeywords) {
        detailKeywords.innerHTML = (item.keywords || [])
          .map((kw) => `<span class="kc-keyword-badge">${escapeHtml(kw)}</span>`)
          .join("");
      }
      if (detailSummary) {
        const summary = item.summary || "";
        detailSummary.textContent = summary;
        detailSummary.classList.toggle("hidden", !summary);
      }
      buildKcDetailTabs(item);
      if (detailOriginal) {
        detailOriginal.textContent = item.original_content || item.content || "";
      }
      renderKcChangesList(detailChanges, item.revision);
      setKcDetailTab("revised");
      showStatus(detailStatus, "", "");
      renderCustomerOptions(item.suggested_customer_id || "");

      const isPending = item.status === "pending";
      if (detailActions) detailActions.classList.toggle("hidden", !isPending);
      if (adoptBtn) adoptBtn.disabled = !isPending;
      if (rejectBtn) rejectBtn.disabled = !isPending;

      modal.classList.remove("hidden");
    }

    async function loadContents({ append = false } = {}) {
      if (!append) offset = 0;
      const params = new URLSearchParams();
      const status = statusFilter?.value ?? "";
      if (status) params.set("status", status);
      if (sourceFilter?.value) params.set("source_id", sourceFilter.value);
      if (searchInput?.value.trim()) params.set("search", searchInput.value.trim());
      params.set("limit", String(pageSize));
      params.set("offset", String(offset));

      showStatus(listStatus, "Lade Inhalte…", "");
      try {
        const data = await api(`/api/tools/knowledge-center/contents?${params.toString()}`);
        customers = data.customers || [];
        sources = data.sources || [];
        renderSourceFilterOptions();
        const batch = data.contents || [];
        total = data.total ?? batch.length;
        contents = append ? contents.concat(batch) : batch;
        if (append) offset += batch.length;
        else offset = batch.length;
        renderGrid();
        showStatus(listStatus, total ? `${total} Eintrag${total === 1 ? "" : "e"}` : "", "ok");
      } catch (err) {
        showStatus(listStatus, err.detail || err.code || "Laden fehlgeschlagen.", "error");
      }
    }

    grid?.addEventListener("click", (event) => {
      const card = event.target.closest(".kc-content-card");
      if (!card) return;
      const item = contents.find((row) => row.id === card.dataset.contentId);
      if (item) openDetail(item);
    });

    statusFilter?.addEventListener("change", () => loadContents().catch(() => {}));
    sourceFilter?.addEventListener("change", () => loadContents().catch(() => {}));
    refreshBtn?.addEventListener("click", () => loadContents().catch(() => {}));
    loadMoreBtn?.addEventListener("click", () => loadContents({ append: true }).catch(() => {}));
    searchInput?.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadContents().catch(() => {}), 300);
    });

    adoptBtn?.addEventListener("click", async () => {
      if (!activeContent) return;
      if (!activeCustomerId) {
        showStatus(detailStatus, "Bitte zuerst einen Kunden in der Sidebar wählen.", "error");
        return;
      }
      adoptBtn.disabled = true;
      showStatus(detailStatus, "Übernehme in KB…", "");
      try {
        const result = await api(`/api/tools/knowledge-center/contents/${activeContent.id}/adopt`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        modal.classList.add("hidden");
        showStatus(listStatus, `In KB übernommen (${result.customer_id}).`, "ok");
        await loadContents();
      } catch (err) {
        showStatus(detailStatus, err.detail || err.code || "Übernahme fehlgeschlagen.", "error");
      } finally {
        adoptBtn.disabled = false;
      }
    });

    rejectBtn?.addEventListener("click", async () => {
      if (!activeContent) return;
      rejectBtn.disabled = true;
      showStatus(detailStatus, "Wird abgelehnt…", "");
      try {
        await api(`/api/tools/knowledge-center/contents/${activeContent.id}/reject`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        modal.classList.add("hidden");
        showStatus(listStatus, "Vorschlag abgelehnt.", "ok");
        await loadContents();
      } catch (err) {
        showStatus(detailStatus, err.detail || err.code || "Ablehnen fehlgeschlagen.", "error");
      } finally {
        rejectBtn.disabled = false;
      }
    });

    loadContents().catch(() => {});
  }

  function initKnowledgeCenterSubmitPage() {
    const form = document.getElementById("kc-submit-form");
    const titleInput = document.getElementById("kc-submit-title");
    const textInput = document.getElementById("kc-submit-text");
    const useAiToggle = document.getElementById("kc-submit-use-ai");
    const presetsWrap = document.getElementById("kc-submit-presets");
    const presetsSection = document.getElementById("kc-submit-presets-wrap");
    const pipelineOrder = document.getElementById("kc-submit-pipeline-order");
    const submitBtn = document.getElementById("kc-submit-btn");
    const submitStatus = document.getElementById("kc-submit-status");
    const myList = document.getElementById("kc-my-list");
    const myEmpty = document.getElementById("kc-my-empty");
    const myCount = document.getElementById("kc-my-count");

    const MAX_PIPELINE_STEPS = 4;
    let presets = [];
    let selectedPresets = ["expand_notes"];

    function presetLabel(presetId) {
      return presets.find((row) => row.id === presetId)?.label || presetId;
    }

    function saveSelectedPresets() {
      localStorage.setItem("kc-submit-presets", JSON.stringify(selectedPresets));
    }

    function renderPipelineOrder() {
      if (!pipelineOrder) return;
      pipelineOrder.innerHTML = "";
      selectedPresets.forEach((presetId, index) => {
        const li = document.createElement("li");
        li.className = "kc-pipeline-chip";
        li.innerHTML = `
          <span class="kc-pipeline-chip-index">${index + 1}</span>
          <span class="kc-pipeline-chip-label">${escapeHtml(presetLabel(presetId))}</span>
          <span class="kc-pipeline-chip-actions">
            <button type="button" class="secondary small" data-move="up" data-index="${index}" aria-label="Nach oben" ${index === 0 ? "disabled" : ""}>↑</button>
            <button type="button" class="secondary small" data-move="down" data-index="${index}" aria-label="Nach unten" ${index === selectedPresets.length - 1 ? "disabled" : ""}>↓</button>
            <button type="button" class="secondary small" data-remove="${index}" aria-label="Entfernen">×</button>
          </span>
        `;
        pipelineOrder.appendChild(li);
      });
    }

    function renderPresets() {
      if (!presetsWrap) return;
      const atLimit = selectedPresets.length >= MAX_PIPELINE_STEPS;
      presetsWrap.innerHTML = "";
      presets.forEach((preset) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "secondary small kc-preset-btn";
        btn.dataset.presetId = preset.id;
        btn.textContent = preset.label;
        btn.disabled = atLimit;
        btn.title = atLimit ? "Maximal 4 Schritte" : "Zur Pipeline hinzufügen";
        presetsWrap.appendChild(btn);
      });
      renderPipelineOrder();
    }

    function syncAiUi() {
      const enabled = Boolean(useAiToggle?.checked);
      presetsSection?.classList.toggle("hidden", !enabled);
      if (presetsSection) presetsSection.setAttribute("aria-hidden", enabled ? "false" : "true");
      if (submitBtn) {
        const stepCount = selectedPresets.length;
        submitBtn.textContent = enabled
          ? stepCount > 1
            ? `KI-Pipeline starten (${stepCount} Schritte)`
            : "KI starten & einreichen"
          : "Vorschlag einreichen";
      }
    }

    async function loadContext() {
      const data = await api("/api/tools/knowledge-center/submit-context");
      presets = data.presets || [];
      if (!selectedPresets.length && presets.length) {
        selectedPresets = [presets[0].id];
      }
      renderPresets();
      syncAiUi();
    }

    async function loadMySubmissions() {
      const data = await api("/api/tools/knowledge-center/my-contents?limit=20");
      const rows = data.contents || [];
      if (myCount) myCount.textContent = `(${data.total ?? rows.length})`;
      if (myEmpty) myEmpty.classList.toggle("hidden", rows.length > 0);
      if (!myList) return;
      myList.innerHTML = rows
        .map(
          (item) => `
          <article class="kc-my-item">
            <div>
              <strong>${escapeHtml(item.title)}</strong>
              <div class="muted">${escapeHtml(item.suggested_customer_name || item.suggested_customer_id || "")} · ${escapeHtml(kcStatusLabel(item.status))}</div>
            </div>
            <span class="muted">${escapeHtml(formatKcDate(item.received_at))}</span>
          </article>
        `,
        )
        .join("");
    }

    const savedAi = localStorage.getItem("kc-submit-use-ai");
    if (savedAi != null && useAiToggle) useAiToggle.checked = savedAi === "1";
    try {
      const savedPresets = JSON.parse(localStorage.getItem("kc-submit-presets") || "[]");
      if (Array.isArray(savedPresets) && savedPresets.length) selectedPresets = savedPresets;
    } catch {
      /* ignore */
    }

    useAiToggle?.addEventListener("change", () => {
      localStorage.setItem("kc-submit-use-ai", useAiToggle.checked ? "1" : "0");
      if (useAiToggle.checked && !selectedPresets.length) {
        selectedPresets = ["expand_notes"];
      }
      syncAiUi();
    });

    presetsWrap?.addEventListener("click", (event) => {
      const btn = event.target.closest(".kc-preset-btn");
      if (!btn || !useAiToggle?.checked || btn.disabled) return;
      const presetId = btn.dataset.presetId;
      if (!presetId) return;
      if (selectedPresets.length >= MAX_PIPELINE_STEPS) return;
      selectedPresets.push(presetId);
      saveSelectedPresets();
      renderPresets();
      syncAiUi();
    });

    pipelineOrder?.addEventListener("click", (event) => {
      const removeBtn = event.target.closest("[data-remove]");
      if (removeBtn) {
        const index = Number(removeBtn.dataset.remove);
        selectedPresets.splice(index, 1);
        if (!selectedPresets.length) selectedPresets = ["expand_notes"];
        saveSelectedPresets();
        renderPresets();
        syncAiUi();
        return;
      }
      const moveBtn = event.target.closest("[data-move]");
      if (!moveBtn || moveBtn.disabled) return;
      const index = Number(moveBtn.dataset.index);
      const swapWith = moveBtn.dataset.move === "up" ? index - 1 : index + 1;
      if (swapWith < 0 || swapWith >= selectedPresets.length) return;
      [selectedPresets[index], selectedPresets[swapWith]] = [selectedPresets[swapWith], selectedPresets[index]];
      saveSelectedPresets();
      renderPresets();
    });

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const rawText = textInput?.value.trim() || "";
      if (!activeCustomerId) {
        showStatus(submitStatus, "Bitte zuerst einen Kunden in der Sidebar wählen.", "error");
        return;
      }
      if (!rawText) {
        showStatus(submitStatus, "Inhalt ist Pflicht.", "error");
        return;
      }
      if (useAiToggle?.checked && !selectedPresets.length) {
        showStatus(submitStatus, "Mindestens ein KI-Schritt wählen.", "error");
        return;
      }
      if (submitBtn) submitBtn.disabled = true;
      const stepLabel = selectedPresets.length > 1 ? `${selectedPresets.length} Schritte` : "1 Schritt";
      showStatus(submitStatus, useAiToggle?.checked ? `KI überarbeitet (${stepLabel})…` : "Wird eingereicht…", "");
      try {
        await api("/api/tools/knowledge-center/submit", {
          method: "POST",
          body: JSON.stringify({
            raw_text: rawText,
            title: titleInput?.value.trim() || null,
            use_ai: Boolean(useAiToggle?.checked),
            presets: useAiToggle?.checked ? selectedPresets : undefined,
          }),
        });
        form.reset();
        if (useAiToggle) useAiToggle.checked = localStorage.getItem("kc-submit-use-ai") === "1";
        syncAiUi();
        showStatus(submitStatus, "Vorschlag eingereicht — wartet auf Freigabe.", "ok");
        await loadMySubmissions();
      } catch (err) {
        showStatus(submitStatus, err.detail || err.code || "Einreichung fehlgeschlagen.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    loadContext()
      .then(() => loadMySubmissions())
      .catch(() => {});
  }

  function initKnowledgeCenterSourcesPage() {
    const tbody = document.getElementById("kc-source-table-body");
    const emptyEl = document.getElementById("kc-source-empty");
    const countEl = document.getElementById("kc-source-count");
    const listStatus = document.getElementById("kc-source-list-status");
    const createForm = document.getElementById("kc-source-create-form");
    const createName = document.getElementById("kc-source-create-name");
    const createHostCode = document.getElementById("kc-source-create-host-code");
    const createStatus = document.getElementById("kc-source-create-status");

    function renderSources(sources) {
      if (!tbody) return;
      tbody.innerHTML = "";
      const rows = sources || [];
      if (countEl) countEl.textContent = `(${rows.length})`;
      if (emptyEl) emptyEl.classList.toggle("hidden", rows.length > 0);

      rows.forEach((source) => {
        const row = document.createElement("tr");
        row.dataset.sourceId = source.id;
        row.innerHTML = `
          <td><span class="kc-source-name-display">${escapeHtml(source.name)}</span></td>
          <td><code>${escapeHtml(source.host_code)}</code></td>
          <td>${source.active ? "Ja" : "Nein"}</td>
          <td class="user-actions-cell">
            <div class="row-actions">
              <button type="button" class="icon-btn secondary kc-source-edit-btn" aria-label="Bearbeiten">${ICON_EDIT}</button>
              <button type="button" class="icon-btn danger kc-source-delete-btn" aria-label="Entfernen">${ICON_TRASH}</button>
            </div>
          </td>
        `;
        tbody.appendChild(row);

        const editRow = document.createElement("tr");
        editRow.className = "kc-source-edit-row hidden";
        editRow.dataset.sourceId = source.id;
        editRow.innerHTML = `
          <td colspan="4">
            <div class="ingest-form">
              <div class="customer-form-row">
                <label>Name<input type="text" class="kc-source-edit-name" value="${escapeHtml(source.name)}" maxlength="120"></label>
                <label class="user-admin-checkbox"><input type="checkbox" class="kc-source-edit-active" ${source.active ? "checked" : ""}> Aktiv</label>
              </div>
              <p class="muted">Host-Code: <code>${escapeHtml(source.host_code)}</code> (unveränderlich)</p>
              <div class="customer-actions">
                <button type="button" class="secondary small kc-source-save-btn">Speichern</button>
                <button type="button" class="secondary small kc-source-cancel-btn">Abbrechen</button>
              </div>
            </div>
          </td>
        `;
        tbody.appendChild(editRow);
      });
    }

    async function loadSources() {
      const data = await api("/api/admin/knowledge-sources");
      renderSources(data.sources || []);
    }

    createForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = createName?.value.trim() || "";
      const hostCode = createHostCode?.value.trim().toLowerCase() || "";
      if (!name || !hostCode) return;
      showStatus(createStatus, "Wird angelegt…", "");
      try {
        await api("/api/admin/knowledge-sources", {
          method: "POST",
          body: JSON.stringify({ name, host_code: hostCode }),
        });
        createForm.reset();
        showStatus(createStatus, "Quelle angelegt.", "ok");
        await loadSources();
      } catch (err) {
        showStatus(createStatus, err.detail || err.code || "Anlegen fehlgeschlagen.", "error");
      }
    });

    tbody?.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      if (target.closest(".kc-source-edit-btn")) {
        const row = target.closest("tr:not(.kc-source-edit-row)");
        if (!row) return;
        const sourceId = row.dataset.sourceId;
        tbody.querySelectorAll(".kc-source-edit-row").forEach((el) => el.classList.add("hidden"));
        tbody.querySelector(`tr.kc-source-edit-row[data-source-id="${sourceId}"]`)?.classList.remove("hidden");
        return;
      }

      if (target.closest(".kc-source-cancel-btn")) {
        target.closest("tr.kc-source-edit-row")?.classList.add("hidden");
        return;
      }

      if (target.closest(".kc-source-save-btn")) {
        const editRow = target.closest("tr.kc-source-edit-row");
        if (!editRow) return;
        const sourceId = editRow.dataset.sourceId;
        const name = editRow.querySelector(".kc-source-edit-name")?.value.trim() || "";
        const active = Boolean(editRow.querySelector(".kc-source-edit-active")?.checked);
        if (!name) {
          showStatus(listStatus, "Name ist Pflicht.", "error");
          return;
        }
        try {
          await api(`/api/admin/knowledge-sources/${sourceId}`, {
            method: "PATCH",
            body: JSON.stringify({ name, active }),
          });
          editRow.classList.add("hidden");
          showStatus(listStatus, "Quelle gespeichert.", "ok");
          await loadSources();
        } catch (err) {
          showStatus(listStatus, err.detail || err.code || "Speichern fehlgeschlagen.", "error");
        }
        return;
      }

      if (target.closest(".kc-source-delete-btn")) {
        const row = target.closest("tr:not(.kc-source-edit-row)");
        if (!row) return;
        const sourceId = row.dataset.sourceId;
        if (!window.confirm("Quelle wirklich löschen?")) return;
        try {
          await api(`/api/admin/knowledge-sources/${sourceId}`, { method: "DELETE" });
          showStatus(listStatus, "Quelle gelöscht.", "ok");
          await loadSources();
        } catch (err) {
          showStatus(listStatus, err.detail || err.code || "Löschen fehlgeschlagen.", "error");
        }
      }
    });

    loadSources().catch(() => {});
  }

  syncActiveCustomerFromSelect();
  setCustomerUiEnabled(Boolean(activeCustomerId));
  initCollapsibleNav();
  initSidebarNavScroll();
  initChatSidebar();
  refreshChatHistory().catch(() => {});

  if (page === "chat") initChatPage();
  if (page === "kb") initKbPage();
  if (page === "tools_bild_zu_text") initImageToTextTool();
  if (page === "tools_kc_content") initKnowledgeCenterContentPage();
  if (page === "tools_kc_submit") initKnowledgeCenterSubmitPage();
  if (page === "tools_kc_sources") initKnowledgeCenterSourcesPage();
  if (page === "admin_knowledge") initAdminKnowledgePage();
  if (page === "admin_prompts") initAdminPromptsPage();
  if (page === "admin_users") initUsersPage();
  if (page === "admin_roles") initRolesPage();
  if (page === "admin_keys") initKeysPage();
  if (page === "admin_keys_presets") initKeysPresetsPage();
  if (page === "admin_keys_assignments") initKeysAssignmentsPage();
  if (page === "customers") initCustomersPage();
})();
