// Nanobanana2 Gallery — AI Bloom Sisters
// 750ギャラリー(gallery.js/gallery.json)とは完全に別データ・別スクリプト。
(function () {
  'use strict';

  const grid = document.getElementById('galleryGrid');
  const meta = document.getElementById('galleryMeta');
  const modal = document.getElementById('modal');
  const modalImg = document.getElementById('modalImg');
  const modalCaption = document.getElementById('modalCaption');
  const modalClose = document.getElementById('modalClose');
  const modalPrev = document.getElementById('modalPrev');
  const modalNext = document.getElementById('modalNext');
  const tabsChar = document.querySelectorAll('.tabs-char .tab');

  const CHAR_LABEL = { lupinus: 'ルピナス', iris: 'アイリス', fiona: 'フィオナ' };

  let allItems = [];
  let curChar = 'lupinus';
  let viewItems = [];
  let modalIdx = -1;

  function load() {
    return fetch('assets/data/nanobanana2.json?ts=' + Date.now())
      .then(r => r.json())
      .then(data => {
        allItems = data.items || [];
        render();
      })
      .catch(err => {
        grid.innerHTML = '<p style="text-align:center;color:#999">ギャラリーの読み込みに失敗しました。</p>';
        console.error(err);
      });
  }
  load();

  function render() {
    viewItems = allItems.filter(it => it.char === curChar);
    const total = viewItems.length;
    meta.textContent = `${CHAR_LABEL[curChar] || curChar} ／ Nanobanana2 （${total}枚）`;
    grid.innerHTML = '';
    if (!total) {
      grid.innerHTML = '<p style="text-align:center;color:#999;padding:3rem">準備中…（生成・QC進行中です）</p>';
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
          <img src="${it.thumb}" alt="${it.caption}" loading="lazy">
          <div class="card-caption">${it.caption}</div>
        </div>
      `;
      card.addEventListener('click', () => openModal(i));
      grid.appendChild(card);
    });
  }

  // タブ
  tabsChar.forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.disabled) return;
      tabsChar.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      curChar = tab.dataset.char;
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
    modalImg.alt = it.caption;
    modalCaption.textContent = it.caption;
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
})();
