const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const uploadButton = document.getElementById('uploadButton');
const fileListContainer = document.getElementById('fileList');
const errorContainer = document.getElementById('errorContainer');
const themeToggle = document.getElementById('themeToggle');
const themeToggleText = document.getElementById('themeToggleText');

const uploadedFiles = new Set();
const fileTypes = [
  {
    iconSrc: "icons/audio_file.svg",
    extensions: [".mp3", ".flac", ".wav", ".wma", ".aac", ".ogg", ".midi", ".m4a"],
  },
  {
    iconSrc: "icons/video_file.svg",
    extensions: [".mp4", ".mkv", ".avi", ".mpeg", ".wmv", ".mov"],
  },
  {
    iconSrc: "icons/docs.svg",
    extensions: [".odt", ".doc", ".docx", ".rtf"],
  },
  {
    iconSrc: "icons/picture_as_pdf.svg",
    extensions: [".pdf"],
  },
  {
    iconSrc: "icons/folder_zip.svg",
    extensions: [".zip", ".tar.gz", ".tar.xz", ".rar", ".7z"],
  },
  {
    iconSrc: "icons/text_snippet.svg",
    extensions: [".txt", ".md"],
  },
  {
    iconSrc: "icons/image.svg",
    extensions: [
      ".png",
      ".jpg",
      ".jpeg",
      ".gif",
      ".tif",
      ".tiff",
      ".webp",
      ".bmp",
      ".raw",
    ],
  },
];

const transferConfig = {
  parallelChunks: 8,
  chunkSizeBytes: 4 * 1024 * 1024,
  maxFileSizeBytes: 100 * 1024 * 1024 * 1024,
};

const MAX_CHUNK_RETRIES = 3;
const THEME_STORAGE_KEY = 'mizban-theme';
const LIGHT_THEME = 'light';
const DARK_THEME = 'dark';

function applyTheme(theme) {
  const resolvedTheme = theme === DARK_THEME ? DARK_THEME : LIGHT_THEME;
  document.documentElement.setAttribute('data-theme', resolvedTheme);

  if (!themeToggle) {
    return;
  }

  const isDark = resolvedTheme === DARK_THEME;
  themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
  if (themeToggleText) {
    themeToggleText.textContent = isDark ? 'Light mode' : 'Dark mode';
  }
}

function resolveInitialTheme() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === LIGHT_THEME || stored === DARK_THEME) {
      return stored;
    }
  } catch (_err) {
    // ignore storage errors
  }

  const documentTheme = document.documentElement.getAttribute('data-theme');
  if (documentTheme === LIGHT_THEME || documentTheme === DARK_THEME) {
    return documentTheme;
  }

  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return DARK_THEME;
  }
  return LIGHT_THEME;
}

function persistTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (_err) {
    // ignore storage errors
  }
}

function initTheme() {
  applyTheme(resolveInitialTheme());

  if (!themeToggle) {
    return;
  }

  themeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') === DARK_THEME ? DARK_THEME : LIGHT_THEME;
    const nextTheme = currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME;
    applyTheme(nextTheme);
    persistTheme(nextTheme);
  });
}

async function loadTransferSettings() {
  try {
    const response = await fetch('/settings/', { method: 'GET' });
    if (!response.ok) {
      return;
    }
    const settings = await response.json();

    const parallel = Number(settings.parallel_chunks);
    if (Number.isFinite(parallel) && parallel > 0) {
      transferConfig.parallelChunks = Math.min(64, Math.floor(parallel));
    }

    const chunkSize = Number(settings.chunk_size_bytes);
    if (Number.isFinite(chunkSize) && chunkSize > 0) {
      transferConfig.chunkSizeBytes = Math.max(256 * 1024, Math.floor(chunkSize));
    }

    const maxFileSize = Number(settings.max_file_size_bytes);
    if (Number.isFinite(maxFileSize) && maxFileSize > 0) {
      transferConfig.maxFileSizeBytes = maxFileSize;
    }
  } catch (_err) {
    // keep defaults
  }
}

/**
 * Uploads a file using chunked parallel streams and falls back to legacy upload.
 * @param {File} file
 * @param {HTMLElement} progressContainer
 * @param {HTMLElement} progressBar
 * @param {HTMLElement} fileCard
 * @returns {Promise<boolean>}
 */
async function upload_file(file, progressContainer, progressBar, fileCard) {
  if (!progressBar || !progressContainer) {
    return false;
  }

  if (file.size > transferConfig.maxFileSizeBytes) {
    showError(`File exceeds maximum size: ${Math.floor(transferConfig.maxFileSizeBytes / (1024 * 1024 * 1024))} GB.`);
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  const chunkedResult = await upload_file_chunked(file, progressContainer, progressBar, fileCard);
  if (chunkedResult === null) {
    return upload_file_legacy(file, progressContainer, progressBar, fileCard);
  }
  return chunkedResult;
}

/**
 * Legacy upload endpoint fallback for older servers.
 * @param {File} file
 * @param {HTMLElement} progressContainer
 * @param {HTMLElement} progressBar
 * @param {HTMLElement} fileCard
 * @returns {Promise<boolean>}
 */
function upload_file_legacy(file, progressContainer, progressBar, fileCard) {
  return new Promise((resolve) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    let determinateMode = false;
    let settled = false;

    xhr.upload.onprogress = (event) => {
      if (!progressBar) return;
      if (event.lengthComputable) {
        if (!determinateMode) {
          prepareDeterminateProgress(progressBar);
          determinateMode = true;
        }
        const percent = Math.min(100, Math.max(0, (event.loaded / event.total) * 100));
        progressBar.style.width = `${percent}%`;
      }
    };

    xhr.onreadystatechange = () => {
      if (xhr.readyState !== XMLHttpRequest.DONE || settled) return;

      if (xhr.status >= 200 && xhr.status < 300) {
        finalizeProgress(progressContainer, progressBar, fileCard, true);
        settled = true;
        resolve(true);
      } else {
        showError('Could not upload the file.');
        finalizeProgress(progressContainer, progressBar, fileCard, false);
        settled = true;
        resolve(false);
      }
    };

    xhr.onerror = () => {
      if (settled) return;
      showError('Network error occurred.');
      finalizeProgress(progressContainer, progressBar, fileCard, false);
      settled = true;
      resolve(false);
    };

    xhr.open('POST', '/upload/');
    xhr.responseType = 'json';
    xhr.send(formData);
  });
}

/**
 * High-throughput chunked upload path.
 * Returns null when endpoint is unavailable and fallback should be used.
 * @param {File} file
 * @param {HTMLElement} progressContainer
 * @param {HTMLElement} progressBar
 * @param {HTMLElement} fileCard
 * @returns {Promise<boolean|null>}
 */
async function upload_file_chunked(file, progressContainer, progressBar, fileCard) {
  const initResponse = await fetch('/upload/chunked/init', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      filename: file.name,
      size: file.size,
      chunk_size: transferConfig.chunkSizeBytes,
    }),
  }).catch(() => null);

  if (!initResponse) {
    showError('Network error occurred.');
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  if (initResponse.status === 404 || initResponse.status === 405) {
    return null;
  }

  if (!initResponse.ok) {
    showError('Could not start upload session.');
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  const initData = await initResponse.json();
  const uploadID = initData.upload_id;
  const chunkSize = Number(initData.chunk_size) || transferConfig.chunkSizeBytes;
  const totalChunks = Number(initData.total_chunks) || Math.ceil(file.size / chunkSize);

  if (!uploadID || !Number.isFinite(totalChunks) || totalChunks <= 0) {
    showError('Upload session response was invalid.');
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  prepareDeterminateProgress(progressBar);

  const parallel = Math.max(1, Math.min(transferConfig.parallelChunks, totalChunks));
  let nextChunk = 0;
  let uploadedBytes = 0;
  let failed = false;

  const workers = Array.from({ length: parallel }, async () => {
    while (true) {
      if (failed) {
        return;
      }
      const chunkIndex = nextChunk;
      nextChunk += 1;
      if (chunkIndex >= totalChunks) {
        return;
      }

      const start = chunkIndex * chunkSize;
      const endExclusive = Math.min(file.size, start + chunkSize);
      const blob = file.slice(start, endExclusive);
      const chunkUploaded = await uploadChunkWithRetry(uploadID, chunkIndex, start, blob);
      if (!chunkUploaded) {
        failed = true;
        return;
      }

      uploadedBytes += blob.size;
      const percent = Math.min(100, Math.max(0, (uploadedBytes / file.size) * 100));
      progressBar.style.width = `${percent}%`;
    }
  });

  await Promise.all(workers);

  if (failed) {
    await abortUploadSession(uploadID);
    showError('Could not upload the file.');
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  const completeResponse = await fetch('/upload/chunked/complete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ upload_id: uploadID }),
  }).catch(() => null);

  if (!completeResponse || !completeResponse.ok) {
    await abortUploadSession(uploadID);
    showError('Could not finalize upload.');
    finalizeProgress(progressContainer, progressBar, fileCard, false);
    return false;
  }

  finalizeProgress(progressContainer, progressBar, fileCard, true);
  return true;
}

async function uploadChunkWithRetry(uploadID, chunkIndex, offset, blob) {
  for (let attempt = 1; attempt <= MAX_CHUNK_RETRIES; attempt += 1) {
    try {
      const response = await fetch('/upload/chunked/chunk', {
        method: 'PUT',
        headers: {
          'X-Upload-ID': uploadID,
          'X-Chunk-Index': String(chunkIndex),
          'X-Chunk-Offset': String(offset),
          'Content-Type': 'application/octet-stream',
        },
        body: blob,
      });

      if (response.ok) {
        return true;
      }

      if (response.status === 404 || response.status === 400) {
        return false;
      }
    } catch (_err) {
      // retry
    }

    await waitMs(150 * attempt);
  }
  return false;
}

async function abortUploadSession(uploadID) {
  try {
    await fetch('/upload/chunked/abort', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ upload_id: uploadID }),
    });
  } catch (_err) {
    // best-effort cleanup only
  }
}

/**
 * Checks if a file exists and then performs parallel ranged download when supported.
 * @param {string} file_name
 * @param {Event} event
 */
async function download_file(file_name, event) {
  if (event) {
    event.preventDefault();
  }

  const url = `/download/${encodeURIComponent(file_name)}`;

  try {
    const headResponse = await fetch(url, { method: 'HEAD' });
    if (!headResponse.ok) {
      alert(`File not found: "${file_name}" may have been deleted. The list will be refreshed.`);
      window.location.reload();
      return;
    }

    const sizeHeader = headResponse.headers.get('Content-Length');
    const acceptRanges = headResponse.headers.get('Accept-Ranges') || '';
    const totalSize = Number(sizeHeader || '0');
    const canParallelDownload =
      Number.isFinite(totalSize) &&
      totalSize > 0 &&
      acceptRanges.toLowerCase().includes('bytes') &&
      typeof window.showSaveFilePicker === 'function';

    if (!canParallelDownload) {
      triggerNativeDownload(url, file_name);
      return;
    }

    await downloadFileParallel(url, file_name, totalSize);
  } catch (error) {
    console.error('Download failed:', error);
    alert('An error occurred while downloading the file.');
  }
}

async function downloadFileParallel(url, fileName, totalSize) {
  let handle;
  try {
    handle = await window.showSaveFilePicker({
      suggestedName: fileName,
    });
  } catch (error) {
    if (error && error.name === 'AbortError') {
      return;
    }
    triggerNativeDownload(url, fileName);
    return;
  }

  const writable = await handle.createWritable();
  const chunkSize = transferConfig.chunkSizeBytes;
  const totalChunks = Math.ceil(totalSize / chunkSize);
  const parallel = Math.max(1, Math.min(transferConfig.parallelChunks, totalChunks));

  let nextChunk = 0;
  let failed = false;
  let writeChain = Promise.resolve();

  const queueWrite = (position, data) => {
    writeChain = writeChain.then(() => writable.write({ type: 'write', position, data }));
    return writeChain;
  };

  const workers = Array.from({ length: parallel }, async () => {
    while (true) {
      if (failed) {
        return;
      }
      const chunkIndex = nextChunk;
      nextChunk += 1;
      if (chunkIndex >= totalChunks) {
        return;
      }

      const start = chunkIndex * chunkSize;
      const end = Math.min(totalSize, start + chunkSize) - 1;
      const chunkData = await downloadChunkWithRetry(url, start, end);
      if (!chunkData) {
        failed = true;
        return;
      }

      await queueWrite(start, chunkData);
    }
  });

  await Promise.all(workers);

  if (failed) {
    await writable.abort();
    showError('Could not download file in parallel.');
    return;
  }

  await writeChain;
  await writable.close();
}

async function downloadChunkWithRetry(url, start, end) {
  for (let attempt = 1; attempt <= MAX_CHUNK_RETRIES; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Range: `bytes=${start}-${end}`,
        },
      });

      if (response.status !== 206) {
        if (response.status === 200 && start === 0) {
          const data = new Uint8Array(await response.arrayBuffer());
          return data;
        }
        if (response.status === 404) {
          return null;
        }
      } else {
        const data = new Uint8Array(await response.arrayBuffer());
        const expected = end - start + 1;
        if (data.byteLength !== expected) {
          await waitMs(120 * attempt);
          continue;
        }
        return data;
      }
    } catch (_err) {
      // retry
    }

    await waitMs(120 * attempt);
  }

  return null;
}

function triggerNativeDownload(url, file_name) {
  const link = document.createElement('a');
  link.href = url;
  link.download = file_name;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Fetches existing uploaded files from the server and displays them.
 */
async function fetchExistingUploads() {
  dropZone.style.display = 'none';

  try {
    const response = await fetch('/files/', {
      method: 'GET'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch existing uploads. Status: ${response.status}`);
    }

    const result = await response.json();

    result.files.forEach(file => {
      uploadedFiles.add(file);
      addFileToList({ name: file, uploaded: true });
    });

    if (uploadedFiles.size === 0) {
      dropZone.style.display = 'flex';
    }
  } catch (error) {
    console.error('Error fetching existing uploads:', error);
    showError('Could not load existing uploads.');
  }
}

// Event Listeners
uploadButton.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  handleFiles(e.target.files);
  fileInput.value = '';
});

document.addEventListener('dragover', (e) => {
  e.preventDefault();
});

document.addEventListener('drop', (e) => {
  e.preventDefault();
  handleFiles(e.dataTransfer.files);
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

/**
 * Handles the selected or dropped files.
 * @param {FileList} files - The list of files to handle.
 */
function handleFiles(files) {
  const newFiles = Array.from(files);

  newFiles.forEach(async file => {
    if (uploadedFiles.has(file.name)) {
      alert(`${file.name} already exists.`);
    } else {
      uploadedFiles.add(file.name);
      const { progressContainer, progressBar, fileIcon, fileCard } = await addFileToList(file);
      const success = await upload_file(file, progressContainer, progressBar, fileCard);
      if (success) {
        await getThumbnail(file.name, fileIcon);
      } else {
        uploadedFiles.delete(file.name);
        if (fileCard && fileCard.parentElement) {
          fileCard.remove();
        }
        if (uploadedFiles.size === 0) {
          dropZone.style.display = 'flex';
        }
      }
    }
  });
}

/**
 * Adds a file to the file list in the UI.
 * @param {Object} file - The file object containing name and upload status.
 * @returns {Object} - Contains the progressBar element.
 */
async function addFileToList(file) {
  if (uploadedFiles.size > 0) {
    dropZone.style.display = 'none';
  }

  const fileDiv = document.createElement('div');
  fileDiv.title = file.name;
  fileDiv.classList.add(
    'file-card',
    'p-2',
    'rounded-lg',
    'text-center',
    'hover:cursor-pointer',
    'transition-all',
    'duration-200',
    'flex',
    'flex-col',
    'items-center',
    'justify-center',
  );
  fileDiv.dataset.uploadState = file.uploaded ? 'complete' : 'uploading';

  const fileIcon = document.createElement('img');
  fileIcon.src = "icons/draft.svg";
  const fileNameLower = file.name.toLowerCase();
  for (let fileType of fileTypes) {
    let found = false;
    for (let extension of fileType.extensions) {
      if (fileNameLower.endsWith(extension)) {
        found = true;
        break;
      }
    }
    if (found) {
      fileIcon.src = fileType.iconSrc;
      break;
    }
  }
  fileIcon.alt = 'File Icon';
  fileIcon.classList.add('file-icon');
  await getThumbnail(file.name, fileIcon);
  const fileName = document.createElement('p');
  fileName.classList.add('text-md', 'font-medium', 'truncate', 'max-w-full');
  fileName.textContent = file.name.length > 10 ? `${file.name.substr(0, 10)}...` : file.name;

  let progressContainer = null;
  let progressBar = null;

  if (!file.uploaded) {
    progressContainer = document.createElement('div');
    progressContainer.classList.add('w-full', 'rounded-full', 'overflow-hidden', 'h-2', 'mt-2', 'upload-progress-track');
    progressBar = document.createElement('div');
    progressBar.classList.add('h-2', 'rounded-full', 'indeterminate-progress', 'transition-all', 'duration-200', 'ease-linear');
    progressContainer.appendChild(progressBar);
  }

  fileDiv.addEventListener('click', (event) => {
    if (fileDiv.dataset.uploadState !== 'complete') {
      event?.preventDefault();
      showError('File is still uploading. Please wait until it finishes.');
      return;
    }
    download_file(file.name, event);
  });

  fileDiv.appendChild(fileIcon);
  fileDiv.appendChild(fileName);
  if (progressContainer)
    fileDiv.appendChild(progressContainer);
  fileListContainer.appendChild(fileDiv);

  return { fileIcon, progressContainer, progressBar, fileCard: fileDiv };
}

/**
 * Finalizes the progress bar for success or failure.
 * @param {HTMLElement} progressContainer
 * @param {HTMLElement} progressBar
 * @param {HTMLElement} fileCard
 * @param {boolean} success
 */
function finalizeProgress(progressContainer, progressBar, fileCard, success) {
  if (!progressBar || !progressContainer) return;

  if (fileCard) {
    fileCard.dataset.uploadState = success ? 'complete' : 'failed';
  }

  progressBar.classList.remove('indeterminate-progress', 'bg-red-500', 'bg-blue-500');
  progressBar.style.background = '';
  progressBar.style.width = '100%';

  const removalDelay = success ? 400 : 1200;

  if (success) {
    progressBar.classList.add('bg-green-500');
  } else {
    progressBar.classList.add('bg-red-500');
  }

  setTimeout(() => {
    if (progressContainer.parentElement) {
      progressContainer.remove();
    }
  }, removalDelay);
}

function prepareDeterminateProgress(progressBar) {
  if (!progressBar) return;
  progressBar.classList.remove('indeterminate-progress');
  progressBar.classList.add('bg-blue-500');
  progressBar.style.background = '';
  progressBar.style.width = '0%';
}

/**
 * Displays an error message to the user.
 * @param {string} message
 */
function showError(message) {
  const errorMsg = document.createElement('p');
  errorMsg.classList.add('error-message', 'text-red-500', 'mt-2');
  errorMsg.textContent = message;
  errorContainer.appendChild(errorMsg);

  setTimeout(() => {
    if (errorMsg.parentElement === errorContainer) {
      errorContainer.removeChild(errorMsg);
    }
  }, 3000);
}

/**
 * Gets thumbnail and sets it on imageElement if available.
 * @param {string} fileName
 * @param {HTMLImageElement} fileIcon
 */
async function getThumbnail(fileName, fileIcon) {
  const url = `/thumbnails/${encodeURIComponent(fileName)}`;

  let response = await fetch(url, { method: 'GET' });
  if (response.status === 200) {
    const imageBlob = await response.blob();
    const imageObjectURL = URL.createObjectURL(imageBlob);
    fileIcon.src = imageObjectURL;
  }
}

function waitMs(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms);
  });
}

// Initialize by fetching transfer settings and existing uploads
window.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  await loadTransferSettings();
  await fetchExistingUploads();
});
