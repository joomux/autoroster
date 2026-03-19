"use strict";

// ---------------------------------------------------------------------------
// File drop zone
// ---------------------------------------------------------------------------
(function () {
  const dropZone = document.getElementById("drop-zone");
  const input = document.getElementById("screenshot");
  const inner = document.getElementById("drop-zone-inner");
  const preview = document.getElementById("drop-preview");
  const previewImg = document.getElementById("preview-img");
  const filename = document.getElementById("drop-filename");
  const removeBtn = document.getElementById("remove-img");
  const submitBtn = document.getElementById("submit-btn");

  if (!dropZone) return;

  // Click anywhere in the drop zone to open file picker
  dropZone.addEventListener("click", (e) => {
    if (e.target === removeBtn || removeBtn.contains(e.target)) return;
    input.click();
  });

  input.addEventListener("change", () => {
    if (input.files && input.files[0]) {
      showPreview(input.files[0]);
    }
  });

  // Drag-and-drop
  ["dragenter", "dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
    });
  });
  dropZone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      // Assign to the file input via DataTransfer
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      showPreview(file);
    }
  });

  // Remove image
  removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    input.value = "";
    inner.hidden = false;
    preview.hidden = true;
    filename.textContent = "";
    previewImg.src = "";
  });

  function showPreview(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      inner.hidden = true;
      preview.hidden = false;
    };
    reader.readAsDataURL(file);
  }

  // Show loading state on submit
  const form = document.getElementById("upload-form");
  if (form && submitBtn) {
    form.addEventListener("submit", () => {
      submitBtn.disabled = true;
      submitBtn.textContent = "Parsing…";
    });
  }
})();
