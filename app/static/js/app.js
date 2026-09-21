function initBookSearch() {
  const input = document.getElementById("search-input");
  const statusEl = document.getElementById("search-status");
  const messageEl = document.getElementById("search-message");
  const resultsEl = document.getElementById("search-results");
  const globalStatusSelect = document.getElementById("reading-status-select");
  if (!input) return;

  let debounceTimer = null;
  let activeController = null;
  const selected = new Map(); // google_books_id -> true, tracks checked cards across re-renders

  let currentQuery = "";
  let currentStart = 0;
  let totalItems = 0;
  const PAGE_SIZE = 40;

  input.addEventListener("input", () => {
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    resultsEl.innerHTML = "";
    removeLoadMoreButton();
    statusEl.textContent = "";

    if (query.length < 2) {
      messageEl.textContent = "";
      return;
    }

    messageEl.textContent = "Searching...";
    debounceTimer = setTimeout(() => runSearch(query, { fresh: true }), 600);
  });

  async function runSearch(query, { fresh }) {
    if (activeController) {
      activeController.abort();
    }
    activeController = new AbortController();

    if (fresh) {
      currentQuery = query;
      currentStart = 0;
    }

    try {
      const res = await fetch(
        `/search-books?q=${encodeURIComponent(currentQuery)}&start=${currentStart}`,
        { signal: activeController.signal }
      );
      const data = await res.json();

      if (data.error) {
        messageEl.textContent = data.error;
        statusEl.textContent = "";
        removeLoadMoreButton();
        return;
      }

      const items = data.items || [];
      totalItems = data.total_items || 0;

      if (fresh && !items.length) {
        messageEl.textContent = "No books found. Try a different spelling.";
        statusEl.textContent = "";
        resultsEl.innerHTML = "";
        removeLoadMoreButton();
        return;
      }

      if (fresh) {
        resultsEl.innerHTML = items.map(renderResultCard).join("");
      } else {
        resultsEl.insertAdjacentHTML("beforeend", items.map(renderResultCard).join(""));
      }

      currentStart += items.length;

      const shownCount = resultsEl.querySelectorAll(".book-card").length;
      messageEl.textContent = "";   // add this
      statusEl.textContent = `${shownCount} of ${totalItems} result${totalItems === 1 ? "" : "s"}`;

      updateLoadMoreButton();
      updateBulkBar();
    } catch (err) {
      if (err.name === "AbortError") return;
      messageEl.textContent = "Something went wrong while searching. Try again.";
    }
  }

function updateLoadMoreButton() {
  removeLoadMoreButton();
  if (currentStart >= totalItems) return; // no more pages

  const wrap = document.createElement("div");
  wrap.id = "load-more-wrap";
  wrap.className = "load-more-wrap";

  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "load-more-btn";
  btn.className = "load-more-btn";
  btn.textContent = "Load more";
  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.textContent = "Loading...";
    runSearch(currentQuery, { fresh: false });
  });

  wrap.appendChild(btn);
  resultsEl.insertAdjacentElement("afterend", wrap);
}

function removeLoadMoreButton() {
  const existing = document.getElementById("load-more-wrap");
  if (existing) existing.remove();
}

  function renderResultCard(book) {
    const coverInner = book.cover_url
      ? `<img src="${escapeAttr(book.cover_url)}" alt="Cover of ${escapeAttr(book.title)}">`
      : `<div class="book-cover-placeholder">${escapeHtml((book.title || "?").charAt(0))}</div>`;
    const yearText = book.year ? ` (${book.year})` : "";
    const id = escapeAttr(book.google_books_id || "");
    const checked = selected.has(book.google_books_id) ? "checked" : "";

    return `
      <div class="book-card">
        <label class="book-select-label">
          <input type="checkbox" class="result-select" data-id="${id}" ${checked}>
        </label>
        <div class="book-cover">${coverInner}</div>
        <p class="book-title">${escapeHtml(book.title)}${yearText}</p>
        <p class="book-author">${escapeHtml(book.author)}</p>
        ${addBookForm(book)}
      </div>
    `;
  }

  function addBookForm(book) {
    return `
      <form method="post" action="/add-book" class="result-add-form">
        <input type="hidden" name="google_books_id" value="${escapeAttr(book.google_books_id || "")}">
        <input type="hidden" name="title" value="${escapeAttr(book.title)}">
        <input type="hidden" name="author" value="${escapeAttr(book.author)}">
        <input type="hidden" name="cover_url" value="${escapeAttr(book.cover_url || "")}">
        <input type="hidden" name="categories" value="${escapeAttr(book.categories || "")}">
        <input type="hidden" name="isbn" value="${escapeAttr(book.isbn)}">
        <input type="hidden" name="status" class="status-carrier">
        <button type="submit" class="btn-small primary">Add</button>
      </form>
    `;
  }

  resultsEl.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form.classList.contains("result-add-form")) return;

    if (!globalStatusSelect.value) {
      e.preventDefault();
      globalStatusSelect.focus();
      messageEl.textContent = "Pick a reading status first.";
      return;
    }
    form.querySelector(".status-carrier").value = globalStatusSelect.value;
  });

  resultsEl.addEventListener("change", (e) => {
    if (!e.target.classList.contains("result-select")) return;
    const id = e.target.dataset.id;
    if (e.target.checked) {
      selected.set(id, true);
    } else {
      selected.delete(id);
    }
    updateBulkBar();
  });

  function updateBulkBar() {
    let bar = document.getElementById("bulk-add-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "bulk-add-bar";
      bar.className = "bulk-add-bar";
      bar.innerHTML = `
        <span id="bulk-count"></span>
        <button type="button" id="bulk-add-btn" class="btn-primary">Add selected books</button>
      `;
      document.body.appendChild(bar);
      document.getElementById("bulk-add-btn").addEventListener("click", submitBulkAdd);
    }

    const count = selected.size;
    bar.style.display = count > 0 ? "flex" : "none";
    document.getElementById("bulk-count").textContent = `${count} selected`;
  }

  function submitBulkAdd() {
    if (!globalStatusSelect.value) {
      globalStatusSelect.focus();
      messageEl.textContent = "Pick a reading status first.";
      return;
    }
    const status = globalStatusSelect.value;

    const form = document.createElement("form");
    form.method = "post";
    form.action = "/add-books";

    selected.forEach((_, id) => {
      const idInput = document.createElement("input");
      idInput.type = "hidden";
      idInput.name = "google_books_id";
      idInput.value = id;
      form.appendChild(idInput);
    });

    const statusInput = document.createElement("input");
    statusInput.type = "hidden";
    statusInput.name = "status";
    statusInput.value = status;
    form.appendChild(statusInput);

    document.body.appendChild(form);
    form.submit();
  }

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function escapeAttr(str) {
    return escapeHtml(str);
  }
}

document.addEventListener("DOMContentLoaded", initBookSearch);