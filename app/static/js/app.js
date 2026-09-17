function initBookSearch() {
  const input = document.getElementById("search-input");
  const statusEl = document.getElementById("search-status");
  const resultsEl = document.getElementById("search-results");
  const globalStatusSelect = document.getElementById("reading-status-select");
  if (!input) return;

  let debounceTimer = null;
  let activeController = null;
  const selected = new Map(); // google_books_id -> true, tracks checked cards across re-renders

  input.addEventListener("input", () => {
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    resultsEl.innerHTML = "";

    if (query.length < 2) {
      statusEl.textContent = "";
      return;
    }

    statusEl.textContent = "Searching...";
    debounceTimer = setTimeout(() => runSearch(query), 600);
  });

  async function runSearch(query) {
    if (activeController) {
      activeController.abort();
    }
    activeController = new AbortController();

    try {
      const res = await fetch(`/search-books?q=${encodeURIComponent(query)}`, {
        signal: activeController.signal,
      });
      const data = await res.json();

      if (data.error) {
        statusEl.textContent = data.error;
        return;
      }

      if (!data.length) {
        statusEl.textContent = "No books found. Try a different spelling.";
        resultsEl.innerHTML = "";
        return;
      }

      statusEl.textContent = `${data.length} result${data.length === 1 ? "" : "s"}`;
      resultsEl.innerHTML = data.map(renderResultCard).join("");
      updateBulkBar();
    } catch (err) {
      if (err.name === "AbortError") return;
      statusEl.textContent = "Something went wrong searching. Try again.";
    }
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

  // Fill each form's hidden status field from the global select right before it submits,
  // and block submission if no status has been chosen yet.
  resultsEl.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form.classList.contains("result-add-form")) return;

    if (!globalStatusSelect.value) {
      e.preventDefault();
      globalStatusSelect.focus();
      statusEl.textContent = "Pick a reading status first.";
      return;
    }
    form.querySelector(".status-carrier").value = globalStatusSelect.value;
  });

  // Track checkbox changes via event delegation, since cards are re-rendered on every search
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
      statusEl.textContent = "Pick a reading status first.";
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
    form.submit(); // real navigation — lets the server's redirect() work as normal
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