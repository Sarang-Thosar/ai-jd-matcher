function showTab(tab) {
  document.getElementById("text").classList.add("hidden");
  document.getElementById("pdf").classList.add("hidden");

  document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active"));

  document.getElementById(tab).classList.remove("hidden");
  event.target.classList.add("active");
}

async function submitText() {
  const resume = document.getElementById("resume").value;
  const jd = document.getElementById("jd").value;

  const res = await fetch("/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume, jd })
  });

  const data = await res.json();
  showResult(data);
}

async function submitPDF() {
  const file = document.getElementById("pdfFile").files[0];
  const jd = document.getElementById("jdPdf").value;

  const form = new FormData();
  form.append("file", file);
  form.append("jd", jd);

  const res = await fetch("/match-pdf", {
    method: "POST",
    body: form
  });

  const data = await res.json();
  showResult(data);
}

function showResult(data) {
  const result = document.getElementById("result");
  result.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
  result.classList.remove("hidden");
}
