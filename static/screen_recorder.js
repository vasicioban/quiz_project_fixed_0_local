// static/screen_recorder.js
let mediaRecorder;
let recordedChunks = [];
let isRecording = false; 
let stream;

function startRecording() {
    return navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true
    }).then(s => {
        stream = s;
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = event => {
            recordedChunks.push(event.data);
        };
        
        mediaRecorder.start();
        isRecording = true;
        console.log("Recording started");
    });
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false; 
        console.log("Recording stopped");
    }
}

function getRecordedChunks() {
    return recordedChunks;
}

window.ScreenRecorder = {
    startRecording,
    stopRecording,
    getRecordedChunks,
    isRecording, 
    stream 
};
