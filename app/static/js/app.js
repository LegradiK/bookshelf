function initBookSearch() {
  const input = document.getElementById("search-input");
  const statusEl = document.getElementById("search-status");
  const resultsEl = document.getElementById("search-results");
  if (!input) return;

  let debounceTimer = null;

  input.addEventListener("input", () => {
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    resultsEl.innerHTML = "";

    if (query.length < 2) {
      statusEl.textContent = "";
      return;
    }

    statusEl.textContent = "Searching...";
    debounceTimer = setTimeout(() => runSearch(query), 350);
  });

  async function runSearch(query) {
    try {
      const res = await fetch(`/search-books?q=${encodeURIComponent(query)}`);
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
    } catch (err) {
      statusEl.textContent = "Something went wrong searching. Try again.";
    }
  }

  function renderResultCard(book) {
    const cover = book.cover_url
      ? `<img src="${escapeAttr(book.cover_url)}" alt="Cover of ${escapeAttr(book.title)}">`
      : "";
    const yearText = book.year ? ` (${book.year})` : "";

    return `
      <div class="result-card">
        <div class="result-cover">${cover}</div>
        <div class="result-info">
          <p class="result-title">${escapeHtml(book.title)}${yearText}</p>
          <p class="result-author">${escapeHtml(book.author)}</p>
          <div class="result-actions">
            ${addBookForm(book, "want_to_read", "Want to read")}
            ${addBookForm(book, "reading", "Start reading", true)}
          </div>
        </div>
      </div>
    `;
  }

  function addBookForm(book, status, label, primary) {
    return `
      <form method="post" action="/add-book" style="display:inline;">
        <input type="hidden" name="google_books_id" value="${escapeAttr(book.google_books_id || "")}">
        <input type="hidden" name="title" value="${escapeAttr(book.title)}">
        <input type="hidden" name="author" value="${escapeAttr(book.author)}">
        <input type="hidden" name="cover_url" value="${escapeAttr(book.cover_url || "")}">
        <input type="hidden" name="status" value="${status}">
        <button type="submit" class="btn-small${primary ? " primary" : ""}">${label}</button>
      </form>
    `;
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
