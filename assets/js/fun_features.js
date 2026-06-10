/* 楽しいコーナー：おみくじ・今日のひとこと・キスカウンター
   Phase1実装：軽量・無依存・サイト全ページで動く。 */
(function() {
  'use strict';

  const CHAR_NAMES = {
    lupinus: { name: 'ルピナス', icon: 'blog/icons/lupinus_happy.png' },
    iris: { name: 'アイリス', icon: 'blog/icons/iris_laugh.png' },
    fiona: { name: 'フィオナ', icon: 'blog/icons/fiona_happy.png' }
  };

  // パスがblog/posts/から見ているケースを考慮（相対パス補正）
  function iconPath(speaker) {
    const base = CHAR_NAMES[speaker]?.icon || '';
    if (location.pathname.includes('/blog/posts/')) {
      return '../icons/' + base.replace('blog/icons/', '');
    }
    if (location.pathname.includes('/blog/')) {
      return base.replace('blog/icons/', 'icons/');
    }
    return base;
  }

  function today() { return new Date().toISOString().slice(0, 10); }

  // ─── 今日のひとこと ───
  function initQuoteOfTheDay() {
    const el = document.getElementById('quote-of-the-day');
    if (!el) return;
    fetch('assets/data/quotes.json').then(r => r.json()).then(data => {
      // 当日固定（日付ベースseed）
      const day = today();
      const seed = day.split('-').reduce((a, b) => a + parseInt(b), 0);
      const q = data.quotes[seed % data.quotes.length];
      const charInfo = CHAR_NAMES[q.speaker] || CHAR_NAMES.lupinus;
      el.innerHTML = `
        <div class="quote-card">
          <img class="quote-icon" src="${iconPath(q.speaker)}" alt="${charInfo.name}" loading="lazy">
          <div class="quote-body">
            <div class="quote-name">${charInfo.name}</div>
            <div class="quote-text">${q.msg}</div>
          </div>
        </div>
      `;
    }).catch(() => { el.style.display = 'none'; });
  }

  // ─── 三姉妹おみくじ ───
  function initOmikuji() {
    const wrap = document.getElementById('omikuji-wrap');
    if (!wrap) return;
    const btn = document.getElementById('omikuji-btn');
    const result = document.getElementById('omikuji-result');
    const STORAGE_KEY = 'aibs_omikuji_' + today();

    // 当日既に引いている場合は表示復元
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      try { showOmikuji(JSON.parse(cached)); } catch(e) {}
    }

    btn.addEventListener('click', () => {
      if (localStorage.getItem(STORAGE_KEY)) {
        const f = JSON.parse(localStorage.getItem(STORAGE_KEY));
        showOmikuji(f);
        return;
      }
      fetch('assets/data/omikuji.json').then(r => r.json()).then(data => {
        const f = data.fortunes[Math.floor(Math.random() * data.fortunes.length)];
        localStorage.setItem(STORAGE_KEY, JSON.stringify(f));
        showOmikuji(f);
      });
    });

    function showOmikuji(f) {
      const charInfo = CHAR_NAMES[f.speaker] || CHAR_NAMES.lupinus;
      result.innerHTML = `
        <div class="omikuji-card">
          <div class="omikuji-luck">${f.luck}</div>
          <div class="omikuji-chat">
            <img class="quote-icon" src="${iconPath(f.speaker)}" alt="${charInfo.name}" loading="lazy">
            <div class="quote-body">
              <div class="quote-name">${charInfo.name}</div>
              <div class="quote-text">${f.msg}</div>
            </div>
          </div>
          <div class="omikuji-note">明日また引けるよ🌸</div>
        </div>
      `;
      result.style.display = 'block';
    }
  }

  // ─── 応援カウンター ───
  function initKissCounter() {
    const wrap = document.getElementById('kiss-counter');
    if (!wrap) return;
    const KEY = 'aibs_kiss_count';
    const btn = document.getElementById('kiss-btn');
    const countEl = document.getElementById('kiss-count');
    let n = parseInt(localStorage.getItem(KEY) || '0');
    countEl.textContent = n;
    btn.addEventListener('click', () => {
      n++;
      localStorage.setItem(KEY, String(n));
      countEl.textContent = n;
      btn.classList.add('kiss-pulse');
      setTimeout(() => btn.classList.remove('kiss-pulse'), 600);
    });
  }

  // ─── あなたとの出会い回数（訪問カウンター） ───
  function initVisitCounter() {
    const el = document.getElementById('visit-counter');
    if (!el) return;
    const KEY = 'aibs_visit_count';
    const TODAY_KEY = 'aibs_visit_today_' + today();
    let total = parseInt(localStorage.getItem(KEY) || '0');
    // 同一日中の連続リロードはカウントしない
    if (!sessionStorage.getItem(TODAY_KEY)) {
      total++;
      localStorage.setItem(KEY, String(total));
      sessionStorage.setItem(TODAY_KEY, '1');
    }
    el.textContent = total;
  }

  // ─── 三姉妹からの応援メッセージ（ランダムガチャ） ───
  function initCheerGacha() {
    const wrap = document.getElementById('cheer-gacha');
    if (!wrap) return;
    const btn = document.getElementById('cheer-btn');
    const result = document.getElementById('cheer-result');
    btn.addEventListener('click', () => {
      fetch('assets/data/cheer.json').then(r => r.json()).then(data => {
        const m = data.messages[Math.floor(Math.random() * data.messages.length)];
        const charInfo = CHAR_NAMES[m.speaker] || CHAR_NAMES.lupinus;
        result.innerHTML = `
          <div class="quote-card cheer-card">
            <img class="quote-icon" src="${iconPath(m.speaker)}" alt="${charInfo.name}" loading="lazy">
            <div class="quote-body">
              <div class="quote-name">${charInfo.name}</div>
              <div class="quote-text">${m.msg}</div>
            </div>
          </div>
        `;
        result.classList.remove('cheer-fade');
        void result.offsetWidth;
        result.classList.add('cheer-fade');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initQuoteOfTheDay();
    initOmikuji();
    initKissCounter();
    initVisitCounter();
    initCheerGacha();
  });
})();
