document.addEventListener('DOMContentLoaded', () => {
  function bindToggle(buttonId, inputId) {
    const button = document.getElementById(buttonId);
    const input = document.getElementById(inputId);
    if (!button || !input) return;
    const icon = button.querySelector('.material-symbols-outlined');
    button.addEventListener('click', () => {
      const show = input.getAttribute('type') === 'password';
      input.setAttribute('type', show ? 'text' : 'password');
      if (icon) icon.textContent = show ? 'visibility_off' : 'visibility';
      button.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
      button.setAttribute('title', show ? '隐藏密码' : '显示密码');
    });
  }

  bindToggle('toggleRegisterPassword', 'registerPassword');
  bindToggle('toggleConfirmPassword', 'registerConfirmPassword');
});
