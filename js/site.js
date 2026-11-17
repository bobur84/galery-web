/* Общий скрипт всех страниц: шапка, языки, слайдер, лента товаров, поиск, анимации.
   Тексты не меняет: счётчик цифр в конце возвращает исходную строку как есть. */
(function(){
  var yr = document.getElementById('yr');
  if (yr) yr.textContent = new Date().getFullYear();
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

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
  var on = document.querySelector('.strip-dirs a.on');
  if (on) on.parentNode.scrollLeft = on.offsetLeft - on.parentNode.offsetLeft - 24;

  // ---- выбор языка: cookie для nginx ----
  document.querySelectorAll('.langs a').forEach(function(a){
    a.addEventListener('click', function(){
      document.cookie = 'lang=' + a.getAttribute('hreflang') + ';path=/;max-age=31536000;samesite=Lax';
    });
  });

  // ---- главная: слайдер фото в герое ----
  // ---- витрина: лента едет по кругу скриптом ----
  // Не CSS-анимацией: та после возврата кнопкой «Назад» замирала на месте.
  // Пауза — пока мышь над лентой или фото выбрано клавишей Tab.
  var track = document.querySelector('.sc-track');
  if (track && !RM){
    var show = track.parentNode, pos = 0, last = 0, hold = false, SPEED = 0.028; // px за мс
    show.addEventListener('mouseenter', function(){ hold = true; });
    show.addEventListener('mouseleave', function(){ hold = false; });
    show.addEventListener('focusin', function(e){ hold = e.target.matches(':focus-visible'); });
    show.addEventListener('focusout', function(){ hold = false; });
    var tick = function(now){
      var dt = last ? Math.min(now - last, 50) : 0;   // после паузы вкладки — без рывка
      last = now;
      var half = track.scrollWidth / 2;
      if (!hold && half){ pos = (pos + dt * SPEED) % half; track.style.transform = 'translate3d(' + (-pos) + 'px,0,0)'; }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    window.addEventListener('pageshow', function(){ last = 0; hold = false; });
  }

  var slides = document.querySelectorAll('#slides .slide'), dots = document.querySelectorAll('#dots button');
  if (slides.length > 1){
    var cur = 0, timer = null;
    var go = function(n){
      cur = (n + slides.length) % slides.length;
      slides.forEach(function(s, i){ s.classList.toggle('on', i === cur); });
      dots.forEach(function(d, i){ d.classList.toggle('on', i === cur); });
    };
    var play = function(){ if (!RM){ clearInterval(timer); timer = setInterval(function(){ go(cur + 1); }, 6000); } };
    dots.forEach(function(d, i){ d.addEventListener('click', function(){ go(i); play(); }); });
    play();
  }

  // ---- лента товаров: стрелки ----
  var prow = document.getElementById('prow');
  if (prow){
    document.querySelectorAll('.arr').forEach(function(b){
      b.addEventListener('click', function(){
        var card = prow.querySelector('.pcard'), step = card ? card.offsetWidth + 24 : 300;
        prow.scrollBy({left: step * +b.getAttribute('data-dir'), behavior: RM ? 'auto' : 'smooth'});
      });
    });
  }

  // ---- главная: поиск по направлениям, брендам и кодам TRIMLINE ----
  var sf = document.getElementById('search');
  if (sf){
    var input = sf.querySelector('input'), res = document.getElementById('searchRes');
    var lang = document.documentElement.lang, idx = [];
    var strip = document.querySelector('.strip'), dirsLbl = strip ? strip.getAttribute('aria-label') : '';
    document.querySelectorAll('.strip-dirs a, .strip-3d').forEach(function(a){
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

  document.querySelectorAll('.tile,.feat,.stat,.brand-link,.brand-card,.contact-card,.form-card,.head,.gallery .ph,.mosaic>div,.split-txt').forEach(function(el){
    el.classList.add('rise');
  });
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      e.target.classList.add('in');
      if (e.target.tagName === 'B') countUp(e.target);
      io.unobserve(e.target);
    });
  }, {threshold:0.1, rootMargin:'0px 0px -5% 0px'});
  document.querySelectorAll('.rise,.stat b,.facts b').forEach(function(el){ io.observe(el); });
})();
