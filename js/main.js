/* =============================================================================
   Eden Presbyterian Church of Oregon — site interactions
   ========================================================================== */
(function () {
  "use strict";

  const configuredTheme = "auto";
  const seasonalThemes = ["spring", "summer", "autumn", "winter"];
  const previewTheme = new URLSearchParams(window.location.search).get("theme");
  const month = new Date().getMonth() + 1;
  const automaticTheme = month >= 3 && month <= 5
    ? "spring"
    : month >= 6 && month <= 8
      ? "summer"
      : month >= 9 && month <= 11
        ? "autumn"
        : "winter";
  const activeTheme = seasonalThemes.includes(previewTheme)
    ? previewTheme
    : configuredTheme === "auto"
      ? automaticTheme
      : configuredTheme;
  const themeColors = {
    spring: "#65935c",
    summer: "#2d8a63",
    autumn: "#69755b",
    winter: "#256047"
  };

  document.documentElement.dataset.theme = activeTheme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.setAttribute("content", themeColors[activeTheme]);

  /* --- Mobile navigation toggle --- */
  const navToggle = document.getElementById("navToggle");
  const primaryNav = document.getElementById("primaryNav");
  const navTools = document.querySelector(".nav-tools details");

  if (navToggle && primaryNav) {
    navToggle.addEventListener("click", function () {
      const isOpen = primaryNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
      document.body.style.overflow = isOpen ? "hidden" : "";
    });

    primaryNav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        if (navTools) navTools.removeAttribute("open");
        primaryNav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
      }
    });
  }

  if (navTools) {
    document.addEventListener("click", function (event) {
      if (!navTools.contains(event.target)) navTools.removeAttribute("open");
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && navTools.open) {
        navTools.removeAttribute("open");
        navTools.querySelector("summary").focus();
      }
    });
  }

  /* --- Newcomer registration QR dialog --- */
  const qrTriggers = document.querySelectorAll("[data-qr-dialog]");
  if (qrTriggers.length) {
    const registrationUrl = "https://forms.gle/TqHZK4pUQ7dxFtd66";
    const qrDialog = document.createElement("dialog");

    qrDialog.className = "qr-dialog";
    qrDialog.setAttribute("aria-labelledby", "qrDialogTitle");
    qrDialog.innerHTML = `
      <div class="qr-dialog__content">
        <button class="qr-dialog__close" type="button" aria-label="닫기">&times;</button>
        <span class="eyebrow">Newcomer Registration</span>
        <h2 class="qr-dialog__title" id="qrDialogTitle">새신자 등록 QR</h2>
        <img class="qr-dialog__image" src="assets/newcomer-registration-qr.png" width="640" height="640" alt="새신자 등록 구글폼 QR 코드" />
        <p class="qr-dialog__text">휴대폰 카메라로 QR 코드를 스캔해 등록 폼을 열어 주세요.</p>
        <a class="link-arrow qr-dialog__link" href="${registrationUrl}" target="_blank" rel="noopener">등록 폼 직접 열기</a>
      </div>`;
    document.body.appendChild(qrDialog);

    const restoreQrDialogState = function () {
      document.body.style.overflow = "";
      const mobileMenuVisible = navToggle && getComputedStyle(navToggle).display !== "none";
      const focusTarget = mobileMenuVisible ? navToggle : navTools.querySelector("summary");
      if (focusTarget) focusTarget.focus();
    };

    const closeQrDialog = function () {
      if (qrDialog.open) qrDialog.close();
      restoreQrDialogState();
    };

    qrTriggers.forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        if (navTools) navTools.removeAttribute("open");
        if (primaryNav) primaryNav.classList.remove("is-open");
        if (navToggle) navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "hidden";
        qrDialog.showModal();
      });
    });

    qrDialog.querySelector(".qr-dialog__close").addEventListener("click", function () {
      closeQrDialog();
    });

    qrDialog.addEventListener("click", function (event) {
      if (event.target === qrDialog) closeQrDialog();
    });

    qrDialog.addEventListener("close", restoreQrDialogState);
  }

  /* --- Header shadow on scroll --- */
  const header = document.querySelector(".site-header");
  const onScroll = function () {
    if (header) header.classList.toggle("is-scrolled", window.scrollY > 8);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* --- Reveal-on-scroll animations --- */
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    const io = new IntersectionObserver(
      function (entries, observer) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* --- Active nav link highlighting (scroll spy) --- */
  const sections = document.querySelectorAll("main section[id]");
  const navLinks = document.querySelectorAll(".primary-nav__list a");
  if ("IntersectionObserver" in window && sections.length && navLinks.length) {
    const linkFor = {};
    navLinks.forEach(function (link) {
      const id = link.getAttribute("href");
      if (id && id.startsWith("#")) linkFor[id.slice(1)] = link;
    });

    const spy = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            navLinks.forEach(function (l) { l.classList.remove("is-active"); });
            const active = linkFor[entry.target.id];
            if (active) active.classList.add("is-active");
          }
        });
      },
      { threshold: 0.5, rootMargin: "-20% 0px -50% 0px" }
    );
    sections.forEach(function (section) { spy.observe(section); });
  }

  /* --- Current year in the footer --- */
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
