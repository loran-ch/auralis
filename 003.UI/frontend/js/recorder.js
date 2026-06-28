document.getElementById('star-btn').addEventListener('click', function() {
            const isFilled = this.style.fontVariationSettings.includes("'FILL' 1");
            this.style.fontVariationSettings = isFilled ? "'FILL' 0" : "'FILL' 1";
            
            const btn = this.parentElement;
            btn.classList.add('scale-125');
            setTimeout(() => btn.classList.remove('scale-125'), 200);
        });

        // Simple waveform variation logic
        const bars = document.querySelectorAll('.waveform-bar');
        setInterval(() => {
            bars.forEach(bar => {
                const randomHeight = Math.floor(Math.random() * 30) + 8;
                bar.style.height = `${randomHeight}px`;
            });
        }, 150);