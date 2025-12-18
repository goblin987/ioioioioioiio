/* ═══════════════════════════════════════════════════════════════
   HEISENBERG'S LAB - Sound System
   Audio feedback and ambient sounds
   ═══════════════════════════════════════════════════════════════ */

class SoundManager {
    constructor() {
        this.enabled = true;
        this.volume = 0.5;
        this.sounds = {};
        this.ambient = null;
        
        // Initialize Web Audio API for better control
        this.audioContext = null;
        
        this.init();
    }
    
    init() {
        // Create audio context on first user interaction
        document.addEventListener('click', () => {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
        }, { once: true });
        
        // Preload sounds
        this.preloadSounds();
    }
    
    preloadSounds() {
        // Define sound URLs (using placeholder base64 for now)
        // In production, replace with actual audio files
        const soundDefs = {
            click: this.generateTone(800, 0.05, 'sine'),
            hover: this.generateTone(600, 0.03, 'sine'),
            success: this.generateTone(880, 0.15, 'sine'),
            error: this.generateTone(200, 0.2, 'sawtooth'),
            addCart: this.generateTone(523, 0.1, 'sine'),
            purchase: this.generateTone(1047, 0.2, 'sine'),
            notification: this.generateTone(440, 0.1, 'triangle'),
        };
        
        // Store sound definitions
        this.soundDefs = soundDefs;
    }
    
    // Generate simple tones using Web Audio API
    generateTone(frequency, duration, type) {
        return { frequency, duration, type };
    }
    
    play(soundName) {
        if (!this.enabled || !this.audioContext) return;
        
        const soundDef = this.soundDefs[soundName];
        if (!soundDef) return;
        
        try {
            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();
            
            oscillator.type = soundDef.type;
            oscillator.frequency.setValueAtTime(soundDef.frequency, this.audioContext.currentTime);
            
            gainNode.gain.setValueAtTime(this.volume * 0.3, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + soundDef.duration);
            
            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);
            
            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + soundDef.duration);
        } catch (e) {
            console.log('Sound play error:', e);
        }
    }
    
    // Play a success jingle (ascending notes)
    playSuccess() {
        if (!this.enabled || !this.audioContext) return;
        
        const notes = [523, 659, 784, 1047]; // C5, E5, G5, C6
        notes.forEach((freq, i) => {
            setTimeout(() => {
                this.playNote(freq, 0.15);
            }, i * 100);
        });
    }
    
    // Play error sound (descending harsh)
    playError() {
        if (!this.enabled || !this.audioContext) return;
        
        const notes = [400, 300, 200];
        notes.forEach((freq, i) => {
            setTimeout(() => {
                this.playNote(freq, 0.1, 'sawtooth');
            }, i * 80);
        });
    }
    
    // Play a single note
    playNote(frequency, duration, type = 'sine') {
        if (!this.audioContext) return;
        
        try {
            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();
            
            oscillator.type = type;
            oscillator.frequency.setValueAtTime(frequency, this.audioContext.currentTime);
            
            gainNode.gain.setValueAtTime(this.volume * 0.2, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + duration);
            
            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);
            
            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + duration);
        } catch (e) {
            console.log('Note play error:', e);
        }
    }
    
    // Play "Breaking Bad" style intro sting
    playIntroSting() {
        if (!this.enabled || !this.audioContext) return;
        
        // Dramatic low notes
        const introNotes = [
            { freq: 110, delay: 0, duration: 0.5 },
            { freq: 130, delay: 200, duration: 0.4 },
            { freq: 165, delay: 400, duration: 0.6 },
        ];
        
        introNotes.forEach(note => {
            setTimeout(() => {
                this.playNote(note.freq, note.duration, 'triangle');
            }, note.delay);
        });
    }
    
    // Play bubbling ambient sound
    playBubbling() {
        if (!this.enabled || !this.audioContext) return;
        
        // Random bubble pops
        const bubble = () => {
            const freq = 200 + Math.random() * 400;
            this.playNote(freq, 0.05, 'sine');
        };
        
        // Create random bubbles
        for (let i = 0; i < 5; i++) {
            setTimeout(bubble, Math.random() * 500);
        }
    }
    
    // Toggle sound on/off
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
    
    // Set volume (0-1)
    setVolume(vol) {
        this.volume = Math.max(0, Math.min(1, vol));
    }
}

// Create global sound manager instance
const soundManager = new SoundManager();

// Haptic feedback for Telegram
function triggerHaptic(type = 'light') {
    try {
        if (window.Telegram?.WebApp?.HapticFeedback) {
            const hf = window.Telegram.WebApp.HapticFeedback;
            switch(type) {
                case 'light': hf.impactOccurred('light'); break;
                case 'medium': hf.impactOccurred('medium'); break;
                case 'heavy': hf.impactOccurred('heavy'); break;
                case 'success': hf.notificationOccurred('success'); break;
                case 'error': hf.notificationOccurred('error'); break;
                case 'warning': hf.notificationOccurred('warning'); break;
            }
        }
    } catch (e) {
        // Haptic not available
    }
}

// Export for use in other scripts
window.soundManager = soundManager;
window.triggerHaptic = triggerHaptic;


