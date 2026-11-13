/* Общий скрипт главной, страниц направлений и 3D-каталога.
   Тексты не меняет: слова заголовков только оборачиваются в span для анимации,
   а счётчик цифр в конце возвращает исходную строку как есть. */
(function(){
  var yr = document.getElementById('yr');
  if (yr) yr.textContent = new Date().getFullYear();

  // ---- шапка ----
  var nav = document.getElementById('nav');
  // на страницах направлений и 3D шапка всегда белая (под ней цветной блок)
  var keep = nav.hasAttribute('data-solid');
  var onScroll = function(){ nav.classList.toggle('solid', keep || window.scrollY > 20); };
  onScroll(); window.addEventListener('scroll', onScroll, {passive:true});
  document.getElementById('burger').addEventListener('click', function(){ nav.classList.toggle('open'); });
  document.querySelectorAll('.nav-links a').forEach(function(a){
    a.addEventListener('click', function(){ nav.classList.remove('open'); });
  });

  // ---- выбор языка: cookie для nginx ----
  document.querySelectorAll('.langs a').forEach(function(a){
    a.addEventListener('click', function(){
      document.cookie = 'lang=' + a.getAttribute('hreflang') + ';path=/;max-age=31536000;samesite=Lax';
    });
  });

  // ================= анимации =================
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (RM || !('IntersectionObserver' in window)) return;

  function splitWords(el){
    var i = 0;
    (function walk(node){
      Array.prototype.slice.call(node.childNodes).forEach(function(n){
        if (n.nodeType === 3){
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function(p){
            if (!p) return;
            if (/^\s+$/.test(p)){ frag.appendChild(document.createTextNode(p)); return; }
            var w = document.createElement('span'), wi = document.createElement('span');
            w.className = 'w'; wi.className = 'wi'; wi.style.setProperty('--i', i++);
            wi.textContent = p; w.appendChild(wi); frag.appendChild(w);
          });
          n.parentNode.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.tagName !== 'BR'){ walk(n); }
      });
    })(el);
    el.classList.add('split');
  }

  // «4 500+», «20+», «5»: считает до числа и возвращает исходный текст
  function countUp(el){
    var t = el.textContent, m = t.match(/^(\D*?)(\d[\d\s ]*\d|\d)(\D*)$/);
    if (!m) return;
    var target = parseInt(m[2].replace(/\D/g, ''), 10), sp = m[2].match(/[\s ]/), sep = sp ? sp[0] : '';
    var fmt = function(n){ return sep ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, sep) : String(n); };
    var t0 = performance.now(), dur = 1600;
    (function f(now){
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 4);
      el.textContent = k < 1 ? m[1] + fmt(Math.round(target * e)) + m[3] : t;
      if (k < 1) requestAnimationFrame(f);
    })(t0);
  }

  document.querySelectorAll('h1, .head h2, .about-txt h2, .dcta h2, .promo3d h2').forEach(splitWords);
  document.querySelectorAll('.hero .eyebrow, .hero .lead, .hero-btns, .head .sub, .dhero .lead, .dhero .tags, .dhero .hero-btns, .crumbs').forEach(function(el, k){
    el.classList.add('fade'); el.style.setProperty('--d', (150 + (k % 4) * 120) + 'ms');
  });
  document.querySelectorAll('.cat-row,.feat,.stat,.contact-card,.form-card,.show-grid,.brand-card,.others .dtile').forEach(function(el){
    el.classList.add('rise');
  });

  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      var el = e.target;
      el.classList.add('in');
      if (el.tagName === 'B') countUp(el);
      io.unobserve(el);
    });
  }, {threshold:0.12, rootMargin:'0px 0px -5% 0px'});
  document.querySelectorAll('.split,.fade,.rise,.dirs,.hero-stats b,.stat b').forEach(function(el){ io.observe(el); });
})();
