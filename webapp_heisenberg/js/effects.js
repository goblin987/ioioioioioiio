/* ═══════════════════════════════════════════════════════════════
   HEISENBERG'S LAB - Visual Effects
   Particles, smoke, transitions
   ═══════════════════════════════════════════════════════════════ */

class EffectsManager {
    constructor() {
        this.particles = [];
        this.isRunning = false;
    }
    
    // Create floating smoke particle
    createSmoke(container, options = {}) {
        const defaults = {
            count: 5,
            color: 'rgba(255, 255, 255, 0.1)',
            size: { min: 20, max: 50 },
            duration: { min: 3000, max: 6000 },
            spread: 100
        };
        
        const opts = { ...defaults, ...options };
        
        for (let i = 0; i < opts.count; i++) {
            setTimeout(() => {
                this.spawnSmokeParticle(container, opts);
            }, i * 200);
        }
    }
    
    spawnSmokeParticle(container, opts) {
        const particle = document.createElement('div');
        const size = opts.size.min + Math.random() * (opts.size.max - opts.size.min);
        const duration = opts.duration.min + Math.random() * (opts.duration.max - opts.duration.min);
        const startX = Math.random() * 100;
        
        particle.style.cssText = `
            position: absolute;
            bottom: 0;
            left: ${startX}%;
            width: ${size}px;
            height: ${size}px;
            background: radial-gradient(circle, ${opts.color} 0%, transparent 70%);
            border-radius: 50%;
            pointer-events: none;
            animation: smokeRise ${duration}ms ease-out forwards;
        `;
        
        container.appendChild(particle);
        
        // Remove after animation
        setTimeout(() => {
            particle.remove();
        }, duration);
    }
    
    // Create crystal sparkle effect
    createSparkle(element) {
        const rect = element.getBoundingClientRect();
        const sparkle = document.createElement('div');
        
        sparkle.style.cssText = `
            position: fixed;
            left: ${rect.left + rect.width / 2}px;
            top: ${rect.top + rect.height / 2}px;
            width: 4px;
            height: 4px;
            background: #00B4D8;
            border-radius: 50%;
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 0 10px #00B4D8, 0 0 20px #00B4D8;
        `;
        
        document.body.appendChild(sparkle);
        
        // Animate outward
        const angle = Math.random() * Math.PI * 2;
        const distance = 30 + Math.random() * 50;
        const duration = 500;
        
        sparkle.animate([
            { 
                transform: 'translate(-50%, -50%) scale(1)',
                opacity: 1 
            },
            { 
                transform: `translate(${Math.cos(angle) * distance - 50}%, ${Math.sin(angle) * distance - 50}%) scale(0)`,
                opacity: 0 
            }
        ], {
            duration: duration,
            easing: 'ease-out'
        });
        
        setTimeout(() => sparkle.remove(), duration);
    }
    
    // Create multiple sparkles
    burstSparkles(element, count = 8) {
        for (let i = 0; i < count; i++) {
            setTimeout(() => this.createSparkle(element), i * 50);
        }
    }
    
    // Screen shake effect
    shake(element, intensity = 5, duration = 500) {
        const originalTransform = element.style.transform;
        const startTime = Date.now();
        
        const shakeFrame = () => {
            const elapsed = Date.now() - startTime;
            if (elapsed >= duration) {
                element.style.transform = originalTransform;
                return;
            }
            
            const progress = elapsed / duration;
            const currentIntensity = intensity * (1 - progress);
            const x = (Math.random() - 0.5) * 2 * currentIntensity;
            const y = (Math.random() - 0.5) * 2 * currentIntensity;
            
            element.style.transform = `translate(${x}px, ${y}px)`;
            requestAnimationFrame(shakeFrame);
        };
        
        requestAnimationFrame(shakeFrame);
    }
    
    // Flash effect for notifications
    flash(color = '#00B4D8', duration = 200) {
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: ${color};
            opacity: 0.3;
            pointer-events: none;
            z-index: 9999;
        `;
        
        document.body.appendChild(flash);
        
        flash.animate([
            { opacity: 0.3 },
            { opacity: 0 }
        ], {
            duration: duration,
            easing: 'ease-out'
        });
        
        setTimeout(() => flash.remove(), duration);
    }
    
    // Create floating chemical formulas
    floatFormula(formula, startX, startY) {
        const el = document.createElement('span');
        el.textContent = formula;
        el.style.cssText = `
            position: fixed;
            left: ${startX}px;
            top: ${startY}px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            color: rgba(46, 204, 113, 0.6);
            pointer-events: none;
            z-index: 9999;
            text-shadow: 0 0 5px rgba(46, 204, 113, 0.3);
        `;
        
        document.body.appendChild(el);
        
        el.animate([
            { 
                transform: 'translateY(0) rotate(0deg)',
                opacity: 0.6 
            },
            { 
                transform: 'translateY(-100px) rotate(10deg)',
                opacity: 0 
            }
        ], {
            duration: 2000,
            easing: 'ease-out'
        });
        
        setTimeout(() => el.remove(), 2000);
    }
    
    // Blue glow pulse on cooking
    cookingPulse(element) {
        element.animate([
            { 
                boxShadow: '0 0 20px rgba(0, 180, 216, 0.3)' 
            },
            { 
                boxShadow: '0 0 60px rgba(0, 180, 216, 0.8)' 
            },
            { 
                boxShadow: '0 0 20px rgba(0, 180, 216, 0.3)' 
            }
        ], {
            duration: 1000,
            easing: 'ease-in-out'
        });
    }
    
    // Success celebration
    celebrateSuccess() {
        // Flash green
        this.flash('#2ECC71', 300);
        
        // Create crystal burst from center
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;
        
        for (let i = 0; i < 12; i++) {
            setTimeout(() => {
                const crystal = document.createElement('div');
                crystal.textContent = '💎';
                crystal.style.cssText = `
                    position: fixed;
                    left: ${centerX}px;
                    top: ${centerY}px;
                    font-size: 24px;
                    pointer-events: none;
                    z-index: 9999;
                `;
                
                document.body.appendChild(crystal);
                
                const angle = (i / 12) * Math.PI * 2;
                const distance = 150 + Math.random() * 100;
                
                crystal.animate([
                    { 
                        transform: 'translate(-50%, -50%) scale(0) rotate(0deg)',
                        opacity: 1 
                    },
                    { 
                        transform: `translate(${Math.cos(angle) * distance - 50}%, ${Math.sin(angle) * distance - 50}%) scale(1) rotate(360deg)`,
                        opacity: 0 
                    }
                ], {
                    duration: 1000,
                    easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
                });
                
                setTimeout(() => crystal.remove(), 1000);
            }, i * 50);
        }
    }
}

// Breaking Bad quotes for random display
const BB_QUOTES = [
    '"I am the one who knocks."',
    '"Say my name."',
    '"Yeah, Science!"',
    '"Tread lightly."',
    '"No half measures."',
    '"I am the danger."',
    '"Chemistry is the study of change."',
    '"Stay out of my territory."',
    '"We\'re done when I say we\'re done."',
    '"I did it for me. I liked it."'
];

function getRandomQuote() {
    return BB_QUOTES[Math.floor(Math.random() * BB_QUOTES.length)];
}

// Create global effects manager
const effectsManager = new EffectsManager();

// Export
window.effectsManager = effectsManager;
window.getRandomQuote = getRandomQuote;
window.BB_QUOTES = BB_QUOTES;


