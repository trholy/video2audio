// --------------------
// DOM Elements
// --------------------
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadListDiv = document.getElementById("upload-list");
const processedListDiv = document.getElementById("processed-list");
const processBtn = document.getElementById("process-btn");
const downloadBtn = document.getElementById("download-btn");
const clearBtn = document.getElementById("clear-btn");
const statusDiv = document.getElementById("status");

// --------------------
// Utility Functions
// --------------------
function showStatus(msg, success = true, persistent = false) {
    statusDiv.textContent = msg;
    statusDiv.style.color = success ? "#76ff03" : "#ff5252";
    statusDiv.style.display = "block";

    if (!persistent) {
        setTimeout(() => statusDiv.style.display = "none", 8000);
    }
}

function updateButtons() {
    processBtn.disabled = uploadListDiv.querySelectorAll("input:checked").length === 0;
    downloadBtn.disabled = processedListDiv.querySelectorAll("input:checked").length === 0;
    clearBtn.disabled = processedListDiv.querySelectorAll("input").length === 0;
}

// --------------------
// Upload Handlers
// --------------------
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("hover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("hover"));
dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("hover");
    uploadFiles(e.dataTransfer.files);
});

function uploadFiles(files) {
    if (!files.length) return;
    showStatus("⬆️ Uploading files...", true, true);

    const formData = new FormData();
    for (let f of files) formData.append("files[]", f);

    fetch("/upload", { method: "POST", body: formData })
        .then(res => res.json())
        .then(() => {
            refreshUploadList();
            showStatus("✅ Files uploaded");
        })
        .catch(err => {
            console.error(err);
            showStatus("❌ Upload failed", false);
        });
}

// --------------------
// Refresh Lists
// --------------------
function refreshUploadList() {
    fetch("/upload_list")
        .then(res => res.json())
        .then(data => {
            uploadListDiv.innerHTML = "";
            if (!data.files.length) {
                uploadListDiv.innerHTML = "<em>No uploaded files</em>";
            } else {
                data.files.forEach(f => {
                    const div = document.createElement("div");
                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.value = f;
                    checkbox.id = "upload-" + f;
                    checkbox.addEventListener("change", updateButtons);

                    const label = document.createElement("label");
                    label.htmlFor = "upload-" + f;
                    label.textContent = f;

                    div.appendChild(checkbox);
                    div.appendChild(label);
                    uploadListDiv.appendChild(div);
                });
            }
            updateButtons();
        });
}

function refreshProcessedList() {
    fetch("/processed_files")
        .then(res => res.json())
        .then(data => {
            processedListDiv.innerHTML = "";
            if (!data.files.length) {
                processedListDiv.innerHTML = "<em>No processed files</em>";
            } else {
                data.files.forEach(f => {
                    const div = document.createElement("div");
                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.value = f;
                    checkbox.id = "processed-" + f;
                    checkbox.addEventListener("change", updateButtons);

                    const label = document.createElement("label");
                    label.htmlFor = "processed-" + f;
                    label.textContent = f;

                    div.appendChild(checkbox);
                    div.appendChild(label);
                    processedListDiv.appendChild(div);
                });
            }
            updateButtons();
        });
}

// --------------------
// Processing
// --------------------
function startProcessing() {
    const selected = Array.from(uploadListDiv.querySelectorAll("input:checked")).map(cb => cb.value);
    if (!selected.length) return;

    showStatus("🔄 Processing started...", true, true);

    fetch("/start_processing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: selected })
    }).then(() => {
        refreshUploadList();
        pollProcessingCompletion(selected);
    }).catch(err => {
        console.error(err);
        showStatus("❌ Failed to start processing", false);
    });
}

function pollProcessingCompletion(files) {
    const interval = setInterval(() => {
        fetch("/processed_files")
            .then(res => res.json())
            .then(data => {
                const remaining = files.filter(f => !data.files.includes(f));
                refreshProcessedList();
                if (remaining.length === 0) {
                    clearInterval(interval);
                    showStatus("✅ Processing completed");
                }
            });
    }, 2000);
}

// --------------------
// Downloads
// --------------------
function downloadSelected() {
    const selected = Array.from(processedListDiv.querySelectorAll("input:checked")).map(cb => cb.value);
    if (!selected.length) return;

    showStatus("⬇️ Downloading...", true, true);

    selected.forEach(f => {
        fetch("/download/" + encodeURIComponent(f))
        .then(resp => resp.blob())
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = f;

            // Append and click, then immediately remove
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            // Release the object URL
            URL.revokeObjectURL(url);
        });
    });

    showStatus("✅ Download completed", true);
}

// --------------------
// Clear Processed Files
// --------------------
function clearProcessed() {
    if (!confirm("⚠️ This will delete all processed files permanently. Continue?")) return;

    fetch("/clear_processed", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            refreshProcessedList();
            showStatus(`✅ Deleted files: ${data.deleted.join(", ")}`);
        })
        .catch(err => {
            console.error(err);
            showStatus("❌ Failed to clear processed files", false);
        });
}

function clearUploads() {
    const selected = Array.from(uploadListDiv.querySelectorAll("input:checked")).map(cb => cb.value);
    if (!selected.length) return;

    if (!confirm("⚠️ This will delete the selected uploaded files permanently. Continue?")) return;

    fetch("/clear_uploads", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({files: selected})
    })
    .then(res => res.json())
    .then(data => {
        refreshUploadList();
        showStatus(`✅ Deleted uploads: ${data.deleted.join(", ")}`, true);
    })
    .catch(err => {
        console.error(err);
        showStatus("❌ Failed to clear uploads", false);
    });
}

// --------------------
// Settings
// --------------------
function applySettings() {
    const settings = {
        codec: document.getElementById("codec").value,
        bitrate: document.getElementById("bitrate").value,
        samplerate: document.getElementById("samplerate").value,
        channels: document.getElementById("channels").value
    };

    fetch("/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings)
    }).then(() => showStatus("✅ Settings applied"));
}

// --------------------
// Initialize
// --------------------
refreshUploadList();
refreshProcessedList();
updateButtons();
