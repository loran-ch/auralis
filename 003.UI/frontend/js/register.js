document.addEventListener('DOMContentLoaded', () => {
        // Password toggle logic
        const togglePass = document.querySelector('button .material-symbols-outlined[data-icon="visibility"]');
        const passInput = document.querySelector('input[type="password"]');
        
        if (togglePass && passInput) {
            togglePass.parentElement.addEventListener('click', () => {
                const type = passInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passInput.setAttribute('type', type);
                togglePass.textContent = type === 'password' ? 'visibility' : 'visibility_off';
            });
        }
    });