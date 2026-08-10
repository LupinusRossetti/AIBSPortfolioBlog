// Gallery core — AI Bloom Sisters
// 2026-08-10 新設。**素材ギャラリー**と**Anima版750枚ギャラリー**の2ページで共有する。
//
// 🚨 既存の assets/js/gallery.js（公開済み・承認済みの750枚ページ用）には一切触らない。
//    あちらを引数化すると公開中のページを壊すリスクを背負うため、るぴちゃん判断で
//    「新規2ページだけ共通化」とした（2026-08-10）。将来まとめたくなったらそのとき移行する。
//
// 使い方：HTML側で読み込む前に設定を置く。
//   <script>
//     window.GALLERY_CONFIG = {
//       dataUrl: 'assets/data/materials.json',
//       charLabel: { lupinus:'ルピナス', iris:'アイリス', fiona:'フィオナ' },
//       catLabel:  { standing:'立ち姿', ... }   // 省略時は JSON の groups を使う
//     };
//   </script>
//   <script src="assets/js/gallery-core.js?v=..."></script>
//
// カテゴリ構成（どのキャラにどのカテゴリがあるか）は **JSONのitemsから自動で組み立てる**。
// ＝ページごとにJSへ直書きしない。カテゴリが増減してもJSを直さなくてよい。
(function () {
  'use strict';

  const CFG = window.GALLERY_CONFIG || {};
  if (!CFG.dataUrl) {
    console.error('[gallery-core] window.GALLERY_CONFIG.dataUrl が未設定です');
    return;
  }

  const grid = document.getElementById('galleryGrid');
  const meta = document.getElementById('galleryMeta');
  const modal = document.getElementById('modal');
  const modalImg = document.getElementById('modalImg');
  const modalCaption = document.getElementById('modalCaption');
  const modalClose = document.getElementById('modalClose');
  const modalPrev = document.getElementById('modalPrev');
  const modalNext = document.getElementById('modalNext');
  const tabsChar = document.querySelectorAll('.tabs-char .tab');
  const tabsCatRoot = document.getElementById('tabsCat');

  let allItems = [];
  let CHAR_CATS = {};          // itemsから自動生成
  let CAT_LABEL = {};          // JSONのgroups または CFG.catLabel
  const CHAR_LABEL = CFG.charLabel || {};
  let curChar = '';
  let curCat = '';
  let viewItems = [];
  let modalIdx = -1;

  // items から「キャラ→カテゴリ（初出順）」を組み立てる
  function buildCharCats(items) {
    const m = {};
    items.forEach(it => {
      if (!m[it.char]) m[it.char] = [];
      if (m[it.char].indexOf(it.category) < 0) m[it.char].push(it.category);
    });
    return m;
  }

  function renderCatTabs() {
    tabsCatRoot.innerHTML = '';
    const cats = CHAR_CATS[curChar] || [];
    curCat = cats[0] || '';
    cats.forEach((cat, i) => {
      const btn = document.createElement('button');
      btn.className = 'tab' + (i === 0 ? ' active' : '');
      btn.setAttribute('role', 'tab');
      btn.dataset.cat = cat;
      btn.textContent = CAT_LABEL[cat] || cat;
      btn.addEventListener('click', () => {
        tabsCatRoot.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        curCat = cat;
        render();
      });
      tabsCatRoot.appendChild(btn);
    });
  }

  function load() {
    return fetch(CFG.dataUrl + '?ts=' + Date.now())
      .then(r => r.json())
      .then(data => {
        allItems = data.items || [];
        CHAR_CATS = buildCharCats(allItems);
        CAT_LABEL = CFG.catLabel || data.groups || {};
        const chars = data.chars || Object.keys(CHAR_CATS);
        curChar = (chars.indexOf(curChar) >= 0) ? curChar : chars[0];
        // HTML側の初期activeタブに合わせる（あれば優先）
        const activeTab = document.querySelector('.tabs-char .tab.active');
        if (activeTab && activeTab.dataset.char && CHAR_CATS[activeTab.dataset.char]) {
          curChar = activeTab.dataset.char;
        }
        renderCatTabs();
        render();
      })
      .catch(err => {
        grid.innerHTML =
          '<p style="text-align:center;color:#999">ギャラリーの読み込みに失敗しました。</p>';
        console.error(err);
      });
  }

  function render() {
    viewItems = allItems.filter(it => it.char === curChar && it.category === curCat);
    const total = viewItems.length;
    // 先頭の絵文字＋空白があれば落として文字だけにする（既存ギャラリーと同じ見せ方）
    const catLabel = String(CAT_LABEL[curCat] || curCat).replace(/^[^\s]+\s/, '');
    meta.textContent = `${CHAR_LABEL[curChar] || curChar} ／ ${catLabel} （${total}枚）`;
    grid.innerHTML = '';
    if (!total) {
      grid.innerHTML = '<p style="text-align:center;color:#999;padding:3rem">準備中…</p>';
      return;
    }
    viewItems.forEach((it, i) => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      card.dataset.id = it.id;
      card.style.animationDelay = (i * 0.025) + 's';
      card.innerHTML = `
        <span class="corner-bl"></span>
        <span class="corner-br"></span>
        <div class="card-frame">
          <img src="${it.thumb}" alt="${it.caption || ''}" loading="lazy">
        </div>
      `;
      card.addEventListener('click', () => openModal(i));
      grid.appendChild(card);
    });
  }

  tabsChar.forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.disabled) return;
      tabsChar.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      curChar = tab.dataset.char;
      renderCatTabs();
      render();
    });
  });

  // モーダル
  function openModal(i) {
    modalIdx = i;
    updateModal();
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
    modal.setAttribute('aria-hidden', 'false');
  }
  function closeModal() {
    modal.classList.remove('open');
    document.body.style.overflow = '';
    modal.setAttribute('aria-hidden', 'true');
    modalIdx = -1;
  }
  function updateModal() {
    if (modalIdx < 0 || modalIdx >= viewItems.length) return;
    const it = viewItems[modalIdx];
    modalImg.src = it.full;
    modalImg.alt = it.caption || '';
    modalCaption.textContent = '';   // キャプション表示は廃止（るぴちゃん確定方針）
  }
  function prevModal() {
    if (modalIdx > 0) modalIdx--; else modalIdx = viewItems.length - 1;
    updateModal();
  }
  function nextModal() {
    if (modalIdx < viewItems.length - 1) modalIdx++; else modalIdx = 0;
    updateModal();
  }

  modalClose.addEventListener('click', closeModal);
  modalPrev.addEventListener('click', prevModal);
  modalNext.addEventListener('click', nextModal);
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

  document.addEventListener('keydown', e => {
    if (!modal.classList.contains('open')) return;
    if (e.key === 'Escape') closeModal();
    else if (e.key === 'ArrowLeft') prevModal();
    else if (e.key === 'ArrowRight') nextModal();
  });

  load();
})();
