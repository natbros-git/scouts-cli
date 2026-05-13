/**
 * Troop 0501 Bulk Advancement — Chrome Extension (3-column UI)
 * READ-ONLY: displays status only, does not write to Scoutbook.
 */

const ORG_GUID = null; // Auto-detected from context or set manually below
// const ORG_GUID = "76747DDD-F9CC-4A43-9253-83DA441C0504"; // Troop 0501
const API_BASE = "https://api.scouting.org";
const WEB_BASE = "https://advancements.scouting.org";

const BSA_RANK_NAMES = new Set([
  "Scout", "Tenderfoot", "Second Class", "First Class",
  "Star Scout", "Life Scout", "Eagle Scout"
]);

// State
let token = null;
let orgGuid = ORG_GUID;
let roster = [];
let selectedScoutIds = new Set();
let selectedRank = null;
let requirements = [];
let selectedReqIds = new Set();
let scoutStatuses = {};

// ── Token ─────────────────────────────────────────────────────

async function getToken() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({url: "https://advancements.scouting.org/*"}, (tabs) => {
      if (tabs.length === 0) {
        reject(new Error("Open advancements.scouting.org and sign in first."));
        return;
      }
      chrome.scripting.executeScript({
        target: {tabId: tabs[0].id},
        func: () => {
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            const val = localStorage.getItem(key);
            if (val && val.startsWith("eyJ") && val.length > 100) return val;
            try {
              const parsed = JSON.parse(val);
              if (parsed && typeof parsed === "object") {
                for (const v of Object.values(parsed)) {
                  if (typeof v === "string" && v.startsWith("eyJ") && v.length > 100) return v;
                  if (typeof v === "object" && v) {
                    for (const vv of Object.values(v)) {
                      if (typeof vv === "string" && vv.startsWith("eyJ") && vv.length > 100) return vv;
                    }
                  }
                }
              }
            } catch(e) {}
          }
          return null;
        }
      }, (results) => {
        if (chrome.runtime.lastError) {
          reject(new Error("Cannot access Scoutbook tab: " + chrome.runtime.lastError.message));
          return;
        }
        const t = results && results[0] && results[0].result;
        if (t) resolve(t);
        else reject(new Error("No token found. Paste it manually below."));
      });
    });
  });
}

// ── API ───────────────────────────────────────────────────────

async function apiGet(path, params = {}) {
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const resp = await fetch(url.toString(), {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/json",
      "x-esb-url": btoa(WEB_BASE + "/"),
    }
  });
  if (!resp.ok) throw new Error(`API ${resp.status}: ${resp.statusText}`);
  return resp.json();
}

// ── Data ──────────────────────────────────────────────────────

function getBsaRank(user) {
  for (const entry of (user.highestRanksApproved || [])) {
    if (entry.programId === 2 || entry.program === "Scouts BSA") return entry.rank;
  }
  const awarded = (user.highestRanksAwarded || []).filter(e => e.programId === 2 || e.program === "Scouts BSA");
  if (awarded.length) {
    awarded.sort((a, b) => (b.level || 0) - (a.level || 0));
    return awarded[0].rank;
  }
  const last = user.lastRankApproved || {};
  if (BSA_RANK_NAMES.has(last.rank)) return last.rank;
  return "Unranked";
}

async function loadRoster() {
  // Auto-detect org if not set
  if (!orgGuid) {
    const uid = getUidFromToken();
    if (!uid) throw new Error("Cannot read userId from token.");
    const profile = await apiGet(`/advancements/v2/${uid}/userActivitySummary`).catch(() => null);
    // Get person profile to find orgs
    const person = await apiGet(`/organizations/v2/person/${uid}/units`).catch(() => null);
    if (person && Array.isArray(person)) {
      // Prefer Troop
      const troop = person.find(o => o.unitType === "Troop");
      orgGuid = troop ? troop.organizationGuid : (person[0] && person[0].organizationGuid);
    }
    if (!orgGuid) throw new Error("Could not detect org. Set ORG_GUID in popup.js.");
  }
  const data = await apiGet(`/organizations/v2/units/${orgGuid}/youths`);
  roster = (data.users || [])
    .filter(u => u.userId)
    .map(u => ({
      userId: u.userId,
      memberId: u.memberId,
      fullName: u.personFullName,
      lastName: u.lastName || "",
      rank: getBsaRank(u),
    }))
    .sort((a, b) => a.lastName.localeCompare(b.lastName));
}

function getUidFromToken() {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.uid;
  } catch(e) { return null; }
}

async function loadRequirements(rankId, versionId) {
  const data = await apiGet(`/advancements/ranks/${rankId}/requirements`, { versionId });
  requirements = (data.requirements || [])
    .filter(r => r.requirementNumber)
    .sort((a, b) => (a.sortOrder || "").localeCompare(b.sortOrder || "", undefined, {numeric: true}));
}

async function loadStatuses(rankId, memberIds) {
  const data = await apiGet(
    `/advancements/v2/organization/${orgGuid}/ranks/${rankId}/userRequirements`,
    { memberId: memberIds.join(",") }
  );
  scoutStatuses = {};
  for (const entry of (Array.isArray(data) ? data : [])) {
    const reqMap = {};
    for (const req of (entry.requirements || [])) reqMap[req.id] = req;
    scoutStatuses[entry.memberId] = { rankStatus: entry.status, requirements: reqMap };
  }
}


// ── UI Helpers ────────────────────────────────────────────────

function showError(msg) {
  const box = document.getElementById("error-box");
  box.textContent = msg;
  box.style.display = "block";
  document.getElementById("token-fallback").style.display = "block";
}

function clearError() {
  document.getElementById("error-box").style.display = "none";
}

function showLoading(show) {
  document.getElementById("loading-overlay").classList.toggle("hidden", !show);
}

function updateFooter() {
  const s = selectedScoutIds.size;
  const r = selectedReqIds.size;
  document.getElementById("footer-info").innerHTML =
    `<strong>${s} scout${s !== 1 ? 's' : ''}</strong> · <strong>${r} requirement${r !== 1 ? 's' : ''}</strong> · Date: <strong>today</strong>`;
  document.getElementById("btn-apply").disabled = (s === 0 || r === 0);
}

// ── Render Scouts ─────────────────────────────────────────────

function renderScouts(filter = "") {
  const list = document.getElementById("scout-list");
  const fl = filter.toLowerCase();
  const filtered = fl ? roster.filter(s => s.fullName.toLowerCase().includes(fl)) : roster;

  list.innerHTML = filtered.map(s => {
    const checked = selectedScoutIds.has(s.memberId) ? "checked" : "";
    const sel = checked ? "selected" : "";
    return `<label class="list-item ${sel}">
      <input type="checkbox" data-mid="${s.memberId}" ${checked}>
      <span class="scout-name">${s.fullName}</span>
      <span class="scout-rank">${s.rank}</span>
    </label>`;
  }).join("");

  document.getElementById("scout-count").textContent =
    `${filtered.length} shown, ${selectedScoutIds.size} selected`;
}

// ── Render Requirements ───────────────────────────────────────

function renderRequirements() {
  const list = document.getElementById("req-list");
  if (requirements.length === 0) {
    list.innerHTML = `<div style="padding:20px;text-align:center;color:#999;font-size:11px;">Select a rank to load requirements</div>`;
    return;
  }

  list.innerHTML = requirements.map(r => {
    const checked = selectedReqIds.has(r.id) ? "checked" : "";
    const sel = checked ? "selected" : "";

    // Status indicator across selected scouts
    let indicator = "";
    if (selectedScoutIds.size > 0 && Object.keys(scoutStatuses).length > 0) {
      const statuses = [...selectedScoutIds].map(mid => {
        const st = scoutStatuses[mid];
        if (!st) return "none";
        const rd = st.requirements[parseInt(r.id)];
        if (rd && (rd.status === "Leader Approved" || rd.status === "Completed")) return "done";
        if (rd && rd.dateCompleted) return "pending";
        return "none";
      });
      if (statuses.every(s => s === "done")) indicator = `<span class="req-status status-done">✓</span>`;
      else if (statuses.some(s => s !== "none")) indicator = `<span class="req-status status-pending">●</span>`;
      else indicator = `<span class="req-status status-none">—</span>`;
    }

    const name = r.short || (r.name || "").substring(0, 55);
    return `<label class="req-item ${sel}">
      <input type="checkbox" data-rid="${r.id}" ${checked}>
      <span class="req-number">${r.requirementNumber}</span>
      <span class="req-name">${name}</span>
      ${indicator}
    </label>`;
  }).join("");

  document.getElementById("req-count").textContent =
    `${requirements.length} total, ${selectedReqIds.size} selected`;
}

// ── Event Wiring ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  // Manual token fallback
  document.getElementById("btn-use-token").addEventListener("click", async () => {
    const t = document.getElementById("manual-token").value.trim();
    if (t && t.startsWith("eyJ")) {
      token = t;
      clearError();
      document.getElementById("token-fallback").style.display = "none";
      try {
        showLoading(true);
        await loadRoster();
        renderScouts();
      } catch (e) { showError(e.message); }
      finally { showLoading(false); }
    }
  });

  // Auto-load token and roster
  try {
    clearError();
    showLoading(true);
    token = await getToken();
    await loadRoster();
    renderScouts();
  } catch (e) { showError(e.message); }
  finally { showLoading(false); }

  // Scout search
  document.getElementById("scout-search").addEventListener("input", (e) => {
    renderScouts(e.target.value);
  });

  // Scout selection
  document.getElementById("scout-list").addEventListener("change", (e) => {
    if (e.target.type === "checkbox") {
      const mid = parseInt(e.target.dataset.mid);
      if (e.target.checked) selectedScoutIds.add(mid);
      else selectedScoutIds.delete(mid);
      e.target.closest(".list-item").classList.toggle("selected", e.target.checked);
      updateFooter();
      // Re-render requirements to update status indicators
      if (requirements.length > 0 && selectedRank) renderRequirements();
    }
  });

  // Select all scouts
  document.getElementById("btn-select-all-scouts").addEventListener("click", () => {
    const filter = document.getElementById("scout-search").value.toLowerCase();
    const filtered = filter ? roster.filter(s => s.fullName.toLowerCase().includes(filter)) : roster;
    const allSelected = filtered.every(s => selectedScoutIds.has(s.memberId));
    filtered.forEach(s => {
      if (allSelected) selectedScoutIds.delete(s.memberId);
      else selectedScoutIds.add(s.memberId);
    });
    renderScouts(filter);
    updateFooter();
  });

  // Rank selection
  document.getElementById("rank-list").addEventListener("click", async (e) => {
    const el = e.target.closest(".rank-option");
    if (!el) return;
    document.querySelectorAll(".rank-option").forEach(r => r.classList.remove("selected"));
    el.classList.add("selected");

    const [id, ver] = el.dataset.rank.split("|");
    selectedRank = { id: parseInt(id), versionId: parseInt(ver) };
    selectedReqIds.clear();

    try {
      showLoading(true);
      await loadRequirements(selectedRank.id, selectedRank.versionId);
      // Load statuses if scouts are selected
      if (selectedScoutIds.size > 0) {
        await loadStatuses(selectedRank.id, [...selectedScoutIds]);
      }
      renderRequirements();
      updateFooter();
    } catch (e) { showError(e.message); }
    finally { showLoading(false); }
  });

  // Requirement selection
  document.getElementById("req-list").addEventListener("change", (e) => {
    if (e.target.type === "checkbox") {
      const rid = e.target.dataset.rid;
      if (e.target.checked) selectedReqIds.add(rid);
      else selectedReqIds.delete(rid);
      e.target.closest(".req-item").classList.toggle("selected", e.target.checked);
      updateFooter();
    }
  });

  // Select all requirements
  document.getElementById("btn-select-all-reqs").addEventListener("click", () => {
    const allSelected = selectedReqIds.size === requirements.length;
    if (allSelected) selectedReqIds.clear();
    else requirements.forEach(r => selectedReqIds.add(r.id));
    renderRequirements();
    updateFooter();
  });

  // Preview button (shows status in an alert for now)
  document.getElementById("btn-apply").addEventListener("click", () => {
    const scouts = roster.filter(s => selectedScoutIds.has(s.memberId));
    const reqs = requirements.filter(r => selectedReqIds.has(r.id));
    let msg = `PREVIEW (Read-Only)\n\nScouts (${scouts.length}):\n`;
    scouts.forEach(s => { msg += `  • ${s.fullName}\n`; });
    msg += `\nRequirements (${reqs.length}):\n`;
    reqs.forEach(r => { msg += `  • [${r.requirementNumber}] ${r.short || r.name.substring(0,40)}\n`; });
    msg += `\n— No changes made —`;
    alert(msg);
  });
});
