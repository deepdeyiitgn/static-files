/**
 * Footer Extras — Uptodown Widget + Watermark System
 * Automatically injects into every page's footer.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {

    /* ===================================================
       1. UPTODOWN WIDGET STYLES
    =================================================== */
    var widgetStyle = document.createElement("style");
    widgetStyle.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@300;600&display=swap');

      .footer-grid-wrapper {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 30px;
      }
      .footer-left { flex: 1; min-width: 250px; }
      .footer-right { flex: 0 0 auto; display: flex; align-items: center; }

      .uptodown-item {
        min-width: 100px;
        width: 100px;
        position: relative;
        vertical-align: top;
        margin: 10px 10px 10px 0;
        white-space: normal;
        line-height: 1.2;
      }
      .uptodown-item figure {
        width: auto;
        height: 100px;
        margin: 0 0 10px;
        text-align: center;
        cursor: pointer;
      }
      .uptodown-item figure img {
        width: 100px;
        height: auto;
        border-radius: 5px;
      }
      .uptodown-item div.utd-name {
        font-family: 'Roboto Slab', serif;
        color: #333333;
        font-size: 14px;
        font-weight: 600;
        word-break: break-word;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-align: center;
      }
      .uptodown-item div.utd-name a {
        text-decoration: none;
        color: inherit;
        cursor: pointer;
      }
      .uptodown-item div.utd-desc {
        font-family: 'Roboto Slab', serif;
        color: #999;
        font-size: 12px;
        font-weight: 300;
        margin-top: 5px;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-align: center;
      }

      /* ============================================
         QUICKLINK WATERMARK
      ============================================ */
      #ql-container{
        width:100%;
        text-align:center;
        padding:18px 0;
        font-family:'Inter',system-ui,-apple-system,sans-serif;
      }
      .ql-watermark{
        background:none;
        border:none;
        cursor:pointer;
        display:inline-flex;
        align-items:center;
        gap:8px;
        opacity:.9;
        transition:.25s ease;
      }
      .ql-watermark:hover{opacity:1}
      .ql-watermark img{height:24px}
      .ql-text{
        display:flex;
        flex-direction:column;
        align-items:flex-start;
        line-height:1.15;
      }
      .ql-title{
        font-size:15px;
        font-weight:600;
        color:#333;
      }
      .ql-sub{
        font-size:12px;
        color:#777;
      }
      .tm{
        font-size:9px;
        vertical-align:super;
      }
      #ql-overlay{
        position:fixed;
        inset:0;
        background:rgba(0,0,0,.55);
        backdrop-filter:blur(4px);
        display:flex;
        align-items:center;
        justify-content:center;
        opacity:0;
        visibility:hidden;
        transition:.3s ease;
        z-index:9999;
      }
      #ql-overlay.active{
        opacity:1;
        visibility:visible;
      }
      #ql-modal{
        background:#ffffff;
        width:90%;
        max-width:480px;
        border-radius:24px;
        padding:38px 30px 30px;
        text-align:center;
        position:relative;
        transform:scale(.9);
        transition:.3s ease;
        box-shadow:0 40px 100px rgba(0,0,0,.25);
      }
      #ql-overlay.active #ql-modal{
        transform:scale(1);
      }
      #ql-close-btn{
        position:absolute;
        top:18px;
        right:20px;
        border:none;
        background:none;
        font-size:20px;
        cursor:pointer;
        color:#999;
        transition:.2s;
      }
      #ql-close-btn:hover{color:#111}
      .ql-header img{height:48px;margin-bottom:14px}
      .ql-header h2{
        margin:0;
        font-size:22px;
        font-weight:700;
        color:#111;
      }
      .ql-header p{
        font-size:14px;
        color:#666;
        margin-top:6px;
      }
      .ql-body p{
        font-size:14px;
        color:#444;
        line-height:1.7;
        margin:14px 0;
      }
      .ql-founder{
        font-size:14px;
        color:#222;
        margin-top:10px;
      }
      .ql-btn-grid{
        margin-top:24px;
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:16px;
      }
      .ql-btn{
        display:flex;
        align-items:center;
        justify-content:center;
        gap:10px;
        padding:16px 0;
        border:none;
        border-radius:16px;
        font-size:15px;
        font-weight:600;
        cursor:pointer;
        color:#fff;
        transition:.25s ease;
      }
      .ql-btn svg{
        width:18px;
        height:18px;
      }
      .ql-btn.primary{background:linear-gradient(135deg,#38bdf8,#6366f1);}
      .ql-btn.dark{background:linear-gradient(135deg,#1e293b,#334155);}
      .ql-btn.red{background:linear-gradient(135deg,#ef4444,#db2777);}
      .ql-btn.purple{background:linear-gradient(135deg,#6366f1,#8b5cf6);}
      .ql-btn:hover{
        transform:translateY(-4px);
        box-shadow:0 14px 30px rgba(0,0,0,.2);
      }

      /* ============================================
         DEEP WATERMARK
      ============================================ */
      .deep-footer-wrapper {
        width: 100%;
        display: flex;
        justify-content: center;
        padding: 15px 10px;
        cursor: pointer;
      }
      .deep-footer-branding {
        display: flex;
        align-items: center;
        gap: 10px;
        transition: transform 0.3s ease;
      }
      .deep-footer-branding:hover {
        transform: scale(1.03);
      }
      .deep-footer-icon {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: linear-gradient(135deg, #111, #333);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
      }
      .deep-footer-icon svg {
        width: 18px;
        height: 18px;
        fill: #fff;
      }
      .deep-footer-text {
        display: flex;
        flex-direction: column;
        line-height: 1.2;
      }
      .deep-footer-title {
        font-size: 15px;
        font-weight: 600;
        color: #222;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      .deep-footer-tagline {
        font-size: 12px;
        color: #777;
        margin-top: 2px;
        white-space: nowrap;
      }
      #deep-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.6);
        z-index: 10000;
        display: flex;
        justify-content: center;
        align-items: center;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.4s ease, visibility 0.4s;
        backdrop-filter: blur(5px);
        padding: 20px;
      }
      #deep-modal-overlay.active {
        opacity: 1;
        visibility: visible;
      }
      .deep-modal-content {
        background: white;
        padding: 35px 25px;
        border-radius: 20px;
        width: 100%;
        max-width: 380px;
        text-align: center;
        position: relative;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        transform: scale(0.5);
        opacity: 0;
        transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.4s ease;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      #deep-modal-overlay.active .deep-modal-content {
        transform: scale(1);
        opacity: 1;
      }
      .deep-profile-img {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid #fff;
        box-shadow: 0 0 20px rgba(214, 51, 132, 0.6);
        margin-bottom: 15px;
      }
      .deep-close-btn {
        position: absolute;
        top: 15px;
        right: 20px;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
        color: #aaa;
      }
      .deep-close-btn:hover { color: #000; }
      .deep-title {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 10px;
        color: #222;
      }
      .deep-subtitle {
        font-size: 14px;
        color: #555;
        margin-bottom: 25px;
        line-height: 1.6;
      }
      .deep-highlight {
        color: #d63384;
        font-weight: bold;
      }
      .deep-btn-container {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;
        margin-bottom: 10px;
      }
      .deep-cta-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: white !important;
        padding: 10px 20px;
        border-radius: 50px;
        font-size: 13px;
        font-weight: 600;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        transition: transform 0.2s, box-shadow 0.2s;
        min-width: 110px;
        cursor: pointer;
      }
      .deep-cta-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.3);
      }
      .deep-btn-wiki { background: linear-gradient(135deg, #222, #444); }
      .deep-btn-insta { background: linear-gradient(45deg, #f09433 0%, #dc2743 50%, #bc1888 100%); }
      .deep-btn-github { background: #24292e; }
      .deep-btn-discord { background: #5865F2; }
    `;
    document.head.appendChild(widgetStyle);

    /* ===================================================
       2. RESTRUCTURE FOOTER — add Uptodown widget on right
    =================================================== */
    var footer = document.querySelector("footer");
    if (footer) {
      var container = footer.querySelector(".container");
      if (container) {
        // Wrap existing content in footer-left
        var leftDiv = document.createElement("div");
        leftDiv.className = "footer-left";
        while (container.firstChild) {
          leftDiv.appendChild(container.firstChild);
        }

        // Create right div with Uptodown widget
        var rightDiv = document.createElement("div");
        rightDiv.className = "footer-right";
        rightDiv.innerHTML = '<div class="uptodown-item">'
          + '<figure onclick="location.href=\'https://transparent-clock.en.uptodown.com/windows\';">'
          + '<img width="100" height="100" alt="Transparent Clock icon" loading="lazy" class="app_card_img" '
          + 'src="https://img.utdstc.com/icon/60a/7b6/60a7b6356f368e1c6408d9b1dd783bea44d625184e3022a95d6d83b60e2c75dd" '
          + 'srcset="https://img.utdstc.com/icon/60a/7b6/60a7b6356f368e1c6408d9b1dd783bea44d625184e3022a95d6d83b60e2c75dd:100 1x, '
          + 'https://img.utdstc.com/icon/60a/7b6/60a7b6356f368e1c6408d9b1dd783bea44d625184e3022a95d6d83b60e2c75dd:200 2x, '
          + 'https://img.utdstc.com/icon/60a/7b6/60a7b6356f368e1c6408d9b1dd783bea44d625184e3022a95d6d83b60e2c75dd:300 3x">'
          + '</figure>'
          + '<div class="utd-name"><a href="https://transparent-clock.en.uptodown.com/windows" title="Download Transparent Clock">Transparent Clock</a></div>'
          + '<div class="utd-desc">A clean always-on-top transparent clock &amp; focus utilities for Windows</div>'
          + '</div>';

        // Create wrapper
        var wrapper = document.createElement("div");
        wrapper.className = "footer-grid-wrapper";
        wrapper.appendChild(leftDiv);
        wrapper.appendChild(rightDiv);
        container.appendChild(wrapper);

        // Add legal link to footer-links if not already present
        var footerLinks = container.querySelector(".footer-links");
        if (footerLinks && !footerLinks.querySelector('a[href*="legal"]')) {
          var legalLink = document.createElement("a");
          // Detect sub-folder pages
          var isSubFolder = window.location.pathname.indexOf("/features/") !== -1;
          legalLink.href = isSubFolder ? "../legal.html" : "legal.html";
          legalLink.textContent = "Legal";
          footerLinks.appendChild(legalLink);
        }
      }
    }

    /* ===================================================
       3. INJECT QUICKLINK WATERMARK
    =================================================== */
    var watermarkDiv = document.createElement("div");
    watermarkDiv.id = "watermark-section";
    watermarkDiv.innerHTML = ''
      + '<div id="ql-container">'
      + '  <button id="ql-open-btn" class="ql-watermark">'
      + '    <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="QuickLink">'
      + '    <div class="ql-text">'
      + '      <span class="ql-title">Powered by QuickLink<span class="tm">\u2122</span></span>'
      + '      <span class="ql-sub">#1 URL Shortening Platform</span>'
      + '    </div>'
      + '  </button>'
      + '</div>'
      + '<div id="ql-overlay">'
      + '  <div id="ql-modal">'
      + '    <button id="ql-close-btn">\u2715</button>'
      + '    <div class="ql-header">'
      + '      <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="QuickLink">'
      + '      <h2>QuickLink<span class="tm">\u2122</span></h2>'
      + '      <p>Smart URL &amp; QR Platform</p>'
      + '    </div>'
      + '    <div class="ql-body">'
      + '      <p>QuickLink is an all-in-one smart link shortening and QR platform designed for speed, clarity and control.</p>'
      + '      <p>Create short links, generate dynamic QR codes, manage redirects, and track performance \u2014 all in one place.</p>'
      + '      <p>Built for creators, developers, students and modern businesses who value simplicity and efficiency.</p>'
      + '      <p class="ql-founder"><strong>Founder &amp; Creator:</strong> Deep Dey</p>'
      + '    </div>'
      + '    <div class="ql-btn-grid">'
      + '      <button onclick="qlGo(\'https://qlynk.vercel.app\')" class="ql-btn primary">'
      + '        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>'
      + '        Website</button>'
      + '      <button onclick="qlGo(\'https://github.com/deepdeyiitgn\')" class="ql-btn dark">'
      + '        <svg viewBox="0 0 24 24"><path d="M12 2C6.5 2 2 6.6 2 12.2c0 4.4 2.9 8.2 6.9 9.5.5.1.7-.2.7-.5v-1.9c-2.8.6-3.4-1.4-3.4-1.4-.4-1.1-1-1.4-1-1.4-.8-.6.1-.6.1-.6.9.1 1.3.9 1.3.9.8 1.4 2 1 2.6.8.1-.6.3-1 .6-1.3-2.2-.3-4.5-1.2-4.5-5.2 0-1.1.4-2 1-2.8-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.8 1 .8-.2 1.6-.3 2.4-.3s1.6.1 2.4.3c2-.1 2.8-1 2.8-1 .5 1.4.2 2.4.1 2.7.6.8 1 1.7 1 2.8 0 4-2.3 4.9-4.5 5.2.3.3.6.9.6 1.8v2.7c0 .3.2.6.7.5 4-1.3 6.9-5.1 6.9-9.5C22 6.6 17.5 2 12 2z" fill="white"/></svg>'
      + '        GitHub</button>'
      + '      <button onclick="qlGo(\'https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/\')" class="ql-btn red">'
      + '        <svg viewBox="0 0 24 24"><path d="M23 12s0-3.5-.4-5c-.2-.8-.8-1.4-1.6-1.6C19.5 5 12 5 12 5s-7.5 0-9 .4c-.8.2-1.4.8-1.6 1.6C1 8.5 1 12 1 12s0 3.5.4 5c.2.8.8 1.4 1.6 1.6 1.5.4 9 .4 9 .4s7.5 0 9-.4c.8-.2 1.4-.8 1.6-1.6.4-1.5.4-5 .4-5zM10 15V9l6 3-6 3z" fill="white"/></svg>'
      + '        YouTube</button>'
      + '      <button onclick="qlGo(\'https://clock.qlynk.me\')" class="ql-btn purple">'
      + '        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
      + '        Study Clock</button>'
      + '    </div>'
      + '  </div>'
      + '</div>';

    /* ===================================================
       4. INJECT DEEP WATERMARK
    =================================================== */
    var deepWatermarkDiv = document.createElement("div");
    deepWatermarkDiv.id = "deep-watermark-section";
    deepWatermarkDiv.innerHTML = ''
      + '<div class="deep-footer-wrapper" id="deep-footer-trigger">'
      + '  <div class="deep-footer-branding">'
      + '    <div class="deep-footer-icon">'
      + '      <svg viewBox="0 0 24 24"><path d="M12 2L15 8H9L12 2ZM4 10H20L12 22L4 10Z"/></svg>'
      + '    </div>'
      + '    <div class="deep-footer-text">'
      + '      <div class="deep-footer-title">Powered by Deep\u2122</div>'
      + '      <div class="deep-footer-tagline">AI &amp; Web Development Solutions</div>'
      + '    </div>'
      + '  </div>'
      + '</div>'
      + '<div id="deep-modal-overlay">'
      + '  <div class="deep-modal-content">'
      + '    <div class="deep-close-btn">&times;</div>'
      + '    <img src="https://qlynk.me/wiki-images/Deep_Dey_New.png" alt="Deep Dey" class="deep-profile-img">'
      + '    <div class="deep-title">Hello, I\'m Deep!</div>'
      + '    <p class="deep-subtitle">'
      + '      I\'m a <strong>Class 11 Student</strong> and a self-taught '
      + '      <strong>AI &amp; Prompt Engineer</strong> (3+ Years). \uD83E\uDD16'
      + '      <br><br>'
      + '      I created <span class="deep-highlight">Transparent Clock</span> — '
      + '      a minimal, privacy-first clock overlay &amp; focus companion for students. \u23F0'
      + '      <br><i>Source-Available • Zero Data Collection • Always-On-Top</i>'
      + '    </p>'
      + '    <p style="font-size: 11px; color: #999; margin-top: 18px; border-top: 1px solid #eee; padding-top: 12px;">'
      + '      &copy; ' + new Date().getFullYear() + ' Deep Dey | All Rights Reserved | QuickLink &times; Transparent Clock'
      + '    </p>'
      + '    <div class="deep-btn-container">'
      + '      <div onclick="openDeepLink(\'wiki\')" class="deep-cta-button deep-btn-wiki">More Info</div>'
      + '      <div onclick="openDeepLink(\'insta\')" class="deep-cta-button deep-btn-insta">Instagram</div>'
      + '    </div>'
      + '    <div class="deep-btn-container">'
      + '      <div onclick="openDeepLink(\'github\')" class="deep-cta-button deep-btn-github">GitHub</div>'
      + '      <div onclick="openDeepLink(\'discord\')" class="deep-cta-button deep-btn-discord">Discord</div>'
      + '    </div>'
      + '  </div>'
      + '</div>';

    // Copyright line below watermarks
    var copyrightBar = document.createElement("div");
    copyrightBar.id = "deep-copyright-bar";
    copyrightBar.style.cssText = "text-align:center; padding:18px 10px; font-size:12px; color:#888; background:#111; border-top:1px solid #222; letter-spacing:0.3px;";
    copyrightBar.innerHTML = '&copy; ' + new Date().getFullYear() + ' Deep Dey | All Rights Reserved | QuickLink &times; Transparent Clock';

    // Insert watermarks + copyright after footer
    if (footer) {
      footer.parentNode.insertBefore(watermarkDiv, footer.nextSibling);
      footer.parentNode.insertBefore(deepWatermarkDiv, watermarkDiv.nextSibling);
      footer.parentNode.insertBefore(copyrightBar, deepWatermarkDiv.nextSibling);
    }

    /* ===================================================
       5. WATERMARK EVENT HANDLERS
    =================================================== */

    // QuickLink watermark
    var qlOverlay = document.getElementById("ql-overlay");
    var qlOpenBtn = document.getElementById("ql-open-btn");
    var qlCloseBtn = document.getElementById("ql-close-btn");

    if (qlOpenBtn && qlOverlay) {
      qlOpenBtn.onclick = function () {
        qlOverlay.classList.add("active");
      };
    }
    if (qlCloseBtn && qlOverlay) {
      qlCloseBtn.onclick = function () {
        qlOverlay.classList.remove("active");
      };
    }
    if (qlOverlay) {
      qlOverlay.addEventListener("click", function (e) {
        if (e.target === qlOverlay) {
          qlOverlay.classList.remove("active");
        }
      });
    }

    window.qlGo = function (url) {
      window.open(url, "_blank");
    };

    // Deep watermark
    var deepLinks = {
      wiki: "https://qlynk.vercel.app/wiki",
      insta: "https://www.instagram.com/deepdey.official",
      github: "https://github.com/deepdeyiitgn",
      discord: "https://discord.com/invite/t6ZKNw556n"
    };

    window.openDeepLink = function (type) {
      window.open(deepLinks[type], "_blank");
    };

    var deepTrigger = document.getElementById("deep-footer-trigger");
    var deepOverlay = document.getElementById("deep-modal-overlay");
    var deepCloseBtn = document.querySelector(".deep-close-btn");

    if (deepTrigger && deepOverlay) {
      deepTrigger.addEventListener("click", function () {
        deepOverlay.classList.add("active");
      });
    }
    if (deepCloseBtn && deepOverlay) {
      deepCloseBtn.addEventListener("click", function () {
        deepOverlay.classList.remove("active");
      });
    }
    if (deepOverlay) {
      deepOverlay.addEventListener("click", function (e) {
        if (e.target === deepOverlay) {
          deepOverlay.classList.remove("active");
        }
      });
    }

    /* ===================================================
       4. LINK PREVIEW PROTECTION
       Converts all <a> href links to onclick navigation
       so browser status bar does not preview the URL.
       Includes mailto:, tel:, and # anchor links.
    =================================================== */
    var allLinks = document.querySelectorAll("a[href]");
    allLinks.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href || href.startsWith("javascript:")) return;
      var target = link.getAttribute("target");
      link.setAttribute("data-href", href);
      link.removeAttribute("href");
      link.style.cursor = "pointer";
      link.addEventListener("click", function (e) {
        e.preventDefault();
        var dest = this.getAttribute("data-href");
        if (dest.startsWith("mailto:") || dest.startsWith("tel:")) {
          window.location.href = dest;
        } else if (dest === "#" || dest.startsWith("#")) {
          var id = dest.substring(1);
          if (id) {
            var el = document.getElementById(id);
            if (el) el.scrollIntoView({ behavior: "smooth" });
          } else {
            window.scrollTo({ top: 0, behavior: "smooth" });
          }
        } else if (target === "_blank") {
          window.open(dest, "_blank", "noopener,noreferrer");
        } else {
          window.location.href = dest;
        }
      });
    });

  });
})();
