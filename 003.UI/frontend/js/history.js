// Simple Interaction logic
        document.querySelectorAll('.card-shadow').forEach(card => {
            card.addEventListener('click', () => {
                // Mimic navigation feedback
                card.classList.add('opacity-70');
                setTimeout(() => card.classList.remove('opacity-70'), 150);
            });
        });

        // Search highlight mock
        const searchInput = document.querySelector('input');
        searchInput.addEventListener('input', (e) => {
            const container = document.getElementById('records-container');
            const emptyState = document.getElementById('empty-state');
            
            if (e.target.value.toLowerCase() === 'empty' || e.target.value === '空') {
                container.classList.add('hidden');
                emptyState.classList.remove('hidden');
                emptyState.classList.add('flex');
            } else {
                container.classList.remove('hidden');
                emptyState.classList.add('hidden');
                emptyState.classList.remove('flex');
            }
        });