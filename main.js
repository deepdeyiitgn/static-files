const toggle = document.querySelector('.nav-toggle');
const navLinks = document.querySelector('.nav-links');

if (toggle && navLinks) {
  toggle.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });
}

const yearTargets = document.querySelectorAll('.js-year');
if (yearTargets.length) {
  const year = new Date().getFullYear();
  yearTargets.forEach((target) => {
    target.textContent = year;
  });
}
