// Client-side logic for microphone streaming
let micButton = null;
let visualizerCanvas = null;
let ws = null;
let mediaRecorder = null;
let audioContext = null;
let analyser = null;
let animationId = null;

function setup() {
    micButton = document.getElementById('mic-button');
    visualizerCanvas = document.getElementById('visualizer');
    if (!micButton) return;

    micButton.addEventListener('click', toggleMic);
}

async function toggleMic() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        source.connect(analyser);

        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.addEventListener('dataavailable', event => {
            if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(event.data);
            }
        });
        mediaRecorder.start(250); // send in chunks every 250ms

        ws = new WebSocket(`ws://${window.location.host}/ws/audio`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            appendMessage(data.text);
        };

        visualize();
        micButton.classList.add('active');
    } catch (err) {
        console.error('Mic access denied:', err);
        alert('Microphone access denied.');
    }
}

function stopRecording() {
    if (mediaRecorder) mediaRecorder.stop();
    if (ws) ws.close();
    cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();
    micButton.classList.remove('active');
}

function visualize() {
    const canvasCtx = visualizerCanvas.getContext('2d');
    analyser.fftSize = 256;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        animationId = requestAnimationFrame(draw);
        analyser.getByteTimeDomainData(dataArray);
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

function appendMessage(text) {
    const messagesDiv = document.querySelector('.messages');
    const div = document.createElement('div');
    div.className = 'message stt';
    div.textContent = text;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

document.addEventListener('DOMContentLoaded', setup);
