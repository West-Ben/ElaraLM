document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('voice-toggle');
    if (!toggle) return;
    toggle.checked = localStorage.getItem('voiceActivated') === 'true';
    toggle.addEventListener('change', () => {
        localStorage.setItem('voiceActivated', toggle.checked);
    });
});
