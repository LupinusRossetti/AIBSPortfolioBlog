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
  const tabsCat = document.querySelectorAll('.tabs-cat .tab');
  // admin
  const adminToggle = document.getElementById('adminToggle');
  const adminBar = document.getElementById('adminBar');
  const adminCount = document.getElementById('adminCount');
  const adminSelectAll = document.getElementById('adminSelectAll');
  const adminClearSel = document.getElementById('adminClearSel');
  const adminDelete = document.getElementById('adminDelete');
  const adminExit = document.getElementById('adminExit');
  const pwDialog = document.getElementById('pwDialog');
  const pwInput = document.getElementById('pwInput');
  const pwOk = document.getElementById('pwOk');
  const pwCancel = document.getElementById('pwCancel');

  const ADMIN_PASS = 'puramu4078';

  let allItems = [];
  let chars = [];
  let curChar = 'lupinus';
  let curCat = 'seiso';
  let viewItems = [];
  let modalIdx = -1;
  let adminMode = false;
  let selected = new Set(); // scene ids

  const CAT_LABEL = { seiso: '清楚', genki: '元気', kawaii: '可愛い', sexy: 'セクシー' };
  const CHAR_LABEL = { lupinus: 'ルピナス', iris: 'アイリス', fiona: 'フィオナ' };

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
    meta.textContent = `${CHAR_LABEL[curChar]} ／ ${CAT_LABEL[curCat]}`;
    grid.innerHTML = '';
    if (!total) {
      grid.innerHTML = '<p style="text-align:center;color:#999;padding:3rem">準備中…</p>';
      return;
    }
    viewItems.forEach((it, i) => {
      const card = document.createElement('div');
      card.className = 'gallery-card' + (selected.has(it.id) ? ' selected' : '');
      card.dataset.id = it.id;
      card.style.animationDelay = (i * 0.025) + 's';
      card.innerHTML = `
        <span class="card-checkbox" aria-label="選択">${selected.has(it.id) ? '✓' : ''}</span>
        <span class="corner-bl"></span>
        <span class="corner-br"></span>
        <div class="card-frame">
          <img src="${it.thumb}" alt="${it.caption}" loading="lazy">
          <div class="card-caption">${it.caption}</div>
        </div>
      `;
      card.addEventListener('click', e => {
        if (adminMode) {
          toggleSelect(it.id, card);
        } else {
          openModal(i);
        }
      });
      grid.appendChild(card);
    });
    updateAdminUI();
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
  tabsCat.forEach(tab => {
    tab.addEventListener('click', () => {
      tabsCat.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      curCat = tab.dataset.cat;
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

  // ===== 管理者 =====
  adminToggle.addEventListener('click', () => {
    pwDialog.classList.add('open');
    pwInput.value = '';
    setTimeout(() => pwInput.focus(), 30);
  });
  pwCancel.addEventListener('click', () => pwDialog.classList.remove('open'));
  pwInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') pwOk.click();
    else if (e.key === 'Escape') pwCancel.click();
  });
  pwOk.addEventListener('click', () => {
    if (pwInput.value === ADMIN_PASS) {
      pwDialog.classList.remove('open');
      enterAdmin();
    } else {
      pwInput.value = '';
      pwInput.placeholder = 'パスワードが違います';
      pwInput.style.borderColor = '#d94e4e';
      setTimeout(() => {
        pwInput.placeholder = 'パスワードを入力';
        pwInput.style.borderColor = '';
      }, 1500);
    }
  });

  function enterAdmin() {
    adminMode = true;
    document.body.classList.add('admin-mode');
    adminBar.classList.add('visible');
    selected.clear();
    render();
  }
  function exitAdmin() {
    adminMode = false;
    document.body.classList.remove('admin-mode');
    adminBar.classList.remove('visible');
    selected.clear();
    render();
  }
  adminExit.addEventListener('click', exitAdmin);

  function toggleSelect(id, card) {
    if (selected.has(id)) {
      selected.delete(id);
      card.classList.remove('selected');
      card.querySelector('.card-checkbox').textContent = '';
    } else {
      selected.add(id);
      card.classList.add('selected');
      card.querySelector('.card-checkbox').textContent = '✓';
    }
    updateAdminUI();
  }
  function updateAdminUI() {
    if (!adminMode) return;
    adminCount.textContent = `選択: ${selected.size}枚`;
    adminDelete.disabled = selected.size === 0;
  }

  adminSelectAll.addEventListener('click', () => {
    viewItems.forEach(it => selected.add(it.id));
    render();
  });
  adminClearSel.addEventListener('click', () => {
    selected.clear();
    render();
  });
  adminDelete.addEventListener('click', () => {
    if (!selected.size) return;
    const ids = Array.from(selected);
    if (!confirm(`${ids.length}枚を削除します。元に戻せません。よろしいですか？`)) return;
    fetch('/api/admin/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pass: ADMIN_PASS, char: curChar, ids: ids })
    })
      .then(r => r.json())
      .then(res => {
        if (res.ok) {
          alert(`${res.deleted}枚を削除しました。`);
          selected.clear();
          load(); // gallery.jsonを再読込
        } else {
          alert('削除失敗: ' + (res.error || 'unknown'));
        }
      })
      .catch(err => {
        alert('削除APIにアクセスできません。\nadmin_server.py で起動してください:\n  cd C:\\ClaudeCode\\aibs-gallery\n  python scripts/admin_server.py');
        console.error(err);
      });
  });
})();
