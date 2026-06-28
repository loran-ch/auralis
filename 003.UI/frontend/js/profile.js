// Scroll effect for header
    window.addEventListener('scroll', () => {
        const header = document.querySelector('header');
        if (window.scrollY > 20) {
            header.classList.add('bg-surface/95', 'shadow-sm');
            header.classList.remove('bg-surface/80');
        } else {
            header.classList.add('bg-surface/80');
            header.classList.remove('bg-surface/95', 'shadow-sm');
        }
    });