/* Settings Page Script */

import { getSettings, updateSettings } from '/static/shared/js/api.js';
import { initTheme, toggleTheme } from '/static/shared/js/theme.js';

// Initialize theme
initTheme();

// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

// Load settings
async function loadSettings() {
  try {
    const settings = await getSettings();
    
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('settings-form').classList.remove('hidden');
    
    // Populate form
    document.getElementById('user_data_path').value = settings.user_data_path || '';
    document.getElementById('venv_path').value = settings.venv_path || '';
    document.getElementById('python_executable').value = settings.python_executable || '';
    document.getElementById('freqtrade_executable').value = settings.freqtrade_executable || '';
    document.getElementById('use_module_execution').checked = settings.use_module_execution;
    
  } catch (error) {
    console.error('Failed to load settings:', error);
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('error').textContent = 'Failed to load settings. Please try again.';
    document.getElementById('error').classList.remove('hidden');
  }
}

// Save settings
document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const settings = {
    user_data_path: document.getElementById('user_data_path').value,
    venv_path: document.getElementById('venv_path').value,
    python_executable: document.getElementById('python_executable').value,
    freqtrade_executable: document.getElementById('freqtrade_executable').value,
    use_module_execution: document.getElementById('use_module_execution').checked,
  };
  
  try {
    await updateSettings(settings);
    
    // Show success message
    const successMessage = document.getElementById('success-message');
    successMessage.classList.remove('hidden');
    
    // Hide success message after 3 seconds
    setTimeout(() => {
      successMessage.classList.add('hidden');
    }, 3000);
    
  } catch (error) {
    console.error('Failed to save settings:', error);
    alert('Failed to save settings. Please try again.');
  }
});

// Cancel button - reload settings
document.getElementById('cancel-btn').addEventListener('click', () => {
  loadSettings();
});

// Load settings on mount
loadSettings();
