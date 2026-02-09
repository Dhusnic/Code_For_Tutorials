// API Configuration
const API_BASE = "http://localhost:8000";

// Run Full Review
async function runReview() {
  const logs = document.getElementById("logs");
  const aiReview = document.getElementById("aiReview");
  const codeChanges = document.getElementById("codeChanges");
  logs.textContent = "Starting review process...\n";

  try {
    // Step 1: Collect Diffs
    logs.textContent += "Collecting diffs...\n";
    let repoPath = document.getElementById("repoPath").value;
    let aiModel = document.getElementById("aiModel").value;
    let maxTokens = document.getElementById("maxTokens").value;
    let orgnization = document.getElementById("organization").value;
    let project = document.getElementById("project").value;
    let repository = document.getElementById("repository").value;
    let prId = document.getElementById("prId").value;
    let password = document.getElementById("password").value;
    let isLocal = document.getElementById("isLocal").checked;
    let review =""
    aiReview.innerHTML = "";
    let body = JSON.stringify({
      repo_path: repoPath,
      ai_model: aiModel,
      max_tokens: maxTokens,
      organization: orgnization,
      project: project,
      repository_name: repository,
      pull_request_id: prId,
      password: password,
      is_local: isLocal
    });
    const diffsResponse = await fetch(`${API_BASE}/api/review-diffs`, {
      method: 'POST',
      body: body,
      headers: {
        'Content-Type': 'application/json'
      }
    }).then(async res => {
      if (!res.ok) {
        throw new Error(`Failed to collect diffs: ${res.statusText}`);
      }
      else {
        if (!res.ok) {
        throw new Error(`Failed to collect diffs: ${res.statusText}`);
        }

        
        const diffsData = await res.json();
        logs.textContent += `✓ Diffs collected (${diffsData.token_estimate} tokens estimated)\n`;
        
        // Step 2: Perform AI Review
        logs.textContent += "Reviewing diffs with AI...\n";
        logs.textContent += "✓ AI review completed\n";
        aiReview.innerHTML = marked.parse(diffsData?.review || "");

        review = diffsData?.review || "";
      }
    });

    body['review'] = review || "";
    // Step 3: Generate Code Changes
    
    logs.textContent += "Generating code changes...\n";
    diffsData= await fetch(`${API_BASE}/api/generate-changes`, {
      method: 'POST',
      body: body,
      headers: {
        'Content-Type': 'application/json'
      }
    }).then(res => {
      return res.json();    
    }).then(data => {
        logs.textContent += "✓ Code changes generated\n";
        diffsData = data; 
        // Display AI Review (Markdown)
        displayCodeChanges(diffsData?.code_changes);
    })
    // logs.textContent += `\nToken estimate: ${diffsData.diffs.tokens_used}\n`;
    // Display AI Review (Markdown)
 


    // Display Code Changes (JSON)
    // const reviewResponse = await fetch(`${API_BASE}/api/review`, {
    //   method: 'POST',
    //   body: body,
    //   headers: {
    //     'Content-Type': 'application/json'
    //   }
    // });

    // if (!reviewResponse.ok) {
    //   throw new Error(`Failed to perform review: ${reviewResponse.statusText}`);
    // }

    // const reviewData = await reviewResponse.json();
    // logs.textContent += "✓ AI review completed\n";

    // // Display AI Review (Markdown)
    // document.getElementById("aiReview").innerHTML = marked.parse(reviewData.review);

    // if (!reviewResponse.ok) {
    //   throw new Error(`Failed to perform review: ${reviewResponse.statusText}`);
    // }

    // const reviewData = await reviewResponse.json();
    // logs.textContent += "✓ AI review completed\n";

    // // Display AI Review (Markdown)
    // document.getElementById("aiReview").innerHTML = marked.parse(reviewData.review);

    // // Step 3: Generate Code Changes
    // logs.textContent += "Generating code changes...\n";
    
    // const changesResponse = await fetch(`${API_BASE}/api/generate-changes`, {
    //   method: 'POST',
    //   headers: {
    //     'Content-Type': 'application/json'
    //   }
    // });

    // if (!changesResponse.ok) {
    //   throw new Error(`Failed to generate changes: ${changesResponse.statusText}`);
    // }

    // const changesData = await changesResponse.json();
    // logs.textContent += "✓ Code changes generated\n";

    // // Display Code Changes (JSON)
    // codeChanges.textContent = JSON.stringify(changesData.code_changes, null, 2);

    // logs.textContent += "\n🎉 Done! Review completed successfully ✔️\n";

  } catch (error) {
    logs.textContent += `\n❌ Error: ${error.message}\n`;
    console.error('Review error:', error);
    alert(`Error during review: ${error.message}`);
  }
}


// Alternative: Run Full Review in One Call
async function runFullReview() {
  const logs = document.getElementById("logs");
  logs.textContent = "Starting full review process...\n";

  try {
    const response = await fetch(`${API_BASE}/api/run-full-review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Review failed: ${response.statusText}`);
    }

    const data = await response.json();

    logs.textContent += "✓ Diffs collected\n";
    logs.textContent += "✓ AI review completed\n";
    logs.textContent += "✓ Code changes generated\n";

    // Display AI Review (Markdown)
    if (data.review) {
      document.getElementById("aiReview").innerHTML = marked.parse(data.review);
    }

    // Display Code Changes (JSON)
    if (data.code_changes) {
      document.getElementById("codeChanges").textContent = 
        JSON.stringify(data.code_changes, null, 2);
    }

    // Display token estimate
    if (data.token_estimate) {
      logs.textContent += `\nToken estimate: ${data.token_estimate}\n`;
    }

    logs.textContent += "\n🎉 Done! Full review completed successfully ✔️\n";

  } catch (error) {
    logs.textContent += `\n❌ Error: ${error.message}\n`;
    console.error('Review error:', error);
    alert(`Error during review: ${error.message}`);
  }
}

// Copy function with better feedback
function copyText(id) {
  const el = document.getElementById(id);
  const text = el.innerText || el.textContent;

  navigator.clipboard.writeText(text)
    .then(() => {
      // Show success toast instead of alert
      showToast('✓ Copied to clipboard');
    })
    .catch(err => {
      console.error('Copy failed:', err);
      alert('Failed to copy to clipboard');
    });
}

// Enhanced copy with visual feedback
function copyTextWithFeedback(id) {
  const el = document.getElementById(id);
  const text = el.innerText || el.textContent;

  navigator.clipboard.writeText(text)
    .then(() => {
      // Create temporary success indicator
      const originalBg = el.style.background;
      el.style.background = '#d1fae5';
      
      setTimeout(() => {
        el.style.background = originalBg;
      }, 500);
      
      showToast('✓ Copied to clipboard');
    })
    .catch(err => {
      console.error('Copy failed:', err);
      showToast('❌ Failed to copy', 'error');
    });
}

// Toast notification helper
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: ${type === 'error' ? '#ef4444' : '#22c55e'};
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Add CSS animations (add to your stylesheet or use inline)
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Individual API call functions for more control
async function collectDiffsOnly() {
  const logs = document.getElementById("logs");
  logs.textContent = "Collecting diffs...\n";

  try {
    const response = await fetch(`${API_BASE}/api/collect-diffs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed: ${response.statusText}`);
    }

    const data = await response.json();
    logs.textContent += `✓ Diffs collected\n`;
    logs.textContent += `Token estimate: ${data.token_estimate}\n`;

    // Display diffs in a dedicated section if you have one
    console.log('Diffs:', data.diffs);
    
    return data;

  } catch (error) {
    logs.textContent += `❌ Error: ${error.message}\n`;
    throw error;
  }
}

async function performReviewOnly() {
  const logs = document.getElementById("logs");
  logs.textContent = "Performing AI review...\n";

  try {
    const response = await fetch(`${API_BASE}/api/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed: ${response.statusText}`);
    }

    const data = await response.json();
    logs.textContent += "✓ Review completed\n";

    // Display review
    document.getElementById("aiReview").innerHTML = marked.parse(data.review);
    
    return data;

  } catch (error) {
    logs.textContent += `❌ Error: ${error.message}\n`;
    throw error;
  }
}

async function generateChangesOnly() {
  const logs = document.getElementById("logs");
  logs.textContent = "Generating code changes...\n";

  try {
    const response = await fetch(`${API_BASE}/api/generate-changes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed: ${response.statusText}`);
    }

    const data = await response.json();
    logs.textContent += "✓ Changes generated\n";

    // Display changes with VS Code style viewer
    displayCodeChanges(data.code_changes);
    
    return data;

  } catch (error) {
    logs.textContent += `❌ Error: ${error.message}\n`;
    throw error;
  }
}

// Global state for code changes
let allChanges = [];
let appliedChanges = new Set();
let cancelledChanges = new Set();
let currentFilter = 'all';

// Display code changes with VS Code style
function displayCodeChanges(changes) {
  const container = document.getElementById('codeChangesContainer');
  
  if (!changes || changes.length === 0) {
    container.innerHTML = `
      <div class="empty-changes">
        <i class="fas fa-code"></i>
        <p>No code changes available</p>
      </div>
    `;
    return;
  }

  // Store changes globally
  allChanges = Array.isArray(changes) ? changes : [changes];
  
  // Group by file
  const groupedChanges = groupChangesByFile(allChanges);
  
  // Render each file's changes
  let html = '';
  Object.entries(groupedChanges).forEach(([filePath, fileChanges], fileIndex) => {
    fileChanges.forEach((change, changeIndex) => {
      html += renderChangeItem(change, fileIndex, changeIndex);
    });
  });
  
  container.innerHTML = html;
}

// Group changes by file path
function groupChangesByFile(changes) {
  const grouped = {};
  
  changes.forEach(change => {
    const filePath = change.diff?.file_path || 'Unknown file';
    if (!grouped[filePath]) {
      grouped[filePath] = [];
    }
    grouped[filePath].push(change);
  });
  
  return grouped;
}

// Render a single change item
function renderChangeItem(change, fileIndex, changeIndex) {
  const changeId = `change-${fileIndex}-${changeIndex}`;
  const diff = change.diff || {};
  const filePath = diff.file_path || 'Unknown file';
  const lineNumber = diff.line_number || '?';
  const newLineNumber = diff.new_start_line_number || lineNumber;
  const changeType = diff.change_type || 'modified';
  const categories = change.categories || [];
  const primaryCategory = categories[0] || 'info';
  
  // Parse old and new content
  const oldLines = parseCodeLines(diff.old_content || '');
  const newLines = parseCodeLines(diff.new_content || '');
  
  return `
    <div class="change-item" data-change-id="${changeId}" data-categories="${categories.join(',')}" data-type="${changeType}">
      <!-- File Header -->
      <div class="file-change-header" onclick="toggleDiff('${changeId}')">
        <div class="file-info">
          <i class="fas fa-chevron-right collapse-icon" id="icon-${changeId}"></i>
          <div>
            <div class="file-path">
              <i class="fas fa-file-code"></i>
              ${escapeHtml(filePath)}
            </div>
            <div class="line-info">
              Lines ${lineNumber} → ${newLineNumber}
            </div>
          </div>
        </div>
        
        <div style="display: flex; align-items: center; gap: 10px;">
          ${categories.map(cat => `<span class="category-badge ${cat}">${cat}</span>`).join('')}
          <span class="change-type-badge ${changeType}">${changeType}</span>
          <span class="status-indicator" id="status-${changeId}" style="display: none;"></span>
        </div>
      </div>

      <!-- Diff Content -->
      <div class="diff-content" id="diff-${changeId}">
        <!-- VS Code Style Diff Viewer -->
        <div class="diff-viewer-container">
          <!-- Old Code Pane -->
          <div class="diff-pane-old">
            <div class="pane-title">
              <i class="fas fa-minus-circle" style="color: #f87171;"></i>
              Original (Line ${lineNumber})
            </div>
            <div class="pane-code">
              ${renderCodeLines(oldLines, 'removed', lineNumber)}
            </div>
          </div>

          <!-- New Code Pane -->
          <div class="diff-pane-new">
            <div class="pane-title">
              <i class="fas fa-plus-circle" style="color: #34d399;"></i>
              Modified (Line ${newLineNumber})
            </div>
            <div class="pane-code">
              ${renderCodeLines(newLines, 'added', newLineNumber)}
            </div>
          </div>
        </div>

        <!-- Explanation Section -->
        <div class="change-explanation">
          <div class="explanation-title">
            <i class="fas fa-info-circle"></i>
            Explanation
          </div>
          <div class="explanation-text">
            ${escapeHtml(change.explanation || 'No explanation provided.')}
          </div>
          
          ${change.comments ? `
            <div class="comment-box">
              <strong>
                <i class="fas fa-lightbulb"></i>
                Note:
              </strong>
              ${escapeHtml(change.comments)}
            </div>
          ` : ''}
        </div>

        <!-- Action Buttons -->
        <div class="change-actions">
          <button class="btn-copy-change" onclick="copyChange('${changeId}')">
            <i class="fas fa-copy"></i>
            Copy
          </button>
          <button class="btn-cancel" onclick="cancelChange('${changeId}')">
            <i class="fas fa-times"></i>
            Cancel
          </button>
          <button class="btn-apply" onclick="applyChange('${changeId}')">
            <i class="fas fa-check"></i>
            Apply Change
          </button>
        </div>
      </div>
    </div>
  `;
}

// Parse code into lines
function parseCodeLines(code) {
  if (!code) return [];
  return code.split('\n');
}

// Render code lines with line numbers
function renderCodeLines(lines, type, startLine) {
  if (!lines || lines.length === 0) {
    return '<div class="code-line line-context"><span class="line-number">-</span><span class="line-code">No content</span></div>';
  }
  
  return lines.map((line, index) => {
    const lineNum = parseInt(startLine) + index;
    const lineClass = type === 'added' ? 'line-added' : type === 'removed' ? 'line-removed' : 'line-context';
    
    return `
      <div class="code-line ${lineClass}">
        <span class="line-number">${lineNum}</span>
        <span class="line-code">${escapeHtml(line) || ' '}</span>
      </div>
    `;
  }).join('');
}

// Toggle diff visibility
function toggleDiff(changeId) {
  const diffContent = document.getElementById(`diff-${changeId}`);
  const icon = document.getElementById(`icon-${changeId}`);
  
  if (diffContent.classList.contains('expanded')) {
    diffContent.classList.remove('expanded');
    icon.classList.remove('expanded');
  } else {
    diffContent.classList.add('expanded');
    icon.classList.add('expanded');
  }
}

// Apply a single change
async function applyChange(changeId) {
  const changeElement = document.querySelector(`[data-change-id="${changeId}"]`);
  const changeIndex = parseInt(changeId.split('-')[1]);
  debugger;
  console.log("Dhusnic All Index :          ",changeIndex);
  console.log("Dhusnic All Changes :          ",allChanges);
  changeIndex = changeIndex +1;
  try {
    change = allChanges[changeIndex];
  } catch (error) {
    change = allChanges[changeIndex - 1];
  }
  let repo_path = document.getElementById("repoPath").value;
  if (!change) {
    showToast('Change not found', 'error');
    return;
  }

  try {
    showToast('Applying change...', 'info');
    
    const response = await fetch(`${API_BASE}/api/apply-changes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        repo_path: repo_path,
        file_path: change.diff.file_path,
        new_content: change.diff.new_content,
        line_number: change.diff.new_start_line_number,
        new_start_line_number: change.diff.new_start_line_number,
        number_of_lines_removed_from_old: change.diff.number_of_lines_removed_from_old,
        number_of_lines_added_in_new: change.diff.number_of_lines_added_in_new,
        old_start_line_number: change.diff.old_start_line_number|| change.diff.line_number,
        old_content: change.diff.old_content
      })
    });

    if (!response.ok) {
      throw new Error('Failed to apply change');
    }

    const result = await response.json();
    
    // Mark as applied
    appliedChanges.add(changeId);
    changeElement.classList.add('applied');
    
    const statusIndicator = document.getElementById(`status-${changeId}`);
    statusIndicator.style.display = 'flex';
    statusIndicator.className = 'status-indicator applied';
    statusIndicator.innerHTML = '<i class="fas fa-check-circle"></i> Applied';
    
    showToast('✅ Change applied successfully!', 'success');
    
  } catch (error) {
    showToast('❌ Failed to apply change: ' + error.message, 'error');
  }
}

// Cancel a change
function cancelChange(changeId) {
  const changeElement = document.querySelector(`[data-change-id="${changeId}"]`);
  
  cancelledChanges.add(changeId);
  changeElement.classList.add('cancelled');
  
  const statusIndicator = document.getElementById(`status-${changeId}`);
  statusIndicator.style.display = 'flex';
  statusIndicator.className = 'status-indicator cancelled';
  statusIndicator.innerHTML = '<i class="fas fa-times-circle"></i> Cancelled';
  
  // Collapse the diff
  const diffContent = document.getElementById(`diff-${changeId}`);
  const icon = document.getElementById(`icon-${changeId}`);
  diffContent.classList.remove('expanded');
  icon.classList.remove('expanded');
  
  showToast('Change cancelled', 'info');
}

// Copy a single change
function copyChange(changeId) {
  const changeIndex = parseInt(changeId.split('-')[1]);
  const change = allChanges[changeIndex];
  
  if (!change) return;
  
  const text = `File: ${change.diff.file_path}\nLine: ${change.diff.line_number}\n\nNew Content:\n${change.diff.new_content}\n\nExplanation: ${change.explanation}`;
  
  navigator.clipboard.writeText(text).then(() => {
    showToast('✓ Change copied to clipboard', 'success');
  }).catch(err => {
    showToast('Failed to copy', 'error');
  });
}

// Copy all changes
function copyAllChanges() {
  const text = allChanges.map(change => {
    return `File: ${change.diff.file_path}\nLine: ${change.diff.line_number}\n\nNew Content:\n${change.diff.new_content}\n\nExplanation: ${change.explanation}\n\n${'='.repeat(80)}\n`;
  }).join('\n');
  
  navigator.clipboard.writeText(text).then(() => {
    showToast('✓ All changes copied to clipboard', 'success');
  }).catch(err => {
    showToast('Failed to copy', 'error');
  });
}

// Apply all changes
async function applyAllChanges() {
  if (allChanges.length === 0) {
    showToast('No changes to apply', 'info');
    return;
  }

  const confirmApply = confirm(`Apply all ${allChanges.length} changes?`);
  if (!confirmApply) return;

  showToast(`Applying ${allChanges.length} changes...`, 'info');
  
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < allChanges.length; i++) {
    const changeId = `change-${i}-0`;
    
    if (!cancelledChanges.has(changeId) && !appliedChanges.has(changeId)) {
      try {
        await applyChange(changeId);
        successCount++;
        await new Promise(resolve => setTimeout(resolve, 300)); // Small delay between applies
      } catch (error) {
        failCount++;
      }
    }
  }

  showToast(`✅ Applied ${successCount} changes. ${failCount} failed.`, 'success');
}

// Filter changes by category
function filterByCategory(category) {
  currentFilter = category;
  
  // Update active button
  document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');
  
  // Filter change items
  document.querySelectorAll('.change-item').forEach(item => {
    const categories = item.dataset.categories.split(',');
    
    if (category === 'all' || categories.includes(category)) {
      item.classList.remove('hidden');
    } else {
      item.classList.add('hidden');
    }
  });
}

// Escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
