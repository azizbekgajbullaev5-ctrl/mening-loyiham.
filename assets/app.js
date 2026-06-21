// ====== Ilova mantig'i ======
const STORAGE_KEY = "oak_arizalar";

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initFiltrlar();
  initModal();
  renderJurnallar();
  initShablon();
  initForm();
  renderArizalar();
});

// ---------- Navigatsiya ----------
function initNav() {
  const tugmalar = document.querySelectorAll(".nav-btn");
  tugmalar.forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      tugmalar.forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".view").forEach((v) => {
        v.classList.toggle("active", v.id === "view-" + view);
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

// ---------- Filtrlar ----------
function initFiltrlar() {
  const sohaSelect = document.getElementById("filter-soha");
  const tilSelect = document.getElementById("filter-til");
  const formJurnal = document.getElementById("form-jurnal");

  SOHALAR.forEach((s) => sohaSelect.add(new Option(s, s)));
  TILLAR.forEach((t) => tilSelect.add(new Option(t, t)));
  JOURNALS.forEach((j) => formJurnal.add(new Option(j.nomi, j.nomi)));

  document.getElementById("qidiruv").addEventListener("input", renderJurnallar);
  sohaSelect.addEventListener("change", renderJurnallar);
  tilSelect.addEventListener("change", renderJurnallar);
}

// ---------- Jurnallarni chizish ----------
function renderJurnallar() {
  const qidiruv = document.getElementById("qidiruv").value.trim().toLowerCase();
  const soha = document.getElementById("filter-soha").value;
  const til = document.getElementById("filter-til").value;
  const royxat = document.getElementById("jurnallar-royxati");

  const natija = JOURNALS.filter((j) => {
    const matnMos =
      !qidiruv ||
      j.nomi.toLowerCase().includes(qidiruv) ||
      j.soha.toLowerCase().includes(qidiruv) ||
      j.davlat.toLowerCase().includes(qidiruv) ||
      j.nashriyot.toLowerCase().includes(qidiruv);
    const sohaMos = !soha || j.soha === soha;
    const tilMos = !til || j.til === til;
    return matnMos && sohaMos && tilMos;
  });

  document.getElementById("natija-soni").textContent =
    natija.length + " ta jurnal topildi";

  if (natija.length === 0) {
    royxat.innerHTML =
      '<p class="empty">Hech qanday jurnal topilmadi. Filtrlarni o\'zgartirib ko\'ring.</p>';
    return;
  }

  royxat.innerHTML = natija
    .map(
      (j) => `
    <div class="card">
      <h3>${esc(j.nomi)}</h3>
      <p class="nashriyot">${esc(j.nashriyot)} · ${esc(j.davlat)}</p>
      <div class="tags">
        <span class="tag">${esc(j.soha)}</span>
        <span class="tag">${esc(j.til)} tili</span>
        <span class="tag kvartil">${esc(j.kvartil)}</span>
      </div>
      <p class="card-tavsif">${esc(j.tavsif.slice(0, 110))}...</p>
      <button class="btn-detail" data-id="${j.id}">Batafsil ko'rish</button>
    </div>`
    )
    .join("");

  royxat.querySelectorAll(".btn-detail").forEach((btn) => {
    btn.addEventListener("click", () => ochModal(Number(btn.dataset.id)));
  });
}

// ---------- Modal ----------
function initModal() {
  document.getElementById("modal-close").addEventListener("click", yopModal);
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") yopModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") yopModal();
  });
}

function ochModal(id) {
  const j = JOURNALS.find((x) => x.id === id);
  if (!j) return;
  document.getElementById("modal-content").innerHTML = `
    <h2>${esc(j.nomi)}</h2>
    <p class="nashriyot" style="color:var(--muted);margin-bottom:14px;">
      ${esc(j.nashriyot)}
    </p>
    <div class="detail-row"><span class="label">Soha</span><span>${esc(j.soha)}</span></div>
    <div class="detail-row"><span class="label">Til</span><span>${esc(j.til)}</span></div>
    <div class="detail-row"><span class="label">Davlat</span><span>${esc(j.davlat)}</span></div>
    <div class="detail-row"><span class="label">ISSN</span><span>${esc(j.issn)}</span></div>
    <div class="detail-row"><span class="label">Indekslanish</span><span>${j.indeks.map(esc).join(", ")}</span></div>
    <div class="detail-row"><span class="label">Kvartil</span><span>${esc(j.kvartil)}</span></div>
    <div class="detail-row"><span class="label">Davriylik</span><span>${esc(j.davriylik)}</span></div>
    <div class="modal-section">
      <h4>Tavsif</h4>
      <p>${esc(j.tavsif)}</p>
    </div>
    <div class="modal-section">
      <h4>Maqola talablari</h4>
      <p>${esc(j.talablar)}</p>
    </div>
    <a class="web-link" href="${esc(j.web)}" target="_blank" rel="noopener">
      Jurnal saytiga o'tish ↗
    </a>`;
  document.getElementById("modal").hidden = false;
}

function yopModal() {
  document.getElementById("modal").hidden = true;
}

// ---------- Shablon yuklash ----------
function initShablon() {
  document.getElementById("shablon-yuklash").addEventListener("click", () => {
    const shablon = `MAQOLA SHABLONI (Xalqaro jurnallar uchun)
============================================

SARLAVHA (Title):
[Maqola nomini kiriting]

MUALLIF(LAR):
[F.I.Sh.], [Tashkilot], [ORCID], [Email]

ANNOTATSIYA (Abstract) — 150-250 so'z:
[Tadqiqot maqsadi, usuli, asosiy natijalari va xulosasi]

KALIT SO'ZLAR (Keywords):
[5-7 ta atama, vergul bilan]

1. KIRISH (Introduction)
[Muammoning dolzarbligi, maqsad va vazifalar]

2. MATERIALLAR VA USULLAR (Methods)
[Tadqiqot metodologiyasi]

3. NATIJALAR (Results)
[Olingan ma'lumotlar, jadval va grafiklar]

4. MUHOKAMA (Discussion)
[Natijalar talqini, taqqoslash]

5. XULOSA (Conclusion)
[Asosiy topilmalar va kelajak istiqbollari]

ADABIYOTLAR (References):
[1] ...
[2] ...

--------------------------------------------
Texnik talablar:
- Times New Roman, 12 pt, qator oralig'i 1.5
- Original (plagiat) darajasi: kamida 75-85%
- Format: .docx yoki LaTeX
`;
    const blob = new Blob([shablon], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "maqola-shabloni.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  });
}

// ---------- Forma ----------
function initForm() {
  const form = document.getElementById("maqola-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const ariza = {
      muallif: data.muallif,
      email: data.email,
      tashkilot: data.tashkilot || "—",
      jurnal: data.jurnal,
      sarlavha: data.sarlavha,
      kalit: data.kalit || "—",
      annotatsiya: data.annotatsiya,
      sana: new Date().toLocaleString("uz-UZ"),
    };

    const arizalar = oqArizalar();
    arizalar.unshift(ariza);
    saqlaArizalar(arizalar);

    const xabar = document.getElementById("yuborilgan-xabar");
    xabar.innerHTML = `✅ <b>Rahmat, ${esc(ariza.muallif)}!</b> Maqolangiz
      "<b>${esc(ariza.jurnal)}</b>" jurnaliga muvaffaqiyatli qabul qilindi.
      Tahririyat siz bilan <b>${esc(ariza.email)}</b> orqali bog'lanadi.`;
    xabar.hidden = false;
    form.reset();
    renderArizalar();
    xabar.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  document.getElementById("tozalash").addEventListener("click", () => {
    if (confirm("Barcha arizalarni o'chirishni tasdiqlaysizmi?")) {
      localStorage.removeItem(STORAGE_KEY);
      renderArizalar();
    }
  });
}

function renderArizalar() {
  const arizalar = oqArizalar();
  const blok = document.getElementById("arizalar-bloki");
  const royxat = document.getElementById("arizalar-royxati");

  if (arizalar.length === 0) {
    blok.hidden = true;
    return;
  }
  blok.hidden = false;
  royxat.innerHTML = arizalar
    .map(
      (a) => `
    <div class="ariza-item">
      <b>${esc(a.sarlavha)}</b> — ${esc(a.jurnal)}<br />
      Muallif: ${esc(a.muallif)} · ${esc(a.email)}<br />
      <small style="color:var(--muted);">${esc(a.sana)}</small>
    </div>`
    )
    .join("");
}

// ---------- Yordamchi funksiyalar ----------
function oqArizalar() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saqlaArizalar(arr) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
