(function () {
  'use strict';
  const D = DATA, $ = id => document.getElementById(id);
  const SVG = 'http://www.w3.org/2000/svg';
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const k in (attrs || {})) {
      if (k === 'class') el.className = attrs[k];
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== false && attrs[k] != null) el.setAttribute(k, attrs[k]);
    }
    for (const kid of kids.flat()) if (kid != null) el.append(kid);
    return el;
  }
  function s(tag, attrs, text) {
    const el = document.createElementNS(SVG, tag);
    for (const k in (attrs || {})) el.setAttribute(k, attrs[k]);
    if (text != null) el.textContent = text;
    return el;
  }
  const tip = $('tip');
  function hover(el, text) {
    el.addEventListener('mousemove', e => {
      tip.textContent = typeof text === 'function' ? text() : text;
      tip.style.display = 'block';
      const w = tip.offsetWidth, x = Math.min(e.clientX + 14, window.innerWidth - w - 8);
      tip.style.left = Math.max(8, x) + 'px'; tip.style.top = (e.clientY + 16) + 'px';
    });
    el.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  }
  const label = (list, id) => (list.find(x => x.id === id) || { label: id }).label;
  const cap = t => t ? t[0].toUpperCase() + t.slice(1) : t;
  const SCOPES = [['core', 'Core: persistent after psychotropics', '--s1'], ['related', 'Related: sister syndromes and persistent non-sexual symptoms', '--s2'], ['adjacent', 'Adjacent: on-treatment dysfunction', '--s3']];
  const human = new Set(D.humanPrimary);
  const fmt = n => n == null ? '' : n.toLocaleString('en-US');
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDate(d) {
    if (!d) return '';
    const [y, m, day] = d.split('-');
    return (day ? +day + ' ' : '') + (m ? MONTHS[+m - 1] + ' ' : '') + y;
  }
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

  // ---- partition state: every section reads its records through these ----
  const PARTS = D.partitions.length ? D.partitions : [{ id: 'all', label: 'All', description: '', drugs: [], everything: true }];
  let PART = PARTS.find(p => p.id === store.get('pssd-part')) || PARTS[0];
  const inPart = r => PART.everything || (r.partitions || []).includes(PART.id);
  const papers = () => D.papers.filter(inPart);
  const trials = () => D.trials.filter(inPart);
  const posts = () => D.community.filter(p => p.source !== 'blog' && inPart(p));
  const articles = () => D.community.filter(p => p.source === 'blog' && inPart(p));
  const faersRows = () => D.faers.rows.filter(r => PART.everything || r.control || PART.drugs.includes(r.drug));

  // ---- theme toggle -----------------------------------------------------
  (function () {
    const root = document.documentElement, btn = $('theme'), mq = window.matchMedia('(prefers-color-scheme: dark)');
    const isDark = () => root.getAttribute('data-theme') ? root.getAttribute('data-theme') === 'dark' : mq.matches;
    const paint = () => { btn.textContent = isDark() ? '☀ Light mode' : '☾ Dark mode'; };
    btn.addEventListener('click', () => { const next = isDark() ? 'light' : 'dark'; root.setAttribute('data-theme', next); store.set('pssd-theme', next); paint(); });
    mq.addEventListener('change', paint); paint();
  })();

  // ---- live update (needs `pssd-atlas serve`) ---------------------------
  (function () {
    const btn = $('update'), box = $('upBox'), HDR = { 'X-PSSD-Atlas': '1', 'Content-Type': 'application/json' };
    const served = location.protocol === 'http:' || location.protocol === 'https:';
    const show = (...kids) => { box.style.display = 'block'; box.replaceChildren(...kids); };
    async function status() { const r = await fetch('api/status', { cache: 'no-store' }); if (!r.ok) throw new Error(r.status); return r.json(); }
    async function watch() {
      btn.disabled = true; btn.textContent = 'Updating…';
      const pre = h('pre'); show(h('b', null, 'Fetching the latest papers, trials and patient reports…'), pre);
      for (;;) {
        await new Promise(r => setTimeout(r, 1200));
        let st; try { st = await status(); } catch (e) { continue; }
        pre.textContent = st.log.join('\n'); pre.scrollTop = pre.scrollHeight;
        if (!st.running) {
          if (st.error) { show(h('b', null, st.error), pre, h('p', null, h('button', { onclick: () => location.reload() }, 'Reload page'))); btn.disabled = false; btn.textContent = 'Update data'; }
          else location.reload();
          return;
        }
      }
    }
    function offline() {
      show(h('b', null, 'Live updating needs the local server.'), h('p', null, 'This page is a saved snapshot, so it cannot fetch new data by itself. In the project folder run ', h('code', null, 'python -m pssd_atlas serve'), ' and open ', h('code', null, 'http://127.0.0.1:8765'), ' — the button then refreshes everything in place.'));
    }
    function ask() {
      const cb = h('input', { type: 'checkbox', id: 'upFaers' });
      show(h('p', null, 'Fetch the latest papers, preprints, trials and patient reports now (about a minute).'),
        h('p', null, h('label', null, cb, ' Also refresh FDA adverse-event data (about 5 minutes; it only changes quarterly)')),
        h('button', { class: 'primary', onclick: async () => {
          const r = await fetch('api/update', { method: 'POST', headers: HDR, body: JSON.stringify({ faers: cb.checked }) });
          if (r.status === 202 || r.status === 409) watch(); else offline();
        } }, 'Start update'), ' ', h('button', { onclick: () => { box.style.display = 'none'; } }, 'Cancel'));
    }
    btn.addEventListener('click', async () => {
      if (!served) return offline();
      try { const st = await status(); st.running ? watch() : ask(); } catch (e) { offline(); }
    });
    if (served) status().then(st => { if (st.running) watch(); }).catch(() => {});
  })();

  // ---- header ----------------------------------------------------------
  const src = (D.meta.sources || {});
  const stale = Object.keys(src).filter(k => src[k].ok === false);
  $('stamp').textContent = 'Data snapshot: ' + (D.meta.generated || 'not yet fetched') +
    (stale.length ? ' (could not refresh: ' + stale.join(', ') + '; showing the previous snapshot for those)' : '');

  function drawTiles() {
    const P = papers(), comp = faersRows().filter(r => r.composite && !r.control);
    const tiles = [
      [P.filter(p => p.scope === 'core').length, 'papers on persistent dysfunction'],
      [P.length, 'papers and preprints in total'],
      [P.filter(p => p.scope === 'core' && human.has(p.study_type)).length, 'persistent-dysfunction papers with original human data'],
      [trials().length, 'registered clinical studies'],
      [comp.filter(r => r.signal).length + ' / ' + comp.length, 'drugs with a sexual-dysfunction reporting signal'],
      [posts().length + articles().length, 'patient posts and blog articles'],
    ];
    $('tiles').replaceChildren(...tiles.map(([n, l]) => h('div', { class: 'tile' }, h('b', null, typeof n === 'number' ? fmt(n) : n), h('span', null, l))));
  }

  // ---- timeline --------------------------------------------------------
  function drawTimeline() {
    const box = $('yearChart'), P = papers(); box.replaceChildren();
    const years = P.map(p => p.year).filter(Boolean);
    if (!years.length) { box.textContent = 'No papers in this view.'; return; }
    const allYears = D.papers.map(p => p.year).filter(Boolean);
    const y1 = Math.max(...allYears), y0 = Math.max(Math.min(...allYears), y1 - 34), clipped = y0 > Math.min(...allYears);
    const counts = {};
    for (const p of P) { if (!p.year) continue; const y = Math.max(p.year, y0); (counts[y] = counts[y] || { core: 0, related: 0, adjacent: 0 })[p.scope]++; }
    const n = y1 - y0 + 1, W = 1000, H = 250, L = 34, B = 24, T = 8, pw = (W - L - 6) / n;
    const max = Math.max(...Object.values(counts).map(c => c.core + c.related + c.adjacent));
    const step = max > 80 ? 20 : max > 40 ? 10 : max > 16 ? 5 : max > 6 ? 2 : 1;
    const top = Math.ceil(max / step) * step, yScale = v => H - B - v / top * (H - B - T);
    const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': 'Stacked bar chart of publications per year by scope' });
    for (let v = 0; v <= top; v += step) {
      svg.append(s('line', { x1: L, x2: W, y1: yScale(v), y2: yScale(v), stroke: 'var(--grid)' }));
      svg.append(s('text', { x: L - 6, y: yScale(v) + 4, 'text-anchor': 'end' }, v));
    }
    for (let i = 0; i < n; i++) {
      const y = y0 + i, c = counts[y] || { core: 0, related: 0, adjacent: 0 }, x = L + i * pw + pw * 0.14, bw = pw * 0.72;
      let acc = 0;
      for (const [k, , col] of SCOPES) {
        if (!c[k]) continue;
        const yTop = yScale(acc + c[k]), hgt = yScale(acc) - yTop;
        svg.append(s('rect', { x, y: yTop, width: bw, height: Math.max(1, hgt - 2), rx: 2, fill: `var(${col})` }));
        acc += c[k];
      }
      if (y % 5 === 0 || i === 0) svg.append(s('text', { x: x + bw / 2, y: H - 7, 'text-anchor': 'middle' }, (i === 0 && clipped ? '≤' : '') + y));
      const hit = s('rect', { x: L + i * pw, y: T, width: pw, height: H - B - T, fill: 'transparent' });
      hover(hit, `${y}${i === 0 && clipped ? ' and earlier' : ''}\nCore: ${c.core}\nRelated: ${c.related}\nAdjacent: ${c.adjacent}`);
      svg.append(hit);
    }
    box.append(svg);
  }
  $('yearLegend').append(...SCOPES.map(([, l, col]) => h('span', null, h('i', { style: `background:var(${col})` }), l)));

  // ---- paper explorer --------------------------------------------------
  const F = { q: $('q'), scope: $('fScope'), type: $('fType'), hyp: $('fHyp'), tx: $('fTx'), drug: $('fDrug'), sym: $('fSym') };
  function fill(sel, first, opts) { sel.append(h('option', { value: '' }, first), ...opts.map(([v, l]) => h('option', { value: v }, l))); }
  fill(F.scope, 'All scopes', SCOPES.map(([k]) => [k, cap(k)]));
  fill(F.type, 'All study designs', D.studyTypes.map(t => [t.id, t.label]).concat([['__human', 'Any original human data']]));
  fill(F.hyp, 'All hypotheses and themes', D.hypotheses.map(x => [x.id, x.label]));
  fill(F.tx, 'All treatments', D.interventions.map(x => [x.id, x.label]));
  fill(F.drug, 'All drugs mentioned', [...new Set(D.papers.flatMap(p => p.drugs))].sort().map(d => [d, cap(d)]));
  fill(F.sym, 'All symptoms', D.symptoms.map(x => [x.id, x.label]));
  let scopeOverride = null, shown = 40, current = [];
  function matches(p) {
    if (scopeOverride ? !scopeOverride.includes(p.scope) : (F.scope.value && p.scope !== F.scope.value)) return false;
    if (F.type.value === '__human' ? !human.has(p.study_type) : (F.type.value && p.study_type !== F.type.value)) return false;
    if (F.hyp.value && !p.hypotheses.includes(F.hyp.value)) return false;
    if (F.tx.value && !p.interventions.includes(F.tx.value)) return false;
    if (F.drug.value && !p.drugs.includes(F.drug.value)) return false;
    if (F.sym.value && !(p.symptoms || []).includes(F.sym.value)) return false;
    const q = F.q.value.trim().toLowerCase();
    if (q) { const hay = (p.title + ' ' + p.abstract + ' ' + p.authors.join(' ')).toLowerCase(); if (!q.split(/\s+/).every(w => hay.includes(w))) return false; }
    return true;
  }
  function paperEl(p) {
    const au = p.authors.length > 4 ? p.authors.slice(0, 3).join(', ') + ' et al.' : p.authors.join(', ');
    return h('div', { class: 'paper' },
      h('div', { class: 't' }, h('a', { href: p.url, target: '_blank', rel: 'noopener' }, p.title || '(untitled)')),
      h('div', { class: 'small' }, [au, p.journal, fmtDate(p.date) || p.year].filter(Boolean).join(' · ')),
      h('div', null, h('span', { class: 'pill ' + p.scope }, p.scope), h('span', { class: 'pill' }, label(D.studyTypes, p.study_type)),
        p.source === 'preprint' ? h('span', { class: 'pill' }, 'preprint, not peer reviewed') : null,
        p.hypotheses.map(x => h('span', { class: 'pill' }, label(D.hypotheses, x))),
        p.interventions.map(x => h('span', { class: 'pill' }, label(D.interventions, x)))),
      p.abstract ? h('details', null, h('summary', null, 'Abstract'), h('p', null, p.abstract)) : null);
  }
  function render() {
    const dir = $('fSort').value === 'old' ? 1 : -1, P = papers();
    // Undated records always go last; partial dates ("2019", "2019-03") sort within their year or month.
    current = P.filter(matches).sort((a, b) => !a.date !== !b.date ? (a.date ? -1 : 1) : dir * (a.date || '').localeCompare(b.date || ''));
    $('count').textContent = `${fmt(current.length)} of ${fmt(P.length)} records` + (scopeOverride ? ` (scope: ${scopeOverride.join(' + ')})` : '');
    $('list').replaceChildren(...current.slice(0, shown).map(paperEl));
    $('more').style.display = current.length > shown ? '' : 'none';
  }
  function setFilters(v) {
    scopeOverride = v.scopes || null;
    F.scope.value = v.scope || ''; F.type.value = v.type || ''; F.hyp.value = v.hyp || ''; F.tx.value = v.tx || ''; F.drug.value = v.drug || ''; F.sym.value = v.sym || ''; F.q.value = '';
    shown = 40; render(); $('explore').scrollIntoView({ behavior: 'smooth' });
  }
  for (const k in F) F[k].addEventListener('input', () => { if (k === 'scope') scopeOverride = null; shown = 40; render(); });
  $('fSort').addEventListener('input', () => { shown = 40; render(); });
  $('more').addEventListener('click', () => { shown += 60; render(); });
  $('reset').addEventListener('click', () => { for (const k in F) F[k].value = ''; scopeOverride = null; shown = 40; render(); });
  $('csv').addEventListener('click', () => {
    const cols = ['id', 'scope', 'date', 'year', 'study_type', 'title', 'journal', 'authors', 'doi', 'url', 'hypotheses', 'interventions', 'drugs'];
    const esc = v => '"' + String(Array.isArray(v) ? v.join('; ') : v == null ? '' : v).replace(/"/g, '""') + '"';
    const csv = [cols.join(',')].concat(current.map(p => cols.map(c => esc(p[c])).join(','))).join('\n');
    const a = h('a', { href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })), download: 'pssd-atlas-papers.csv' });
    document.body.append(a); a.click(); a.remove();
  });

  // ---- evidence matrix -------------------------------------------------
  function drawMatrix() {
    const scopes = $('mxScope').value.split(','), P = papers().filter(p => scopes.includes(p.scope));
    const types = D.studyTypes.filter(t => t.id !== 'other');
    const grid = D.hypotheses.map(x => ({ x, row: types.map(t => P.filter(p => p.hypotheses.includes(x.id) && p.study_type === t.id).length) }));
    const max = Math.max(1, ...grid.flatMap(g => g.row));
    const tbl = $('mx'); tbl.replaceChildren();
    tbl.append(h('tr', null, h('th', null, ''), types.map(t => h('th', { class: 'col' }, t.label)), h('th', { class: 'col' }, 'All')));
    for (const kind of ['mechanism', 'theme']) {
      tbl.append(h('tr', { class: 'grp' }, h('td', { colspan: types.length + 2 }, kind === 'mechanism' ? 'Proposed mechanisms' : 'Research themes')));
      for (const g of grid.filter(g => g.x.kind === kind)) {
        const total = P.filter(p => p.hypotheses.includes(g.x.id)).length;
        const name = h('td', null, g.x.label); hover(name, g.x.description);
        tbl.append(h('tr', null, name, g.row.map((v, i) => {
          if (!v) return h('td', { class: 'cell zero' }, '·');
          const td = h('td', { class: 'cell', tabindex: 0, role: 'button', style: `background:rgba(var(--seq),${(0.1 + 0.55 * Math.sqrt(v / max)).toFixed(2)})`,
            'aria-label': `${v} papers: ${g.x.label}, ${types[i].label}` }, v);
          const go = () => setFilters({ scopes, hyp: g.x.id, type: types[i].id });
          td.addEventListener('click', go); td.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
          hover(td, `${g.x.label}\n${types[i].label}: ${v} paper${v > 1 ? 's' : ''}`);
          return td;
        }), h('td', { class: 'num' }, total)));
      }
    }
  }
  $('mxScope').addEventListener('input', drawMatrix);

  // ---- gaps ------------------------------------------------------------
  function drawGaps() {
    const pool = papers().filter(p => p.scope !== 'adjacent');
    const rows = D.hypotheses.filter(x => x.kind === 'mechanism').map(x => {
      const ps = pool.filter(p => p.hypotheses.includes(x.id));
      const hum = ps.filter(p => human.has(p.study_type)).length, ctl = ps.filter(p => p.study_type === 'rct' || p.study_type === 'clinical_trial').length;
      const ani = ps.filter(p => p.study_type === 'animal').length, rev = ps.filter(p => ['review', 'systematic_review', 'commentary'].includes(p.study_type)).length;
      return { x, n: ps.length, hum, ctl, ani, rev, ratio: hum ? rev / hum : null };
    }).sort((a, b) => a.hum - b.hum || b.rev - a.rev);
    const t = $('gapTable'); t.replaceChildren();
    t.append(h('tr', null, ['Hypothesis', 'Papers', 'Original human data', 'of which trials', 'Animal studies', 'Reviews and commentary', 'Reviews per human study', 'Assessment'].map((c, i) => h('th', { class: i && i < 7 ? 'num' : '' }, c))));
    for (const r of rows) {
      const flag = r.n === 0 ? h('span', { class: 'flag' }, '⚠ Nothing published')
        : r.hum === 0 ? h('span', { class: 'flag' }, r.ani ? '⚠ Animal data only' : '⚠ No original data')
        : r.hum < 5 ? h('span', { class: 'flag' }, '⚠ Very little human data')
        : r.ratio > 2 ? h('span', { class: 'flag' }, '⚠ Mostly reviews') : h('span', { class: 'ok' }, '✓ Some human data');
      const a = h('a', { href: '#explore' }, r.x.label);
      a.addEventListener('click', e => { e.preventDefault(); setFilters({ scopes: ['core', 'related'], hyp: r.x.id }); });
      const name = h('td', null, a); hover(name, r.x.description);
      t.append(h('tr', null, name, h('td', { class: 'num' }, r.n), h('td', { class: 'num' }, r.hum), h('td', { class: 'num' }, r.ctl), h('td', { class: 'num' }, r.ani),
        h('td', { class: 'num' }, r.rev), h('td', { class: 'num' }, r.ratio == null ? '–' : r.ratio.toFixed(1)), h('td', null, flag)));
    }
  }

  // ---- symptoms studied ------------------------------------------------
  function drawSymptoms() {
    const P = papers(), t = $('symTable'); t.replaceChildren();
    t.append(h('tr', null, ['Symptom', 'Papers', 'on persistent dysfunction', 'with original human data', 'Randomised trials'].map((c, i) => h('th', { class: i ? 'num' : '' }, c))));
    const rows = D.symptoms.map(x => { const ps = P.filter(p => (p.symptoms || []).includes(x.id));
      return { x, n: ps.length, core: ps.filter(p => p.scope === 'core').length, hum: ps.filter(p => p.scope === 'core' && human.has(p.study_type)).length, rct: ps.filter(p => p.study_type === 'rct').length }; })
      .sort((a, b) => b.core - a.core || b.n - a.n);
    for (const r of rows) {
      const a = h('a', { href: '#explore' }, r.x.label);
      a.addEventListener('click', e => { e.preventDefault(); setFilters({ sym: r.x.id }); });
      t.append(h('tr', null, h('td', null, a), ...[r.n, r.core, r.hum, r.rct].map(v => h('td', { class: 'num' }, v))));
    }
  }

  // ---- treatments ------------------------------------------------------
  function drawTreatments() {
    const P = papers(), TR = trials();
    const rows = D.interventions.map(x => {
      const ps = P.filter(p => p.interventions.includes(x.id)), tr = TR.filter(t => t.intervention_tags.includes(x.id));
      return { x, n: ps.length, core: ps.filter(p => p.scope === 'core').length, hum: ps.filter(p => human.has(p.study_type)).length,
        rct: ps.filter(p => p.study_type === 'rct').length, tr: tr.length, active: tr.filter(t => /RECRUITING|ACTIVE|ENROLLING|NOT_YET/.test(t.status)).length };
    }).sort((a, b) => b.n - a.n);
    const t = $('txTable'); t.replaceChildren();
    t.append(h('tr', null, ['Candidate', 'Papers', 'in persistent-dysfunction papers', 'Human data', 'Randomised trials', 'Registered trials', 'Active or recruiting'].map((c, i) => h('th', { class: i ? 'num' : '' }, c))));
    for (const r of rows) {
      const a = h('a', { href: '#explore' }, r.x.label);
      a.addEventListener('click', e => { e.preventDefault(); setFilters({ tx: r.x.id }); });
      t.append(h('tr', null, h('td', null, a), ...[r.n, r.core, r.hum, r.rct, r.tr, r.active].map(v => h('td', { class: 'num' }, v))));
    }
  }

  // ---- trials ----------------------------------------------------------
  function drawTrials() {
    const sc = $('trScope').value, t = $('trTable'); t.replaceChildren();
    t.append(h('tr', null, ['Study', 'Scope', 'Status', 'Phase', 'N', 'Start', 'Interventions'].map(c => h('th', null, c))));
    const rows = trials().filter(x => !sc || x.scope === sc);
    for (const x of rows) {
      t.append(h('tr', null, h('td', null, h('a', { href: x.url, target: '_blank', rel: 'noopener' }, x.brief_title || x.id), h('div', { class: 'small' }, x.id + (x.has_results ? ' · results posted' : ''))),
        h('td', null, h('span', { class: 'pill ' + x.scope }, x.scope)), h('td', null, x.status.replace(/_/g, ' ').toLowerCase()),
        h('td', null, x.phases.join(', ').replace(/PHASE/g, '').replace(/NA/, 'n/a') || '–'), h('td', { class: 'num' }, x.enrollment == null ? '–' : x.enrollment),
        h('td', null, x.start || '–'), h('td', null, x.interventions.slice(0, 4).join('; ') || '–')));
    }
    if (!rows.length) t.append(h('tr', null, h('td', { colspan: 7 }, 'No registered studies in this view.')));
  }
  $('trScope').addEventListener('input', drawTrials);

  // ---- forest plot -----------------------------------------------------
  const fx = $('fxReaction');
  fx.append(...D.faers.reactions.map(r => h('option', { value: r }, cap(r.toLowerCase()))));
  function drawForest() {
    const rows = faersRows().filter(r => r.reaction === fx.value), box = $('forest'); box.replaceChildren();
    if (!rows.length) { box.textContent = 'No adverse-event data yet.'; return; }
    const W = 1000, L = 250, R = 190, rh = 22, T = 26, H = T + rows.length * rh + 10 + (new Set(rows.map(r => r.drug_class)).size) * 20;
    const vals = rows.flatMap(r => r.ror ? [r.ror_lo, r.ror_hi] : []);
    const lo = Math.min(0.2, ...vals) * 0.8, hi = Math.max(5, ...vals) * 1.2;
    const X = v => L + (Math.log(Math.min(hi, Math.max(lo, v))) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * (W - L - R);
    const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': 'Forest plot of reporting odds ratios by drug' });
    for (const tk of [0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000]) {
      if (tk < lo || tk > hi) continue;
      svg.append(s('line', { x1: X(tk), x2: X(tk), y1: T - 6, y2: H, stroke: tk === 1 ? 'var(--text-2)' : 'var(--grid)', 'stroke-width': tk === 1 ? 1.5 : 1 }));
      svg.append(s('text', { x: X(tk), y: 12, 'text-anchor': 'middle' }, tk));
    }
    svg.append(s('text', { x: W - R + 12, y: 12 }, 'ROR (95% CI) · reports'));
    let y = T, cls = null;
    for (const r of rows) {
      if (r.drug_class !== cls) { cls = r.drug_class; y += 20; svg.append(s('text', { x: 0, y: y - 6, style: 'font-weight:600' }, cls)); }
      const cy = y + rh / 2, col = r.control ? 'var(--muted-mark)' : 'var(--s1)';
      svg.append(s('text', { x: 14, y: cy + 4, class: 'lab' }, cap(r.drug)));
      if (r.ror) {
        svg.append(s('line', { x1: X(r.ror_lo), x2: X(r.ror_hi), y1: cy, y2: cy, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
        svg.append(s('circle', { cx: X(r.ror), cy, r: 5, fill: col, stroke: 'var(--surface)', 'stroke-width': 2 }));
        svg.append(s('text', { x: W - R + 12, y: cy + 4 }, `${r.ror.toFixed(2)} (${r.ror_lo.toFixed(2)}–${r.ror_hi.toFixed(2)}) · ${fmt(r.a)}`));
      } else svg.append(s('text', { x: W - R + 12, y: cy + 4 }, r.a ? 'not estimable' : 'no reports'));
      const hit = s('rect', { x: 0, y, width: W, height: rh, fill: 'transparent' });
      hover(hit, `${r.drug} · ${r.reaction.toLowerCase()}\n${fmt(r.a)} of ${fmt(r.drug_total)} reports for this drug\n` +
        (r.ror ? `ROR ${r.ror.toFixed(2)} (95% CI ${r.ror_lo.toFixed(2)}–${r.ror_hi.toFixed(2)})\nPRR ${r.prr.toFixed(2)}\n${r.signal ? 'Meets signal threshold' : 'Below signal threshold'}` : 'Too few reports to estimate'));
      svg.append(hit); y += rh;
    }
    box.append(svg);
  }
  fx.addEventListener('input', drawForest);

  // ---- background guide -----------------------------------------------
  function drawGuide() {
    const G = D.guide || {}, P = papers(), B = D.targets.binding || {};
    $('guideNote').textContent = G.note || '';
    const drugs = Object.keys(B).filter(d => PART.everything || PART.drugs.includes(d));
    const known = new Set((D.targets.targets || []).map(t => t.symbol));
    const open = new Set([...document.querySelectorAll('#briefs details[open]')].map(d => d.dataset.id));
    $('briefs').replaceChildren(...(G.brief || []).map(b => {
      const d = h('details', { open: open.has(b.id) ? '' : null }, h('summary', null, h('b', null, b.title)), h('p', null, b.summary),
        h('ul', null, (b.points || []).map(x => h('li', null, x))));
      d.dataset.id = b.id;
      if ((b.avenue || []).length) {
        const t = h('table', null, h('tr', null, ['Avenue', 'Rationale', 'Evidence'].map(c => h('th', null, c))),
          b.avenue.map(a => h('tr', null, h('td', null, a.name), h('td', null, a.rationale), h('td', null, a.evidence))));
        d.append(h('h3', null, 'Avenues and how strong the evidence is'), h('div', { class: 'scroll' }, t),
          h('p', { class: 'small' }, 'None has been shown to work for the persistent condition. These are prescription decisions for a clinician who knows the history.'));
      }
      if ((b.tests || []).length) d.append(h('h3', null, 'What can be measured'), h('ul', null, b.tests.map(x => h('li', null, x))));
      if ((b.symptoms || []).length) {
        d.append(h('h3', null, 'In the atlas (current view)'), h('p', null, b.symptoms.map(sid => {
          const ps = P.filter(p => (p.symptoms || []).includes(sid)), core = ps.filter(p => p.scope === 'core').length;
          const a = h('a', { href: '#explore', class: 'pill' }, `${label(D.symptoms, sid)}: ${ps.length} papers, ${core} on persistent dysfunction`);
          a.addEventListener('click', e => { e.preventDefault(); setFilters({ sym: sid }); });
          return a;
        })));
      }
      return d;
    }));
    const t = $('pathTable'); t.replaceChildren();
    t.append(h('tr', null, ['Stage', 'What happens', 'Key molecules', 'Targets', 'Implicated drugs binding strongly'].map(c => h('th', null, c))));
    let grp = null;
    for (const r of (G.pathway || [])) {
      if (r.group !== grp) { grp = r.group; t.append(h('tr', { class: 'grp' }, h('td', { colspan: 5, style: 'font-weight:600;color:var(--text-2);padding-top:14px' }, grp))); }
      const binders = [...new Set(drugs.filter(d => r.genes.some(g => B[d][g] && B[d][g].pki >= 7)))];
      t.append(h('tr', null, h('td', null, h('b', null, r.stage)), h('td', null, r.what), h('td', null, r.molecules),
        h('td', null, r.genes.map(g => known.has(g) ? h('a', { href: '#targets', class: 'pill' }, g) : h('span', { class: 'pill' }, g))),
        h('td', { class: 'small' }, !r.genes.length ? '–' : binders.length ? `${binders.length} of ${drugs.length}: ${binders.slice(0, 5).map(cap).join(', ')}${binders.length > 5 ? '…' : ''}` : 'none in available data')));
    }
  }

  // ---- drug targets ---------------------------------------------------
  function drawTargets() {
    const B = D.targets.binding || {}, cls = D.drugClasses || {};
    const drugs = Object.keys(B).filter(d => Object.keys(B[d]).length && (PART.everything || PART.drugs.includes(d)));
    const classOrder = [...new Set(Object.values(cls))];
    drugs.sort((a, b) => classOrder.indexOf(cls[a]) - classOrder.indexOf(cls[b]));   // keep each class together
    const strong = (d, g) => B[d][g] && B[d][g].pki >= 7;
    const tbl = $('bindTable'), sum = $('bindSummary'); tbl.replaceChildren(); sum.replaceChildren();
    if (!drugs.length) sum.textContent = 'No binding data yet.';
    else {
      const genes = [...new Set(drugs.flatMap(d => Object.keys(B[d])))]
        .map(g => ({ g, n: drugs.filter(d => strong(d, g)).length })).filter(x => x.n >= 2 || (drugs.length < 4 && x.n))
        .sort((a, b) => b.n - a.n || a.g.localeCompare(b.g)).slice(0, 22);
      const half = genes.filter(x => x.n >= drugs.length / 2).map(x => `${x.g} (${x.n} of ${drugs.length})`);
      sum.append(h('b', null, 'Bound strongly by at least half the drugs in this view: '), half.length ? half.join(', ') + '.' : 'no single protein.');
      if (PART.everything) {
        const grp = d => ['SSRI', 'SNRI'].includes(cls[d]) ? 'a' : (cls[d] === 'Antipsychotic' || d === 'mirtazapine') ? 'b' : null;
        const A = drugs.filter(d => grp(d) === 'a'), Bg = drugs.filter(d => grp(d) === 'b');
        const both = genes.filter(x => A.filter(d => strong(d, x.g)).length >= A.length / 2 && Bg.filter(d => strong(d, x.g)).length >= Bg.length / 2).map(x => x.g);
        sum.append(h('br'), h('b', null, 'Shared by most SSRIs/SNRIs and most antipsychotics plus mirtazapine: '), both.length ? both.join(', ') + '.' : 'no protein. The two groups have no common direct target in these data, so any shared mechanism would have to lie downstream.');
      }
      tbl.append(h('tr', null, h('th', null, ''), genes.map(x => h('th', { class: 'col' }, x.g))));
      let last = null;
      for (const d of drugs) {
        if (cls[d] !== last) { last = cls[d]; tbl.append(h('tr', { class: 'grp' }, h('td', { colspan: genes.length + 1 }, last))); }
        tbl.append(h('tr', null, h('td', null, cap(d)), genes.map(x => {
          const c = B[d][x.g];
          if (!c) return h('td', { class: 'cell zero' }, '·');
          const td = h('td', { class: 'cell', style: `cursor:default;background:rgba(var(--seq),${Math.max(0.06, Math.min(0.7, (c.pki - 5) / 5 * 0.7)).toFixed(2)})` }, c.pki.toFixed(1));
          const ki = Math.pow(10, 9 - c.pki);
          hover(td, `${cap(d)} · ${x.g}\nKi about ${ki >= 100 ? Math.round(ki) : ki.toPrecision(2)} nM (pKi ${c.pki})\n${c.n} measurement${c.n > 1 ? 's' : ''}`);
          return td;
        })));
      }
    }
    const pt = $('profTable'), PR = D.targets.profiles || {}; pt.replaceChildren();
    pt.append(h('tr', null, ['Drug', 'Class', 'Formula', 'Molecular weight', 'First approved', 'Strongest binding (pKi)'].map((c, i) => h('th', { class: i === 3 || i === 4 ? 'num' : '' }, c))));
    for (const d of drugs) {
      const p = PR[d] || {}, top = Object.entries(B[d]).sort((a, b) => b[1].pki - a[1].pki).slice(0, 6);
      pt.append(h('tr', null, h('td', null, p.url ? h('a', { href: p.url, target: '_blank', rel: 'noopener' }, cap(d)) : cap(d)), h('td', null, cls[d] || ''),
        h('td', null, p.formula || '–'), h('td', { class: 'num' }, p.weight ? (+p.weight).toFixed(1) : '–'), h('td', { class: 'num' }, p.approved || '–'),
        h('td', null, top.map(([g, c]) => h('span', { class: 'pill' }, `${g} ${c.pki.toFixed(1)}`)))));
    }
    const t = $('tgTable'); t.replaceChildren();
    const T = D.targets.targets || [];
    if (!T.length) { t.append(h('tr', null, h('td', null, 'No target data yet.'))); return; }
    const tpm = v => v == null ? '–' : v >= 10 ? Math.round(v) : v.toFixed(1);
    t.append(h('tr', null, ['Target', 'Hypothesis', 'Why it is a candidate', 'Marketed drugs acting on it', 'Implicated drugs binding it', 'Spinal cord', 'Hypothalamus', 'Skin'].map((c, i) => h('th', { class: i > 3 ? 'num' : '' }, c))));
    const order = D.hypotheses.map(x => x.id);
    for (const x of T.slice().sort((a, b) => order.indexOf(a.hypothesis) - order.indexOf(b.hypothesis))) {
      const e = x.expression_tpm, m = x.marketed_drugs, nb = drugs.filter(d => strong(d, x.symbol)).length;
      t.append(h('tr', null, h('td', null, h('a', { href: x.url, target: '_blank', rel: 'noopener' }, x.symbol), h('div', { class: 'small' }, x.name)),
        h('td', null, label(D.hypotheses, x.hypothesis)), h('td', { class: 'small' }, x.rationale),
        h('td', null, m.length ? `${m.length}: ${m.slice(0, 3).join(', ')}${m.length > 3 ? '…' : ''}` : h('span', { class: 'flag' }, 'None yet')),
        h('td', { class: 'num' }, nb || '–'), h('td', { class: 'num' }, tpm(e.spinal_cord)), h('td', { class: 'num' }, tpm(e.hypothalamus)), h('td', { class: 'num' }, tpm(e.skin))));
    }
  }

  // ---- patient reports -------------------------------------------------
  const TX = D.interventions.concat(D.communityInterventions || []);
  let ptShown = 25, ptTx = '', ptRec = false, blShown = 15, blSrc = '';
  function drawPatients() {
    const box = $('ptBody'), all = posts(); box.replaceChildren();
    if (!D.community.some(p => p.source !== 'blog')) {
      box.append(h('div', { class: 'note' }, 'No patient posts have been collected yet. Reddit collection is switched off because Reddit requires approval before any API access, and the two patient forums block automated access. Pages you saved yourself can be added with the import command. See the README.'));
      return drawArticles(box);
    }
    if (!all.length) { box.append(h('p', null, 'No collected patient posts mention the drugs in this view.')); return drawArticles(box); }
    const dates = all.map(p => p.date).filter(Boolean).sort();
    box.append(h('p', null, h('b', null, fmt(all.length)), ` posts, ${fmtDate(dates[0])} to ${fmtDate(dates[dates.length - 1])}. `,
      h('b', null, fmt(all.filter(p => p.recovery).length)), ' mention recovery or remission.'));
    box.append(h('div', { class: 'note' }, 'These are self-selected anecdotes read by keyword rules, not clinical data. People who are still unwell post more than people who recovered, a drug or treatment being named does not mean it was the cause or the cure, and the outcome columns are a rough reading of nearby words. Use this to spot leads worth checking, not as evidence that something works.'));

    // what people tried
    const tx = TX.map(x => {
      const hits = all.flatMap(p => p.treatments.filter(t => t.id === x.id)), c = o => hits.filter(t => t.outcome === o).length;
      return { x, n: hits.length, better: c('better'), none: c('none'), worse: c('worse'), mixed: c('mixed'), mentioned: c('mentioned') };
    }).filter(r => r.n).sort((a, b) => b.n - a.n);
    const t1 = h('table');
    t1.append(h('tr', null, ['What people tried or discussed', 'Posts', 'Described as helping', 'No effect', 'Described as worsening', 'Mixed', 'Outcome unclear'].map((c, i) => h('th', { class: i ? 'num' : '' }, c))));
    for (const r of tx) {
      const a = h('a', { href: '#patients' }, r.x.label);
      a.addEventListener('click', e => { e.preventDefault(); ptTx = r.x.id; ptShown = 25; drawPatients(); $('ptList').scrollIntoView({ behavior: 'smooth' }); });
      t1.append(h('tr', null, h('td', null, a), ...[r.n, r.better, r.none, r.worse, r.mixed, r.mentioned].map(v => h('td', { class: 'num' }, v))));
    }
    box.append(h('h3', null, 'Treatments discussed'), h('div', { class: 'scroll' }, t1));

    // symptoms and drugs, side by side
    function freq(title, items) {
      const max = Math.max(1, ...items.map(i => i[1])), t = h('table');
      for (const [l, n] of items) t.append(h('tr', null, h('td', null, l), h('td', null, h('span', { class: 'bar', style: `width:${Math.round(110 * n / max)}px` }), `${n} (${Math.round(100 * n / all.length)}%)`)));
      return h('div', null, h('h3', null, title), t);
    }
    const sym = D.symptoms.map(x => [x.label, all.filter(p => p.symptoms.includes(x.id)).length]).filter(x => x[1]).sort((a, b) => b[1] - a[1]);
    const dr = {}; for (const p of all) for (const d of p.drugs) dr[d] = (dr[d] || 0) + 1;
    const drugs = Object.entries(dr).sort((a, b) => b[1] - a[1]).slice(0, 14).map(([d, n]) => [cap(d), n]);
    box.append(h('div', { class: 'cols' }, freq('Symptoms mentioned', sym), freq('Drugs mentioned', drugs)));

    // posts
    const sel = h('select', { 'aria-label': 'Filter by treatment' }, h('option', { value: '' }, 'All treatments'), tx.map(r => h('option', { value: r.x.id, selected: r.x.id === ptTx ? '' : null }, r.x.label)));
    sel.addEventListener('input', () => { ptTx = sel.value; ptShown = 25; drawPatients(); });
    const cb = h('input', { type: 'checkbox' }); cb.checked = ptRec;
    cb.addEventListener('input', () => { ptRec = cb.checked; ptShown = 25; drawPatients(); });
    const list = all.filter(p => (!ptTx || p.treatments.some(t => t.id === ptTx)) && (!ptRec || p.recovery));
    const OUT = { better: 'helped', none: 'no effect', worse: 'worse', mixed: 'mixed', mentioned: '' };
    box.append(h('h3', { id: 'ptList' }, 'Posts'), h('div', { class: 'filters' }, sel, h('label', { class: 'small' }, cb, ' Mentions recovery only')),
      h('p', { class: 'small' }, `${fmt(list.length)} posts, newest first`),
      ...list.slice(0, ptShown).map(p => h('div', { class: 'paper' },
        h('div', null, h('a', { href: p.url, target: '_blank', rel: 'noopener' }, `${p.community} · ${fmtDate(p.date)}`), h('span', { class: 'small' }, ` · ${p.replies} replies`)),
        h('div', null, p.drugs.map(d => h('span', { class: 'pill core' }, cap(d))), p.symptoms.map(x => h('span', { class: 'pill' }, label(D.symptoms, x))),
          p.treatments.map(t => h('span', { class: 'pill adjacent' }, label(TX, t.id) + (OUT[t.outcome] ? ': ' + OUT[t.outcome] : ''))),
          p.recovery ? h('span', { class: 'pill related' }, 'mentions recovery') : null))));
    if (list.length > ptShown) box.append(h('p', null, h('button', { onclick: () => { ptShown += 50; drawPatients(); } }, 'Show more')));
    drawArticles(box);
  }

  // Blog and advocacy-site articles: published pieces, listed by title.
  function drawArticles(box) {
    const all = articles();
    if (!D.community.some(p => p.source === 'blog')) return;
    box.append(h('h3', null, 'Blogs and advocacy sites'));
    if (!all.length) { box.append(h('p', { class: 'small' }, 'No collected articles mention the drugs in this view.')); return; }
    const names = [...new Set(all.map(p => p.community))].sort();
    const sel = h('select', { 'aria-label': 'Filter by site' }, h('option', { value: '' }, 'All sites'), names.map(n => h('option', { value: n, selected: n === blSrc ? '' : null }, n)));
    sel.addEventListener('input', () => { blSrc = sel.value; blShown = 15; drawPatients(); });
    const list = all.filter(p => !blSrc || p.community === blSrc);
    box.append(h('p', { class: 'small' }, 'Articles about persistent sexual dysfunction from patient organisations and commentators. Opinion and advocacy, not peer-reviewed research.'),
      h('div', { class: 'filters' }, sel), h('p', { class: 'small' }, `${fmt(list.length)} articles, newest first`),
      ...list.slice(0, blShown).map(p => h('div', { class: 'paper' },
        h('div', { class: 't' }, h('a', { href: p.url, target: '_blank', rel: 'noopener' }, p.title || p.url)),
        h('div', { class: 'small' }, `${p.community} · ${fmtDate(p.date)}`),
        h('div', null, p.drugs.slice(0, 6).map(d => h('span', { class: 'pill core' }, cap(d))), p.treatments.slice(0, 6).map(t => h('span', { class: 'pill adjacent' }, label(TX, t.id)))))));
    if (list.length > blShown) box.append(h('p', null, h('button', { onclick: () => { blShown += 40; drawPatients(); } }, 'Show more articles')));
  }

  // ---- partition bar ---------------------------------------------------
  function drawAll() {
    for (const b of $('seg').children) b.setAttribute('aria-pressed', b.dataset.id === PART.id);
    $('partNote').textContent = PART.everything ? PART.description
      : `${PART.description} A record is included when its title, abstract or post names one of these drugs, so some records are only partly about them.`;
    drawTiles(); drawGuide(); drawTimeline(); drawMatrix(); drawGaps(); drawSymptoms(); drawTreatments(); drawTrials(); drawForest(); drawTargets(); drawPatients(); render();
  }
  $('seg').append(...PARTS.map(p => {
    const b = h('button', { 'aria-pressed': 'false' }, p.label); b.dataset.id = p.id;
    b.addEventListener('click', () => { PART = p; store.set('pssd-part', p.id); scopeOverride = null; shown = 40; ptShown = 25; ptTx = ''; blShown = 15; blSrc = ''; drawAll(); });
    return b;
  }));
  drawAll();
})();
