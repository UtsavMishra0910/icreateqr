let qrScanner = null;
let isProcessing = false;
let lastScanned = "";
let lastScanAt = 0;

const statusBox = document.getElementById("scan-status");
const startButton = document.getElementById("start-scan");
const stopButton = document.getElementById("stop-scan");

function setStatus(type, message) {
    statusBox.className = `status ${type}`;
    statusBox.textContent = message;
}

function extractRegNo(decodedText) {
    if (!decodedText) return null;
    if (decodedText.startsWith("REG:")) {
        return decodedText.replace("REG:", "").trim();
    }
    return decodedText.trim();
}

async function onScanSuccess(decodedText) {
    const regNo = extractRegNo(decodedText);
    if (!regNo || isProcessing) return;

    // Debounce repeated detections from the same QR within 3 seconds.
    const now = Date.now();
    if (lastScanned === regNo && now - lastScanAt < 3000) {
        return;
    }

    isProcessing = true;
    lastScanned = regNo;
    lastScanAt = now;

    try {
        const body = new URLSearchParams({ reg_no: regNo });
        const response = await fetch("/attendance/mark", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString(),
        });
        const payload = await response.json();

        if (payload.status === "success") {
            setStatus("success", payload.message);
        } else if (payload.status === "duplicate") {
            setStatus("error", payload.message);
        } else {
            setStatus("error", payload.detail || "Scan failed");
        }
    } catch (error) {
        setStatus("error", "Unable to mark attendance. Check network/server.");
    } finally {
        isProcessing = false;
    }
}

async function startScanner() {
    if (!window.Html5Qrcode) {
        setStatus("error", "Scanner library failed to load");
        return;
    }
    if (!qrScanner) {
        qrScanner = new Html5Qrcode("qr-reader");
    }
    try {
        await qrScanner.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 250, height: 250 } },
            onScanSuccess
        );
        setStatus("idle", "Scanner is running...");
    } catch (err) {
        setStatus("error", "Could not access webcam. Please allow camera permission.");
    }
}

async function stopScanner() {
    if (qrScanner && qrScanner.isScanning) {
        await qrScanner.stop();
        setStatus("idle", "Scanner stopped.");
    }
}

if (startButton && stopButton) {
    startButton.addEventListener("click", startScanner);
    stopButton.addEventListener("click", stopScanner);
}
