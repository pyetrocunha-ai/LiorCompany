/* Cliente HTTP comum para as APIs autenticadas. */
(function () {
  'use strict';
  window.LIOR_API = {
    request: async function (path, options) {
      options = options || {};
      var state = window.LIOR_AUTH_STATE || {};
      var headers = Object.assign({Accept:'application/json'}, options.headers || {});
      if (options.body && typeof options.body !== 'string') {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
      }
      if (state.csrfToken && options.method && options.method !== 'GET') headers['X-CSRF-Token'] = state.csrfToken;
      var response = await fetch(path, Object.assign({credentials:'same-origin', headers:headers}, options));
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(data.error || 'Não foi possível concluir a operação.');
      return data;
    }
  };
}());

(function () {
  'use strict';
  function lookupCep(cep) {
    var cleanCep = String(cep).replace(/\D/g, '');
    return fetch('https://viacep.com.br/ws/' + cleanCep + '/json/')
      .then(function (response) {
        if (!response.ok) throw new Error('Falha ao consultar o CEP.');
        return response.json();
      }).then(function (data) {
        if (!data || data.erro) throw new Error('CEP não encontrado.');
        return data;
      }).catch(function () {
        return new Promise(function (resolve, reject) {
          var callback = 'liorCepCallback_' + Date.now();
          var script = document.createElement('script');
          var timer = setTimeout(function () { cleanup(); reject(new Error('CEP indisponível.')); }, 10000);
          function cleanup() {
            clearTimeout(timer);
            if (script.parentNode) script.parentNode.removeChild(script);
            try { delete window[callback]; } catch (_) { window[callback] = undefined; }
          }
          window[callback] = function (data) {
            cleanup();
            if (!data || data.erro) reject(new Error('CEP não encontrado.'));
            else resolve(data);
          };
          script.onerror = function () { cleanup(); reject(new Error('CEP indisponível.')); };
          script.src = 'https://viacep.com.br/ws/' + cleanCep + '/json/?callback=' + callback;
          document.head.appendChild(script);
        });
      });
  }
  window.LIOR_API.lookupCep = lookupCep;
}());
