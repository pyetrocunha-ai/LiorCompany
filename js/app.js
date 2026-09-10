/* Bootstrap da loja: os módulos cuidam de estado, telas e integrações. */
(function () {
  'use strict';
  function byId(id) { return document.getElementById(id); }
  function showView(name) {
    ['home', 'categories', 'products', 'about', 'contact'].forEach(function (view) {
      var node = byId(view + 'View');
      if (node) node.className = 'view' + (view === name ? ' active' : '') +
        (view === 'home' ? '' : ' section');
    });
    window.scrollTo(0, 0);
    byId('navMenu').className = '';
  }
  function closeDrawers() {
    ['productModal', 'cartDrawer', 'searchDrawer', 'favoritesDrawer', 'accountModal'].forEach(function (id) {
      var node = byId(id);
      if (node) node.className = node.className.replace(/\s*show/g, '');
    });
    byId('overlay').className = 'overlay';
  }
  function openDrawer(id) {
    closeDrawers();
    byId('overlay').className = 'overlay show';
    byId(id).className += ' show';
  }
  function categoryFilter(filter) {
    var cards = document.querySelectorAll('[data-category-card]');
    cards.forEach(function (card) {
      var hidden = filter !== 'all' && card.getAttribute('data-category-card') !== filter;
      card.classList.toggle('category-hidden', hidden);
    });
    document.querySelectorAll('[data-category-view-filter]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-category-view-filter') === filter);
    });
  }
  function shippingEstimate(address) {
    var state = String(address.uf || '').toUpperCase();
    var local = String(address.localidade || '').toLowerCase();
    var pac = {price:24.90, min:5, max:9};
    var sedex = {price:39.90, min:2, max:5};
    if (state === 'SC') {
      pac = {price:local === 'itajaí' ? 9.90 : 14.90, min:local === 'itajaí' ? 1 : 2, max:local === 'itajaí' ? 2 : 4};
      sedex = {price:local === 'itajaí' ? 14.90 : 22.90, min:1, max:2};
    } else if (['PR', 'RS'].indexOf(state) !== -1) {
      pac = {price:18.90, min:3, max:6}; sedex = {price:29.90, min:1, max:3};
    } else if (['SP', 'RJ', 'MG', 'ES'].indexOf(state) !== -1) {
      pac = {price:22.90, min:4, max:8}; sedex = {price:36.90, min:2, max:4};
    } else if (['DF', 'GO', 'MS', 'MT'].indexOf(state) !== -1) {
      pac = {price:28.90, min:6, max:10}; sedex = {price:46.90, min:3, max:6};
    } else if (['BA', 'SE', 'AL', 'PE', 'PB', 'RN', 'CE', 'PI', 'MA'].indexOf(state) !== -1) {
      pac = {price:34.90, min:7, max:13}; sedex = {price:59.90, min:4, max:8};
    } else if (['TO', 'PA', 'AP', 'AM', 'RR', 'RO', 'AC'].indexOf(state) !== -1) {
      pac = {price:42.90, min:9, max:17}; sedex = {price:74.90, min:5, max:11};
    }
    return {pac: pac, sedex: sedex};
  }
  function renderShipping(address) {
    var quote = shippingEstimate(address);
    var output = byId('shippingResult');
    output.className = 'shipping-success shipping-options';
    output.innerHTML = '<span class="shipping-destination">De Itajaí - SC para <strong>' +
      (address.localidade || 'Destino') + ' - ' + (address.uf || '') + '</strong></span>' +
      ['pac', 'sedex'].map(function (type) {
        var option = quote[type];
        return '<button type="button" class="shipping-option" data-shipping-type="' + type +
          '"><span><b>' + (type === 'pac' ? 'PAC · Envio normal' : 'SEDEX · Envio expresso') +
          '</b><small>' + option.min + ' a ' + option.max + ' dias úteis</small></span><strong>' +
          window.LIOR_CATALOG_UI.money(option.price) + '</strong></button>';
      }).join('');
    output.querySelectorAll('[data-shipping-type]').forEach(function (button) {
      button.onclick = function () {
        var type = button.getAttribute('data-shipping-type');
        window.LIOR_CART.setShipping(Object.assign({type:type, label:type === 'pac' ? 'PAC (Envio normal)' : 'SEDEX'},
          quote[type], {destination:(address.localidade || '') + ' - ' + (address.uf || ''), cep:address.cep}));
      };
    });
  }
  function bind() {
    window.LIOR_APP = {showView: showView};
    window.LIOR_CATALOG_UI.init();
    window.LIOR_CART.init();
    window.LIOR_ACCOUNT.init();
    byId('menuButton').onclick = function () { byId('navMenu').classList.toggle('show'); };
    byId('searchButton').onclick = function () { openDrawer('searchDrawer'); };
    byId('favoritesButton').onclick = function () {
      window.LIOR_CART.renderFavorites(); openDrawer('favoritesDrawer');
    };
    byId('cartButton').onclick = function () { openDrawer('cartDrawer'); };
    byId('accountButton').onclick = function () {
      window.LIOR_ACCOUNT.refresh(); openDrawer('accountModal');
    };
    byId('accountOwnerAccess').onclick = function () {
      alert('A área do lojista está temporariamente indisponível. Nenhum PIN é aceito no navegador.');
    };
    byId('closeCart').onclick = closeDrawers;
    byId('closeModal').onclick = closeDrawers;
    byId('overlay').onclick = closeDrawers;
    document.querySelectorAll('[data-close-utility]').forEach(function (button) {
      button.onclick = closeDrawers;
    });
    byId('searchInput').oninput = window.LIOR_CATALOG_UI.renderProducts;
    byId('globalSearchInput').oninput = function () {
      var term = this.value.toLowerCase();
      var result = window.LIOR_CATALOG_UI.products().filter(function (product) {
        return product.name.toLowerCase().indexOf(term) !== -1;
      });
      byId('globalSearchResults').innerHTML = result.map(function (product) {
        return '<button data-product="' + product.id + '">' + product.name + '</button>';
      }).join('') || '<div class="empty">Nenhum produto encontrado.</div>';
    };
    byId('categoryFilter').onchange = function () {
      window.LIOR_CATALOG_UI.setCategory(this.value);
      showView('products');
    };
    byId('checkoutButton').onclick = window.LIOR_CHECKOUT.open;
    byId('applyCoupon').onclick = function () {
      var valid = window.LIOR_CART.applyCoupon(byId('cartCoupon').value);
      var value = byId('cartCoupon').value.trim();
      byId('couponMessage').textContent = valid ? 'Cupom aplicado: 10% de desconto.' :
        (value ? 'Cupom inválido.' : 'Cupom removido.');
    };
    byId('calculateShipping').onclick = function () {
      var input = byId('shippingCep');
      var cep = input.value.replace(/\D/g, '');
      if (cep.length !== 8) { byId('shippingResult').textContent = 'Digite um CEP válido com 8 números.'; return; }
      window.LIOR_API.lookupCep(cep).then(renderShipping).catch(function () {
        byId('shippingResult').textContent = 'CEP não encontrado ou serviço indisponível.';
      });
    };
    document.addEventListener('click', function (event) {
      var target = event.target.closest ? event.target.closest('[data-view],[data-cat],[data-product],[data-favorite],[data-cart-minus],[data-cart-plus],[data-remove],[data-category-view-filter],[data-shirt-line],[data-gallery-index]') : null;
      if (!target) return;
      if (target.dataset.view) {
        if (target.dataset.view === 'categories') categoryFilter('all');
        showView(target.dataset.view);
        return;
      }
      if (target.dataset.categoryViewFilter) { categoryFilter(target.dataset.categoryViewFilter); return; }
      if (target.dataset.cat) { window.LIOR_CATALOG_UI.openCategory(target.dataset.cat); return; }
      if (target.dataset.shirtLine) { window.LIOR_CATALOG_UI.setLine(target.dataset.shirtLine); return; }
      if (target.dataset.product) { window.LIOR_CATALOG_UI.showProduct(target.dataset.product); return; }
      if (target.dataset.favorite) { window.LIOR_CART.toggleFavorite(target.dataset.favorite); return; }
      if (target.dataset.cartMinus) { window.LIOR_CART.change(Number(target.dataset.cartMinus), -1); return; }
      if (target.dataset.cartPlus) { window.LIOR_CART.change(Number(target.dataset.cartPlus), 1); return; }
      if (target.dataset.remove) { window.LIOR_CART.remove(Number(target.dataset.remove)); return; }
      if (target.dataset.galleryIndex) {
        window.LIOR_CATALOG_UI.updateGallery(Number(target.dataset.galleryIndex)); return;
      }
    });
    byId('qtyMinus').onclick = function () {
      var input = byId('qtyInput'); input.value = Math.max(1, Number(input.value) - 1);
    };
    byId('qtyPlus').onclick = function () {
      var input = byId('qtyInput'); input.value = Math.min(6, Number(input.value) + 1);
    };
    byId('addToCart').onclick = function () {
      var product = window.LIOR_CATALOG_UI.current();
      if (!product) return;
      var size = document.querySelector('#sizeOptions .active');
      window.LIOR_CART.add(product.id, size ? size.textContent : 'M', Number(byId('qtyInput').value) || 1);
      closeDrawers(); openDrawer('cartDrawer');
    };
    byId('sizeOptions').onclick = function (event) {
      var button = event.target.closest('[data-size]');
      if (!button) return;
      byId('sizeOptions').querySelectorAll('button').forEach(function (item) { item.classList.remove('active'); });
      button.classList.add('active');
    };
    byId('galleryPrev').onclick = function () { window.LIOR_CATALOG_UI.updateGallery(-1); };
    byId('galleryNext').onclick = function () { window.LIOR_CATALOG_UI.updateGallery(1); };
    byId('galleryZoomButton').onclick = window.LIOR_CATALOG_UI.openZoom;
    byId('modalImage').onclick = window.LIOR_CATALOG_UI.openZoom;
    byId('zoomClose').onclick = window.LIOR_CATALOG_UI.closeZoom;
    byId('zoomIn').onclick = function () {
      window.LIOR_CATALOG_UI.setZoom(Number(byId('zoomLevel').textContent.replace('%', '')) / 100 + 0.5);
    };
    byId('zoomOut').onclick = function () {
      window.LIOR_CATALOG_UI.setZoom(Number(byId('zoomLevel').textContent.replace('%', '')) / 100 - 0.5);
    };
    byId('zoomReset').onclick = function () { window.LIOR_CATALOG_UI.setZoom(1); };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
}());
