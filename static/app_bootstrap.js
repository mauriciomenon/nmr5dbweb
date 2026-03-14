// Bootstrap da tela principal de busca.

document.addEventListener('DOMContentLoaded', () => {
  try {
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
  } catch (e) {
    const msg = e && e.message ? e.message : 'erro de inicializacao';
    logUi('ERROR', 'bootstrap falhou: ' + msg);
  }
});
