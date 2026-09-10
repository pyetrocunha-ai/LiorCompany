/* Contrato de checkout: a prévia local é recalculada e persistida pelo servidor. */
(function () {
  'use strict';
  window.LIOR_CHECKOUT = {
    buildItems: function (cart, products) {
      return cart.map(function (item) {
        var product = products.find(function (candidate) { return candidate.id === item.id; });
        return product ? {id: product.id, name: product.name, size: item.size, qty: item.qty, unitPrice: product.price} : null;
      }).filter(Boolean);
    },
    total: function (items, freight, discount) {
      var subtotal = items.reduce(function (sum, item) { return sum + item.unitPrice * item.qty; }, 0);
      return {subtotal: subtotal, freight: Number(freight) || 0, discount: Math.min(Number(discount) || 0, subtotal), total: Math.max(0, subtotal - Math.min(Number(discount) || 0, subtotal) + (Number(freight) || 0))};
    }
  };
}());

(function () {
  'use strict';
  function account() { return window.LIOR_ACCOUNT && window.LIOR_ACCOUNT.local() || {}; }
  function addressText(value) {
    value = value || {};
    return [value.recipient || value.name, value.street && (value.street + (value.number ? ', ' + value.number : '')),
      value.complement, value.district, value.city].filter(Boolean).join(' · ');
  }
  function context() {
    var user = account();
    var items = window.LIOR_CHECKOUT.buildItems(window.LIOR_CART.items(), window.LIOR_CATALOG_UI.products());
    var shipping = window.LIOR_CART.shipping();
    var totals = window.LIOR_CHECKOUT.total(items, shipping ? shipping.price : 0, window.LIOR_CART.discount());
    return {
      subtotal: totals.subtotal, discount: totals.discount, freight: totals.freight, total: totals.total,
      coupon: window.LIOR_CART.coupon(), shipping: shipping, items: items,
      buyer: {name: user.name || '', email: user.email || user.contact || '',
        cpf: String(user.cpf || '').replace(/\D/g, ''), phone: user.phone || ''},
      address: {recipient: user.recipient || user.name || '', street: user.street || '',
        number: user.number || '', complement: user.complement || '', reference: user.reference || '',
        district: user.district || '', city: user.city || '', cep: user.cep || '',
        text: addressText(user)}
    };
  }
  function open() {
    if (!window.LIOR_CART.items().length) { alert('Sua sacola está vazia.'); return; }
    var authenticated = window.LIOR_ACCOUNT && window.LIOR_ACCOUNT.user && window.LIOR_ACCOUNT.user();
    if (!authenticated || !authenticated.id) {
      alert('Faça login na sua conta para criar e acompanhar um pedido com segurança.');
      var accountButton = document.getElementById('accountButton');
      if (accountButton) accountButton.click();
      return;
    }
    var value = context();
    window.LIOR_CHECKOUT_CONTEXT = value;
    if (window.LIOR_PAYMENT && window.LIOR_PAYMENT.open) window.LIOR_PAYMENT.open(value);
  }
  function finalize(payment) {
    var cart = window.LIOR_CART.items();
    if (!cart.length) return null;
    var paymentId = payment && payment.id ? String(payment.id) : '';
    if (paymentId && localStorage.getItem('lior_paid_' + paymentId)) {
      return localStorage.getItem('lior_paid_' + paymentId);
    }
    if (payment && payment.order_id) {
      if (paymentId) localStorage.setItem('lior_paid_' + paymentId, String(payment.order_id));
      window.LIOR_CART.clear();
      if (window.LIOR_ACCOUNT && window.LIOR_ACCOUNT.loadOrders) window.LIOR_ACCOUNT.loadOrders();
      return String(payment.order_id);
    }
    var value = context();
    var id = 'PED' + Date.now();
    var order = {id: id, createdAt: Date.now(), status: 'placed', items: value.items,
      subtotal: value.subtotal, discount: value.discount, coupon: value.coupon,
      shipping: value.shipping, total: value.total, address: value.address,
      paymentMethod: payment && payment.payment_method_id === 'pix' ? 'Pix — aprovado' : 'Cartão — aprovado',
      paymentId: paymentId};
    var orders = window.LIOR_ACCOUNT.orders();
    orders.push(order);
    window.LIOR_ACCOUNT.saveOrders(orders);
    if (paymentId) localStorage.setItem('lior_paid_' + paymentId, id);
    window.LIOR_CART.clear();
    return id;
  }
  window.LIOR_CHECKOUT = Object.assign(window.LIOR_CHECKOUT, {
    context: context,
    open: open,
    finalizePaidOrder: finalize
  });
  window.LIOR_STORE = {finalizePaidOrder: finalize, getCheckoutContext: context};
}());
