// Gallery — AI Bloom Sisters
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
  const tabsCatRoot = document.getElementById('tabsCat');

  let allItems = [];
  let chars = [];
  let curChar = 'lupinus';
  let curCat = 'seiso';
  let viewItems = [];
  let modalIdx = -1;

  const CAT_LABEL = {
    seiso: '🤍 清楚(仮)', elegant: '🌹 エレガント', idol: '🎤 アイドル',
    kawaii: '🌸 可愛い', sexy: '💕 セクシー',
    genki: '😆 元気', gakuen: '🎒 学園青春',
    yasashii: '☕ やさしい', fantasy: '✨ ファンタジー',
  };
  const CHAR_LABEL = { lupinus: 'ルピナス', iris: 'アイリス', fiona: 'フィオナ' };
  const CHAR_CATS = {
    lupinus: ['seiso','elegant','idol','kawaii','sexy'],
    iris:    ['genki','idol','gakuen','kawaii','sexy'],
    fiona:   ['yasashii','fantasy','idol','kawaii','sexy'],
  };

  function renderCatTabs(){
    tabsCatRoot.innerHTML = '';
    CHAR_CATS[curChar].forEach((cat, i) => {
      const btn = document.createElement('button');
      btn.className = 'tab' + (i === 0 ? ' active' : '');
      btn.setAttribute('role','tab');
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
    // 初期カテゴリを現キャラの先頭に
    curCat = CHAR_CATS[curChar][0];
  }

  // データ読込
  function load() {
    return fetch('assets/data/gallery.json?ts=' + Date.now())
      .then(r => r.json())
      .then(data => {
        allItems = data.items || [];
        chars = data.chars || [];
        render();
      })
      .catch(err => {
        grid.innerHTML = '<p style="text-align:center;color:#999">ギャラリーの読み込みに失敗しました。</p>';
        console.error(err);
      });
  }
  load();

  function render() {
    viewItems = allItems.filter(it => it.char === curChar && it.category === curCat);
    const total = viewItems.length;
    const catLabel = (CAT_LABEL[curCat] || curCat).replace(/^[^\s]+\s/, '');
    meta.textContent = `${CHAR_LABEL[curChar]} ／ ${catLabel} （${total}枚）`;
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
      renderCatTabs(); // キャラに応じて再構築
      render();
    });
  });
  // 初期カテゴリタブ
  renderCatTabs();

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
