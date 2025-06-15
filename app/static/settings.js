document.addEventListener('DOMContentLoaded', () => {
    const voiceToggle = document.getElementById('voice-toggle');
    if (voiceToggle) {
        voiceToggle.checked = localStorage.getItem('voiceActivated') === 'true';
        voiceToggle.addEventListener('change', () => {
            localStorage.setItem('voiceActivated', voiceToggle.checked);
        });
    }

    const confInput = document.getElementById('confidence-threshold');
    if (confInput) {
        const stored = parseFloat(localStorage.getItem('confidenceThreshold') || '0.65');
        confInput.value = stored;
        confInput.addEventListener('change', () => {
            localStorage.setItem('confidenceThreshold', confInput.value);
        });
    }

    const feedbackToggle = document.getElementById('feedback-toggle');
    if (feedbackToggle) {
        feedbackToggle.checked = localStorage.getItem('feedbackEnabled') !== 'false';
        feedbackToggle.addEventListener('change', () => {
            localStorage.setItem('feedbackEnabled', feedbackToggle.checked);
        });
    }

    const modeSelect = document.getElementById('feedback-mode');
    if (modeSelect) {
        modeSelect.value = localStorage.getItem('feedbackMode') || 'persistent';
        modeSelect.addEventListener('change', () => {
            localStorage.setItem('feedbackMode', modeSelect.value);
        });
    }

    const ttsSelect = document.getElementById('tts-select');
    const reloadBtn = document.getElementById('reload-tts');

    async function loadTtsModels() {
        const res = await fetch('/tts/models');
        const data = await res.json();
        if (!ttsSelect) return;
        ttsSelect.innerHTML = '';
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (data.selected === m) opt.selected = true;
            ttsSelect.appendChild(opt);
        });
    }

    if (ttsSelect) {
        loadTtsModels();
        ttsSelect.addEventListener('change', async () => {
            await fetch('/tts/select?name=' + encodeURIComponent(ttsSelect.value), { method: 'POST' });
        });
    }
    if (reloadBtn) reloadBtn.addEventListener('click', loadTtsModels);
});
