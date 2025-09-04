const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadListDiv = document.getElementById("upload-list");
const processedListDiv = document.getElementById("processed-list");
const processBtn = document.getElementById("process-btn");
const downloadBtn = document.getElementById("download-btn");
const statusDiv = document.getElementById("status");

// Utility: show status message
function showStatus(msg, success=true, persistent=false) {
    statusDiv.textContent = msg;
    statusDiv.style.color = success ? "#76ff03" : "#ff5252";
    statusDiv.style.display = "block";

    if (!persistent) {
        setTimeout(()=>statusDiv.style.display="none", 8000); // auto-hide after 8s if not persistent
    }
}

// Enable/disable buttons based on selections
function updateButtons() {
    processBtn.disabled = uploadListDiv.querySelectorAll("input:checked").length === 0;
    downloadBtn.disabled = processedListDiv.querySelectorAll("input:checked").length === 0;
}

// Click to open file dialog
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

// Drag & drop events
dropZone.addEventListener("dragover", e=>{ e.preventDefault(); dropZone.classList.add("hover"); });
dropZone.addEventListener("dragleave", ()=>dropZone.classList.remove("hover"));
dropZone.addEventListener("drop", e=>{
    e.preventDefault();
    dropZone.classList.remove("hover");
    uploadFiles(e.dataTransfer.files);
});

// Upload files
function uploadFiles(files) {
    showStatus("⬆️ Uploading files...", true, true); // persistent
    const formData = new FormData();
    for(let f of files) formData.append("files[]", f);

    fetch("/upload", {method:"POST", body:formData})
    .then(res=>res.json())
    .then(()=>{
        refreshUploadList();
        showStatus("✅ Files uploaded", true); // now auto-hide after default time
    });
}

// Refresh lists
function refreshUploadList() {
    fetch("/upload_list")
    .then(res=>res.json())
    .then(data=>{
        uploadListDiv.innerHTML = "";
        data.files.forEach(f=>{
            const div = document.createElement("div");
            const checkbox = document.createElement("input");
            checkbox.type="checkbox"; checkbox.value=f; checkbox.id="upload-"+f;
            checkbox.addEventListener("change", updateButtons);
            const label = document.createElement("label");
            label.htmlFor="upload-"+f;
            label.textContent=f;
            div.appendChild(checkbox);
            div.appendChild(label);
            uploadListDiv.appendChild(div);
        });
        updateButtons();
    });
}

function refreshProcessedList() {
    fetch("/processed_files")
    .then(res=>res.json())
    .then(data=>{
        processedListDiv.innerHTML = "";
        data.files.forEach(f=>{
            const div = document.createElement("div");
            const checkbox = document.createElement("input");
            checkbox.type="checkbox"; checkbox.value=f; checkbox.id="processed-"+f;
            checkbox.addEventListener("change", updateButtons);
            const label = document.createElement("label");
            label.htmlFor="processed-"+f;
            label.textContent=f;
            div.appendChild(checkbox);
            div.appendChild(label);
            processedListDiv.appendChild(div);
        });
        updateButtons();
    });
}

// Poll processed list every 3 seconds
setInterval(refreshProcessedList, 3000);

// Start processing
function startProcessing() {
    const selected = Array.from(uploadListDiv.querySelectorAll("input:checked")).map(cb=>cb.value);
    if (!selected.length) return;

    showStatus("🔄 Processing started...", true, true); // persistent

    fetch("/start_processing", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({files:selected})
    }).then(()=> {
        refreshUploadList();
        waitForProcessingCompletion(selected);
    });
}

// Poll until all files are processed
function waitForProcessingCompletion(files) {
    const interval = setInterval(()=>{
        fetch("/processed_files")
        .then(res=>res.json())
        .then(data=>{
            const processedFiles = data.files;
            const remaining = files.filter(f => !processedFiles.includes(f));
            if (remaining.length === 0) {
                clearInterval(interval);
                showStatus("✅ Processing completed", true); // auto-hide after 8s
                refreshProcessedList();
            }
        });
    }, 2000); // check every 2 seconds
}

// Download selected files
function downloadSelected() {
    const selected = Array.from(processedListDiv.querySelectorAll("input:checked")).map(cb=>cb.value);
    if (!selected.length) return;

    showStatus("⬇️ Downloading...", true, true); // persistent

    let completed = 0;
    selected.forEach(f=>{
        fetch("/download/" + encodeURIComponent(f))
        .then(resp => resp.blob())
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = f;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            completed++;
            if (completed === selected.length) {
                showStatus("✅ Download completed", true); // now auto-hide
            }
        });
    });
}

// Apply settings
function applySettings() {
    const settings = {
        codec: document.getElementById("codec").value,
        bitrate: document.getElementById("bitrate").value,
        samplerate: document.getElementById("samplerate").value,
        channels: document.getElementById("channels").value
    };
    fetch("/settings", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(settings)
    })
    .then(res=>res.json())
    .then(()=>showStatus("✅ Settings applied"));
}

// Initial refresh
refreshUploadList();
refreshProcessedList();
