document.addEventListener("DOMContentLoaded", () => {
  const menuToggle = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector(".nav");

  if (!menuToggle || !nav) {
    return;
  }

  menuToggle.addEventListener("click", () => {
    nav.classList.toggle("open");
  });
});
