// Simple Audio Player Simulation
        const playBtn = document.getElementById('play-pause');
        let isPlaying = false;

        playBtn.addEventListener('click', () => {
            isPlaying = !isPlaying;
            const icon = playBtn.querySelector('.material-symbols-outlined');
            icon.textContent = isPlaying ? 'pause' : 'play_arrow';
            
            if(isPlaying) {
                playBtn.classList.add('bg-secondary');
                playBtn.classList.remove('bg-primary');
            } else {
                playBtn.classList.add('bg-primary');
                playBtn.classList.remove('bg-secondary');
            }
        });

        // Speed Toggle
        const speedBtn = document.getElementById('speed-toggle');
        const speeds = ['1x 倍速', '1.25x 倍速', '1.5x 倍速', '2x 倍速'];
        let currentSpeedIdx = 2;

        speedBtn.addEventListener('click', () => {
            currentSpeedIdx = (currentSpeedIdx + 1) % speeds.length;
            speedBtn.textContent = speeds[currentSpeedIdx];
        });

        // Jump to logic (Visual Mock)
        function jumpTo(seconds) {
            console.log('Jumping to', seconds, 'seconds');
            // Visual feedback
            const toast = document.createElement('div');
            toast.className = 'fixed bottom-24 left-1/2 -translate-x-1/2 bg-ink-deep text-white px-4 py-2 rounded-full text-xs font-medium z-[100] animate-bounce';
            toast.textContent = `跳转至 ${Math.floor(seconds/60)}:${(seconds%60).toString().padStart(2, '0')}...`;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 1500);
        }

        // Randomize waveform a bit for "living" feel
        const bars = document.querySelectorAll('.waveform-bar');
        bars.forEach(bar => {
            bar.style.height = (Math.random() * 70 + 20) + '%';
        });