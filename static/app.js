// OmniLoad Frontend Application - Downloader & Converter Suite

let currentTab = 'single';
let currentFormat = 'mp4';
let currentVideoInfo = null;
let allTasks = {};
let allHistoryItems = [];
let historyFilterType = 'all';
let isCloudMode = false;
let ws = null;

// Converter Suite State
let converterMode = 'pdf2img'; // 'pdf2img', 'img2pdf', 'img2img', 'pdfmerge'
let selectedConverterFiles = [];

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initWebSocket();
  loadInitialTasks();
  loadHistory();
  loadSystemStatus();
  loadSettings();
  initDropzone();

  const urlInput = document.getElementById('single-url-input');
  if (urlInput) {
    urlInput.addEventListener('input', handleUrlInput);
    urlInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        analyzeUrl();
      }
    });
  }
});

function initTheme() {
  const saved = localStorage.getItem('omniload_theme');
  if (saved === 'amoled') {
    document.body.classList.add('theme-amoled');
    updateThemeIcon(true);
  }
}

function toggleAmoledTheme() {
  const isAmoled = document.body.classList.toggle('theme-amoled');
  localStorage.setItem('omniload_theme', isAmoled ? 'amoled' : 'midnight');
  updateThemeIcon(isAmoled);
  showToast(isAmoled ? 'เปิดโหมด AMOLED Pure Black (มืดสนิท)' : 'เปิดโหมด Midnight Dark (น้ำเงินเข้ม)', 'info');
}

function updateThemeIcon(isAmoled) {
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.innerHTML = isAmoled ? '<i class="fa-solid fa-sun text-yellow-400"></i>' : '<i class="fa-solid fa-moon text-indigo-400"></i>';
  }
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  if (typeof message === 'string') {
    message = message.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '').replace(/[\x00-\x1F\x7F-\x9F]/g, '').replace(/^ERROR:\s*/i, '');
  }

  const toast = document.createElement('div');
  toast.className = `pointer-events-auto flex items-center space-x-3 px-4 py-3 rounded-xl text-xs font-medium shadow-2xl transition-all duration-300 transform translate-y-2 opacity-0 glass-card border ${
    type === 'success' ? 'border-emerald-500/40 text-emerald-300' :
    type === 'error' ? 'border-rose-500/40 text-rose-300' :
    'border-indigo-500/40 text-indigo-300'
  }`;

  const icon = type === 'success' ? 'fa-circle-check' :
               type === 'error' ? 'fa-triangle-exclamation' : 'fa-circle-info';

  toast.innerHTML = `
    <i class="fa-solid ${icon} text-base"></i>
    <span class="flex-1">${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  }, 10);

  setTimeout(() => {
    toast.classList.add('opacity-0', '-translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function switchTab(tabName) {
  currentTab = tabName;
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => {
    el.classList.remove('active', 'bg-indigo-600', 'text-white', 'shadow');
    el.classList.add('text-gray-400');
  });

  const activeContent = document.getElementById(`tab-content-${tabName}`);
  if (activeContent) activeContent.classList.remove('hidden');

  const activeBtn = document.getElementById(`tab-btn-${tabName}`);
  if (activeBtn) {
    activeBtn.classList.add('active', 'bg-indigo-600', 'text-white', 'shadow');
    activeBtn.classList.remove('text-gray-400');
  }

  if (tabName === 'history') loadHistory();
  if (tabName === 'settings') loadSystemStatus();
}

// URL Platform Detection
function detectPlatformName(url) {
  const u = url.toLowerCase();
  if (u.includes('youtube.com') || u.includes('youtu.be')) return { name: 'YouTube', icon: 'fa-brands fa-youtube', class: 'badge-yt' };
  if (u.includes('twitter.com') || u.includes('x.com')) return { name: 'X (Twitter)', icon: 'fa-brands fa-x-twitter', class: 'badge-tw' };
  if (u.includes('tiktok.com') || u.includes('douyin.com')) return { name: 'TikTok', icon: 'fa-brands fa-tiktok', class: 'badge-tt' };
  if (u.includes('instagram.com')) return { name: 'Instagram', icon: 'fa-brands fa-instagram', class: 'badge-ig' };
  if (u.includes('pinterest.com') || u.includes('pin.it')) return { name: 'Pinterest', icon: 'fa-brands fa-pinterest', class: 'badge-pin' };
  if (u.includes('facebook.com') || u.includes('fb.watch')) return { name: 'Facebook', icon: 'fa-brands fa-facebook', class: 'badge-fb' };
  if (u.includes('reddit.com') || u.includes('redd.it')) return { name: 'Reddit', icon: 'fa-brands fa-reddit-alien', class: 'badge-reddit' };
  if (u.includes('threads.net')) return { name: 'Threads', icon: 'fa-brands fa-threads', class: 'badge-threads' };
  if (u.includes('soundcloud.com')) return { name: 'SoundCloud', icon: 'fa-brands fa-soundcloud', class: 'badge-soundcloud' };
  if (u.includes('bilibili.com') || u.includes('b23.tv')) return { name: 'Bilibili', icon: 'fa-solid fa-tv', class: 'badge-bilibili' };
  if (u.includes('twitch.tv')) return { name: 'Twitch', icon: 'fa-brands fa-twitch', class: 'badge-twitch' };
  if (u.includes('bsky.app')) return { name: 'Bluesky', icon: 'fa-solid fa-cloud', class: 'badge-bsky' };
  if (u.includes('vimeo.com')) return { name: 'Vimeo', icon: 'fa-brands fa-vimeo', class: 'badge-generic' };
  if (u.length > 5) return { name: 'Web Media', icon: 'fa-solid fa-link', class: 'badge-generic' };
  return null;
}

function handleUrlInput() {
  const url = document.getElementById('single-url-input').value.trim();
  const detector = document.getElementById('platform-detector');
  const badge = document.getElementById('detected-platform-badge');
  const iconContainer = document.getElementById('input-platform-icon');

  const detected = detectPlatformName(url);
  if (detected && url.length > 6) {
    detector.classList.remove('hidden');
    badge.className = `px-2.5 py-0.5 rounded-full font-medium ${detected.class}`;
    badge.innerHTML = `<i class="${detected.icon} mr-1"></i> ${detected.name}`;
    iconContainer.innerHTML = `<i class="${detected.icon} text-indigo-400"></i>`;
  } else {
    detector.classList.add('hidden');
    iconContainer.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i>`;
  }
}

async function pasteClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      document.getElementById('single-url-input').value = text;
      handleUrlInput();
      showToast('วางลิงก์จากคลิปบอร์ดแล้ว', 'info');
      analyzeUrl();
    }
  } catch (err) {
    showToast('ไม่สามารถอ่านคลิปบอร์ดได้ กรุณากด Ctrl+V เพื่อวาง', 'error');
  }
}

// Analyze URL & Preview
async function analyzeUrl() {
  const url = document.getElementById('single-url-input').value.trim();
  if (!url) {
    showToast('กรุณาวางลิงก์ที่ต้องการดาวน์โหลด', 'error');
    return;
  }

  const analyzeBtn = document.getElementById('analyze-btn');
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>กำลังตรวจสอบ...</span>`;

  try {
    const res = await fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'ไม่สามารถดึงข้อมูลวิดีโอได้ ตรวจสอบว่าลิงก์ถูกต้องหรือเป็นสาธารณะ', 'error');
      return;
    }

    currentVideoInfo = data;
    renderPreviewCard(data);
    showToast(`ดึงข้อมูลสำเร็จ: ${data.title}`, 'success');

  } catch (e) {
    showToast(`เกิดข้อผิดพลาด: ${e.message}`, 'error');
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i><span>ตรวจสอบคลิป</span>`;
  }
}

function renderPreviewCard(info) {
  const previewCard = document.getElementById('preview-card');
  const thumb = document.getElementById('preview-thumb');
  const title = document.getElementById('preview-title');
  const duration = document.getElementById('preview-duration');
  const uploader = document.getElementById('preview-uploader');
  const platformTag = document.getElementById('preview-platform-tag');

  thumb.src = info.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=60';
  title.textContent = info.title;
  duration.textContent = info.duration_formatted || '--:--';
  uploader.innerHTML = `<i class="fa-solid fa-user-circle mr-1"></i><span>${info.uploader}</span>`;
  platformTag.textContent = info.platform;

  previewCard.classList.remove('hidden');
  previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function cancelPreview() {
  document.getElementById('preview-card').classList.add('hidden');
  currentVideoInfo = null;
}

// Format Selector
function selectFormatType(type) {
  currentFormat = type;
  const mp4Btn = document.getElementById('format-opt-mp4');
  const mp3Btn = document.getElementById('format-opt-mp3');
  const videoSelect = document.getElementById('quality-video-select');
  const audioSelect = document.getElementById('quality-audio-select');

  if (type === 'mp4') {
    mp4Btn.classList.add('active', 'bg-indigo-600', 'text-white');
    mp4Btn.classList.remove('text-gray-400');
    mp3Btn.classList.remove('active', 'bg-indigo-600', 'text-white');
    mp3Btn.classList.add('text-gray-400');

    videoSelect.classList.remove('hidden');
    audioSelect.classList.add('hidden');
  } else {
    mp3Btn.classList.add('active', 'bg-indigo-600', 'text-white');
    mp3Btn.classList.remove('text-gray-400');
    mp4Btn.classList.remove('active', 'bg-indigo-600', 'text-white');
    mp4Btn.classList.add('text-gray-400');

    audioSelect.classList.remove('hidden');
    videoSelect.classList.add('hidden');
  }
}

// Single Download Trigger
async function startSingleDownload() {
  const urlInput = document.getElementById('single-url-input');
  const url = urlInput.value.trim();
  if (!url) {
    showToast('กรุณาวางลิงก์ที่ต้องการดาวน์โหลด', 'error');
    return;
  }

  const quality = currentFormat === 'mp4' 
    ? document.getElementById('single-video-quality').value 
    : document.getElementById('single-audio-quality').value;

  const customTitle = document.getElementById('single-custom-title').value.trim();

  const startBtn = document.getElementById('start-download-btn');
  startBtn.disabled = true;
  startBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>กำลังเริ่ม...</span>`;

  try {
    const payload = {
      url: url,
      format_type: currentFormat,
      quality: quality,
      custom_title: customTitle
    };

    if (currentVideoInfo && currentVideoInfo.direct_url) {
      payload.direct_url = currentVideoInfo.direct_url;
    }

    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.success) {
      showToast('เพิ่มรายการดาวน์โหลดเรียบร้อยแล้ว!', 'success');
      urlInput.value = '';
      document.getElementById('single-custom-title').value = '';
      cancelPreview();
      handleUrlInput();
    } else {
      showToast(data.detail || 'เกิดข้อผิดพลาดในการเริ่มดาวน์โหลด', 'error');
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  } finally {
    startBtn.disabled = false;
    startBtn.innerHTML = `<i class="fa-solid fa-download"></i><span>เริ่มดาวน์โหลดทันที</span>`;
  }
}

// Batch Download Trigger
async function startBatchDownload() {
  const batchInput = document.getElementById('batch-urls-input');
  const text = batchInput.value.trim();
  if (!text) {
    showToast('กรุณาวางลิงก์ในช่องข้อความอย่างน้อย 1 ลิงก์', 'error');
    return;
  }

  const urls = text.split('\n').map(u => u.trim()).filter(u => u.length > 5);
  if (urls.length === 0) {
    showToast('ไม่พบลำดับ URL ที่ถูกต้อง', 'error');
    return;
  }

  const format = document.getElementById('batch-format-select').value;
  const quality = document.getElementById('batch-quality-select').value;
  const batchBtn = document.getElementById('start-batch-btn');

  batchBtn.disabled = true;
  batchBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>กำลังเริ่มคิว (${urls.length})...</span>`;

  try {
    const res = await fetch('/api/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        urls: urls,
        format_type: format,
        quality: quality
      })
    });

    const data = await res.json();
    if (data.success) {
      showToast(`เริ่มดาวน์โหลด ${data.count} รายการแล้ว!`, 'success');
      batchInput.value = '';
      switchTab('single');
    } else {
      showToast(data.detail || 'เกิดข้อผิดพลาดในการสร้างคิว', 'error');
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  } finally {
    batchBtn.disabled = false;
    batchBtn.innerHTML = `<i class="fa-solid fa-play"></i><span>เริ่มดาวน์โหลดทั้งชุด</span>`;
  }
}

function clearBatchInput() {
  document.getElementById('batch-urls-input').value = '';
}

// =========================================================================
// UNIVERSAL CONVERTER SUITE LOGIC
// =========================================================================

function setConverterMode(mode) {
  converterMode = mode;
  document.querySelectorAll('.conv-tab-btn').forEach(btn => {
    btn.classList.remove('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
    btn.classList.add('text-gray-400');
  });

  const activeBtn = document.getElementById(`conv-mode-${mode}`);
  if (activeBtn) {
    activeBtn.classList.add('active', 'bg-indigo-600', 'text-white', 'shadow-sm');
    activeBtn.classList.remove('text-gray-400');
  }

  // Hide all option groups and show current
  document.querySelectorAll('[id^="opt-group-"]').forEach(el => el.classList.add('hidden'));
  const optGroup = document.getElementById(`opt-group-${mode}`);
  if (optGroup) optGroup.classList.remove('hidden');

  // Update titles & hints
  const title = document.getElementById('conv-title');
  const desc = document.getElementById('conv-desc');
  const hint = document.getElementById('dropzone-hint');
  const icon = document.getElementById('dropzone-icon');

  if (mode === 'pdf2img') {
    title.innerHTML = `<i class="fa-solid fa-file-pdf text-indigo-400 mr-2"></i><span>แปลงไฟล์ PDF เป็นรูปภาพ (JPG / PNG)</span>`;
    desc.textContent = 'แปลงเอกสาร PDF ทุกหน้าเป็นรูปภาพความละเอียดสูง (150 หรือ 300 DPI) พร้อมดาวน์โหลด ZIP';
    hint.textContent = 'รองรับไฟล์ .PDF (แปลงได้ทุกหน้า ไม่จำกัดขนาด)';
    icon.className = 'fa-solid fa-file-pdf';
  } else if (mode === 'img2pdf') {
    title.innerHTML = `<i class="fa-solid fa-images text-pink-400 mr-2"></i><span>รวมรูปภาพทุกชนิดเป็นไฟล์ PDF (Everything ➔ PDF)</span>`;
    desc.textContent = 'เลือกรูปภาพหลายๆ รูป (JPG, PNG, WEBP, BMP, GIF) เพื่อรวมเป็นเอกสาร PDF เล่มเดียว';
    hint.textContent = 'รองรับไฟล์ .JPG, .PNG, .WEBP, .BMP, .GIF, .TIFF (เลือกหลายรูปพร้อมกันได้)';
    icon.className = 'fa-solid fa-images';
  } else if (mode === 'img2img') {
    title.innerHTML = `<i class="fa-solid fa-image text-cyan-400 mr-2"></i><span>แปลงฟอร์แมตรูปภาพ (Image Format Converter)</span>`;
    desc.textContent = 'แปลงระหว่างฟอร์แมต JPG, PNG, WEBP, BMP พร้อมปรับคุณภาพการบีบอัด';
    hint.textContent = 'รองรับไฟล์ .WEBP, .PNG, .JPG, .BMP, .TIFF, .GIF';
    icon.className = 'fa-solid fa-arrows-rotate';
  } else if (mode === 'pdfmerge') {
    title.innerHTML = `<i class="fa-solid fa-object-group text-emerald-400 mr-2"></i><span>รวมหลายไฟล์ PDF เข้าด้วยกัน (PDF Merge)</span>`;
    desc.textContent = 'เลือกหลายๆ ไฟล์ PDF เพื่อรวมเป็นไฟล์ PDF เดียวอย่างสมบูรณ์แบบ';
    hint.textContent = 'รองรับไฟล์ .PDF หลายไฟล์';
    icon.className = 'fa-solid fa-object-group';
  }

  clearSelectedFiles();
}

function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('border-indigo-500', 'bg-indigo-950/20');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('border-indigo-500', 'bg-indigo-950/20');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      addFilesToConverter(Array.from(files));
    }
  }, false);
}

function triggerFileInput() {
  const input = document.getElementById('file-input');
  if (input) {
    if (converterMode === 'pdf2img' || converterMode === 'pdfmerge') {
      input.accept = '.pdf,application/pdf';
    } else {
      input.accept = 'image/*,.pdf,.webp,.png,.jpg,.jpeg,.bmp,.tiff,.gif';
    }
    input.multiple = (converterMode !== 'pdf2img');
    input.click();
  }
}

function handleFileSelect(event) {
  const files = event.target.files;
  if (files && files.length > 0) {
    addFilesToConverter(Array.from(files));
  }
}

function addFilesToConverter(files) {
  if (converterMode === 'pdf2img') {
    selectedConverterFiles = [files[0]];
  } else {
    selectedConverterFiles = selectedConverterFiles.concat(files);
  }
  renderSelectedFiles();
}

function clearSelectedFiles() {
  selectedConverterFiles = [];
  const fileInput = document.getElementById('file-input');
  if (fileInput) fileInput.value = '';
  renderSelectedFiles();
  document.getElementById('conversion-result-card').classList.add('hidden');
}

function removeFileByIndex(index) {
  selectedConverterFiles.splice(index, 1);
  renderSelectedFiles();
}

function renderSelectedFiles() {
  const card = document.getElementById('selected-files-card');
  const list = document.getElementById('selected-files-list');
  const count = document.getElementById('selected-count');

  if (selectedConverterFiles.length === 0) {
    card.classList.add('hidden');
    return;
  }

  card.classList.remove('hidden');
  count.textContent = selectedConverterFiles.length;

  list.innerHTML = selectedConverterFiles.map((file, idx) => `
    <div class="flex items-center justify-between p-2 rounded-xl bg-gray-900/60 border border-gray-800 text-xs">
      <div class="flex items-center space-x-2 truncate">
        <i class="fa-solid fa-file-lines text-indigo-400"></i>
        <span class="text-white truncate font-medium">${escapeHtml(file.name)}</span>
        <span class="text-[11px] text-gray-500 font-mono">(${formatBytes(file.size)})</span>
      </div>
      <button onclick="removeFileByIndex(${idx})" class="text-gray-500 hover:text-rose-400 p-1">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
  `).join('');
}

async function startConversion() {
  if (selectedConverterFiles.length === 0) {
    showToast('กรุณาเลือกไฟล์ที่ต้องการแปลงก่อน', 'error');
    return;
  }

  const startBtn = document.getElementById('start-convert-btn');
  startBtn.disabled = true;
  startBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>กำลังประมวลผล...</span>`;

  try {
    let endpoint = '';
    const formData = new FormData();

    if (converterMode === 'pdf2img') {
      endpoint = '/api/convert/pdf-to-images';
      formData.append('file', selectedConverterFiles[0]);
      formData.append('output_format', document.getElementById('pdf2img-format').value);
      formData.append('dpi', document.getElementById('pdf2img-dpi').value);
      formData.append('quality', document.getElementById('pdf2img-quality').value);

    } else if (converterMode === 'img2pdf') {
      endpoint = '/api/convert/images-to-pdf';
      selectedConverterFiles.forEach(f => formData.append('files', f));
      formData.append('pdf_name', document.getElementById('img2pdf-name').value.trim() || 'combined_images.pdf');

    } else if (converterMode === 'img2img') {
      endpoint = '/api/convert/image-to-image';
      selectedConverterFiles.forEach(f => formData.append('files', f));
      formData.append('target_format', document.getElementById('img2img-target').value);
      formData.append('quality', document.getElementById('img2img-quality').value);

    } else if (converterMode === 'pdfmerge') {
      endpoint = '/api/convert/pdf-merge';
      selectedConverterFiles.forEach(f => formData.append('files', f));
      formData.append('output_filename', document.getElementById('pdfmerge-name').value.trim() || 'merged_document.pdf');
    }

    const res = await fetch(endpoint, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok || data.detail) {
      throw new Error(data.detail || 'Conversion failed');
    }

    showToast('แปลงไฟล์สำเร็จเรียบร้อยแล้ว!', 'success');
    renderConversionResults(data);
    loadHistory();

  } catch (e) {
    showToast(`เกิดข้อผิดพลาด: ${e.message}`, 'error');
  } finally {
    startBtn.disabled = false;
    startBtn.innerHTML = `<i class="fa-solid fa-repeat"></i><span>เริ่มแปลงไฟล์ทันที</span>`;
  }
}

function renderConversionResults(data) {
  const resultCard = document.getElementById('conversion-result-card');
  const actions = document.getElementById('conv-result-actions');
  const grid = document.getElementById('conv-result-grid');

  resultCard.classList.remove('hidden');
  actions.innerHTML = '';
  grid.innerHTML = '';

  if (converterMode === 'pdf2img') {
    if (data.zip_download_url) {
      actions.innerHTML = `
        <a href="${data.zip_download_url}" download class="px-3.5 py-1.5 rounded-xl bg-pink-600 hover:bg-pink-500 text-white font-bold text-xs transition flex items-center space-x-1.5 shadow-md">
          <i class="fa-solid fa-file-zipper"></i>
          <span>ดาวน์โหลด ZIP รวมทุกหน้า (${data.total_pages} หน้า)</span>
        </a>
      `;
    }

    grid.innerHTML = data.pages.map(p => `
      <div class="glass-card rounded-xl p-2.5 flex flex-col space-y-2 border border-gray-800 group">
        <div class="aspect-[3/4] rounded-lg overflow-hidden bg-black/40 border border-gray-800 relative">
          <img src="${p.download_url}" alt="Page ${p.page}" class="w-full h-full object-contain">
          <span class="absolute top-1.5 left-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-black/80 text-white">หน้า ${p.page}</span>
        </div>
        <div class="flex items-center justify-between text-[11px]">
          <span class="text-gray-400 truncate max-w-[100px]">${formatBytes(p.size_bytes)}</span>
          <a href="${p.download_url}" download class="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-[10px] flex items-center space-x-1">
            <i class="fa-solid fa-download"></i>
            <span>บันทึก</span>
          </a>
        </div>
      </div>
    `).join('');

  } else if (converterMode === 'img2pdf' || converterMode === 'pdfmerge') {
    actions.innerHTML = `
      <a href="${data.download_url}" download class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition flex items-center space-x-1.5 shadow-md">
        <i class="fa-solid fa-download"></i>
        <span>ดาวน์โหลดไฟล์ PDF (${formatBytes(data.size_bytes)})</span>
      </a>
    `;

    grid.innerHTML = `
      <div class="col-span-full glass-card rounded-xl p-6 text-center space-y-3">
        <div class="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-3xl mx-auto flex items-center justify-center">
          <i class="fa-solid fa-file-pdf"></i>
        </div>
        <div>
          <h5 class="text-sm font-bold text-white">${escapeHtml(data.filename)}</h5>
          <p class="text-xs text-gray-400 mt-1">${data.total_pages} หน้า &bull; ขนาด ${formatBytes(data.size_bytes)}</p>
        </div>
      </div>
    `;

  } else if (converterMode === 'img2img') {
    grid.innerHTML = data.results.map(r => `
      <div class="glass-card rounded-xl p-2.5 flex flex-col space-y-2 border border-gray-800">
        <div class="aspect-square rounded-lg overflow-hidden bg-black/40 border border-gray-800">
          <img src="${r.download_url}" alt="${escapeHtml(r.filename)}" class="w-full h-full object-cover">
        </div>
        <div class="flex items-center justify-between text-[11px]">
          <span class="text-gray-300 truncate max-w-[90px] font-medium" title="${escapeHtml(r.filename)}">${escapeHtml(r.filename)}</span>
          <a href="${r.download_url}" download class="px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-[10px]">
            <i class="fa-solid fa-download mr-1"></i> โหลด
          </a>
        </div>
      </div>
    `).join('');
  }

  resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// WebSocket Connection & Real-Time Tasks
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'init') {
        allTasks = {};
        if (msg.tasks && Array.isArray(msg.tasks)) {
          msg.tasks.forEach(t => { allTasks[t.task_id] = t; });
        }
        renderTaskList();
      } else if (msg.type === 'task_update') {
        const task = msg.data;
        const prevStatus = allTasks[task.task_id]?.status;
        allTasks[task.task_id] = task;
        renderTaskList();

        if (task.status === 'completed' && prevStatus !== 'completed') {
          showToast(`ดาวน์โหลดเสร็จสมบูรณ์: ${task.filename || task.title}`, 'success');
          loadHistory();
        } else if (task.status === 'error' && prevStatus !== 'error') {
          showToast(`การดาวน์โหลดผิดพลาด: ${task.error}`, 'error');
        }
      }
    } catch (e) {
      console.error('WS parse error:', e);
    }
  };

  ws.onclose = () => {
    setTimeout(initWebSocket, 2500);
  };
}

async function loadInitialTasks() {
  try {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    allTasks = {};
    tasks.forEach(t => { allTasks[t.task_id] = t; });
    renderTaskList();
  } catch (e) {
    console.error('Failed to load tasks:', e);
  }
}

function renderTaskList() {
  const container = document.getElementById('task-list-container');
  const countLabel = document.getElementById('active-count-label');
  if (!container) return;

  const taskArray = Object.values(allTasks).sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  
  if (countLabel) {
    countLabel.textContent = `${taskArray.length} รายการ`;
  }

  if (taskArray.length === 0) {
    container.innerHTML = `
      <div id="empty-task-placeholder" class="glass-card rounded-xl p-8 text-center text-gray-500 text-xs">
        <i class="fa-solid fa-arrow-up-from-bracket text-2xl mb-2 text-gray-600 block"></i>
        ยังไม่มีรายการดาวน์โหลดที่กำลังทำงาน วางลิงก์ด้านบนเพื่อเริ่มดาวน์โหลด
      </div>
    `;
    return;
  }

  container.innerHTML = taskArray.map(task => {
    const isCompleted = task.status === 'completed';
    const isError = task.status === 'error';
    const isProcessing = task.status === 'processing';

    const statusBadge = isCompleted ? `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold"><i class="fa-solid fa-check mr-1"></i>เสร็จสิ้น</span>` :
                        isError ? `<span class="px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-[10px] font-bold" title="${escapeHtml(task.error)}"><i class="fa-solid fa-xmark mr-1"></i>ผิดพลาด</span>` :
                        isProcessing ? `<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[10px] font-bold"><i class="fa-solid fa-spinner fa-spin mr-1"></i>กำลังรวมไฟล์ / แปลง MP3</span>` :
                        `<span class="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 text-[10px] font-bold"><i class="fa-solid fa-cloud-arrow-down mr-1"></i>กำลังดาวน์โหลด</span>`;

    const formatBadge = task.format_type === 'mp3' ? `<span class="px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/30 text-[10px] font-bold">MP3</span>` :
                                                    `<span class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-[10px] font-bold">MP4</span>`;

    const pct = task.percent || 0;
    const displayName = task.filename || task.title || task.current_file || task.url;

    return `
      <div class="glass-card rounded-xl p-4 transition-all duration-200 border ${isCompleted ? 'border-emerald-500/20' : isError ? 'border-rose-500/20' : 'border-gray-800'}">
        <div class="flex items-start justify-between gap-3 mb-2">
          <div class="flex items-center space-x-2 truncate">
            ${formatBadge}
            <span class="text-xs font-semibold text-white truncate" title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</span>
          </div>
          <div class="flex-shrink-0">
            ${statusBadge}
          </div>
        </div>

        ${!isError ? `
          <div class="w-full bg-gray-900 rounded-full h-2 overflow-hidden mb-2 border border-gray-800/80">
            <div class="h-full rounded-full transition-all duration-200 ${isCompleted ? 'bg-emerald-500' : isProcessing ? 'bg-amber-500 progress-striped' : 'bg-gradient-to-r from-indigo-500 to-purple-500 progress-striped'}" style="width: ${pct}%"></div>
          </div>
        ` : `
          <div class="text-[11px] text-rose-400 bg-rose-950/30 p-2 rounded-lg mb-2 font-mono break-all">
            ${escapeHtml(task.error || 'Unknown error')}
          </div>
        `}

        <div class="flex flex-wrap items-center justify-between text-[11px] text-gray-400 gap-2">
          <div class="flex items-center space-x-3">
            <span><i class="fa-solid fa-gauge-high mr-1 text-gray-500"></i>${task.speed_str || '--'}</span>
            <span><i class="fa-regular fa-clock mr-1 text-gray-500"></i>ETA: ${task.eta_str || '--'}</span>
            <span><i class="fa-solid fa-hard-drive mr-1 text-gray-500"></i>${task.downloaded_str || '0 B'} / ${task.total_str || '--'}</span>
          </div>

          <div class="flex items-center space-x-2">
            ${isCompleted ? `
              <button onclick="playMediaByName('${escapeHtml(task.filename)}')" class="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition flex items-center space-x-1">
                <i class="fa-solid fa-play text-[10px]"></i>
                <span>เล่น</span>
              </button>
              <a href="/downloads/${encodeURIComponent(task.filename)}" download class="px-2.5 py-1 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-[11px] font-medium transition flex items-center space-x-1">
                <i class="fa-solid fa-download text-[10px]"></i>
                <span>ดาวน์โหลด</span>
              </a>
              ${!isCloudMode ? `
                <button onclick="openFileInFolder('${escapeHtml(task.filename)}')" class="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-[11px] transition flex items-center space-x-1" title="เปิดตำแหน่งไฟล์ในเครื่อง">
                  <i class="fa-regular fa-folder-open text-[10px]"></i>
                  <span>เปิดโฟลเดอร์</span>
                </button>
              ` : ''}
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Media History / Library
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    allHistoryItems = await res.json();
    
    const badge = document.getElementById('history-badge');
    if (badge) badge.textContent = allHistoryItems.length;

    filterHistory();
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

function setHistoryFilter(type) {
  historyFilterType = type;
  document.querySelectorAll('.history-filter-btn').forEach(btn => {
    btn.classList.remove('active', 'bg-indigo-600', 'text-white');
    btn.classList.add('text-gray-400');
  });

  const activeBtn = document.getElementById(`filter-btn-${type}`);
  if (activeBtn) {
    activeBtn.classList.add('active', 'bg-indigo-600', 'text-white');
    activeBtn.classList.remove('text-gray-400');
  }

  filterHistory();
}

function filterHistory() {
  const container = document.getElementById('history-items-container');
  const searchInput = document.getElementById('history-search-input');
  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!container) return;

  const filtered = allHistoryItems.filter(item => {
    const matchSearch = item.filename.toLowerCase().includes(searchTerm);
    const matchType = (historyFilterType === 'all') || (item.media_type === historyFilterType);
    return matchSearch && matchType;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="glass-card rounded-2xl p-12 text-center text-gray-500 text-xs">
        <i class="fa-regular fa-folder-open text-3xl mb-2 text-gray-600 block"></i>
        ไม่พบไฟล์ในโฟลเดอร์ดาวน์โหลด
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(item => {
    const isVideo = item.media_type === 'video';
    const isImage = item.media_type === 'image';
    const icon = isVideo ? 'fa-film text-cyan-400' : isImage ? 'fa-image text-emerald-400' : 'fa-music text-pink-400';
    const typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold ${isVideo ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : isImage ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-pink-500/10 text-pink-400 border border-pink-500/30'}">${item.ext}</span>`;

    const dateStr = new Date(item.modified_at * 1000).toLocaleString('th-TH', {
      dateStyle: 'short',
      timeStyle: 'short'
    });

    return `
      <div class="glass-card rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-gray-700 transition">
        <div class="flex items-center space-x-3 truncate">
          <div class="w-10 h-10 rounded-lg bg-gray-900 border border-gray-800 flex items-center justify-center flex-shrink-0">
            <i class="fa-solid ${icon} text-base"></i>
          </div>
          <div class="truncate">
            <div class="flex items-center space-x-2">
              ${typeBadge}
              <h4 class="text-xs font-semibold text-white truncate" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</h4>
            </div>
            <p class="text-[11px] text-gray-400 mt-0.5">
              <span>${item.size_str}</span> &bull; <span>${dateStr}</span>
            </p>
          </div>
        </div>

        <div class="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
          <button onclick="playMediaObject('${encodeURIComponent(JSON.stringify(item))}')" class="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition flex items-center space-x-1">
            <i class="fa-solid fa-play text-[10px]"></i>
            <span>เล่นไฟล์</span>
          </button>
          
          <a href="${item.download_url}" download class="px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition flex items-center space-x-1" title="ดาวน์โหลดเก็บเข้าเครื่อง">
            <i class="fa-solid fa-download text-[10px]"></i>
            <span>โหลดเข้าเครื่อง</span>
          </a>

          ${!isCloudMode ? `
            <button onclick="openFileInFolder('${escapeHtml(item.filename)}')" class="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs transition" title="เปิดไฟล์ใน Windows Explorer">
              <i class="fa-regular fa-folder-open"></i>
            </button>
          ` : ''}

          <button onclick="deleteHistoryItem('${escapeHtml(item.filename)}')" class="p-2 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 text-xs transition" title="ลบไฟล์">
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// Media Player Modal
function playMediaObject(encodedJson) {
  try {
    const item = JSON.parse(decodeURIComponent(encodedJson));
    openMediaPlayer(item);
  } catch (e) {
    console.error('Play error:', e);
  }
}

function playMediaByName(filename) {
  const item = allHistoryItems.find(x => x.filename === filename);
  if (item) {
    openMediaPlayer(item);
  } else {
    openMediaPlayer({
      filename: filename,
      media_type: filename.toLowerCase().endsWith('.mp3') ? 'audio' : 'video',
      stream_url: `/api/stream/${encodeURIComponent(filename)}`,
      download_url: `/downloads/${encodeURIComponent(filename)}`
    });
  }
}

function openMediaPlayer(item) {
  const modal = document.getElementById('player-modal');
  const title = document.getElementById('player-modal-title');
  const wrapper = document.getElementById('player-wrapper');
  const modalInfo = document.getElementById('player-modal-info');
  const downloadLink = document.getElementById('player-download-link');
  const revealBtn = document.getElementById('player-reveal-btn');
  const icon = document.getElementById('player-modal-icon');

  title.textContent = item.filename;
  modalInfo.textContent = item.size_str ? `ขนาด: ${item.size_str}` : '';
  downloadLink.href = item.download_url;
  
  if (revealBtn) {
    if (isCloudMode) {
      revealBtn.classList.add('hidden');
    } else {
      revealBtn.classList.remove('hidden');
      revealBtn.onclick = () => openFileInFolder(item.filename);
    }
  }

  const streamSrc = item.stream_url || item.download_url;

  if (item.media_type === 'video') {
    icon.className = 'fa-solid fa-film text-cyan-400';
    wrapper.innerHTML = `
      <video controls autoplay class="w-full h-full rounded-xl bg-black">
        <source src="${streamSrc}">
        เบราว์เซอร์ของคุณไม่รองรับการเล่นวิดีโอนี้
      </video>
    `;
  } else if (item.media_type === 'image') {
    icon.className = 'fa-solid fa-image text-emerald-400';
    wrapper.innerHTML = `
      <img src="${streamSrc}" alt="Preview" class="max-w-full max-h-full object-contain rounded-xl">
    `;
  } else {
    icon.className = 'fa-solid fa-music text-pink-400';
    wrapper.innerHTML = `
      <div class="flex flex-col items-center justify-center p-8 space-y-4 w-full">
        <div class="w-20 h-20 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-3xl shadow-lg">
          <i class="fa-solid fa-compact-disc fa-spin" style="--fa-animation-duration: 6s;"></i>
        </div>
        <p class="text-xs text-gray-300 text-center font-medium truncate max-w-sm">${escapeHtml(item.filename)}</p>
        <audio controls autoplay class="w-full max-w-md">
          <source src="${streamSrc}">
          เบราว์เซอร์ของคุณไม่รองรับการเล่นเสียงนี้
        </audio>
      </div>
    `;
  }

  modal.classList.remove('hidden');
}

function closeMediaPlayer() {
  const modal = document.getElementById('player-modal');
  const wrapper = document.getElementById('player-wrapper');
  wrapper.innerHTML = '';
  modal.classList.add('hidden');
}

// Windows Explorer Open Folder
async function openDownloadFolder() {
  try {
    const res = await fetch('/api/open-folder', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('เปิดโฟลเดอร์ดาวน์โหลดแล้ว', 'success');
    } else {
      showToast(data.message || 'ไม่สามารถเปิดโฟลเดอร์ได้', 'info');
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  }
}

async function openFileInFolder(filename) {
  try {
    const res = await fetch('/api/open-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`เปิดตำแหน่งไฟล์ ${filename} แล้ว`, 'success');
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  }
}

async function deleteHistoryItem(filename) {
  if (!confirm(`คุณต้องการลบไฟล์ "${filename}" ใช่หรือไม่?`)) return;

  try {
    const res = await fetch(`/api/history/${encodeURIComponent(filename)}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (data.success) {
      showToast(`ลบไฟล์ ${filename} เรียบร้อยแล้ว`, 'info');
      loadHistory();
    }
  } catch (e) {
    showToast(`ลบไม่สำเร็จ: ${e.message}`, 'error');
  }
}

// System Status & Settings
async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system-status');
    const data = await res.json();

    isCloudMode = data.is_cloud_mode;

    const navFolderBtn = document.getElementById('nav-open-folder-btn');
    const histFolderBtn = document.getElementById('history-open-folder-btn');
    const envBadge = document.getElementById('env-mode-badge');
    const deployMode = document.getElementById('sys-deploy-mode');

    if (isCloudMode) {
      if (navFolderBtn) navFolderBtn.classList.add('hidden');
      if (histFolderBtn) histFolderBtn.classList.add('hidden');
      if (envBadge) {
        envBadge.className = 'px-2 py-0.5 text-[10px] font-semibold rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30';
        envBadge.textContent = 'Web-App Server Mode';
      }
      if (deployMode) deployMode.textContent = 'Docker / Cloud VPS';
    } else {
      if (deployMode) deployMode.textContent = 'Local Windows Desktop';
    }

    document.getElementById('sys-ffmpeg-status').innerHTML = data.ffmpeg_status === 'Ready'
      ? `<i class="fa-solid fa-circle-check mr-1 text-emerald-400"></i> พร้อมใช้งาน (Active)`
      : `<i class="fa-solid fa-triangle-exclamation mr-1 text-rose-400"></i> ไม่พบ`;
    
    document.getElementById('sys-python-ver').textContent = data.python_version;
    document.getElementById('sys-ytdlp-ver').textContent = data.ytdlp_version;
    document.getElementById('sys-disk-free').textContent = `${data.disk_free_str} (${data.disk_free_percent}% เหลืออยู่)`;
    document.getElementById('setting-download-dir').value = data.download_dir;

    if (data.auto_cleanup_hours !== undefined) {
      document.getElementById('setting-cleanup-hours').value = data.auto_cleanup_hours;
    }

  } catch (e) {
    console.error('System status load error:', e);
  }
}

async function updateYtDlp() {
  const btn = document.getElementById('btn-update-ytdlp');
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> อัปเดต...`;

  try {
    const res = await fetch('/api/update-ytdlp', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('อัปเดต yt-dlp ล่าสุดเรียบร้อยแล้ว!', 'success');
      loadSystemStatus();
    } else {
      showToast(`อัปเดตล้มเหลว: ${data.error || 'Unknown error'}`, 'error');
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `อัปเดต`;
  }
}

async function triggerManualCleanup() {
  try {
    const res = await fetch('/api/cleanup-now', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`ล้างไฟล์เก่าเรียบร้อย: ลบไป ${data.result.deleted_count} ไฟล์`, 'success');
      loadHistory();
      loadSystemStatus();
    }
  } catch (e) {
    showToast(`ข้อผิดพลาด: ${e.message}`, 'error');
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if (data.video_format) document.getElementById('setting-default-video').value = data.video_format;
    if (data.audio_bitrate) document.getElementById('setting-default-audio').value = data.audio_bitrate;
    if (data.auto_cleanup_hours !== undefined) document.getElementById('setting-cleanup-hours').value = data.auto_cleanup_hours;
  } catch (e) {}
}

async function saveAppSettings() {
  const video_format = document.getElementById('setting-default-video').value;
  const audio_bitrate = document.getElementById('setting-default-audio').value;
  const auto_cleanup_hours = parseInt(document.getElementById('setting-cleanup-hours').value, 10);

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_format, audio_bitrate, auto_cleanup_hours })
    });
    const data = await res.json();
    if (data.success) {
      showToast('บันทึกการตั้งค่าเรียบร้อยแล้ว', 'success');
    }
  } catch (e) {
    showToast(`บันทึกไม่สำเร็จ: ${e.message}`, 'error');
  }
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
