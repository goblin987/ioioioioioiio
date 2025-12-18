/* ═══════════════════════════════════════════════════════════════
   HEISENBERG'S LAB - Main Application
   ═══════════════════════════════════════════════════════════════ */

// App State
const state = {
    currentSection: 'lab',
    cart: [],
    products: [],
    user: {
        name: 'PINKMAN',
        rank: 'DISTRIBUTOR',
        level: 3,
        xp: 1247,
        xpMax: 2000,
        balance: 420.69,
        heat: 45
    }
};

// Sample Products (will be replaced by API data)
const SAMPLE_PRODUCTS = [
    {
        id: 1,
        name: 'Blue Sky',
        formula: 'C₁₀H₁₅N',
        emoji: '💎',
        category: 'crystal',
        purity: 99.1,
        price: 80.00,
        stock: 12,
        batch: '#0042',
        description: 'Heisenberg\'s signature product. 99.1% pure.'
    },
    {
        id: 2,
        name: 'Chili P Special',
        formula: 'C₁₀H₁₅N + C₁₈H₂₇NO₃',
        emoji: '🌿',
        category: 'green',
        purity: 96.2,
        price: 45.00,
        stock: 8,
        batch: '#0038',
        description: 'Jesse\'s special recipe with the secret ingredient.'
    },
    {
        id: 3,
        name: 'Madrigal Tabs',
        formula: 'C₂₀H₂₅N₃O',
        emoji: '💊',
        category: 'pills',
        purity: 91.0,
        price: 35.00,
        stock: 20,
        batch: '#0051',
        description: 'Pharmaceutical grade from Madrigal Electromotive.'
    },
    {
        id: 4,
        name: 'Cap\'n Cook',
        formula: 'C₁₂H₁₇NO',
        emoji: '🍄',
        category: 'green',
        purity: 88.5,
        price: 55.00,
        stock: 3,
        batch: '#0029',
        description: 'The original recipe before Heisenberg.'
    },
    {
        id: 5,
        name: 'Los Pollos Blend',
        formula: 'C₁₀H₁₅N',
        emoji: '🐔',
        category: 'crystal',
        purity: 97.8,
        price: 70.00,
        stock: 15,
        batch: '#0044',
        description: 'Distributed through legitimate business channels.'
    },
    {
        id: 6,
        name: 'Vamonos Pest',
        formula: 'C₁₀H₁₅N',
        emoji: '🧪',
        category: 'crystal',
        purity: 95.5,
        price: 60.00,
        stock: 0,
        batch: '#0033',
        description: 'Mobile lab production. Currently unavailable.'
    }
];

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    console.log('🧪 Heisenberg\'s Lab initializing...');
    
    // Load products
    state.products = SAMPLE_PRODUCTS;
    
    // Setup event listeners
    setupIntro();
    setupNavigation();
    setupFilterTabs();
    setupModal();
    
    // Render products
    renderProducts();
    
    // Update UI
    updateBalanceDisplay();
    updateCartBadge();
    
    // Random quote rotation
    setInterval(rotateQuote, 10000);
    
    console.log('✅ Heisenberg\'s Lab ready!');
}

// ═══════════════════════════════════════════════════════════════
// INTRO SEQUENCE
// ═══════════════════════════════════════════════════════════════

function setupIntro() {
    const enterBtn = document.getElementById('enter-btn');
    const introOverlay = document.getElementById('intro-overlay');
    const mainApp = document.getElementById('main-app');
    
    if (enterBtn) {
        enterBtn.addEventListener('click', () => {
            // Play sound
            if (window.soundManager) {
                soundManager.playIntroSting();
            }
            
            // Trigger haptic
            if (window.triggerHaptic) {
                triggerHaptic('heavy');
            }
            
            // Fade out intro
            introOverlay.classList.add('fade-out');
            
            // Show main app
            setTimeout(() => {
                introOverlay.style.display = 'none';
                mainApp.classList.remove('hidden');
                
                // Play bubbling sound
                if (window.soundManager) {
                    soundManager.playBubbling();
                }
            }, 800);
        });
    }
    
    // Skip intro if already seen (optional)
    const skipIntro = sessionStorage.getItem('intro_seen');
    if (skipIntro) {
        introOverlay.style.display = 'none';
        mainApp.classList.remove('hidden');
    }
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            navigateTo(section);
            
            // Sound & haptic
            if (window.soundManager) soundManager.play('click');
            if (window.triggerHaptic) triggerHaptic('light');
        });
    });
}

function navigateTo(sectionId) {
    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === sectionId);
    });
    
    // Update section visibility
    document.querySelectorAll('.section').forEach(section => {
        section.classList.toggle('active', section.id === `section-${sectionId}`);
    });
    
    state.currentSection = sectionId;
}

// ═══════════════════════════════════════════════════════════════
// FILTER TABS
// ═══════════════════════════════════════════════════════════════

function setupFilterTabs() {
    const tabs = document.querySelectorAll('.filter-tab');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Update active state
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Filter products
            const filter = tab.dataset.filter;
            filterProducts(filter);
            
            // Sound
            if (window.soundManager) soundManager.play('click');
        });
    });
}

function filterProducts(category) {
    const filtered = category === 'all' 
        ? state.products 
        : state.products.filter(p => p.category === category);
    
    renderProducts(filtered);
}

// ═══════════════════════════════════════════════════════════════
// RENDER PRODUCTS
// ═══════════════════════════════════════════════════════════════

function renderProducts(products = state.products) {
    const grid = document.getElementById('product-grid');
    if (!grid) return;
    
    grid.innerHTML = products.map(product => createProductCard(product)).join('');
    
    // Add click listeners
    grid.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('click', () => {
            const productId = parseInt(card.dataset.id);
            openProductModal(productId);
        });
    });
    
    // Add to cart button listeners
    grid.querySelectorAll('.add-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const productId = parseInt(btn.dataset.id);
            addToCart(productId);
        });
    });
}

function createProductCard(product) {
    const purityClass = product.purity >= 95 ? 'high' : product.purity >= 85 ? 'medium' : 'low';
    const stockClass = product.stock === 0 ? 'out' : product.stock <= 5 ? 'low' : '';
    const stockText = product.stock === 0 ? 'SOLD OUT' : `${product.stock} left`;
    const imageClass = product.category === 'crystal' ? 'crystal' : '';
    
    return `
        <div class="product-card" data-id="${product.id}" data-batch="BATCH ${product.batch}">
            <span class="purity-badge ${purityClass}">${product.purity}%</span>
            <div class="product-image ${imageClass}">${product.emoji}</div>
            <div class="product-name">${product.name}</div>
            <div class="product-formula">${product.formula}</div>
            <div class="purity-section">
                <div class="purity-label">
                    <span>PURITY</span>
                    <span class="purity-value">${product.purity}%</span>
                </div>
                <div class="purity-bar">
                    <div class="purity-fill" style="width: ${product.purity}%"></div>
                </div>
            </div>
            <div class="product-footer">
                <span class="product-price">€${product.price.toFixed(2)}</span>
                <span class="product-stock ${stockClass}">${stockText}</span>
            </div>
            ${product.stock > 0 ? `
                <button class="add-btn" data-id="${product.id}">🛢️ ADD TO BARREL</button>
            ` : `
                <button class="add-btn" disabled style="opacity: 0.5; cursor: not-allowed;">UNAVAILABLE</button>
            `}
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════
// PRODUCT MODAL
// ═══════════════════════════════════════════════════════════════

function setupModal() {
    const modal = document.getElementById('product-modal');
    const closeBtn = document.getElementById('modal-close');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }
}

function openProductModal(productId) {
    const product = state.products.find(p => p.id === productId);
    if (!product) return;
    
    const modal = document.getElementById('product-modal');
    const modalBody = document.getElementById('modal-body');
    
    modalBody.innerHTML = `
        <div class="modal-product-header">
            <div class="modal-product-image">${product.emoji}</div>
            <h2 class="modal-product-name">${product.name}</h2>
            <div class="modal-product-formula">${product.formula}</div>
        </div>
        
        <div class="modal-purity-section">
            <div class="modal-purity-label">
                <span>PURITY LEVEL</span>
                <span style="color: var(--crystal-blue); font-weight: bold;">${product.purity}%</span>
            </div>
            <div class="modal-purity-bar">
                <div class="modal-purity-fill" style="width: ${product.purity}%"></div>
            </div>
        </div>
        
        <div class="modal-details">
            <div class="modal-detail-row">
                <span>Batch Number</span>
                <span>${product.batch}</span>
            </div>
            <div class="modal-detail-row">
                <span>Category</span>
                <span style="text-transform: capitalize;">${product.category}</span>
            </div>
            <div class="modal-detail-row">
                <span>Stock</span>
                <span>${product.stock > 0 ? product.stock + ' units' : 'OUT OF STOCK'}</span>
            </div>
        </div>
        
        <p style="color: var(--text-muted); font-size: 0.9em; margin-bottom: 20px; font-style: italic;">
            "${product.description}"
        </p>
        
        <div class="modal-price">
            <div class="modal-price-label">PRICE PER UNIT</div>
            <div class="modal-price-value">€${product.price.toFixed(2)}</div>
        </div>
        
        ${product.stock > 0 ? `
            <button class="modal-add-btn" onclick="addToCart(${product.id}); closeModal();">
                🛢️ ADD TO BARREL
            </button>
        ` : `
            <button class="modal-add-btn" disabled style="opacity: 0.5; cursor: not-allowed;">
                UNAVAILABLE
            </button>
        `}
    `;
    
    modal.classList.add('active');
    
    // Sound
    if (window.soundManager) soundManager.play('click');
}

function closeModal() {
    const modal = document.getElementById('product-modal');
    modal.classList.remove('active');
}

// ═══════════════════════════════════════════════════════════════
// CART FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function addToCart(productId) {
    const product = state.products.find(p => p.id === productId);
    if (!product || product.stock <= 0) return;
    
    // Check if already in cart
    const existing = state.cart.find(item => item.id === productId);
    if (existing) {
        existing.quantity++;
    } else {
        state.cart.push({ ...product, quantity: 1 });
    }
    
    // Update UI
    updateCartBadge();
    renderCart();
    
    // Effects
    if (window.soundManager) soundManager.playSuccess();
    if (window.triggerHaptic) triggerHaptic('success');
    if (window.effectsManager) effectsManager.flash('#2ECC71', 150);
    
    // Show toast
    showToast(`${product.name} added to barrel!`, 'success');
}

function removeFromCart(productId) {
    state.cart = state.cart.filter(item => item.id !== productId);
    updateCartBadge();
    renderCart();
    
    if (window.soundManager) soundManager.play('click');
}

function updateCartBadge() {
    const badge = document.getElementById('nav-cart-badge');
    const count = document.getElementById('cart-count');
    const total = state.cart.reduce((sum, item) => sum + item.quantity, 0);
    
    if (badge) {
        badge.textContent = total;
        badge.style.display = total > 0 ? 'flex' : 'none';
    }
    
    if (count) {
        count.textContent = `${total} item${total !== 1 ? 's' : ''}`;
    }
}

function renderCart() {
    const cartItems = document.getElementById('cart-items');
    const cartSummary = document.getElementById('cart-summary');
    
    if (!cartItems) return;
    
    if (state.cart.length === 0) {
        cartItems.innerHTML = `
            <div class="empty-cart">
                <span class="barrel-icon">🛢️</span>
                <p>Your barrel is empty</p>
                <p class="sub">"No half measures."</p>
            </div>
        `;
        if (cartSummary) cartSummary.style.display = 'none';
        return;
    }
    
    cartItems.innerHTML = state.cart.map(item => `
        <div class="cart-item">
            <div class="cart-item-image">${item.emoji}</div>
            <div class="cart-item-info">
                <div class="cart-item-name">${item.name}</div>
                <div class="cart-item-details">${item.purity}% pure • Qty: ${item.quantity}</div>
            </div>
            <div class="cart-item-price">€${(item.price * item.quantity).toFixed(2)}</div>
            <button class="cart-item-remove" onclick="removeFromCart(${item.id})">✕</button>
        </div>
    `).join('');
    
    // Update summary
    const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    
    if (cartSummary) {
        cartSummary.style.display = 'block';
        document.getElementById('cart-subtotal').textContent = `€${subtotal.toFixed(2)}`;
        document.getElementById('cart-total').textContent = `€${subtotal.toFixed(2)}`;
    }
}

// ═══════════════════════════════════════════════════════════════
// UI UPDATES
// ═══════════════════════════════════════════════════════════════

function updateBalanceDisplay() {
    const balanceEl = document.getElementById('user-balance');
    if (balanceEl) {
        balanceEl.textContent = `€${state.user.balance.toFixed(2)}`;
    }
}

function rotateQuote() {
    const quoteEl = document.getElementById('random-quote');
    if (quoteEl && window.getRandomQuote) {
        quoteEl.style.opacity = 0;
        setTimeout(() => {
            quoteEl.textContent = getRandomQuote();
            quoteEl.style.opacity = 1;
        }, 300);
    }
}

// ═══════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(t => t.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(-20px)';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// ═══════════════════════════════════════════════════════════════
// COOK ORDER (Checkout placeholder)
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    const cookBtn = document.getElementById('cook-order-btn');
    if (cookBtn) {
        cookBtn.addEventListener('click', () => {
            if (state.cart.length === 0) return;
            
            // Show success overlay
            const overlay = document.getElementById('success-overlay');
            overlay.classList.add('active');
            
            // Effects
            if (window.effectsManager) effectsManager.celebrateSuccess();
            if (window.soundManager) soundManager.playSuccess();
            if (window.triggerHaptic) triggerHaptic('success');
            
            // Clear cart
            state.cart = [];
            updateCartBadge();
            renderCart();
            
            // Hide overlay after delay
            setTimeout(() => {
                overlay.classList.remove('active');
                navigateTo('lab');
            }, 3000);
        });
    }
});

// Global functions for inline handlers
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.closeModal = closeModal;
window.showToast = showToast;


