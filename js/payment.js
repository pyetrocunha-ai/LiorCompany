(function () {
  'use strict';

  var controller = null;
  var pollTimer = null;
  var checkoutContext = null;
  var apiBase = (window.LIOR_CONFIG && window.LIOR_CONFIG.paymentApiBase) || '/api';

  function el(id) { return document.getElementById(id); }
  function brl(value) {
    return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }
  function show(node, visible) { if (node) node.hidden = !visible; }
  function setText(id, text) { var node = el(id); if (node) node.textContent = text; }

  function resetCheckoutUI() {
    clearInterval(pollTimer);
    pollTimer = null;
    show(el('paymentLoading'), true);
    show(el('paymentConfigMessage'), false);
    show(el('paymentResultPanel'), false);
    show(el('pixStatusPanel'), false);
    show(el('paymentBrick_container'), true);
    el('paymentBrick_container').innerHTML = '';
  }

  function openModal() {
    el('overlay').className = 'overlay show';
    el('paymentModal').className = 'payment-modal show';
  }

  async function unmountBrick() {
    if (controller && typeof controller.unmount === 'function') {
      try { await controller.unmount(); } catch (_) {}
    }
    controller = null;
  }

  async function closeCheckout() {
    clearInterval(pollTimer);
    pollTimer = null;
    await unmountBrick();
    el('overlay').className = 'overlay';
    el('paymentModal').className = 'payment-modal';
  }

  function showSetupMessage(message) {
    show(el('paymentLoading'), false);
    show(el('paymentBrick_container'), false);
    show(el('paymentConfigMessage'), true);
    var box = el('paymentConfigMessage');
    if (message) box.querySelector('p').textContent = message;
  }

  function showResult(kind, title, text, buttonText, action) {
    show(el('paymentLoading'), false);
    show(el('paymentBrick_container'), false);
    show(el('pixStatusPanel'), false);
    show(el('paymentResultPanel'), true);
    var icon = el('paymentResultIcon');
    icon.textContent = kind === 'success' ? '✓' : kind === 'pending' ? '…' : '!';
    icon.className = 'payment-result-icon ' + kind;
    setText('paymentResultKicker', kind === 'success' ? 'Pagamento aprovado' : 'Pagamento');
    setText('paymentResultTitle', title);
    setText('paymentResultText', text);
    var button = el('paymentResultButton');
    button.textContent = buttonText || 'Continuar';
    button.onclick = action || closeCheckout;
  }

  function sanitizeStatus(payment) {
    return {
      id: payment.id,
      status: payment.status,
      status_detail: payment.status_detail,
      payment_method_id: payment.payment_method_id,
      payment_type_id: payment.payment_type_id,
      transaction_amount: payment.transaction_amount,
      order_id: payment.order_id
    };
  }

  function finishApproved(payment) {
    clearInterval(pollTimer);
    pollTimer = null;
    localStorage.removeItem('lior_pending_payment');
    if (window.LIOR_STORE && typeof window.LIOR_STORE.finalizePaidOrder === 'function') {
      window.LIOR_STORE.finalizePaidOrder(sanitizeStatus(payment));
    }
    var method = payment.payment_method_id === 'pix' ? 'Pix' : 'cartão';
    showResult('success', 'Pagamento confirmado', 'O pagamento por ' + method + ' foi aprovado e o pedido já aparece em “Meus pedidos”.', 'Ver meus pedidos', async function () {
      await closeCheckout();
      var accountButton = el('accountButton');
      if (accountButton) accountButton.click();
      setTimeout(function () {
        var ordersTab = document.querySelector('[data-account-tab="orders"]');
        if (ordersTab) ordersTab.click();
      }, 120);
    });
  }

  function handleTerminalStatus(payment) {
    if (payment.status === 'approved') {
      finishApproved(payment);
      return true;
    }
    if (payment.status === 'rejected' || payment.status === 'cancelled') {
      clearInterval(pollTimer);
      pollTimer = null;
      localStorage.removeItem('lior_pending_payment');
      showResult('error', 'Pagamento não aprovado', 'Revise os dados ou escolha outra forma de pagamento.', 'Tentar novamente', function () {
        window.LIOR_PAYMENT.open(checkoutContext);
      });
      return true;
    }
    return false;
  }

  async function fetchPaymentStatus(paymentId) {
    return window.LIOR_API.request(apiBase + '/payments/' + encodeURIComponent(paymentId), {headers: {Accept: 'application/json'}});
  }

  function startAutomaticConfirmation(paymentId) {
    clearInterval(pollTimer);
    var attempts = 0;
    var check = async function () {
      attempts += 1;
      try {
        var payment = await fetchPaymentStatus(paymentId);
        if (handleTerminalStatus(payment)) return;
        setText('pixStatusText', payment.status === 'in_process' ? 'Pagamento em análise. A confirmação será automática.' : 'Aguardando o banco confirmar o Pix...');
      } catch (error) {
        setText('pixStatusText', 'Conexão instável. Tentando confirmar novamente...');
      }
      if (attempts >= 225) {
        clearInterval(pollTimer);
        pollTimer = null;
        setText('pixStatusText', 'O QR Code continua válido. Você pode fechar esta tela e voltar depois.');
      }
    };
    check();
    pollTimer = setInterval(check, 4000);
  }

  function showPix(payment) {
    var qr = payment.qr_code_base64;
    if (!qr) {
      showResult('pending', 'Pix criado', 'O pagamento foi criado, mas o QR Code não foi devolvido pelo processador. Atualize e tente novamente.', 'Fechar');
      return;
    }
    show(el('paymentLoading'), false);
    show(el('paymentBrick_container'), false);
    show(el('paymentResultPanel'), false);
    show(el('pixStatusPanel'), true);
    el('dynamicPixQr').src = 'data:image/png;base64,' + qr;
    localStorage.setItem('lior_pending_payment', JSON.stringify({ id: payment.id, context: checkoutContext, createdAt: Date.now() }));
    startAutomaticConfirmation(payment.id);
  }

  async function submitPayment(formData) {
    if (!checkoutContext.orderId) throw new Error('O pedido ainda não foi criado. Faça login e tente novamente.');
    return window.LIOR_API.request(apiBase + '/payments', {
      method: 'POST',
      body: {formData: formData, orderId: checkoutContext.orderId}
    });
  }

  async function ensureOrder() {
    if (checkoutContext.orderId) return checkoutContext.orderId;
    var result = await window.LIOR_API.request('/api/orders', {
      method: 'POST',
      body: {checkout: checkoutContext}
    });
    if (!result.order || !result.order.id) throw new Error('Não foi possível criar o pedido.');
    checkoutContext.orderId = result.order.id;
    checkoutContext.total = Number(result.order.total);
    setText('paymentTotal', brl(checkoutContext.total));
    return checkoutContext.orderId;
  }

  async function mountBrick(publicKey) {
    if (!window.MercadoPago) throw new Error('O módulo seguro de pagamentos não carregou.');
    var mp = new window.MercadoPago(publicKey, { locale: 'pt-BR', advancedFraudPrevention: true });
    var bricksBuilder = mp.bricks({ theme: 'dark' });
    var payer = {};
    if (checkoutContext.buyer && checkoutContext.buyer.email) payer.email = checkoutContext.buyer.email;
    if (checkoutContext.buyer && checkoutContext.buyer.cpf) payer.identification = { type: 'CPF', number: checkoutContext.buyer.cpf };

    controller = await bricksBuilder.create('payment', 'paymentBrick_container', {
      initialization: { amount: Number(checkoutContext.total.toFixed(2)), payer: payer },
      customization: {
        paymentMethods: {
          bankTransfer: 'all',
          creditCard: 'all',
          debitCard: 'all'
        },
        visual: {
          style: {
            theme: 'dark',
            customVariables: {
              textPrimaryColor: '#f5f1e8',
              textSecondaryColor: '#b8afa2',
              inputBackgroundColor: '#080808',
              formBackgroundColor: '#080808',
              baseColor: '#c79a4a',
              baseColorFirstVariant: '#efd18d',
              baseColorSecondVariant: '#8d672b',
              outlinePrimaryColor: '#c79a4a',
              outlineSecondaryColor: '#3f321f',
              buttonTextColor: '#080808',
              borderRadiusSmall: '0px',
              borderRadiusMedium: '0px',
              borderRadiusLarge: '0px',
              formPadding: '8px'
            }
          }
        }
      },
      callbacks: {
        onReady: function () { show(el('paymentLoading'), false); },
        onSubmit: function (payload) {
          return ensureOrder().then(function () { return submitPayment(payload.formData); }).then(function (payment) {
            if (payment.payment_method_id === 'pix') showPix(payment);
            else if (!handleTerminalStatus(payment)) {
              showResult('pending', 'Pagamento em análise', 'O banco está analisando a transação. A atualização será automática.', 'Fechar');
              localStorage.setItem('lior_pending_payment', JSON.stringify({ id: payment.id, context: checkoutContext, createdAt: Date.now() }));
              startAutomaticConfirmation(payment.id);
            }
          }).catch(function (error) {
            showResult('error', 'Não foi possível pagar', error.message, 'Tentar novamente', function () {
              window.LIOR_PAYMENT.open(checkoutContext);
            });
            throw error;
          });
        },
        onError: function (error) {
          console.error('Mercado Pago Brick:', error);
          show(el('paymentLoading'), false);
        }
      }
    });
  }

  async function open(context) {
    checkoutContext = context;
    resetCheckoutUI();
    openModal();
    setText('paymentTotal', brl(context.total));
    try {
      await ensureOrder();
      var response = await fetch(apiBase + '/config', { headers: { Accept: 'application/json' } });
      var config = await response.json();
      if (!response.ok || !config.configured || !config.publicKey) {
        showSetupMessage(config.message || 'O servidor de pagamento precisa ser configurado antes de receber pagamentos reais.');
        return;
      }
      await mountBrick(config.publicKey);
    } catch (error) {
      showSetupMessage('Abra a loja com “python server_python/app.py”. O arquivo HTML sozinho não consegue confirmar Pix nem processar cartões.');
    }
  }

  async function resumePendingPayment() {
    var raw = localStorage.getItem('lior_pending_payment');
    if (!raw) return;
    try {
      var pending = JSON.parse(raw);
      if (!pending.id || !pending.context) return;
      if (Date.now() - Number(pending.createdAt || 0) > 36 * 60 * 60 * 1000) {
        localStorage.removeItem('lior_pending_payment');
        return;
      }
      var payment = await fetchPaymentStatus(pending.id);
      if (payment.status === 'approved') {
        checkoutContext = pending.context;
        if (window.LIOR_STORE && typeof window.LIOR_STORE.finalizePaidOrder === 'function') window.LIOR_STORE.finalizePaidOrder(payment);
        localStorage.removeItem('lior_pending_payment');
      }
    } catch (_) {}
  }

  window.LIOR_PAYMENT = { open: open, close: closeCheckout };
  el('closePayment').onclick = closeCheckout;
  el('paymentResultButton').onclick = closeCheckout;
  el('overlay').addEventListener('click', function (event) {
    if (el('paymentModal').classList.contains('show')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeCheckout();
    }
  }, true);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && el('paymentModal').classList.contains('show')) closeCheckout();
  });
  setTimeout(resumePendingPayment, 600);
})();
