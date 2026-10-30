/**
 * GitHub Description Generator - Client-side Interactive Application Logic
 * Copyright (c) 2026 じゅーかきん
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const analyzeForm = document.getElementById('analyzeForm');
  const repoInput = document.getElementById('repoInput');
  const selectLang = document.getElementById('selectLang');
  const selectTone = document.getElementById('selectTone');
  const charLimit = document.getElementById('charLimit');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const btnIcon = document.getElementById('btnIcon');
  const btnText = document.getElementById('btnText');

  const engineStatusText = document.getElementById('engineStatusText');
  const resultsSection = document.getElementById('resultsSection');
  const repoLink = document.getElementById('repoLink');
  const badgeLang = document.getElementById('badgeLang');
  const badgeStars = document.getElementById('badgeStars');
  const badgeForks = document.getElementById('badgeForks');
  const badgeReadme = document.getElementById('badgeReadme');
  const badgeEngine = document.getElementById('badgeEngine');

  const descEditor = document.getElementById('descEditor');
  const charCounter = document.getElementById('charCounter');
  const copyBtn = document.getElementById('copyBtn');
  const toggleUpdateBtn = document.getElementById('toggleUpdateBtn');
  const updatePanel = document.getElementById('updatePanel');
  const githubTokenInput = document.getElementById('githubTokenInput');
  const executePatchBtn = document.getElementById('executePatchBtn');
  const topicsContainer = document.getElementById('topicsContainer');
  const toastContainer = document.getElementById('toastContainer');

  const tabButtons = document.querySelectorAll('.tab-btn');

  // Application State
  let currentAnalysis = null;
  let currentTone = 'concise';
  let activeTopics = new Set();

  // Helper to resolve API paths whether hosted at root '/' or under a subpath like '/tool/github-description/'
  function getApiUrl(endpoint) {
    const path = window.location.pathname;
    const basePath = path.endsWith('/') ? path : path + '/';
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    return `${basePath}${cleanEndpoint}`;
  }

  // 1. Initial Health Check
  checkHealth();

  async function checkHealth() {
    try {
      const res = await fetch(getApiUrl('health'));
      if (res.ok) {
        const data = await res.json();
        const engineLabel = {
          gemini: 'Gemini AI 稼働中',
          openai: 'OpenAI 稼働中',
          heuristic: 'スマート分析エンジン 稼働中'
        }[data.ai_engine] || 'オンライン';
        engineStatusText.textContent = engineLabel;
      }
    } catch {
      engineStatusText.textContent = 'オフライン (接続エラー)';
    }
  }

  // 2. Form Submission & Analysis
  analyzeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rawInput = repoInput.value.trim();

    if (!rawInput) {
      showToast('リポジトリ名またはURLを入力してください。', 'error');
      repoInput.focus();
      return;
    }

    setLoading(true);

    try {
      const payload = {
        repo_input: rawInput,
        language: selectLang.value,
        tone: selectTone.value,
        target_char_limit: parseInt(charLimit.value, 10) || 350
      };

      const res = await fetch(getApiUrl('api/analyze'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        const errorMsg = data.error || 'リポジトリの解析に失敗しました。';
        showToast(errorMsg, 'error');
        return;
      }

      currentAnalysis = data;
      currentTone = payload.tone;
      renderAnalysis(data);
      showToast('リポジトリの分析と説明文生成が完了しました！', 'success');

    } catch (err) {
      showToast('サーバーとの通信中にエラーが発生しました。', 'error');
    } finally {
      setLoading(false);
    }
  });

  function renderAnalysis(data) {
    const meta = data.metadata;

    // Summary Card
    repoLink.textContent = meta.full_name;
    repoLink.href = meta.html_url;
    badgeLang.textContent = meta.language || 'Multi-language';
    badgeStars.textContent = `⭐ ${meta.stars.toLocaleString()}`;
    badgeForks.textContent = `🍴 ${meta.forks.toLocaleString()}`;
    badgeReadme.textContent = meta.has_readme ? '📖 READMEあり' : '⚠️ READMEなし';
    badgeReadme.style.color = meta.has_readme ? 'inherit' : '#f59e0b';

    const engineNameMap = {
      gemini: '🤖 Gemini Flash',
      openai: '🤖 OpenAI GPT',
      heuristic: '⚡ Smart Engine'
    };
    badgeEngine.textContent = engineNameMap[data.engine_used] || '🤖 AI Engine';

    // Tabs state
    tabButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tone === currentTone);
    });

    // Populate Editor
    descEditor.value = data.suggested_description;
    updateCharCounter();

    // Populate Topics
    topicsContainer.innerHTML = '';
    activeTopics.clear();

    const allTopics = [...new Set([...(meta.topics || []), ...(data.suggested_topics || [])])];
    allTopics.forEach(topic => {
      activeTopics.add(topic);
      const chip = document.createElement('span');
      chip.className = 'topic-chip active';
      chip.textContent = `#${topic}`;
      chip.addEventListener('click', () => {
        if (activeTopics.has(topic)) {
          activeTopics.delete(topic);
          chip.classList.remove('active');
        } else {
          activeTopics.add(topic);
          chip.classList.add('active');
        }
      });
      topicsContainer.appendChild(chip);
    });

    // Show workspace
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // 3. Tab Switching
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tone = btn.dataset.tone;
      currentTone = tone;

      if (currentAnalysis && currentAnalysis.alternative_descriptions) {
        const found = currentAnalysis.alternative_descriptions.find(v => v.tone === tone);
        if (found && found.description) {
          descEditor.value = found.description;
          updateCharCounter();
        }
      }
    });
  });

  // 4. Character Counter
  descEditor.addEventListener('input', updateCharCounter);

  function updateCharCounter() {
    const len = descEditor.value.length;
    charCounter.textContent = `${len} / 350 文字`;

    charCounter.classList.remove('warning', 'danger');
    if (len > 350) {
      charCounter.classList.add('danger');
    } else if (len > 320) {
      charCounter.classList.add('warning');
    }
  }

  // 5. Copy to Clipboard
  copyBtn.addEventListener('click', async () => {
    const text = descEditor.value.trim();
    if (!text) {
      showToast('コピーする説明文が空です。', 'error');
      return;
    }

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        descEditor.select();
        document.execCommand('copy');
      }
      showToast('説明文をクリップボードにコピーしました！', 'success');
    } catch {
      showToast('コピーに失敗しました。直接テキストを選択してコピーしてください。', 'error');
    }
  });

  // 6. Direct Update Toggle
  toggleUpdateBtn.addEventListener('click', () => {
    updatePanel.classList.toggle('show');
    if (updatePanel.classList.contains('show')) {
      githubTokenInput.focus();
    }
  });

  // 7. Execute GitHub Description Update
  executePatchBtn.addEventListener('click', async () => {
    if (!currentAnalysis) return;

    const token = githubTokenInput.value.trim();
    if (!token) {
      showToast('GitHub Personal Access Token (PAT) を入力してください。', 'error');
      githubTokenInput.focus();
      return;
    }

    const newDescription = descEditor.value.trim();
    if (!newDescription) {
      showToast('説明文を入力してください。', 'error');
      return;
    }

    if (newDescription.length > 350) {
      showToast('説明文はGitHubの制限（350文字）以内に収めてください。', 'error');
      return;
    }

    executePatchBtn.disabled = true;
    executePatchBtn.innerHTML = '<span class="spinner"></span> <span>GitHubへ送信中...</span>';

    try {
      const payload = {
        owner: currentAnalysis.metadata.owner,
        repo: currentAnalysis.metadata.repo,
        description: newDescription,
        topics: Array.from(activeTopics),
        github_token: token
      };

      const res = await fetch(getApiUrl('api/update'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        showToast(data.error || 'リポジトリ更新に失敗しました。', 'error');
        return;
      }

      showToast(data.message || 'GitHubリポジトリの説明文を更新しました！', 'success');
      updatePanel.classList.remove('show');
      githubTokenInput.value = ''; // Clear token from memory/input for safety

    } catch {
      showToast('更新リクエスト中に通信エラーが発生しました。', 'error');
    } finally {
      executePatchBtn.disabled = false;
      executePatchBtn.innerHTML = '<span>GitHubリポジトリの説明文を更新実行</span>';
    }
  });

  // Helper: Loading UI State
  function setLoading(isLoading) {
    analyzeBtn.disabled = isLoading;
    if (isLoading) {
      btnIcon.innerHTML = '<span class="spinner"></span>';
      btnText.textContent = 'リポジトリ分析中...';
    } else {
      btnIcon.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
      `;
      btnText.textContent = 'リポジトリを解析・生成';
    }
  }

  // Helper: Toast Notifications
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
    } else {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
});
