// Bootstrap da tela principal de busca.

document.addEventListener('DOMContentLoaded', () => {
  setupModalBindings();
  setupFilePanelBindings();
  setupUploadBindings();
  setupFlowBindings();
  setupIndexBindings();
  setupSearchBindings();
  setupBootstrapGlobalHandlers();
  setFlowHint('', false);
  logUi('INFO', 'modal exists=' + !!$('configModal'));
  refreshUiState({ sync: true });
  scheduleStatusPoll();
});
