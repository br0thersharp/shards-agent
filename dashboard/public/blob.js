// Chibi Blob Animation — Canvas 2D
// A translucent blue slime with kawaii eyes, inspired by classic JRPG slimes

class ChibiBlob {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.state = 'idle';
    this.time = 0;
    this.tauntText = '';
    this.tauntTimer = 0;
    this.stateTimer = 0;
    this.prevState = 'idle';

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = rect.width;
    this.h = rect.height;
    this.cx = this.w / 2;
    this.cy = this.h * 0.65;
    this.baseRadius = Math.min(this.w, this.h) * 0.22;
  }

  setState(newState) {
    if (newState === this.state) return;
    this.prevState = this.state;
    this.state = newState;
    this.stateTimer = 0;
    if (newState === 'win' || newState === 'loss' || newState === 'shopping') {
      setTimeout(() => {
        if (this.state === newState) {
          this.state = this.prevState === newState ? 'idle' : this.prevState;
        }
      }, 3000);
    }
  }

  showTaunt(text) {
    this.tauntText = text;
    this.tauntTimer = 4;
  }

  update(dt) {
    this.time += dt;
    if (this.tauntTimer > 0) this.tauntTimer -= dt;
    this.stateTimer += dt;
  }

  draw() {
    const ctx = this.ctx;
    const t = this.time;
    const r = this.baseRadius;
    let cx = this.cx;
    let cy = this.cy;

    ctx.clearRect(0, 0, this.w, this.h);

    // State-dependent transforms
    let scaleX = 1, scaleY = 1, offsetY = 0, shake = 0, rotation = 0;
    let eyeStyle = 'normal';
    let mouthStyle = 'smile';
    let blushAlpha = 0.5;
    let tint = null;

    switch (this.state) {
      case 'idle':
        offsetY = Math.sin(t * 1.5) * 5;
        scaleX = 1 + Math.sin(t * 1.2) * 0.02;
        scaleY = 1 + Math.cos(t * 1.2) * 0.02;
        break;

      case 'queue':
        offsetY = Math.abs(Math.sin(t * 3)) * -18;
        scaleY = 1 + Math.sin(t * 3) * 0.06;
        scaleX = 1 - Math.sin(t * 3) * 0.04;
        eyeStyle = 'looking';
        blushAlpha = 0.7;
        break;

      case 'combat':
        shake = Math.sin(t * 20) * 1.5;
        scaleX = 1 + Math.sin(t * 4) * 0.04;
        scaleY = 1 - Math.sin(t * 4) * 0.02;
        eyeStyle = 'narrow';
        mouthStyle = 'none';
        blushAlpha = 0.2;
        if (Math.sin(t * 2) > 0.7) tint = 'rgba(255, 50, 50, 0.12)';
        break;

      case 'win': {
        const st = this.stateTimer;
        offsetY = -Math.abs(Math.sin(st * 5)) * 25;
        rotation = Math.sin(st * 8) * 0.2;
        scaleX = 1.08 + Math.sin(st * 6) * 0.08;
        scaleY = 1.08 + Math.cos(st * 6) * 0.08;
        eyeStyle = 'stars';
        mouthStyle = 'wide';
        blushAlpha = 0.9;
        break;
      }

      case 'loss': {
        const st = this.stateTimer;
        const squish = Math.min(st * 2, 1);
        scaleX = 1 + squish * 0.25;
        scaleY = 1 - squish * 0.35;
        offsetY = squish * r * 0.25;
        eyeStyle = 'droop';
        mouthStyle = 'frown';
        blushAlpha = 0;
        tint = `rgba(128, 128, 128, ${0.2 * squish})`;
        break;
      }

      case 'shopping':
        offsetY = Math.sin(t * 2) * 4;
        eyeStyle = 'dollar';
        mouthStyle = 'smile';
        blushAlpha = 0.6;
        break;
    }

    const isTaunting = this.tauntTimer > 0;
    if (isTaunting && this.state !== 'win' && this.state !== 'loss') {
      mouthStyle = 'open';
    }

    ctx.save();
    ctx.translate(cx + shake, cy + offsetY);
    ctx.rotate(rotation);
    ctx.scale(scaleX, scaleY);

    // Shadow
    ctx.beginPath();
    ctx.ellipse(0, r * 0.65, r * 0.7, r * 0.1, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.18)';
    ctx.fill();

    // Body
    this.drawBody(ctx, r);

    // Tint overlay
    if (tint) {
      ctx.save();
      ctx.globalCompositeOperation = 'source-atop';
      ctx.beginPath();
      ctx.ellipse(0, 0, r * 1.2, r * 1.1, 0, 0, Math.PI * 2);
      ctx.fillStyle = tint;
      ctx.fill();
      ctx.restore();
    }

    // Blush cheeks
    this.drawBlush(ctx, r, blushAlpha);

    // Eyes
    this.drawEyes(ctx, r, eyeStyle);

    // Mouth
    this.drawMouth(ctx, r, mouthStyle);

    ctx.restore();

    // Speech bubble
    if (isTaunting && this.tauntText) {
      this.drawSpeechBubble(ctx, cx, cy + offsetY - r * scaleY - 25);
    }
  }

  drawBody(ctx, r) {
    const t = this.time;
    const w1 = Math.sin(t * 2) * 2;
    const w2 = Math.cos(t * 1.7) * 3;

    // Teardrop / pudgy slime shape — wider at bottom, rounded top
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.85);

    // Top-right curve (narrower at top)
    ctx.bezierCurveTo(
      r * 0.45 + w1, -r * 0.85,
      r * 0.8, -r * 0.5 + w2,
      r * 0.85, -r * 0.1
    );
    // Right side bulge (wider at middle-bottom)
    ctx.bezierCurveTo(
      r * 0.9 + w2, r * 0.25,
      r * 0.85, r * 0.55 + w1,
      r * 0.5, r * 0.65
    );
    // Bottom (flat-ish, sitting on ground)
    ctx.bezierCurveTo(
      r * 0.25, r * 0.7,
      -r * 0.25, r * 0.7,
      -r * 0.5, r * 0.65
    );
    // Left side bulge
    ctx.bezierCurveTo(
      -r * 0.85, r * 0.55 - w1,
      -r * 0.9 - w2, r * 0.25,
      -r * 0.85, -r * 0.1
    );
    // Top-left curve
    ctx.bezierCurveTo(
      -r * 0.8, -r * 0.5 - w2,
      -r * 0.45 - w1, -r * 0.85,
      0, -r * 0.85
    );

    // Main gradient — translucent blue
    const grad = ctx.createRadialGradient(-r * 0.15, -r * 0.25, 0, 0, r * 0.1, r * 1.1);
    grad.addColorStop(0, 'rgba(140, 210, 255, 0.95)');
    grad.addColorStop(0.3, 'rgba(70, 160, 235, 0.9)');
    grad.addColorStop(0.7, 'rgba(40, 120, 210, 0.85)');
    grad.addColorStop(1, 'rgba(25, 80, 170, 0.9)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Subtle outline
    ctx.strokeStyle = 'rgba(20, 60, 140, 0.5)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Big glossy highlight — top left
    ctx.beginPath();
    ctx.ellipse(-r * 0.2, -r * 0.45, r * 0.22, r * 0.14, -0.4, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.55)';
    ctx.fill();

    // Smaller secondary highlight
    ctx.beginPath();
    ctx.ellipse(-r * 0.35, -r * 0.25, r * 0.07, r * 0.05, -0.3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.fill();

    // Bottom reflection / translucency effect
    ctx.beginPath();
    ctx.ellipse(r * 0.1, r * 0.35, r * 0.35, r * 0.12, 0.1, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(100, 180, 240, 0.15)';
    ctx.fill();
  }

  drawBlush(ctx, r, alpha) {
    if (alpha <= 0) return;
    const cheekY = r * 0.15;
    const cheekSpread = r * 0.45;
    const cheekR = r * 0.11;

    ctx.globalAlpha = alpha;
    // Left cheek
    ctx.beginPath();
    ctx.ellipse(-cheekSpread, cheekY, cheekR, cheekR * 0.6, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 130, 160, 0.7)';
    ctx.fill();
    // Right cheek
    ctx.beginPath();
    ctx.ellipse(cheekSpread, cheekY, cheekR, cheekR * 0.6, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 130, 160, 0.7)';
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  drawEyes(ctx, r, style) {
    const t = this.time;
    const eyeSpacing = r * 0.27;
    const eyeY = -r * 0.08;
    const eyeR = r * 0.13;

    for (let side = -1; side <= 1; side += 2) {
      const ex = side * eyeSpacing;

      switch (style) {
        case 'normal':
        case 'looking': {
          const lookX = style === 'looking' ? Math.sin(t * 1.5) * eyeR * 0.3 : 0;

          // Eye shape — tall rounded
          ctx.beginPath();
          ctx.ellipse(ex, eyeY, eyeR * 0.85, eyeR * 1.1, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#1a1a2e';
          ctx.fill();

          // Large white reflection (top-right of each eye)
          ctx.beginPath();
          ctx.ellipse(ex + eyeR * 0.25 + lookX * 0.3, eyeY - eyeR * 0.3, eyeR * 0.3, eyeR * 0.35, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.fill();

          // Small white reflection (bottom-left)
          ctx.beginPath();
          ctx.arc(ex - eyeR * 0.2 + lookX * 0.2, eyeY + eyeR * 0.25, eyeR * 0.12, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(255,255,255,0.8)';
          ctx.fill();
          break;
        }

        case 'narrow': {
          // Narrowed — horizontal slit
          ctx.beginPath();
          ctx.ellipse(ex, eyeY, eyeR * 0.9, eyeR * 0.45, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#1a1a2e';
          ctx.fill();

          // Sharp glint
          ctx.beginPath();
          ctx.ellipse(ex + eyeR * 0.2, eyeY - eyeR * 0.1, eyeR * 0.2, eyeR * 0.15, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.fill();

          // Angry brow
          ctx.beginPath();
          ctx.moveTo(ex - eyeR * 1.1, eyeY - eyeR * 0.8 + side * 3);
          ctx.lineTo(ex + eyeR * 1.1, eyeY - eyeR * 0.8 - side * 3);
          ctx.strokeStyle = 'rgba(20, 60, 140, 0.7)';
          ctx.lineWidth = 2.5;
          ctx.lineCap = 'round';
          ctx.stroke();
          break;
        }

        case 'stars':
          this.drawStar(ctx, ex, eyeY, eyeR * 1.0, 5, '#FFD700');
          break;

        case 'droop': {
          // Sad droopy eyes
          ctx.beginPath();
          ctx.ellipse(ex, eyeY + 3, eyeR * 0.7, eyeR * 0.55, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#1a1a2e';
          ctx.fill();

          // Dim reflection
          ctx.beginPath();
          ctx.arc(ex + eyeR * 0.15, eyeY - eyeR * 0.05, eyeR * 0.15, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(255,255,255,0.5)';
          ctx.fill();

          // Sad brows
          ctx.beginPath();
          ctx.moveTo(ex - eyeR, eyeY - eyeR * 0.7 - side * 2.5);
          ctx.lineTo(ex + eyeR, eyeY - eyeR * 0.7 + side * 2.5);
          ctx.strokeStyle = 'rgba(20, 60, 140, 0.5)';
          ctx.lineWidth = 2;
          ctx.lineCap = 'round';
          ctx.stroke();
          break;
        }

        case 'dollar': {
          // Dollar sign eyes
          ctx.beginPath();
          ctx.ellipse(ex, eyeY, eyeR * 0.85, eyeR * 1.1, 0, 0, Math.PI * 2);
          ctx.fillStyle = '#90EE90';
          ctx.fill();
          ctx.strokeStyle = 'rgba(20, 60, 140, 0.4)';
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.font = `bold ${eyeR * 1.3}px monospace`;
          ctx.fillStyle = '#1a6b1a';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText('$', ex, eyeY);
          break;
        }
      }
    }
  }

  drawMouth(ctx, r, style) {
    const mouthY = r * 0.3;

    switch (style) {
      case 'smile':
        // Small kawaii smile — just a little curve
        ctx.beginPath();
        ctx.moveTo(-r * 0.08, mouthY);
        ctx.quadraticCurveTo(0, mouthY + r * 0.08, r * 0.08, mouthY);
        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 1.8;
        ctx.lineCap = 'round';
        ctx.stroke();
        break;

      case 'open':
        ctx.beginPath();
        ctx.ellipse(0, mouthY + 2, r * 0.08, r * 0.06, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#2d0a3a';
        ctx.fill();
        break;

      case 'wide':
        // Big happy mouth
        ctx.beginPath();
        ctx.ellipse(0, mouthY, r * 0.14, r * 0.1, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#2d0a3a';
        ctx.fill();
        // Teeth
        ctx.beginPath();
        ctx.rect(-r * 0.08, mouthY - r * 0.04, r * 0.16, r * 0.03);
        ctx.fillStyle = '#fff';
        ctx.fill();
        break;

      case 'frown':
        ctx.beginPath();
        ctx.moveTo(-r * 0.07, mouthY + r * 0.04);
        ctx.quadraticCurveTo(0, mouthY - r * 0.03, r * 0.07, mouthY + r * 0.04);
        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 1.8;
        ctx.lineCap = 'round';
        ctx.stroke();
        break;
    }
  }

  drawStar(ctx, x, y, r, points, color) {
    ctx.beginPath();
    for (let i = 0; i < points * 2; i++) {
      const angle = (i * Math.PI) / points - Math.PI / 2;
      const dist = i % 2 === 0 ? r : r * 0.4;
      const sx = x + Math.cos(angle) * dist;
      const sy = y + Math.sin(angle) * dist;
      if (i === 0) ctx.moveTo(sx, sy);
      else ctx.lineTo(sx, sy);
    }
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  drawSpeechBubble(ctx, x, y) {
    const text = this.tauntText;
    const maxWidth = this.w * 0.85;
    ctx.font = '11px "Courier New", monospace';
    const metrics = ctx.measureText(text);
    const textWidth = Math.min(metrics.width, maxWidth);
    const padding = 8;
    const bubbleW = textWidth + padding * 2;
    const bubbleH = 26;
    const bx = x - bubbleW / 2;
    const by = Math.max(2, y - bubbleH - 6);

    const alpha = Math.min(1, this.tauntTimer / 0.5);
    ctx.globalAlpha = alpha;

    // Bubble with rounded corners
    const br = 10;
    ctx.beginPath();
    ctx.moveTo(bx + br, by);
    ctx.lineTo(bx + bubbleW - br, by);
    ctx.arcTo(bx + bubbleW, by, bx + bubbleW, by + br, br);
    ctx.lineTo(bx + bubbleW, by + bubbleH - br);
    ctx.arcTo(bx + bubbleW, by + bubbleH, bx + bubbleW - br, by + bubbleH, br);
    // Pointer
    ctx.lineTo(x + 6, by + bubbleH);
    ctx.lineTo(x, by + bubbleH + 8);
    ctx.lineTo(x - 3, by + bubbleH);
    ctx.lineTo(bx + br, by + bubbleH);
    ctx.arcTo(bx, by + bubbleH, bx, by + bubbleH - br, br);
    ctx.lineTo(bx, by + br);
    ctx.arcTo(bx, by, bx + br, by, br);
    ctx.closePath();

    // Slightly blue-tinted bubble
    ctx.fillStyle = 'rgba(240, 248, 255, 0.95)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(40, 100, 180, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = '#1a1a2e';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, by + bubbleH / 2, maxWidth);

    ctx.globalAlpha = 1;
  }
}
