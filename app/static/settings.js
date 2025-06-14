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
});
