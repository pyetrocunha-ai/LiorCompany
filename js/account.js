/* Dados locais mantidos apenas como fallback para checkout sem sessão. */
(function () {
  'use strict';
  window.LIOR_ACCOUNT = {
    readLocal: function () {
      try { return JSON.parse(localStorage.getItem('lior_account') || '{}') || {}; }
      catch (_) { return {}; }
    },
    writeLocal: function (account) {
      try { localStorage.setItem('lior_account', JSON.stringify(account)); } catch (_) {}
    }
  };
  window.accountAddressText = function (account) {
    account = account || {};
    return [account.recipient || account.name, account.street && (account.street + (account.number ? ', ' + account.number : '')), account.complement, account.district, account.city]
      .filter(Boolean).join(' · ');
  };
}());

(function () {
  'use strict';
  var state = {user: null, csrfToken: '', loading: false};
  window.LIOR_AUTH_STATE = state;
  var reviewTarget = null;
  var reviewStars = 5;
  function byId(id) { return document.getElementById(id); }
  function local() {
    return window.LIOR_ACCOUNT.readLocal();
  }
  function saveLocal(value) {
    window.LIOR_ACCOUNT.writeLocal(value);
    return value;
  }
  function orders() {
    try {
      var value = JSON.parse(localStorage.getItem('lior_orders') || '[]');
      return Array.isArray(value) ? value : [];
    } catch (_) { return []; }
  }
  function saveOrders(value) {
    try { localStorage.setItem('lior_orders', JSON.stringify(value)); } catch (_) {}
  }
  function message(id, text, error) {
    var node = byId(id);
    if (!node) return;
    node.textContent = text || '';
    node.className = 'auth-message' + (error ? ' error' : '');
  }
  function showAuthView(view) {
    ['loginForm', 'registerForm', 'forgotForm'].forEach(function (id) {
      byId(id).classList.toggle('is-hidden', id !== view + 'Form');
    });
  }
  function switchTab(name) {
    document.querySelectorAll('[data-account-tab]').forEach(function (tab) {
      tab.classList.toggle('active', tab.getAttribute('data-account-tab') === name);
    });
    ['orders', 'favorites', 'profile', 'addresses', 'payments', 'security'].forEach(function (tab) {
      var panel = byId('account' + tab.charAt(0).toUpperCase() + tab.slice(1) + 'Panel');
      if (panel) panel.classList.toggle('active', tab === name);
    });
    if (name === 'favorites' && window.LIOR_CART) window.LIOR_CART.renderFavorites(byId('accountFavorites'));
  }
  function userData() {
    var user = state.user || {};
    return user.user || user;
  }
  function paint(authenticated) {
    byId('accountAuthPanel').classList.toggle('is-hidden', authenticated);
    byId('accountPrivateArea').classList.toggle('is-hidden', !authenticated);
    byId('accountModal').classList.toggle('is-authenticated', authenticated);
    document.querySelector('.customer-account-sidebar').classList.toggle('is-locked', !authenticated);
  }
  function fill(user) {
    var profile = user.profile || {};
    var address = user.address || {};
    var value = Object.assign({}, profile, address, {email: profile.email || user.email || ''});
    saveLocal(value);
    [['accountName', value.name], ['accountNickname', value.nickname], ['accountCpf', value.cpf],
      ['accountContact', value.contact || value.email], ['accountBirthDate', value.birthDate],
      ['accountCep', value.cep], ['accountRecipient', value.recipient || value.name],
      ['accountStreet', value.street], ['accountNumber', value.number], ['accountComplement', value.complement],
      ['accountReference', value.reference], ['accountDistrict', value.district], ['accountCity', value.city]]
      .forEach(function (entry) { if (byId(entry[0])) byId(entry[0]).value = entry[1] || ''; });
    byId('customerGreeting').textContent = value.nickname || value.name || 'Cliente LIOR';
    byId('customerAvatar').textContent = (value.nickname || value.name || 'L').charAt(0).toUpperCase();
    if (byId('accountContactType')) byId('accountContactType').value = value.contactType === 'phone' ? 'phone' : 'email';
    renderOrders();
    if (window.LIOR_CART) window.LIOR_CART.renderFavorites(byId('accountFavorites'));
    if (state.user) loadOrders();
  }
  function renderOrders() {
    var box = byId('accountOrders');
    if (!box) return;
    var value = orders();
    box.innerHTML = value.slice().reverse().map(function (order, reverseIndex) {
      var orderIndex = value.length - reverseIndex - 1;
      return '<article class="account-order"><h3>Pedido ' + order.id + '</h3><strong>' +
        (order.paymentMethod || 'Pagamento') + '</strong><p>Total: ' +
        Number(order.total || 0).toLocaleString('pt-BR', {style:'currency', currency:'BRL'}) +
        '</p><span class="order-status">' + (order.status || 'placed') + '</span>' +
        (order.items || []).map(function (item, itemIndex) {
          return '<div class="order-item"><span>' + item.id + ' · tam. ' + item.size + '</span>' +
            (order.status === 'delivered' && !item.reviewed ?
              '<button class="primary" data-review-order="' + orderIndex + '" data-review-item="' + itemIndex + '">Avaliar produto</button>' : '') +
            '</div>';
        }).join('') + '</article>';
    }).join('') || '<div class="empty account-empty-order"><strong>Você ainda não possui pedidos.</strong></div>';
  }
  async function loadOrders() {
    if (!state.user) return;
    try {
      var data = await auth('/api/orders');
      if (Array.isArray(data.orders)) saveOrders(data.orders);
      renderOrders();
    } catch (_) {}
  }
  function openReview(orderIndex, itemIndex) {
    var value = orders();
    if (!value[orderIndex] || !value[orderIndex].items || !value[orderIndex].items[itemIndex]) return;
    reviewTarget = {orderIndex: orderIndex, itemIndex: itemIndex};
    reviewStars = 5;
    byId('accountReviewProduct').textContent = value[orderIndex].items[itemIndex].id;
    byId('accountReviewText').value = '';
    byId('accountReviewModal').className = 'account-modal review-account-modal show';
  }
  function closeReview() {
    reviewTarget = null;
    byId('accountReviewModal').className = 'account-modal review-account-modal';
  }
  function submitReview() {
    if (!reviewTarget) return;
    var text = byId('accountReviewText').value.trim();
    if (!text) { byId('accountReviewMessage').textContent = 'Escreva um comentário antes de publicar.'; return; }
    var value = orders();
    value[reviewTarget.orderIndex].items[reviewTarget.itemIndex].reviewed = true;
    saveOrders(value);
    var item = value[reviewTarget.orderIndex].items[reviewTarget.itemIndex];
    var reviews = {};
    try { reviews = JSON.parse(localStorage.getItem('lior_reviews') || '{}'); } catch (_) {}
    reviews[item.id] = reviews[item.id] || [];
    reviews[item.id].push({name:local().nickname || local().name || 'Cliente LIOR', text:text,
      stars:reviewStars, createdAt:Date.now()});
    try { localStorage.setItem('lior_reviews', JSON.stringify(reviews)); } catch (_) {}
    closeReview();
    renderOrders();
  }
  async function auth(path, options) {
    var data = options || {};
    data.method = data.method || 'GET';
    if (data.method !== 'GET') data.headers = Object.assign({}, data.headers, {'X-CSRF-Token': state.csrfToken});
    var response = await window.LIOR_API.request(path, data);
    if (response.csrfToken) state.csrfToken = response.csrfToken;
    return response;
  }
  async function refresh() {
    if (state.loading) return;
    state.loading = true;
    try {
      var data = await auth('/api/auth/me');
      state.user = data.authenticated ? data.user : null;
      paint(Boolean(state.user));
      if (state.user) fill(state.user);
    } catch (error) {
      state.user = null;
      paint(false);
      message('loginMessage', error.message, true);
    } finally { state.loading = false; }
  }
  async function saveProfile() {
    var profile = {name: byId('accountName').value, nickname: byId('accountNickname').value,
      cpf: byId('accountCpf').value, contactType: byId('accountContactType').value,
      contact: byId('accountContact').value, birthDate: byId('accountBirthDate').value,
      gender: (document.querySelector('input[name="accountGender"]:checked') || {}).value || ''};
    try { var data = await auth('/api/account/profile', {method:'POST', body: profile});
      state.user = data.user; fill(data.user); message('accountMessage', 'Perfil salvo com segurança.'); }
    catch (error) { message('accountMessage', error.message, true); }
  }
  async function saveAddress() {
    var address = {};
    ['cep','recipient','street','number','complement','reference','district','city'].forEach(function (key) {
      address[key] = byId('account' + key.charAt(0).toUpperCase() + key.slice(1)).value;
    });
    try { var data = await auth('/api/account/address', {method:'POST', body: address});
      state.user = data.user; fill(data.user); message('addressMessage', 'Endereço salvo com segurança.'); }
    catch (error) { message('addressMessage', error.message, true); }
  }
  function init() {
    byId('saveAccount').onclick = saveProfile;
    byId('saveAddress').onclick = saveAddress;
    byId('customerLogout').onclick = async function () {
      try { await auth('/api/auth/logout', {method:'POST', body:{}}); } catch (_) {}
      state.user = null; state.csrfToken = ''; window.LIOR_AUTH_STATE.csrfToken = ''; paint(false);
    };
    byId('openRegister').onclick = function () { showAuthView('register'); };
    byId('openLogin').onclick = function () { showAuthView('login'); };
    byId('openForgot').onclick = function () { showAuthView('forgot'); };
    byId('forgotBackLogin').onclick = function () { showAuthView('login'); };
    document.querySelectorAll('[data-account-tab]').forEach(function (tab) {
      tab.onclick = function () { switchTab(tab.getAttribute('data-account-tab')); };
    });
    byId('forgotForm').onsubmit = function (event) {
      event.preventDefault();
      message('forgotMessage', 'As instruções serão enviadas quando o serviço de e-mail da loja estiver conectado.');
    };
    byId('closeAccountReview').onclick = closeReview;
    byId('accountReviewSubmit').onclick = submitReview;
    byId('accountStarPicker').onclick = function (event) {
      var button = event.target.closest('[data-account-star]');
      if (button) reviewStars = Number(button.getAttribute('data-account-star')) || 5;
    };
    document.addEventListener('click', function (event) {
      var button = event.target.closest('[data-review-order]');
      if (button) openReview(Number(button.dataset.reviewOrder), Number(button.dataset.reviewItem));
    });
    byId('changePasswordForm').onsubmit = async function (event) {
      event.preventDefault();
      var next = byId('newPassword').value;
      if (next !== byId('confirmNewPassword').value) {
        message('passwordChangeMessage', 'A confirmação não confere.', true); return;
      }
      try {
        await auth('/api/auth/change-password', {method:'POST',
          body:{currentPassword:byId('currentPassword').value, newPassword:next}});
        this.reset(); message('passwordChangeMessage', 'Senha alterada com segurança.');
      } catch (error) { message('passwordChangeMessage', error.message, true); }
    };
    byId('savePaymentMethod').onclick = async function () {
      var selected = document.querySelector('input[name="preferredPayment"]:checked');
      if (!selected) return;
      try {
        var data = await auth('/api/account/profile', {method:'POST', body:{preferredPayment:selected.value}});
        state.user = data.user; fill(data.user); message('paymentMessage', 'Preferência salva.');
      } catch (error) { message('paymentMessage', error.message, true); }
    };
    byId('accountCep').addEventListener('input', function () {
      var value = this.value.replace(/\D/g, '').slice(0, 8);
      this.value = value.length > 5 ? value.slice(0, 5) + '-' + value.slice(5) : value;
      if (value.length !== 8) return;
      window.LIOR_API.lookupCep(value).then(function (address) {
        byId('accountDistrict').value = address.bairro || '';
        byId('accountCity').value = [address.localidade, address.uf].filter(Boolean).join(' - ');
        if (!byId('accountStreet').value) byId('accountStreet').value = address.logradouro || '';
      }).catch(function () {});
    });
    byId('loginForm').onsubmit = async function (event) {
      event.preventDefault();
      try { var data = await auth('/api/auth/login', {method:'POST',
        body:{email:byId('loginEmail').value, password:byId('loginPassword').value}});
        state.user = data.user; paint(true); fill(data.user); this.reset();
      } catch (error) { message('loginMessage', error.message, true); }
    };
    byId('loginGoogle').onclick = async function () {
      try {
        var config = await auth('/api/config');
        if (!config.googleClientId) throw new Error('O login Google ainda não foi configurado.');
        var start = function () {
          window.google.accounts.id.initialize({client_id:config.googleClientId, callback:async function (response) {
            try {
              var data = await auth('/api/auth/google', {method:'POST', body:{credential:response.credential}});
              state.user = data.user; paint(true); fill(data.user);
            } catch (error) { message('googleLoginMessage', error.message, true); }
          }});
          var googleButton = byId('googleLoginButton');
          googleButton.innerHTML = '';
          googleButton.classList.remove('is-hidden');
          byId('loginGoogle').classList.add('is-hidden');
          window.google.accounts.id.renderButton(googleButton, {theme:'outline', size:'large', text:'signin_with', shape:'rectangular', width:360});
        };
        if (window.google && window.google.accounts && window.google.accounts.id) start();
        else {
          var script = document.createElement('script');
          script.src = 'https://accounts.google.com/gsi/client';
          script.onload = start; script.onerror = function () { message('googleLoginMessage', 'Não foi possível carregar o Google.', true); };
          document.head.appendChild(script);
        }
      } catch (error) { message('googleLoginMessage', error.message, true); }
    };
    byId('registerForm').onsubmit = async function (event) {
      event.preventDefault();
      if (byId('registerPassword').value !== byId('registerPasswordConfirm').value) {
        message('registerMessage', 'As senhas não conferem.', true); return;
      }
      try { var data = await auth('/api/auth/register', {method:'POST', body:{
        name:byId('registerName').value, nickname:byId('registerNickname').value,
        cpf:byId('registerCpf').value, email:byId('registerEmail').value,
        phone:byId('registerPhone').value, birthDate:byId('registerBirthDate').value,
        password:byId('registerPassword').value}});
        state.user = data.user; paint(true); fill(data.user); this.reset();
      } catch (error) { message('registerMessage', error.message, true); }
    };
    refresh();
  }
  window.LIOR_ACCOUNT = Object.assign(window.LIOR_ACCOUNT, {
    init: init, local: local, orders: orders, saveOrders: saveOrders, loadOrders: loadOrders,
    refresh: refresh, user: userData, renderOrders: renderOrders
  });
  window.LIOR_AUTH_STATE = state;
}());
