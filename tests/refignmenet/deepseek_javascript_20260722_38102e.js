import { formRenderer } from './form-renderer.js';

// 1. Open machine dialog
function openMachineDialog(machineData = null) {
  const dialog = document.getElementById('machineDialog');
  const container = dialog.querySelector('.form-container');
  
  // Render the form
  const form = formRenderer.render('machine', machineData);
  container.innerHTML = '';
  container.appendChild(form);
  
  // Handle save
  form.querySelector('form').addEventListener('submit', (e) => {
    e.preventDefault();
    const data = formRenderer.collect(form);
    const validation = formRenderer.validate('machine', data);
    
    if (validation.valid) {
      saveMachine(data);
    } else {
      showValidationErrors(validation.errors);
    }
  });
  
  dialog.showModal();
}

// 2. Open settings dialog
function openSettingsDialog(settingsData) {
  const container = document.getElementById('settingsRoot');
  const form = formRenderer.render('settings', settingsData);
  container.innerHTML = '';
  container.appendChild(form);
}