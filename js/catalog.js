/* Catálogo estático da loja. A aplicação consome esta fonte única de produtos. */
(function () {
  'use strict';
  var products = [
    {id:'dryfit-preta',category:'camisetas',line:'Dry Fit',name:'Camiseta Dry Fit Preta',price:60,images:['img/dryfit-preta-frente-new.jpg','img/dryfit-preta-verso-new.jpg'],desc:'Camiseta esportiva leve, respirável e confortável para treino e rotina.'},
    {id:'alg-preta',category:'camisetas',line:'Algodão 30.1',name:'Camiseta Algodão 30.1 Preta',price:90,images:['img/algodao-preta-frente-new.jpg','img/algodao-preta-verso-new.jpg'],desc:'Algodão 30.1 macio, respirável e com acabamento minimalista.'},
    {id:'alg-off',category:'camisetas',line:'Algodão 30.1',name:'Camiseta Algodão 30.1 Off White',price:90,images:['img/algodao-offwhite-frente-new.jpg','img/algodao-offwhite-verso-new.jpg'],desc:'Algodão 30.1 com toque confortável e cor off white sofisticada.'},
    {id:'alg-branca',category:'camisetas',line:'Algodão 30.1',name:'Camiseta Algodão 30.1 Branca',price:90,images:['img/camiseta-branca-frente-new.jpg','img/camiseta-branca-verso-new.jpg'],desc:'Peça essencial em algodão 30.1, limpa e versátil.'},
    {id:'prem-preta',category:'camisetas',line:'Premium',name:'Camiseta Premium Preta',price:120,images:['img/premium-preta-frente-new.jpg','img/premium-preta-verso-new.jpg'],desc:'Linha superior com tecido de toque mais encorpado e acabamento refinado.'},
    {id:'prem-branca',category:'camisetas',line:'Premium',name:'Camiseta Premium Branca',price:120,images:['img/premium-branca-frente-new.jpg','img/premium-branca-verso-new.jpg'],desc:'Tecido premium, caimento elegante e conforto elevado.'},
    {id:'prem-cinza',category:'camisetas',line:'Premium',name:'Camiseta Premium Cinza',price:120,images:['img/premium-cinza-frente-new.jpg','img/premium-cinza-verso-new.jpg'],desc:'Linha premium em cinza, com visual discreto e acabamento superior.'},
    {id:'over-marrom',category:'camisetas',line:'Oversized',name:'Camiseta Oversized Marrom',price:100,images:['img/oversized-marrom-frente-new.jpg','img/oversized-marrom-verso-new.jpg'],desc:'Modelagem ampla, moderna e confortável.'},
    {id:'over-branca',category:'camisetas',line:'Oversized',name:'Camiseta Oversized Branca',price:100,images:['img/oversized-branca-frente-new.jpg','img/oversized-branca-verso-new.jpg'],desc:'Modelagem oversized branca com identidade minimalista LIOR.'},
    {id:'moletom-preto',category:'moletons',line:'Canguru',name:'Moletom Canguru Preto',price:120,images:['img/moletom-preto-frente-new.jpg','img/moletom-preto-verso-new.jpg'],desc:'Moletom com capuz, bolso canguru e punhos ajustados.'},
    {id:'comp-preto',category:'shorts',line:'Dry Fit com Compressão',name:'Shorts Dry Fit com Compressão Preto',price:59,images:['img/short-compressao-preto-frente-new.jpg','img/short-compressao-preto-verso-new.jpg'],desc:'Shorts esportivo com camada de compressão interna.'},
    {id:'comp-chumbo',category:'shorts',line:'Dry Fit com Compressão',name:'Shorts Dry Fit com Compressão Chumbo',price:59,images:['img/short-compressao-chumbo-frente-new.jpg','img/short-compressao-chumbo-verso-new.jpg'],desc:'Performance e conforto em tom chumbo.'},
    {id:'comp-marinho',category:'shorts',line:'Dry Fit com Compressão',name:'Shorts Dry Fit com Compressão Azul Marinho',price:59,images:['img/short-compressao-marinho-frente-new.jpg','img/short-compressao-marinho-verso-new.jpg'],desc:'Shorts esportivo azul-marinho com compressão.'},
    {id:'comp-branco',category:'shorts',line:'Dry Fit com Compressão',name:'Shorts Dry Fit com Compressão Branco',price:59,images:['img/short-compressao-branco-frente-new.jpg','img/short-compressao-branco-verso-new.jpg'],desc:'Shorts branco com forro de compressão preto.'},
    {id:'elas-branco',category:'shorts',line:'Elastano sem Forro',name:'Shorts Elastano Branco',price:45,images:['img/short-elastano-branco-frente-new.jpg','img/short-elastano-branco-verso-new.jpg'],desc:'Shorts leve com elastano, sem forro interno.'},
    {id:'elas-preto',category:'shorts',line:'Elastano sem Forro',name:'Shorts Elastano Preto',price:45,images:['img/short-elastano-preto-frente-new.jpg','img/short-elastano-preto-verso-new.jpg'],desc:'Shorts preto com elastano, leve e sem forro interno.'},
    {id:'calca-preta',category:'calcas',line:'Tactel com Elastano',name:'Calça Tactel com Elastano Preta',price:70,images:['img/calca-preta-frente-new.jpg','img/calca-preta-verso-new.jpg'],desc:'Calça leve com cintura ajustável, bolsos e punho na barra.'},
    {id:'calca-cinza',category:'calcas',line:'Tactel com Elastano',name:'Calça Tactel com Elastano Cinza',price:70,images:['img/calca-cinza-frente-new.jpg','img/calca-cinza-verso-new.jpg'],desc:'Tactel com elastano em cinza, confortável e versátil.'},
    {id:'cv-preta-sem',category:'cortaventos',line:'Sem Forro',name:'Corta-Vento Preta sem Forro',price:100,images:['img/cortavento-preta-sem-frente-new.jpg','img/cortavento-preta-sem-verso-new.jpg','img/cortavento-preta-sem-detalhe-new.jpg'],desc:'Jaqueta leve, sem forro interno, com capuz e bolsos.'},
    {id:'cv-chumbo-sem',category:'cortaventos',line:'Sem Forro',name:'Corta-Vento Chumbo sem Forro',price:100,images:['img/cortavento-chumbo-sem-frente-new.jpg','img/cortavento-chumbo-sem-verso-new.jpg','img/cortavento-chumbo-sem-detalhe-new.jpg'],desc:'Corta-vento chumbo leve e sem forro.'},
    {id:'cv-marinho-sem',category:'cortaventos',line:'Sem Forro',name:'Corta-Vento Azul Marinho sem Forro',price:100,images:['img/cortavento-marinho-sem-frente-new.jpg','img/cortavento-marinho-sem-verso-new.jpg','img/cortavento-marinho-sem-detalhe-new.jpg'],desc:'Corta-vento azul-marinho sem forro interno.'},
    {id:'cv-preta-forro',category:'cortaventos',line:'Com Forro',name:'Corta-Vento Preta com Forro',price:100,images:['img/cortavento-preta-forro-frente-new.jpg','img/cortavento-preta-forro-verso-new.jpg','img/cortavento-preta-forro-detalhe-new.jpg'],desc:'Jaqueta preta com forro interno em tela respirável.'},
    {id:'cv-verde-forro',category:'cortaventos',line:'Com Forro',name:'Corta-Vento Verde Militar com Forro',price:100,images:['img/cortavento-verde-forro-frente-new.jpg','img/cortavento-verde-forro-verso-new.jpg','img/cortavento-verde-forro-detalhe-new.jpg'],desc:'Jaqueta verde militar com forro interno em tela.'}
  ];
  var cats = [
    {id:'camisetas',name:'Camisetas',icon:'shirt',desc:'Algodão Premium e Oversized',image:'img/categories_v9/category-camisetas-v9.jpg'},
    {id:'shorts',name:'Shorts',icon:'shorts',desc:'Compressão e elastano',image:'img/categories_v9/category-shorts-v9.jpg'},
    {id:'calcas',name:'Calças',icon:'pants',desc:'Tactel com elastano',image:'img/categories_v9/category-calcas-v9.jpg'},
    {id:'moletons',name:'Moletons',icon:'hoodie',desc:'Conforto para dias frios',image:'img/categories_v9/category-moletons-v9.jpg'},
    {id:'cortaventos',name:'Corta-Ventos',icon:'wind',desc:'Com e sem forro',image:'img/categories_v9/category-cortaventos-v9.jpg'}
  ];
  window.LIOR_CATALOG = { products: products, categories: cats };
}());

(function () {
  'use strict';
  var products = window.LIOR_CATALOG.products;
  var categories = window.LIOR_CATALOG.categories;
  var current = null;
  var galleryIndex = 0;
  var currentCategory = 'all';
  var currentLine = 'all';
  var zoomScale = 1;

  function byId(id) { return document.getElementById(id); }
  function money(value) {
    return Number(value || 0).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
  }
  function renderReviews() {
    var list = byId('reviewsList');
    if (!list || !current) return;
    var reviews = [];
    try { reviews = JSON.parse(localStorage.getItem('lior_reviews') || '{}')[current.id] || []; } catch (_) {}
    byId('reviewsCount').textContent = reviews.length + ' avaliação' + (reviews.length === 1 ? '' : 'ões');
    list.innerHTML = reviews.map(function (review) {
      return '<article class="review-card"><strong>' + escapeHtml(review.name) + '</strong><span class="stars-display">' +
        '★★★★★'.slice(0, review.stars || 5) + '</span><p>' + escapeHtml(review.text) + '</p></article>';
    }).join('') || '<div class="empty-reviews">Ainda não há avaliações publicadas para este produto.</div>';
  }
  function openZoom() {
    if (!current) return;
    byId('zoomImage').src = current.images[galleryIndex];
    byId('zoomTitle').textContent = current.name;
    zoomScale = 1;
    byId('zoomImage').style.setProperty('--zoom-scale', zoomScale);
    byId('zoomLevel').textContent = '100%';
    byId('zoomViewer').className = 'zoom-viewer show';
  }
  function closeZoom() { byId('zoomViewer').className = 'zoom-viewer'; }
  function setZoom(value) {
    zoomScale = Math.max(1, Math.min(4, value));
    byId('zoomImage').style.setProperty('--zoom-scale', zoomScale);
    byId('zoomLevel').textContent = Math.round(zoomScale * 100) + '%';
  }
  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
      return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char];
    });
  }
  function find(id) {
    return products.find(function (product) { return product.id === id; }) || null;
  }
  function renderCategories() {
    var grid = byId('categoryGrid');
    var filter = byId('categoryFilterBar');
    var select = byId('categoryFilter');
    if (!grid || !filter || !select) return;
    grid.innerHTML = categories.map(function (category) {
      return '<button class="category-card category-image-card" data-cat="' + category.id +
        '" data-category-card="' + category.id + '"><img class="category-final-image" src="' +
        category.image + '" alt="' + escapeHtml(category.name) + ' — ' +
        escapeHtml(category.desc) + '" loading="eager"></button>';
    }).join('');
    filter.innerHTML = '<button class="active" data-category-view-filter="all">Todas</button>' +
      categories.map(function (category) {
        return '<button data-category-view-filter="' + category.id + '">' + category.name + '</button>';
      }).join('');
    select.innerHTML = '<option value="all">Todas as categorias</option>' +
      categories.map(function (category) {
        return '<option value="' + category.id + '">' + category.name + '</option>';
      }).join('');
  }
  function renderProducts() {
    var grid = byId('productGrid');
    if (!grid) return;
    var toolbar = byId('categoryFilter') && byId('categoryFilter').parentNode;
    var lineHost = byId('shirtLineFilters');
    if (!lineHost && toolbar && toolbar.parentNode) {
      lineHost = document.createElement('div');
      lineHost.id = 'shirtLineFilters';
      lineHost.className = 'shirt-line-filters';
      toolbar.parentNode.appendChild(lineHost);
    }
    if (lineHost) {
      var lines = ['Algodão 30.1', 'Premium', 'Oversized'];
      lineHost.className = currentCategory === 'camisetas' ? 'shirt-line-filters' : 'shirt-line-filters hidden';
      lineHost.innerHTML = currentCategory === 'camisetas' ? '<span>Escolha a linha:</span>' +
        lines.map(function (line) {
          return '<button class="' + (line === currentLine ? 'active' : '') +
            '" data-shirt-line="' + line + '">' + line + '</button>';
        }).join('') : '';
    }
    var term = (byId('searchInput') && byId('searchInput').value || '').toLowerCase();
    var line = currentLine;
    var favoriteIds = window.LIOR_CART ? window.LIOR_CART.favorites() : [];
    var visible = products.filter(function (product) {
      return (currentCategory === 'all' || product.category === currentCategory) &&
        (line === 'all' || product.line === line) &&
        (!term || product.name.toLowerCase().indexOf(term) !== -1);
    });
    grid.innerHTML = visible.length ? visible.map(function (product) {
      var favorite = favoriteIds.indexOf(product.id) !== -1;
      return '<article class="product-card"><button class="favorite-card-button ' +
        (favorite ? 'active' : '') + '" data-favorite="' + product.id +
        '" aria-label="Salvar como favorito">◇</button><button class="product-photo" data-product="' +
        product.id + '"><img src="' + product.images[0] + '" alt="' + escapeHtml(product.name) +
        '"></button><div class="product-info"><div class="line">' + escapeHtml(product.line) +
        '</div><h3>' + escapeHtml(product.name) + '</h3><div class="price">' + money(product.price) +
        '</div><button class="primary" data-product="' + product.id + '">Ver produto</button></div></article>';
    }).join('') : '<div class="empty">Nenhum produto encontrado.</div>';
  }
  function showProduct(id) {
    current = find(id);
    if (!current) return;
    galleryIndex = 0;
    byId('modalCategory').textContent = current.line;
    byId('modalName').textContent = current.name;
    byId('modalPrice').textContent = money(current.price);
    byId('modalDescription').textContent = current.desc;
    byId('qtyInput').value = 1;
    byId('sizeOptions').innerHTML = ['P', 'M', 'G', 'GG'].map(function (size) {
      return '<button class="size-btn ' + (size === 'M' ? 'active' : '') +
        '" data-size="' + size + '">' + size + '</button>';
    }).join('');
    byId('thumbs').innerHTML = current.images.map(function (image, index) {
      return '<button type="button" class="thumb-button ' + (!index ? 'active' : '') +
        '" data-gallery-index="' + index + '"><img src="' + image + '" alt=""></button>';
    }).join('');
    updateGallery();
    renderReviews();
    byId('overlay').className = 'overlay show';
    byId('productModal').className = 'modal product-modal show';
  }
  function updateGallery() {
    if (!current) return;
    galleryIndex = (galleryIndex + current.images.length) % current.images.length;
    var image = byId('modalImage');
    image.src = current.images[galleryIndex];
    image.alt = current.name;
    byId('galleryCounter').textContent = (galleryIndex + 1) + ' / ' + current.images.length;
    Array.prototype.forEach.call(byId('thumbs').children, function (button, index) {
      button.className = 'thumb-button ' + (index === galleryIndex ? 'active' : '');
    });
  }
  function openCategory(category) {
    currentCategory = category || 'all';
    currentLine = 'all';
    var selected = categories.find(function (item) { return item.id === currentCategory; });
    byId('categoryFilter').value = currentCategory;
    byId('productTitle').textContent = selected ? selected.name : 'Todos os produtos';
    renderProducts();
    window.LIOR_APP.showView('products');
  }
  window.LIOR_CATALOG_UI = {
    init: function () { renderCategories(); renderProducts(); },
    products: function () { return products; },
    find: find,
    renderProducts: renderProducts,
    renderCategories: renderCategories,
    openCategory: openCategory,
    showProduct: showProduct,
    updateGallery: updateGallery,
    openZoom: openZoom,
    closeZoom: closeZoom,
    setZoom: setZoom,
    current: function () { return current; },
    setCategory: function (category) { currentCategory = category || 'all'; renderProducts(); },
    setLine: function (line) { currentLine = line || 'all'; renderProducts(); },
    money: money
  };
}());
