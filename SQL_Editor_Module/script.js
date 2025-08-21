// static/script.js - COMPLETELY UPDATED
document.addEventListener('DOMContentLoaded', function() {
  // Tab navigation
  const navLinks = document.querySelectorAll('.nav-link');
  const tabContents = document.querySelectorAll('.tab-content');
  
  navLinks.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Remove active class from all links and contents
      navLinks.forEach(l => l.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      
      // Add active class to clicked link and corresponding content
      this.classList.add('active');
      const tabId = this.getAttribute('data-tab');
      document.getElementById(tabId).classList.add('active');
    });
  });
  
  // SQL Editor functionality
  const sql = document.getElementById('sql');
  const consoleEl = document.getElementById('console');
  const runBtn = document.getElementById('runBtn');
  const clearBtn = document.getElementById('clearBtn');
  const formatBtn = document.getElementById('formatBtn');
  const statusEl = document.getElementById('status');
  const lengthInfo = document.getElementById('lengthInfo');
  
  function updateLength() {
    lengthInfo.textContent = `${sql.value.length} chars`;
  }
  
  sql.addEventListener('input', updateLength);
  updateLength();
  
  // Simple formatter: trims lines & uppercases common keywords
  function simpleFormat(text) {
    const keywords = ['select', 'from', 'where', 'and', 'or', 'group by', 'order by', 'insert', 'into', 'values', 'update', 'set', 'delete', 'create', 'table', 'join', 'left', 'right', 'inner', 'outer', 'limit'];
    let out = text.replace(/\s+$/gm, '');
    keywords.forEach(k => {
      const rex = new RegExp(`\\b${k}\\b`, 'gi');
      out = out.replace(rex, m => m.toUpperCase());
    });
    return out;
  }
  
  function setLoading(button, isLoading) {
    if (isLoading) {
      button.disabled = true;
      button.innerHTML = '<span class="loading"></span> Processing...';
    } else {
      button.disabled = false;
      button.innerHTML = button.getAttribute('data-original-text');
    }
  }
  
  async function runQuery() {
    const q = sql.value.trim();
    if (!q) {
      consoleEl.innerHTML = '<div class="message-error">Nothing to run. Type a SQL command first.</div>';
      return;
    }
    
    statusEl.textContent = 'Running…';
    setLoading(runBtn, true);
    
    try {
      const response = await fetch('/execute-sql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: q })
      });
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      let data;
      
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        // If not JSON, get the text and try to parse it
        const text = await response.text();
        try {
          data = JSON.parse(text);
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}...`);
        }
      }
      
      if (data.error) {
        consoleEl.innerHTML = `<div class="message-error">${data.error}</div>`;
      } else {
        consoleEl.textContent = JSON.stringify(data, null, 2);
      }
      
      statusEl.textContent = 'Done';
    } catch (err) {
      consoleEl.innerHTML = `<div class="message-error">Network error: ${err.message}</div>`;
      statusEl.textContent = 'Error';
    } finally {
      setLoading(runBtn, false);
    }
  }
  
  // Store original button text
  runBtn.setAttribute('data-original-text', runBtn.textContent);
  
  runBtn.addEventListener('click', runQuery);
  clearBtn.addEventListener('click', () => {
    sql.value = '';
    consoleEl.textContent = 'No output yet.';
    statusEl.textContent = 'Cleared';
    updateLength();
  });
  
  formatBtn.addEventListener('click', () => {
    sql.value = simpleFormat(sql.value);
    updateLength();
    statusEl.textContent = 'Formatted';
  });
  
  // Keyboard shortcut: Ctrl/Cmd + Enter
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      runQuery();
    }
  });
  
  // Data Analyzer functionality
  let currentColumns = [];
  const uploadForm = document.getElementById('uploadForm');
  const uploadStatus = document.getElementById('uploadStatus');
  const uploadButton = uploadForm.querySelector('button[type="submit"]');
  
  // Store original button text
  uploadButton.setAttribute('data-original-text', uploadButton.textContent);
  
  // Handle dataset upload
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('datasetFile');
    const file = fileInput.files[0];
    
    if (!file) {
      alert('Please select a file first');
      return;
    }
    
    setLoading(uploadButton, true);
    uploadStatus.innerHTML = '<span class="loading"></span> Uploading...';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch('/upload-dataset', {
        method: 'POST',
        body: formData
      });
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      let result;
      
      if (contentType && contentType.includes('application/json')) {
        result = await response.json();
      } else {
        // If not JSON, get the text and try to parse it
        const text = await response.text();
        try {
          result = JSON.parse(text);
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}...`);
        }
      }
      
      if (result.error) {
        uploadStatus.innerHTML = `<div class="message-error">${result.error}</div>`;
      } else {
        // Update dataset info - FIXED: result.shape is now an array
        document.getElementById('datasetInfo').innerHTML = `
          <div class="dataset-info">
            <h3>Current Dataset: ${file.name}</h3>
            <p>Shape: ${result.shape[0]} rows × ${result.shape[1]} columns</p>
            <p>Rows inserted: ${result.rowsInserted}</p>
            <p>Database status: ${result.dbStatus || 'Data saved to database'}</p>
          </div>
        `;
        
        // Update column dropdown
        currentColumns = result.columns;
        const columnSelect = document.getElementById('columnSelect');
        columnSelect.innerHTML = '';
        currentColumns.forEach(col => {
          const option = document.createElement('option');
          option.value = col;
          option.textContent = col;
          columnSelect.appendChild(option);
        });
        
        document.getElementById('resultContent').innerHTML = "Dataset ready for analysis";
        uploadStatus.innerHTML = `<div class="message-success">${result.message}</div>`;
      }
    } catch (error) {
      console.error('Upload error:', error);
      uploadStatus.innerHTML = `<div class="message-error">Error uploading file: ${error.message}</div>`;
    } finally {
      setLoading(uploadButton, false);
    }
  });
  
  // Expose analyze and visualize functions to global scope
  window.analyze = async function(action) {
    const resultContent = document.getElementById('resultContent');
    resultContent.innerHTML = '<span class="loading"></span> Analyzing...';
    
    try {
      const response = await fetch(`/analyze?action=${action}`);
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      let result;
      
      if (contentType && contentType.includes('application/json')) {
        result = await response.json();
      } else {
        // If not JSON, get the text and try to parse it
        const text = await response.text();
        try {
          result = JSON.parse(text);
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}...`);
        }
      }
      
      displayResult(result);
    } catch (error) {
      resultContent.innerHTML = `<div class="message-error">Error during analysis: ${error.message}</div>`;
    }
  };
  
  window.visualize = async function(action) {
    const column = document.getElementById('columnSelect').value;
    if (!column) {
      alert('Please select a column first');
      return;
    }
    
    const resultContent = document.getElementById('resultContent');
    resultContent.innerHTML = '<span class="loading"></span> Generating visualization...';
    
    try {
      const response = await fetch(`/analyze?action=${action}&column=${encodeURIComponent(column)}`);
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      let result;
      
      if (contentType && contentType.includes('application/json')) {
        result = await response.json();
      } else {
        // If not JSON, get the text and try to parse it
        const text = await response.text();
        try {
          result = JSON.parse(text);
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}...`);
        }
      }
      
      displayResult(result);
    } catch (error) {
      resultContent.innerHTML = `<div class="message-error">Error during visualization: ${error.message}</div>`;
    }
  };
  
  function displayResult(result) {
    const resultDiv = document.getElementById('resultContent');
    
    if (result.error) {
      resultDiv.innerHTML = `<div class="message-error">${result.error}</div>`;
      return;
    }
    
    if (typeof result.result === 'string' && result.result.startsWith('data:image/png')) {
      // This is a base64 encoded image
      resultDiv.innerHTML = `<img src="${result.result}" style="max-width:100%; margin-top:20px;">`;
    } else if (typeof result.result === 'string') {
      // HTML table
      resultDiv.innerHTML = result.result;
    } else if (Array.isArray(result.result)) {
      // List of items
      resultDiv.innerHTML = `<ul>${result.result.map(item => `<li>${item}</li>`).join('')}</ul>`;
    } else {
      // JSON object
      resultDiv.innerHTML = `<pre>${JSON.stringify(result.result, null, 2)}</pre>`;
    }
  }
  
  // Test backend connection on load
  async function testConnection() {
    try {
      const response = await fetch('/health');
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      let data;
      
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        // If not JSON, get the text and try to parse it
        const text = await response.text();
        try {
          data = JSON.parse(text);
        } catch {
          throw new Error(`Server returned: ${text.substring(0, 100)}...`);
        }
      }
      
      console.log('Backend health:', data);
    } catch (error) {
      console.error('Backend connection test failed:', error);
    }
  }
  
  testConnection();
});