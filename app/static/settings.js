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
    const addBtn = document.getElementById('add-tts');
    // Modal elements
    const ttsModal = document.getElementById('tts-modal');
    const ttsModalSelect = document.getElementById('tts-modal-select');
    const ttsModalDownload = document.getElementById('tts-modal-download');
    const ttsModalCancel = document.getElementById('tts-modal-cancel');
    const ttsModalStatus = document.getElementById('tts-modal-status');

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
    if (addBtn && ttsModal && ttsModalSelect && ttsModalDownload && ttsModalCancel) {
        addBtn.addEventListener('click', async () => {
            ttsModalStatus.textContent = '';
            ttsModalSelect.innerHTML = '<option>Loading...</option>';
            ttsModal.style.display = 'flex';
            try {
                const res = await fetch('/tts/available');
                const data = await res.json();
                ttsModalSelect.innerHTML = '';
                if (data.models && data.models.length) {
                    data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        ttsModalSelect.appendChild(opt);
                    });
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'No models available';
                    ttsModalSelect.appendChild(opt);
                }
            } catch (err) {
                ttsModalSelect.innerHTML = '';
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'Error loading models';
                ttsModalSelect.appendChild(opt);
            }
        });

        ttsModalCancel.addEventListener('click', () => {
            ttsModal.style.display = 'none';
            ttsModalStatus.textContent = '';
        });

        ttsModalDownload.addEventListener('click', async () => {
            const name = ttsModalSelect.value;
            if (!name) {
                ttsModalStatus.textContent = 'Please select a model.';
                return;
            }
            ttsModalStatus.textContent = 'Downloading...';
            try {
                const resp = await fetch('/tts/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });
                if (resp.ok) {
                    await loadTtsModels();
                    ttsModalStatus.textContent = 'Model downloaded!';
                    setTimeout(() => {
                        ttsModal.style.display = 'none';
                        ttsModalStatus.textContent = '';
                    }, 1000);
                } else {
                    const err = await resp.json();
                    ttsModalStatus.textContent = 'Error: ' + (err.error || 'unknown');
                }
            } catch (e) {
                ttsModalStatus.textContent = 'Error downloading model.';
            }
        });
    }

    const sttSelect = document.getElementById('stt-select');
    const reloadStt = document.getElementById('reload-stt');

    async function loadSttModels() {
        const res = await fetch('/stt/models');
        const data = await res.json();
        if (!sttSelect) return;
        sttSelect.innerHTML = '';
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (data.selected === m) opt.selected = true;
            sttSelect.appendChild(opt);
        });
    }

    if (sttSelect) {
        loadSttModels();
        sttSelect.addEventListener('change', async () => {
            await fetch('/stt/select?name=' + encodeURIComponent(sttSelect.value), { method: 'POST' });
        });
    }
    if (reloadStt) reloadStt.addEventListener('click', loadSttModels);

    const llmSelect = document.getElementById('llm-select');
    const llmSource = document.getElementById('llm-source');
    const reloadLlm = document.getElementById('reload-llm');

    async function loadLlmModels() {
        const source = llmSource ? llmSource.value : 'local';
        const res = await fetch('/llm/models?source=' + source);
        const data = await res.json();
        if (!llmSelect) return;
        llmSelect.innerHTML = '';
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            llmSelect.appendChild(opt);
        });
    }

    if (llmSource) llmSource.addEventListener('change', loadLlmModels);
    if (llmSelect) {
        loadLlmModels();
        llmSelect.addEventListener('change', async () => {
            await fetch('/llm/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: llmSource ? llmSource.value : 'local', name: llmSelect.value })
            });
        });
    }
    if (reloadLlm) reloadLlm.addEventListener('click', loadLlmModels);
});
