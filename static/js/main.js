document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("navToggle");
  const links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open);
    });
  }

  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 6000);
  });

  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(target).classList.add("active");
    });
  });

  const textarea = document.getElementById("review_text");
  const counter = document.getElementById("charCount");
  if (textarea && counter) {
    const update = () => (counter.textContent = `${textarea.value.length} characters`);
    update();
    textarea.addEventListener("input", update);
  }

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("csv_file");
  const filenameEl = document.getElementById("dzFilename");
  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    ["dragenter", "dragover"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files[0];
      if (file) {
        fileInput.files = e.dataTransfer.files;
        if (filenameEl) filenameEl.textContent = `Selected: ${file.name}`;
      }
    });
    fileInput.addEventListener("change", () => {
      if (fileInput.files[0] && filenameEl) {
        filenameEl.textContent = `Selected: ${fileInput.files[0].name}`;
      }
    });
  }

  document.querySelectorAll(".cm-fill[data-target]").forEach((el) => {
    const target = el.dataset.target;
    requestAnimationFrame(() => {
      el.style.width = target + "%";
    });
  });
});