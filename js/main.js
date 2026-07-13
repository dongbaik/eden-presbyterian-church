/* =============================================================================
   Eden Presbyterian Church of Oregon — site interactions
   ========================================================================== */
(function () {
  "use strict";

  /* --- Mobile navigation toggle --- */
  const navToggle = document.getElementById("navToggle");
  const primaryNav = document.getElementById("primaryNav");

  if (navToggle && primaryNav) {
    navToggle.addEventListener("click", function () {
      const isOpen = primaryNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
      document.body.style.overflow = isOpen ? "hidden" : "";
    });

    primaryNav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        primaryNav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
        document.body.style.overflow = "";
      }
    });
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
