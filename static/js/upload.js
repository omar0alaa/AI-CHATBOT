// static/js/upload.js
// Handles file upload for Proto AI

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput) return;
    fileInput.addEventListener('change', async function() {
        if (!fileInput.files.length) return;
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        document.getElementById('uploadStatus').innerText = 'Uploading...';
        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('uploadStatus').innerText = 'File uploaded and indexed!';
                if (window.showUploadedFile) window.showUploadedFile(data.filename);
            } else {
                document.getElementById('uploadStatus').innerText = 'Upload failed: ' + (data.error || 'Unknown error');
            }
        } catch (err) {
            document.getElementById('uploadStatus').innerText = 'Upload failed: ' + err;
        }
        fileInput.value = '';
    });
});
