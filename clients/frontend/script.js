const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const uploadButton = document.getElementById('uploadButton');
const fileListContainer = document.getElementById('fileList');
const errorContainer = document.getElementById('errorContainer');

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


/**
 * Uploads a file to the server and manages the progress bar animation.
 * @param {File} file - The file to upload.
 * @param {HTMLElement} progressContainer - The progress container element.
 * @param {HTMLElement} progressBar - The progress bar element associated with the file.
 * @param {HTMLElement} fileCard - The file container element.
 * @returns {Promise<boolean>} True when upload succeeds, otherwise false.
 */
function upload_file(file, progressContainer, progressBar, fileCard) {
  return new Promise((resolve) => {
    if (!progressBar || !progressContainer) {
      resolve(false);
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    let determinateMode = false;
    let settled = false;

    xhr.upload.onprogress = (event) => {
      if (!progressBar) return;
      if (event.lengthComputable) {
        if (!determinateMode) {
          determinateMode = true;
          progressBar.classList.remove('indeterminate-progress');
          progressBar.classList.add('bg-blue-500');
          progressBar.style.background = '';
          progressBar.style.width = '0%';
        }
        const percent = Math.min(
          100,
          Math.max(0, (event.loaded / event.total) * 100)
        );
        progressBar.style.width = `${percent}%`;
      }
    };

    xhr.onreadystatechange = () => {
      if (xhr.readyState !== XMLHttpRequest.DONE) return;
      if (settled) return;

      let responsePayload = null;
      if (xhr.responseType === 'json') {
        responsePayload = xhr.response;
      } else if (xhr.responseText) {
        try {
          responsePayload = JSON.parse(xhr.responseText);
        } catch (_err) {
          responsePayload = null;
        }
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        if (responsePayload) {
          console.log('File uploaded successfully:', responsePayload);
        }
        finalizeProgress(progressContainer, progressBar, fileCard, true);
        settled = true;
        resolve(true);
      } else {
        console.error('Error uploading file:', xhr.status, xhr.responseText);
        showError('Could not upload the file.');
        finalizeProgress(progressContainer, progressBar, fileCard, false);
        settled = true;
        resolve(false);
      }
    };

    xhr.onerror = () => {
      if (settled) return;
      console.error('Network error or request was blocked.');
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
 * Checks if a file exists and then initiates a browser-native download.
 * @param {string} file_name - The name of the file to download.
 * @param {Event} event - The event object (optional).
 */
async function download_file(file_name, event) {
  if (event) {
    event.preventDefault();
  }

  const url = `/download/${encodeURIComponent(file_name)}`;

  try {
    // ✨ Step 1: Send a HEAD request to check if the file exists
    const response = await fetch(url, { method: 'HEAD' });

    // ✨ Step 2: Check the response status
    if (!response.ok) {
      // If the file doesn't exist (e.g., 404 Not Found), show an alert and refresh
      alert(`File not found: "${file_name}" may have been deleted. The list will be refreshed.`);
      window.location.reload();
      return;
    }

    // ✨ Step 3: If the check was successful, trigger the native browser download
    const link = document.createElement('a');
    link.href = url;
    link.download = file_name; // This attribute suggests the filename to the browser
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

  } catch (error) {
    console.error('Download check failed:', error);
    alert('An error occurred while checking for the file.');
  }
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
    'bg-gray-100',
    'p-2',
    'rounded-lg',
    'text-center',
    'text-gray-700',
    'hover:bg-secondary',
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
  fileIcon.classList.add('file-icon'); // Apply the fixed size class
  await getThumbnail(file.name, fileIcon);
  const fileName = document.createElement('p');
  fileName.classList.add('text-md', 'font-medium', 'truncate', 'max-w-full');
  fileName.textContent = file.name.length > 10 ? `${file.name.substr(0, 10)}...` : file.name;

  let progressContainer = null;
  let progressBar = null;

  if (!file.uploaded) {
    progressContainer = document.createElement('div');
    progressContainer.classList.add('w-full', 'rounded-full', 'overflow-hidden', 'h-2', 'mt-2');
    progressBar = document.createElement('div');
    progressBar.classList.add('h-2', 'rounded-full', 'indeterminate-progress', 'transition-all', 'duration-200', 'ease-linear');
    progressContainer.appendChild(progressBar);
  }

  // Add event listener with event parameter to prevent default behavior
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
 * @param {HTMLElement} fileCard - The file container element.
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

/**
 * Displays an error message to the user.
 * @param {string} message - The error message to display.
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
 * Gets thumbnail from api and if its succesful set it as imageElement given.
 * @param {string} fileName - thumbnail file name
 * @param {HTMLImageElement} fileIcon - imageElemnt to set thumbnail
 */
async function getThumbnail(fileName, fileIcon) {
  const url = `/thumbnails/${encodeURIComponent(fileName)}`;

  const options = {
    method: "GET"
  };

  let response = await fetch(url, options);
  if (response.status === 200) {
    const imageBlob = await response.blob();
    const imageObjectURL = URL.createObjectURL(imageBlob);
    fileIcon.src = imageObjectURL;
  };
}

// Initialize by fetching existing uploads
document.addEventListener('DOMContentLoaded', fetchExistingUploads);
