// Micro-interactions for input fields
        document.querySelectorAll('input').forEach(input => {
            const container = input.closest('.input-focus-ring');
            if (container) {
                const icon = container.querySelector('.material-symbols-outlined');
                input.addEventListener('focus', () => {
                    icon.style.fontVariationSettings = "'FILL' 1";
                });
                input.addEventListener('blur', () => {
                    icon.style.fontVariationSettings = "'FILL' 0";
                });
            }
        });