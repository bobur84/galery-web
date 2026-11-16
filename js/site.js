/* Общий скрипт всех страниц: шапка, языки, вкладки направлений, поиск, анимации.
   Тексты не меняет: счётчик цифр в конце возвращает исходную строку как есть. */
(function(){
  var yr = document.getElementById('yr');
  if (yr) yr.textContent = new Date().getFullYear();

  // ---- шапка: меню на телефоне ----
  var nav = document.getElementById('nav'), burger = document.getElementById('burger');
  if (nav && burger){
    burger.addEventListener('click', function(){
      var open = nav.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.querySelectorAll('.nav-links a').forEach(function(a){
      a.addEventListener('click', function(){
        nav.classList.remove('open'); burger.setAttribute('aria-expanded', 'false');
      });
    });
  }
  // активный пункт полосы направлений — в зоне видимости (на телефоне полоса прокручивается)
  var on = document.querySelector('.strip a.on');
  if (on && on.scrollIntoView) on.parentNode.scrollLeft = on.offsetLeft - 24;

  // ---- выбор языка: cookie для nginx ----
  document.querySelectorAll('.langs a').forEach(function(a){
    a.addEventListener('click', function(){
      document.cookie = 'lang=' + a.getAttribute('hreflang') + ';path=/;max-age=31536000;samesite=Lax';
    });
  });

  // ---- главная: вкладки «Пять направлений» ----
  var tabs = document.querySelectorAll('.dtab');
  if (tabs.length){
    var panels = document.querySelectorAll('.dpanel');
    var show = function(tab, focus){
      tabs.forEach(function(t){
        var sel = t === tab;
        t.classList.toggle('on', sel);
        t.setAttribute('aria-selected', sel ? 'true' : 'false');
        t.tabIndex = sel ? 0 : -1;
      });
      var id = tab.getAttribute('aria-controls');
      panels.forEach(function(p){ p.hidden = p.id !== id; });
      if (focus) tab.focus();
    };
    tabs.forEach(function(t, i){
      t.addEventListener('click', function(e){ e.preventDefault(); show(t); });
      t.addEventListener('keydown', function(e){
        var k = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (k){ e.preventDefault(); show(tabs[(i + k + tabs.length) % tabs.length], true); }
      });
    });
    show(tabs[0]);
  }

  // ---- главная: поиск по направлениям, брендам и кодам TRIMLINE ----
  var sf = document.getElementById('search');
  if (sf){
    var input = sf.querySelector('input'), res = document.getElementById('searchRes');
    var lang = document.documentElement.lang, idx = [];
    var strip = document.querySelector('.strip'), dirsLbl = strip ? strip.getAttribute('aria-label') : '';
    document.querySelectorAll('.strip a').forEach(function(a){
      idx.push({t: a.textContent, h: a.getAttribute('href'), k: dirsLbl});
    });
    document.querySelectorAll('#brands .brand-link').forEach(function(a){
      idx.push({t: a.textContent, h: a.getAttribute('href'), k: ''});
    });
    (sf.getAttribute('data-codes') || '').split(' ').forEach(function(c){
      if (c) idx.push({t: 'TRIMLINE ' + c, h: '/' + lang + '/trimline/?q=' + encodeURIComponent(c), k: ''});
    });
    var esc = function(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
    var norm = function(s){ return s.toLowerCase().replace(/[\s\-·]+/g, ''); };
    var found = [];
    var draw = function(){
      var q = norm(input.value.trim());
      if (!q){ res.hidden = true; found = []; return; }
      found = idx.filter(function(x){ return norm(x.t).indexOf(q) > -1; }).slice(0, 8);
      res.innerHTML = found.length
        ? found.map(function(x){ return '<a href="' + esc(x.h) + '"><span>' + esc(x.t) + '</span><small>' + esc(x.k) + '</small></a>'; }).join('')
        : '<p>' + esc(sf.getAttribute('data-empty')) + '</p>';
      res.hidden = false;
    };
    input.addEventListener('input', draw);
    input.addEventListener('focus', draw);
    document.addEventListener('click', function(e){ if (!sf.contains(e.target)) res.hidden = true; });
    input.addEventListener('keydown', function(e){ if (e.key === 'Escape') res.hidden = true; });
    // Enter: первый найденный вариант; иначе — поиск в каталоге TRIMLINE (action формы)
    sf.addEventListener('submit', function(e){
      if (found.length){ e.preventDefault(); location.href = found[0].h; }
    });
  }

  // ================= анимации =================
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (RM || !('IntersectionObserver' in window)) return;

  // «4 500+», «20+», «5»: считает до числа и возвращает исходный текст
  function countUp(el){
    var t = el.textContent, m = t.match(/^(\D*?)(\d[\d\s ]*\d|\d)(\D*)$/);
    if (!m) return;
    var target = parseInt(m[2].replace(/\D/g, ''), 10), sp = m[2].match(/[\s ]/), sep = sp ? sp[0] : '';
    var fmt = function(n){ return sep ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, sep) : String(n); };
    var t0 = performance.now(), dur = 1600;
    (function f(now){
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 4);
      el.textContent = k < 1 ? m[1] + fmt(Math.round(target * e)) + m[3] : t;
      if (k < 1) requestAnimationFrame(f);
    })(t0);
  }

  document.querySelectorAll('.circ,.feat,.stat,.brand-link,.brand-card,.contact-card,.form-card,.head').forEach(function(el){
    el.classList.add('rise');
  });
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      e.target.classList.add('in');
      if (e.target.tagName === 'B') countUp(e.target);
      io.unobserve(e.target);
    });
  }, {threshold:0.12, rootMargin:'0px 0px -5% 0px'});
  document.querySelectorAll('.rise,.stat b,.hero-stats b').forEach(function(el){ io.observe(el); });
})();
