const NOTES_KEY = "evidence-notes";
const notesEl = document.getElementById("notes-input");
document.getElementById("save-notes").addEventListener("click", () => {
  localStorage.setItem(NOTES_KEY, notesEl.value || "");
  alert("Notes saved.");
});
document.getElementById("clear-notes").addEventListener("click", () => {
  if (confirm("Clear your notes?")) {
    notesEl.value = "";
    localStorage.removeItem(NOTES_KEY);
  }
});
(function initNotes() {
  const saved = localStorage.getItem(NOTES_KEY);
  if (saved) notesEl.value = saved;
})();

const apiBase = "http://127.0.0.1:8000";
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const evidenceView = document.getElementById("evidence-view");

async function extractEvidence(inputText) {
  statusEl.textContent = "Calling /extract…";
  try {
    const res = await fetch(`${apiBase}/extract`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ text: inputText })
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`API ${res.status}: ${text}`);
    const data = JSON.parse(text);
    resultEl.textContent = JSON.stringify(data, null, 2);
    evidenceView.innerHTML = "<pre style='margin:0'>" + resultEl.textContent + "</pre>";
    statusEl.textContent = "Done.";
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Error";
    alert("API error: " + err.message);
  }
}

document.getElementById("extract-btn").addEventListener("click", () => {
  const input = document.getElementById("extract-input").value.trim();
  if (!input) { alert("Please paste some text first."); return; }
  extractEvidence(input);
});
