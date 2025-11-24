# Los Santos Shop - Mini App Master Plan & Progress

## 🎯 Goal
Create a "Next Level" high-quality, professional Telegram Mini App with a GTA San Andreas theme. It must be interactive, smooth, and polished.

## 🛠 Current Status
- **Framework:** Single Page Application (SPA) in `index.html`.
- **Theme:** GTA SA (Green/Gold/Black).
- **Payment:** Solana (Terminal Style) with QR Code.
- **Map:** Interactive SVG with Blips.

## 📋 To-Do List (High Priority)

### 1. First Impressions (The "Vibe")
- [x] **Boot Sequence:** Add a retro BIOS/Loading screen on startup.
- [x] **Start Screen:** "PRESS START" screen to initialize Audio context (for radio/sfx).
- [ ] **Sound Effects:** Add UI sounds (hover, click, buy) using reliable CDN sources.

### 2. Interactive Characters ("The Crew")
- [x] **Character Overlay System:** JS logic to slide character cutouts (CJ, Smoke, Ryder) in from the screen edge.
    -   *Trigger: Add to Cart -> CJ Thumbs up* (Implemented: "NICE CHOICE!")
    -   *Trigger: Error -> Ryder scowl* (Pending)
    -   *Trigger: Purchase -> Big Smoke "Ooooooh"* (Implemented: "RESPECT +")
- [ ] **Idle Animations:** Random appearances or comments.

### 3. UI/UX Polish (Professional Feel)
- [ ] **Visual Radio:** Replace text toggle with a "Radio Wheel" or "Tuner" UI.
- [ ] **Transitions:** Add smooth fade/slide transitions between Shop/Map/Stats.
- [ ] **Button Feedback:** CSS `transform: scale` and brightness effects on interactions.
- [ ] **CRT Effect Refinement:** Make the scanlines high-res and subtle.

### 4. Advanced Shop
- [ ] **Category "Wall":** Horizontal scroll for categories (Weapons, Apparel, Drugs).
- [ ] **3D Tilt Cards:** CSS `perspective` on product cards to make them tilt on touch/hover.

## 🐛 Bug Tracker
- [x] Modals overlapping header (Fixed: Fullscreen z-index 99999)
- [x] Broken CJ Image (Fixed: Placeholder)
- [x] Map Background Transparency (Fixed: Solid Ocean Blue)

## 📝 Notes
- Keep file size optimized (loading times).
- Ensure compatibility with Telegram Web View on iOS/Android.
