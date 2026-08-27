document.addEventListener('DOMContentLoaded', () => {
  // Password show/hide
  const passInput = document.getElementById('passwordInput');
  const toggleBtn = document.getElementById('togglePassword');
  const toggleIcon = toggleBtn && toggleBtn.querySelector('.material-symbols-outlined');

  if (passInput && toggleBtn && toggleIcon) {
    toggleBtn.addEventListener('click', () => {
      const show = passInput.getAttribute('type') === 'password';
      passInput.setAttribute('type', show ? 'text' : 'password');
      toggleIcon.textContent = show ? 'visibility_off' : 'visibility';
      toggleBtn.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
      toggleBtn.setAttribute('title', show ? '隐藏密码' : '显示密码');
    });
  }

  // Micro-interactions for left-side field icons
  document.querySelectorAll('.input-focus-ring input').forEach((input) => {
    const container = input.closest('.input-focus-ring');
    if (!container) return;
    const icon = container.querySelector('.material-symbols-outlined.absolute.left-4')
      || container.querySelector('span.material-symbols-outlined');
    if (!icon) return;
    input.addEventListener('focus', () => {
      icon.style.fontVariationSettings = "'FILL' 1";
    });
    input.addEventListener('blur', () => {
      icon.style.fontVariationSettings = "'FILL' 0";
    });
  });
});
