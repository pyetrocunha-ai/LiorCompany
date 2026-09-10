/* Armazenamento local da sacola e favoritos, compartilhado pelos módulos da loja. */
(function () {
  'use strict';
  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
    catch (_) { return fallback; }
  }
  window.LIOR_CART = {
    load: function () { var value = read('lior_cart', []); return Array.isArray(value) ? value : []; },
    save: function (items) { try { localStorage.setItem('lior_cart', JSON.stringify(items)); } catch (_) {} },
    loadFavorites: function () { var value = read('lior_favorites', []); return Array.isArray(value) ? value : []; },
    saveFavorites: function (items) { try { localStorage.setItem('lior_favorites', JSON.stringify(items)); } catch (_) {} }
  };
}());

(function () {
  'use strict';
  var items = window.LIOR_CART.load();
  var favoriteItems = window.LIOR_CART.loadFavorites();
  var coupon = '';
  var discount = 0;
  var shipping = null;
  function byId(id) { return document.getElementById(id); }
  function products() { return window.LIOR_CATALOG_UI.products(); }
  function money(value) { return window.LIOR_CATALOG_UI.money(value); }
  function persist() { window.LIOR_CART.save(items); }
  function product(id) { return products().find(function (item) { return item.id === id; }); }
  function render() {
    var subtotal = 0;
    var count = 0;
    var html = items.map(function (item, index) {
      var selected = product(item.id);
      if (!selected) return '';
      subtotal += selected.price * item.qty;
      count += item.qty;
      return '<div class="cart-row"><img src="' + selected.images[0] + '" alt=""><div class="cart-row-info"><strong>' +
        selected.name + '</strong><small>Tam. ' + item.size + '</small><div class="cart-qty"><button data-cart-minus="' +
        index + '">−</button><span>' + item.qty + '</span><button data-cart-plus="' + index + '">+</button></div><div>' +
        money(selected.price * item.qty) + '</div></div><button class="remove-cart" data-remove="' + index + '">×</button></div>';
    }).join('');
    var freight = shipping ? Number(shipping.price) || 0 : 0;
    var applied = Math.min(discount, subtotal);
    byId('cartItems').innerHTML = html || '<div class="empty">Sua sacola está vazia.</div>';
    byId('cartSubtotal').textContent = money(subtotal);
    byId('cartDiscount').textContent = money(applied);
    byId('cartShipping').textContent = shipping ? money(freight) + ' · ' + shipping.label : 'A calcular';
    byId('cartTotal').textContent = money(Math.max(0, subtotal - applied + freight));
    byId('cartCount').textContent = count;
  }
  function add(id, size, quantity) {
    var existing = items.find(function (item) { return item.id === id && item.size === size; });
    if (existing) existing.qty = Math.min(6, existing.qty + quantity);
    else items.push({id: id, size: size, qty: Math.min(6, quantity)});
    persist();
    render();
  }
  function change(index, amount) {
    if (!items[index]) return;
    items[index].qty += amount;
    if (items[index].qty < 1) items.splice(index, 1);
    if (items[index]) items[index].qty = Math.min(6, items[index].qty);
    persist();
    render();
  }
  function remove(index) { items.splice(index, 1); persist(); render(); }
  function clear() { items.length = 0; persist(); render(); }
  function toggleFavorite(id) {
    var index = favoriteItems.indexOf(id);
    if (index === -1) favoriteItems.push(id); else favoriteItems.splice(index, 1);
    window.LIOR_CART.saveFavorites(favoriteItems);
    render();
    window.LIOR_CATALOG_UI.renderProducts();
  }
  function renderFavorites(target) {
    var box = target || byId('favoritesItems');
    if (!box) return;
    box.innerHTML = favoriteItems.map(function (id) {
      var selected = product(id);
      return selected ? '<div class="favorite-row"><img src="' + selected.images[0] + '" alt=""><div><strong>' +
        selected.name + '</strong><span>' + money(selected.price) + '</span></div><button data-product="' + id +
        '">Ver</button><button data-favorite="' + id + '">Remover</button></div>' : '';
    }).join('') || '<div class="empty">Você ainda não salvou produtos favoritos.</div>';
  }
  function applyCoupon(value) {
    coupon = String(value || '').trim().toUpperCase();
    discount = coupon === 'LIOR10' ? items.reduce(function (sum, item) {
      var selected = product(item.id);
      return sum + (selected ? selected.price * item.qty : 0);
    }, 0) * 0.1 : 0;
    render();
    return coupon === 'LIOR10';
  }
  window.LIOR_CART = Object.assign(window.LIOR_CART, {
    init: render,
    items: function () { return items.slice(); },
    favorites: function () { return favoriteItems.slice(); },
    add: add,
    change: change,
    remove: remove,
    clear: clear,
    toggleFavorite: toggleFavorite,
    renderFavorites: renderFavorites,
    applyCoupon: applyCoupon,
    coupon: function () { return coupon; },
    discount: function () { return discount; },
    shipping: function () { return shipping; },
    setShipping: function (value) { shipping = value; render(); },
    render: render
  });
}());
