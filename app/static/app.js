// Client-side logic for microphone streaming
let micButton = null;
let visualizerCanvas = null;
let ws = null;
let mediaRecorder = null;
let sttOutput = null;
let tooltip = null;
let voiceIndicator = null;
let voiceRing = null;
let audioContext = null;
let analyser = null;
let animationId = null;
let voiceActivated = false;
let vadTimeout = null;
const vadThreshold = 0.02; // simple RMS threshold
const silenceTimeout = 1000; // ms
let micStream = null;
let feedbackThreshold = parseFloat(localStorage.getItem('confidenceThreshold') || '0.65');
let feedbackEnabled = localStorage.getItem('feedbackEnabled') !== 'false';
let feedbackMode = localStorage.getItem('feedbackMode') || 'persistent';
let aiOutputElem = null;
let chatInput = null;
let speakBtn = null;
let stopBtn = null;
let ttsTimer = null;
let ttsQueue = [];
let speaking = false;
let speakWs = null;
let currentAudio = null;

function setup() {
    micButton = document.getElementById('mic-button');
    visualizerCanvas = document.getElementById('visualizer');
    sttOutput = document.getElementById('stt-output');
    tooltip = document.getElementById('tooltip');
    voiceIndicator = document.getElementById('voice-indicator');
    voiceRing = document.getElementById('voice-ring');
    const ttsInput = document.getElementById('tts-input');
    const ttsPlay = document.getElementById('tts-play');
    aiOutputElem = document.getElementById('ai-output');
    chatInput = document.querySelector('.input-area input[type="text"]');
    const chatForm = document.querySelector('.input-area');
    speakBtn = document.getElementById('speak-now');
    stopBtn = document.getElementById('stop-speak');

    voiceActivated = localStorage.getItem('voiceActivated') === 'true';

    if (micButton) micButton.addEventListener('click', toggleMic);
    if (sttOutput) {
        sttOutput.addEventListener('mouseover', showTooltip);
        sttOutput.addEventListener('mouseout', hideTooltip);
    }
    if (ttsPlay && ttsInput) {
        ttsPlay.addEventListener('click', () => speakText(ttsInput.value));
    }
    if (chatForm && chatInput) {
        chatForm.addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const text = chatInput.value.trim();
            if (!text) return;
            chatInput.value = '';
            appendMessage(text, 'user', Date.now());
            let result = '';
            try {
                const res = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });
                const data = await res.json();
                result = data.result;
            } catch (err) {
                result = '';
            }
            if (!result || result.startsWith('[LLM unreachable') || result.includes('Model unavailable')) {
                result = 'LLM not found';
            }
            if (aiOutputElem) {
                aiOutputElem.value = result;
                if (ttsTimer) clearTimeout(ttsTimer);
                ttsTimer = setTimeout(() => speakText(aiOutputElem.value), 1000);
            }
            appendMessage(result, 'assistant', Date.now());

        });
    }
    if (speakBtn && aiOutputElem) {
        speakBtn.addEventListener('click', () => {
            if (ttsTimer) { clearTimeout(ttsTimer); ttsTimer = null; }
            speakText(aiOutputElem.value);
        });
    }
    if (stopBtn) {
        stopBtn.addEventListener('click', stopSpeaking);
    }
    if (aiOutputElem) {
        aiOutputElem.addEventListener('input', () => {
            if (ttsTimer) { clearTimeout(ttsTimer); ttsTimer = null; }
        });
    }
}

async function toggleMic() {
    if (audioContext) {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(micStream);
        analyser = audioContext.createAnalyser();
        source.connect(analyser);

        visualize();
        if (!voiceActivated) {
            beginStreaming(micStream);
        }
        if (voiceIndicator) voiceIndicator.classList.add('active');
        if (voiceRing) voiceRing.classList.add('active');
    } catch (err) {
        console.error('Mic access denied:', err);
        alert('Microphone access denied.');
    }
}

function stopRecording() {
    stopStreaming();
    cancelAnimationFrame(animationId);
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (micStream) {
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
    }
    if (vadTimeout) {
        clearTimeout(vadTimeout);
        vadTimeout = null;
    }
    if (voiceIndicator) voiceIndicator.classList.remove('active');
    if (voiceRing) voiceRing.classList.remove('active');
}

function beginStreaming(stream) {
    if (mediaRecorder) return;
    ws = new WebSocket(`ws://${window.location.host}/ws/audio`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        appendTranscription(data.text, data.confidence, data.timestamp, data.audio);
        if (data.text) {
            const ts = data.timestamp ? data.timestamp * 1000 : Date.now();
            appendMessage(data.text, 'user', ts);
        }
    };

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.addEventListener('dataavailable', (event) => {
        if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(event.data);
        }
    });
    mediaRecorder.start(250);
    micButton.classList.add('active');
    if (voiceRing) voiceRing.classList.add('active');
}

function stopStreaming() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        mediaRecorder = null;
    }
    if (ws) {
        ws.close();
        ws = null;
    }
    micButton.classList.remove('active');
    if (voiceRing) voiceRing.classList.remove('active');
}


function visualize() {
    const canvasCtx = visualizerCanvas.getContext('2d');
    analyser.fftSize = 256;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        animationId = requestAnimationFrame(draw);
        analyser.getByteTimeDomainData(dataArray);

        if (voiceActivated) {
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                const v = (dataArray[i] - 128) / 128;
                sum += v * v;
            }
            const rms = Math.sqrt(sum / bufferLength);
            if (rms > vadThreshold) {
                if (!mediaRecorder) beginStreaming(micStream);
                if (vadTimeout) {
                    clearTimeout(vadTimeout);
                    vadTimeout = null;
                }
            } else if (mediaRecorder && !vadTimeout) {
                vadTimeout = setTimeout(() => {
                    stopStreaming();
                }, silenceTimeout);
            }
        }

        canvasCtx.fillStyle = '#f3f3f3';
        canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = '#6200ee';
        canvasCtx.beginPath();
        const sliceWidth = visualizerCanvas.width / bufferLength;
        let x = 0;
        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * visualizerCanvas.height / 2;
            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        canvasCtx.lineTo(visualizerCanvas.width, visualizerCanvas.height / 2);
        canvasCtx.stroke();
    }
    draw();
}

function appendMessage(text, role = 'user', timestamp = Date.now()) {
    const messagesDiv = document.querySelector('.messages');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = `${role === 'user' ? 'You' : 'AI'} • ${new Date(timestamp).toLocaleTimeString()}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    div.appendChild(meta);
    div.appendChild(bubble);
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function appendTranscription(text, confidence, timestamp, audioB64) {
    if (!sttOutput) return;
    feedbackThreshold = parseFloat(localStorage.getItem('confidenceThreshold') || feedbackThreshold);
    feedbackEnabled = localStorage.getItem('feedbackEnabled') !== 'false';
    feedbackMode = localStorage.getItem('feedbackMode') || feedbackMode;

    const span = document.createElement('span');
    if (feedbackEnabled && confidence !== undefined && confidence < feedbackThreshold) {
        span.classList.add('uncertain');
        if (feedbackMode === 'temporary') {
            setTimeout(() => span.classList.remove('uncertain'), 5000);
        }
    }
    span.textContent = text + ' ';
    if (confidence !== undefined) span.dataset.confidence = confidence.toFixed(2);
    if (timestamp) span.dataset.timestamp = new Date(timestamp * 1000).toLocaleTimeString();
    if (audioB64) span.dataset.audio = audioB64;

    if (audioB64) {
        const btn = document.createElement('button');
        btn.textContent = '⏵';
        btn.className = 'replay';
        btn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            const blob = b64ToBlob(audioB64, 'audio/webm');
            const url = URL.createObjectURL(blob);
            const a = new Audio(url);
            a.play();
        });
        span.appendChild(btn);
    }

    sttOutput.appendChild(span);
    sttOutput.scrollTop = sttOutput.scrollHeight;
}

function showTooltip(e) {
    const target = e.target.closest('span');
    if (!target || !tooltip) return;
    if (!target.dataset.confidence) return;
    let text = `Conf: ${target.dataset.confidence}`;
    if (target.dataset.timestamp) text += ` | ${target.dataset.timestamp}`;
    tooltip.textContent = text;
    tooltip.style.left = e.pageX + 'px';
    tooltip.style.top = (e.pageY - 30) + 'px';
    tooltip.style.display = 'block';
}

function hideTooltip() {
    if (tooltip) tooltip.style.display = 'none';
}

function b64ToBlob(b64, mime) {
    const byteChars = atob(b64);
    const byteNums = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNums[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNums)], { type: mime });
}

document.addEventListener('DOMContentLoaded', setup);

function speakText(text) {
    if (!text) return;
    ttsQueue.push(text);
    processSpeechQueue();
}

function processSpeechQueue() {
    if (speaking || ttsQueue.length === 0) return;
    const text = ttsQueue.shift();
    speaking = true;
    if (stopBtn) stopBtn.style.display = 'inline-block';
    speakWs = new WebSocket(`ws://${window.location.host}/ws/tts`);
    const chunks = [];
    speakWs.binaryType = 'arraybuffer';
    speakWs.onmessage = (ev) => {
        if (ev.data.byteLength === 0) {
            const blob = new Blob(chunks, { type: 'audio/wav' });
            const url = URL.createObjectURL(blob);
            currentAudio = new Audio(url);
            currentAudio.addEventListener('ended', () => {
                speaking = false;
                if (stopBtn) stopBtn.style.display = 'none';
                processSpeechQueue();
            });
            currentAudio.play();
            speakWs.close();
        } else {
            chunks.push(ev.data);
        }
    };
    speakWs.onopen = () => speakWs.send(text);
}

function stopSpeaking() {
    if (speakWs) { speakWs.close(); speakWs = null; }
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    speaking = false;
    if (stopBtn) stopBtn.style.display = 'none';
    ttsQueue = [];
}
