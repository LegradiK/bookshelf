function initBulkSelect() {
  const grid = document.getElementById("book-grid");
  const bulkForm = document.getElementById("bulk-delete-form");
  if (!grid) return;

  const selected = new Set();
  let bar = null;

  grid.addEventListener("change", (e) => {
    if (!e.target.classList.contains("book-select")) return;
    const id = e.target.dataset.id;
    if (e.target.checked) selected.add(id);
    else selected.delete(id);
    updateBar();
  });

  function updateBar() {
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "bulk-delete-bar";
      bar.className = "bulk-add-bar";
      bar.innerHTML = `
        <span id="bulk-delete-count"></span>
        <button type="button" id="bulk-delete-btn" class="btn-text-danger">Delete selected</button>
      `;
      document.body.appendChild(bar);
      document.getElementById("bulk-delete-btn").addEventListener("click", submitDelete);
    }
    const count = selected.size;
    bar.style.display = count > 0 ? "flex" : "none";
    document.getElementById("bulk-delete-count").textContent = `${count} selected`;
  }

  function submitDelete() {
    if (!selected.size) return;
    if (!confirm(`Remove ${selected.size} book${selected.size === 1 ? "" : "s"} from your shelf?`)) return;

    bulkForm.innerHTML = "";
    selected.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "book_id";
      input.value = id;
      bulkForm.appendChild(input);
    });
    bulkForm.submit();
  }
}

document.addEventListener("DOMContentLoaded", initBulkSelect);