document.querySelectorAll('.knowledge-card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.classList.add('shadow-md');
                card.classList.add('-translate-y-1');
            });
            card.addEventListener('mouseleave', () => {
                card