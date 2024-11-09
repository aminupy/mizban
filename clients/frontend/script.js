// const BASE_URL = `http://localhost:8000`;
const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const uploadButton = document.getElementById('uploadButton');
const fileListContainer = document.getElementById('fileList');
const errorContainer = document.getElementById('errorContainer');

const uploadedFiles = new Set();


/**
 * Uploads a file to the server and manages the progress bar animation.
 * @param {File} file - The file to upload.
 * @param {HTMLElement} progressBar - The progress bar element associated with the file.
 */
async function upload_file(file, progressBar) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    // Start the infinite loading animation
    simulateProgress(progressBar, true);

    const response = await fetch('/api/files/upload/', {
      method: 'POST',
      body: formData
    });

    if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
      const result = await response.json();
      console.log('File uploaded successfully:', result);

      // Stop the loading animation and mark as completed
      simulateProgress(progressBar, false);
      progressBar.style.width = '100%'; // Optional: Indicate completion
      progressBar.classList.add('bg-green-500'); // Optional: Change color to indicate success
    } else {
      const responseText = await response.text(); // For debugging
      console.error('Unexpected response format:', responseText);
      throw new Error(`Unexpected response format or failed upload. Status: ${response.status}`);
    }
  } catch (error) {
    if (error instanceof SyntaxError) {
      console.error('Response was not valid JSON:', error);
      showError('Server returned an unexpected response.');
    } else if (error instanceof TypeError) {
      console.error('Network error or request was blocked:', error);
      showError('Network error occurred.');
    } else {
      console.error('Error uploading file:', error);
      showError('Could not upload the file.');
    }

    // Stop the loading animation and indicate failure
    if (progressBar) {
      simulateProgress(progressBar, false);
      progressBar.classList.add('bg-red-500'); // Optional: Change color to indicate error
    }
  }
}

/**
 * Initiates a file download without pre-fetching the file data.
 * @param {string} file_name - The name of the file to download.
 * @param {Event} event - The event object (optional).
 */
function download_file(file_name, event) {
  // If event is provided, prevent default behavior
  if (event) {
    event.preventDefault();
  }

  // Construct the download URL
  const url = `/api/files/download/${encodeURIComponent(file_name)}`;

  // Create a temporary anchor element
  const link = document.createElement('a');
  link.href = url;
  link.download = file_name; // Optional: Suggests a default file name

  // Append the link to the body (required for Firefox)
  document.body.appendChild(link);

  // Programmatically click the link to trigger the download
  link.click();

  // Clean up by removing the link
  document.body.removeChild(link);
}

/**
 * Fetches existing uploaded files from the server and displays them.
 */
async function fetchExistingUploads() {
  dropZone.style.display = 'none';

  try {
    const response = await fetch('/api/files/files/', {
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

  newFiles.forEach(file => {
    if (uploadedFiles.has(file.name)) {
      alert(`${file.name} already exists.`);
    } else {
      uploadedFiles.add(file.name);
      const { progressBar } = addFileToList(file);
      upload_file(file, progressBar); // Pass progress bar to upload_file
    }
  });
}

/**
 * Adds a file to the file list in the UI.
 * @param {Object} file - The file object containing name and upload status.
 * @returns {Object} - Contains the progressBar element.
 */
function addFileToList(file) {
  if (uploadedFiles.size > 0) {
    dropZone.style.display = 'none';
  }

  const fileDiv = document.createElement('div');
  fileDiv.classList.add(
    'bg-gray-100',
    'p-4',
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
    'gap-2'
  );

  const fileIcon = document.createElement('img');
  fileIcon.src = './file_icon.svg';
  fileIcon.alt = 'File Icon';
  fileIcon.classList.add('w-12');

  const fileName = document.createElement('p');
  fileName.classList.add('text-md', 'font-medium', 'truncate', 'max-w-full');
  fileName.textContent = file.name.length > 10 ? `${file.name.substr(0, 10)}...` : file.name;

  const progressContainer = document.createElement('div');
  progressContainer.classList.add('w-full', 'rounded-full', 'overflow-hidden', 'h-2', 'mt-2');

  let progressBar = null;
  if (!file.uploaded) {
    progressBar = document.createElement('div');
    progressBar.classList.add('bg-blue-500', 'h-2', 'rounded-full', 'indeterminate-progress');
    progressContainer.appendChild(progressBar);
  }

  // Add event listener with event parameter to prevent default behavior
  fileDiv.addEventListener('click', (event) => {
    download_file(file.name, event);
  });


  fileDiv.appendChild(fileIcon);
  fileDiv.appendChild(fileName);
  fileDiv.appendChild(progressContainer);
  fileListContainer.appendChild(fileDiv);

  return { progressBar };
}

/**
 * Manages the progress bar animation.
 * @param {HTMLElement} progressBar - The progress bar element.
 * @param {boolean} show - Whether to show (start) or hide (stop) the animation.
 */
function simulateProgress(progressBar, show) {
  if (show) {
    progressBar.classList.add('indeterminate-progress');
  } else {
    progressBar.classList.remove('indeterminate-progress');
    progressBar.classList.add('hidden'); // Hide the progress bar after completion or error
  }
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

// Initialize by fetching existing uploads
document.addEventListener('DOMContentLoaded', fetchExistingUploads);
