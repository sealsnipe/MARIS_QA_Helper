(() => {
  const boot = window.APP_BOOT || {};
  const page = boot.page || "chat";
  const globalCustomerId = boot.globalCustomerId || "global";
  const customerLabels = boot.customerLabels || {};
  const isAdmin = Boolean(boot.isAdmin);
  let activeCustomerId = boot.activeCustomerId || "";
  let activeCustomerName = boot.activeCustomerName || "";

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
    const { readOnly = false, showCustomer = false, adminEdit = null } = options;
    if (!listEl) return;
    listEl.innerHTML = "";
    if (countEl) countEl.textContent = `(${documents.length})`;
    emptyEl?.classList.toggle("hidden", documents.length > 0);

    for (const doc of documents) {
      const item = document.createElement("li");
      item.className = "doc-item";
      item.dataset.docId = doc.id;

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
          ${renderExtractionBadges(doc.extraction_meta)}
        </span>
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

  async function refreshAdminDocuments(scope = "global") {
    const base =
      scope === "global"
        ? "/api/admin/documents"
        : `/api/admin/customers/${encodeURIComponent(scope)}/documents`;
    const data = await api(base);
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
          basePath: base,
          onRefresh: () => refreshAdminDocuments(scope),
        },
      },
    );
  }

  function knowledgeScopeLabel(scope) {
    if (scope === "global") return "Global";
    return customerLabels[scope] || scope;
  }

  function initAdminNav() {
    const group = document.getElementById("admin-nav-group");
    const toggle = document.getElementById("admin-nav-toggle");
    if (!group || !toggle) return;

    toggle.addEventListener("click", () => {
      group.classList.toggle("expanded");
      toggle.setAttribute("aria-expanded", group.classList.contains("expanded") ? "true" : "false");
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

  function renderExtractionBadges(extractionMeta) {
    if (!extractionMeta || typeof extractionMeta !== "object") return "";
    const parts = [];
    if (extractionMeta.coverage === "partial" && extractionMeta.image_count > 0) {
      const missing = Math.max(0, extractionMeta.image_count - (extractionMeta.images_processed || 0));
      if (missing > 0) {
        parts.push(`<span class="badge partial">· ${missing} Bild(er) nicht verarbeitet</span>`);
      }
    }
    if (extractionMeta.vision_used) {
      parts.push('<span class="badge vision">· Vision-OCR</span>');
    }
    return parts.join(" ");
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

      if (!file) return;

      const lowerName = file.name.toLowerCase();
      if (!INSPECTABLE_FILE_PATTERN.test(lowerName)) return;

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
      }
    };

    setupDropzone(dropzone, fileInput, fileLabel, (file) => {
      setFile(file).catch(() => {});
    }, () => Boolean(selectedFile));

    textInput?.addEventListener("input", () => {
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
      setFile(file).catch(() => {});
    });

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

    if (activeCustomerId) {
      refreshKbDocuments().catch(() => showStatus(document.getElementById("ingest-status"), "Dokumente konnten nicht geladen werden.", "error"));
    }
  }

  function initImageToTextTool() {
    const zone = document.getElementById("image-paste-zone");
    const fileInput = document.getElementById("image-file-input");
    const listEl = document.getElementById("image-preview-list");
    const transcribeBtn = document.getElementById("transcribe-btn");
    const clearBtn = document.getElementById("clear-images-btn");
    const statusEl = document.getElementById("tool-status");
    const outputEl = document.getElementById("transcribe-output");
    const outputContent = document.getElementById("output-content");
    const copyAllBtn = document.getElementById("copy-all-btn");

    let images = []; // {id, file: File, url: string}

    function renderList() {
      if (!listEl) return;
      listEl.innerHTML = "";
      if (images.length === 0) {
        transcribeBtn.disabled = true;
        return;
      }
      transcribeBtn.disabled = false;

      images.forEach((img) => {
        const card = document.createElement("div");
        card.className = "image-preview-card";
        card.innerHTML = `
          <img src="${img.url}" alt="">
          <div class="card-label">${escapeHtml(img.file.name)}</div>
          <label style="font-size:0.7rem;display:flex;align-items:center;gap:4px;margin-top:4px;">
            <input type="checkbox" class="select-img" data-id="${img.id}" checked> OCR
          </label>
          <button type="button" class="remove-btn" data-id="${img.id}">×</button>
        `;
        listEl.appendChild(card);
      });
    }

    listEl?.addEventListener("click", (e) => {
      const removeBtn = e.target.closest(".remove-btn");
      if (removeBtn) {
        const id = removeBtn.dataset.id;
        const entry = images.find((i) => i.id === id);
        if (entry) URL.revokeObjectURL(entry.url);
        images = images.filter((i) => i.id !== id);
        renderList();
        if (outputEl) outputEl.classList.add("hidden");
      }
    });

    function addImage(file) {
      if (!file || !file.type.startsWith("image/")) return;
      const id = "img_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
      const url = URL.createObjectURL(file);
      images.push({ id, file, url });
      renderList();
      if (outputEl) outputEl.classList.add("hidden");
      showStatus(statusEl, "");
    }

    function handlePaste(ev) {
      if (ev.defaultPrevented) return; // another listener (zone/form/doc) already handled this paste
      let added = false;
      if (typeof fileFromClipboard === "function") {
        const f = fileFromClipboard(ev.clipboardData);
        if (f) {
          ev.preventDefault();
          addImage(f);
          added = true;
        }
      }
      if (!added && ev.clipboardData && ev.clipboardData.files && ev.clipboardData.files.length) {
        ev.preventDefault();
        Array.from(ev.clipboardData.files).forEach(addImage);
      }
    }

    if (zone && fileInput) {
      zone.addEventListener("click", () => {
        fileInput.click();
        zone.focus(); // ensure focused so paste targets the zone (like KB dropzone)
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

      // paste support on the zone itself (mirrors setupDropzone in KB)
      zone.addEventListener("paste", handlePaste);

      // also on the containing form (like the ingest-form paste listener in bindIngestForm for KB)
      // this makes Ctrl+V work even if focus is on other elements inside the form area
      const toolForm = document.getElementById("image-tool-form");
      toolForm?.addEventListener("paste", handlePaste);

      // Document-level listener for this dedicated tool page.
      // Makes "Strg+V" work from anywhere on the page (no need to focus the dropzone first),
      // using the exact same fileFromClipboard helper as the KB implementation.
      // Non-image pastes do nothing (no preventDefault).
      document.addEventListener("paste", handlePaste);

      // drag & drop bonus
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
      renderList();
      if (outputEl) outputEl.classList.add("hidden");
      if (outputContent) outputContent.innerHTML = "";
      showStatus(statusEl, "");
    });

    transcribeBtn?.addEventListener("click", async () => {
      const selected = [];
      if (!listEl) return;
      listEl.querySelectorAll(".select-img:checked").forEach((cb) => {
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
        const results = res.results || [];

        outputContent.innerHTML = "";
        let allTextParts = [];

        results.forEach((r, idx) => {
          const item = document.createElement("div");
          item.className = "output-item";

          const head = document.createElement("div");
          head.style.fontWeight = "600";
          head.style.marginBottom = "0.25rem";
          head.textContent = r.filename || `Bild ${idx + 1}`;
          item.appendChild(head);

          if (r.error) {
            const err = document.createElement("div");
            err.className = "status error";
            err.textContent = r.error + (r.detail ? ` (${r.detail})` : "");
            item.appendChild(err);
          } else {
            const ta = document.createElement("textarea");
            ta.value = r.text || "";
            ta.rows = Math.min(12, Math.max(3, (r.text || "").split("\n").length));
            ta.style.width = "100%";
            ta.readOnly = true;
            item.appendChild(ta);

            const copyOne = document.createElement("button");
            copyOne.type = "button";
            copyOne.className = "secondary small";
            copyOne.style.marginTop = "0.25rem";
            copyOne.textContent = "Diesen Text kopieren";
            copyOne.addEventListener("click", () => {
              navigator.clipboard.writeText(ta.value || "").then(() => {
                const old = copyOne.textContent;
                copyOne.textContent = "Kopiert!";
                setTimeout(() => (copyOne.textContent = old), 1200);
              }).catch(() => {});
            });
            item.appendChild(copyOne);

            allTextParts.push(r.text || "");
          }
          outputContent.appendChild(item);
        });

        if (copyAllBtn) {
          copyAllBtn.onclick = () => {
            const joined = allTextParts.join("\n\n---\n\n");
            navigator.clipboard.writeText(joined).then(() => {
              const old = copyAllBtn.textContent;
              copyAllBtn.textContent = "Kopiert!";
              setTimeout(() => (copyAllBtn.textContent = old), 1200);
            }).catch(() => {});
          };
        }

        if (outputEl) outputEl.classList.remove("hidden");
        showStatus(statusEl, "Fertig — Text kann kopiert werden.", "ok");
      } catch (err) {
        const msg = (err && err.code) ? `Fehler: ${err.code}` : "Transkription fehlgeschlagen.";
        showStatus(statusEl, msg, "error");
      } finally {
        transcribeBtn.disabled = images.length === 0;
      }
    });

    // initial render
    renderList();
    if (outputEl) outputEl.classList.add("hidden");
  }

  function initAdminKnowledgePage() {
    const scopeSelect = document.getElementById("knowledge-scope");
    const scopeLabel = document.getElementById("knowledge-scope-label");
    const scopeHint = document.getElementById("knowledge-scope-hint");
    const statusEl = document.getElementById("admin-ingest-status");

    function currentScope() {
      return scopeSelect?.value || "global";
    }

    function updateScopeUi() {
      const scope = currentScope();
      if (scopeLabel) scopeLabel.textContent = `(${knowledgeScopeLabel(scope)})`;
      if (scopeHint) {
        scopeHint.textContent =
          scope === "global"
            ? "Gilt mandantenübergreifend — wird zusätzlich zur Kunden-KB durchsucht."
            : `Kunden-Wissensdatenbank für ${knowledgeScopeLabel(scope)}.`;
      }
    }

    async function refreshScopeDocuments() {
      await refreshAdminDocuments(currentScope());
    }

    scopeSelect?.addEventListener("change", () => {
      closeAllDocEditPanels(document.getElementById("admin-doc-list"));
      updateScopeUi();
      refreshScopeDocuments().catch(() =>
        showStatus(statusEl, "Dokumente konnten nicht geladen werden.", "error"),
      );
    });

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

    updateScopeUi();
    refreshScopeDocuments().catch(() =>
      showStatus(statusEl, "Dokumente konnten nicht geladen werden.", "error"),
    );
  }

  function initAdminPromptsPage() {
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

  function readCustomerCheckboxValues(container, namePrefix) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(`input[name="${namePrefix}"]:checked`)).map(
      (el) => el.value,
    );
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
    const createCustomers = document.getElementById("user-create-customers");
    const createStatus = document.getElementById("user-create-status");
    let assignableCustomers = [];
    let customerNameById = {};

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
          <td colspan="5">
            <div class="ingest-form">
              <div class="customer-form-row user-form-row">
                <label>E-Mail<input type="email" class="user-edit-email" value="${escapeHtml(user.email)}" maxlength="200"></label>
                <label>Neues Passwort (optional)<input type="password" class="user-edit-password" minlength="8" placeholder="leer = unverändert"></label>
                <label class="user-admin-checkbox"><input type="checkbox" class="user-edit-admin" ${user.is_admin ? "checked" : ""}> Administrator</label>
                <label class="user-admin-checkbox"><input type="checkbox" class="user-edit-active" ${user.is_active ? "checked" : ""}> Aktiv</label>
              </div>
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
        renderCustomerCheckboxes(
          editRow.querySelector(".user-edit-customers"),
          assignableCustomers,
          user.customer_ids,
          `edit-${user.id}`,
        );
      });
    }

    async function loadUsers() {
      const data = await api("/api/admin/users");
      assignableCustomers = data.customers || [];
      customerNameById = Object.fromEntries(assignableCustomers.map((c) => [c.id, c.name]));
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
        const customerIds = readCustomerCheckboxValues(editRow?.querySelector(".user-edit-customers"), `edit-${userId}`);
        if (!email) {
          showStatus(listStatus, "E-Mail ist Pflicht.", "error");
          return;
        }
        showStatus(listStatus, "Speichern…");
        try {
          const body = { email, customer_ids: customerIds, is_admin: isAdmin, is_active: isActive };
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
      const customerIds = readCustomerCheckboxValues(createCustomers, "create");
      if (!email || !password) {
        showStatus(createStatus, "E-Mail und Passwort sind Pflicht.", "error");
        return;
      }
      showStatus(createStatus, "Anlegen…");
      try {
        await api("/api/admin/users", {
          method: "POST",
          body: JSON.stringify({ email, password, customer_ids: customerIds, is_admin: isAdmin }),
        });
        if (createEmail) createEmail.value = "";
        if (createPassword) createPassword.value = "";
        if (createAdmin) createAdmin.checked = false;
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
        row.innerHTML = `
          <td>
            <code class="customer-id-display">${escapeHtml(customer.id)}</code>
            <input type="text" class="customer-id-input hidden" value="${escapeHtml(customer.id)}" maxlength="64">
          </td>
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
      const idDisplay = row.querySelector(".customer-id-display");
      const idInput = row.querySelector(".customer-id-input");
      const nameDisplay = row.querySelector(".customer-name-display");
      const nameInput = row.querySelector(".customer-name-input");
      const editBtn = row.querySelector(".customer-edit-btn");
      const saveBtn = row.querySelector(".customer-save-btn");
      const cancelBtn = row.querySelector(".customer-cancel-btn");

      if (target.classList.contains("customer-edit-btn")) {
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

  if (isAdmin) initAdminNav();

  if (page === "chat") initChatPage();
  if (page === "kb") initKbPage();
  if (page === "tools_bild_zu_text") initImageToTextTool();
  if (page === "admin_knowledge") initAdminKnowledgePage();
  if (page === "admin_prompts") initAdminPromptsPage();
  if (page === "admin_users") initUsersPage();
  if (page === "customers") initCustomersPage();
})();
