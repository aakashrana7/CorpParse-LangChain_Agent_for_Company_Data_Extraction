/* CorpParse Frontend JS
 * Assumptions about backend /extract response:
 *   Content-Type: application/json
 *   Shape: { data: [ { company_name: string, founding_date: "YYYY-MM-DD", founders: string[] | string } ] }
 * We render a table + CSV console and enable client-side CSV download.
 */

const form = document.getElementById('extractForm');
const essayInput = document.getElementById('essayInput');
const fileInput = document.getElementById('fileInput');
const statusEl = document.getElementById('status');

const resultsBody = document.getElementById('resultsBody');
const csvConsole = document.getElementById('csvConsole');
const downloadBtn = document.getElementById('downloadCsvBtn');
const copyCsvBtn = document.getElementById('copyCsvBtn');
const extractBtn = document.getElementById('extractBtn');
const clearBtn = document.getElementById('clearBtn');
const demoBtn = document.getElementById('demoBtn');

const tabTable = document.getElementById('tabTable');
const tabCsv = document.getElementById('tabCsv');
const panelTable = document.getElementById('panelTable');
const panelCsv = document.getElementById('panelCsv');

document.getElementById('year').textContent = new Date().getFullYear();

let currentCsv = '';

/* ---------- Tabs ---------- */
function activateTab(which) {
  if (which === 'table') {
    tabTable.classList.add('active');
    tabCsv.classList.remove('active');
    panelTable.classList.add('active');
    panelCsv.classList.remove('active');
    tabTable.setAttribute('aria-selected','true');
    tabCsv.setAttribute('aria-selected','false');
  } else {
    tabCsv.classList.add('active');
    tabTable.classList.remove('active');
    panelCsv.classList.add('active');
    panelTable.classList.remove('active');
    tabCsv.setAttribute('aria-selected','true');
    tabTable.setAttribute('aria-selected','false');
  }
}
tabTable.addEventListener('click', () => activateTab('table'));
tabCsv.addEventListener('click', () => activateTab('csv'));

/* ---------- Helpers ---------- */
function setStatus(msg, type = '') {
  statusEl.textContent = msg;
  statusEl.className = 'status' + (type ? ` ${type}` : '');
}
function clearStatus() { setStatus(''); }

function resetOutput() {
  resultsBody.innerHTML = '';
  csvConsole.textContent = 'No results yet.';
  currentCsv = '';
  downloadBtn.classList.add('disabled');
  downloadBtn.setAttribute('href', '#');
}

function foundersToDisplay(founders) {
  if (Array.isArray(founders)) {
    // Pythonic list style exactly as requested
    return `['${founders.join("', '")}']`;
  }
  // If backend already sends a string (possibly formatted), pass-through
  return String(founders ?? '');
}

function escapeCsvField(val) {
  // Escape quotes by doubling them and wrap in quotes if contains comma/quote/newline
  const s = String(val ?? '');
  if (/[",\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function buildCsv(rows) {
  const header = ['S.N.', 'Company Name', 'Founded in', 'Founded by'];
  const lines = [header.join(',')];

  rows.forEach((row, i) => {
    const sn = i + 1;
    const company = row.company_name ?? row.CompanyName ?? '';
    const date = row.founding_date ?? row.FoundedIn ?? '';
    const founders = foundersToDisplay(row.founders ?? row.FoundedBy ?? []);
    lines.push([
      escapeCsvField(sn),
      escapeCsvField(company),
      escapeCsvField(date),
      escapeCsvField(founders),
    ].join(','));
  });

  return lines.join('\n');
}

function renderTable(rows) {
  resultsBody.innerHTML = '';
  rows.forEach((row, i) => {
    const tr = document.createElement('tr');
    const sn = i + 1;
    const company = row.company_name ?? '';
    const date = row.founding_date ?? '';
    const founders = foundersToDisplay(row.founders);

    tr.innerHTML = `
      <td>${sn}</td>
      <td>${company}</td>
      <td>${date}</td>
      <td>${founders}</td>
    `;
    resultsBody.appendChild(tr);
  });
}

function enableDownload(csvText) {
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  downloadBtn.setAttribute('href', url);
  downloadBtn.classList.remove('disabled');
}

/* ---------- Actions ---------- */
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearStatus();
  resetOutput();
  activateTab('table');

  const hasFile = fileInput.files && fileInput.files.length > 0;
  const text = (essayInput.value || '').trim();

  if (!hasFile && !text) {
    setStatus('Please paste text or choose a .pdf/.txt file.', 'error');
    return;
  }

  extractBtn.disabled = true;
  extractBtn.textContent = 'Extracting…';

  try {
    // Always use multipart/form-data for simplicity
    const formData = new FormData();
    if (hasFile) {
      formData.append('file', fileInput.files[0]);
    }
    if (text) {
      formData.append('essay_text', text);
    }

    const res = await fetch('/extract', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || `Request failed with status ${res.status}`);
    }

    const payload = await res.json();
    const rows = Array.isArray(payload?.data) ? payload.data : [];

    if (!rows.length) {
      setStatus('No data extracted. Please check your input content.', 'error');
      return;
    }

    // Render table + CSV console + enable download
    renderTable(rows);
    currentCsv = buildCsv(rows);
    csvConsole.textContent = currentCsv;
    enableDownload(currentCsv);
    setStatus('Extraction complete.', 'success');

  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    extractBtn.disabled = false;
    extractBtn.textContent = 'Run Extraction';
  }
});

clearBtn.addEventListener('click', () => {
  essayInput.value = '';
  fileInput.value = '';
  resetOutput();
  clearStatus();
});

copyCsvBtn.add
