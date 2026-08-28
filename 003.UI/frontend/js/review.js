// Auralis 智听 — 真实课堂音频播放器
(function () {
  const audio = document.getElementById('lecture-audio');
  const playBtn = document.getElementById('play-pause');
  const speedBtn = document.getElementById('speed-toggle');
  const rewindBtn = document.getElementById('rewind-10');
  const forwardBtn = document.getElementById('forward-10');
  const bars = Array.from(document.querySelectorAll('.waveform-bar'));
  const speeds = [1, 1.25, 1.5, 2];
  let speedIndex = 0;

  if (!audio || !playBtn) return;

  function updatePlayState() {
    const playing = !audio.paused && !audio.ended;
    playBtn.querySelector('.material-symbols-outlined').textContent = playing ? 'pause' : 'play_arrow';
    playBtn.classList.toggle('bg-secondary', playing);
    playBtn.classList.toggle('bg-primary', !playing);
  }

  function showMessage(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 2200);
  }

  playBtn.addEventListener('click', function () {
    if (!audio.src) {
      showMessage('该课堂没有保存音频');
      return;
    }
    if (audio.paused) {
      audio.play().catch(() => showMessage('音频播放失败'));
    } else {
      audio.pause();
    }
  });

  audio.addEventListener('play', updatePlayState);
  audio.addEventListener('pause', updatePlayState);
  audio.addEventListener('ended', updatePlayState);
  audio.addEventListener('timeupdate', function () {
    if (!audio.duration) return;
    const progress = audio.currentTime / audio.duration;
    bars.forEach((bar, index) => {
      bar.classList.toggle('bg-primary', index / bars.length <= progress);
      bar.classList.toggle('bg-outline-variant', index / bars.length > progress);
    });
  });

  speedBtn.addEventListener('click', function () {
    speedIndex = (speedIndex + 1) % speeds.length;
    audio.playbackRate = speeds[speedIndex];
    speedBtn.textContent = speeds[speedIndex] + 'x 倍速';
  });
  speedBtn.textContent = '1x 倍速';

  rewindBtn.addEventListener('click', function () {
    audio.currentTime = Math.max(0, audio.currentTime - 10);
  });
  forwardBtn.addEventListener('click', function () {
    audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10);
  });

  bars.forEach((bar, index) => {
    bar.style.height = (25 + ((index * 37) % 65)) + '%';
  });
})();
