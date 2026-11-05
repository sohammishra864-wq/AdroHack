// Generates high quality mock images as base64 data URLs via canvas for offline simulation

export function createCarPhotoUrl(): string {
  const canvas = document.createElement('canvas');
  canvas.width = 800;
  canvas.height = 550;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // Background - showroom/street gradient
  const bgGrad = ctx.createLinearGradient(0, 0, 0, 550);
  bgGrad.addColorStop(0, '#788292');
  bgGrad.addColorStop(0.5, '#9fa9b8');
  bgGrad.addColorStop(0.7, '#cbd5e1');
  bgGrad.addColorStop(1, '#475569');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, 800, 550);

  // Ground reflection
  ctx.fillStyle = '#334155';
  ctx.fillRect(0, 420, 800, 130);

  // Car Body (Silver metallic sedan rear corner/bumper)
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(100, 400);
  ctx.bezierCurveTo(120, 320, 200, 240, 380, 210);
  ctx.lineTo(650, 210);
  ctx.bezierCurveTo(720, 260, 760, 330, 780, 420);
  ctx.lineTo(100, 420);
  ctx.closePath();

  const carGrad = ctx.createLinearGradient(100, 210, 780, 420);
  carGrad.addColorStop(0, '#e2e8f0');
  carGrad.addColorStop(0.3, '#f8fafc');
  carGrad.addColorStop(0.7, '#94a3b8');
  carGrad.addColorStop(1, '#64748b');
  ctx.fillStyle = carGrad;
  ctx.fill();

  // Tail light
  ctx.fillStyle = '#dc2626';
  ctx.beginPath();
  ctx.moveTo(600, 260);
  ctx.lineTo(720, 270);
  ctx.lineTo(700, 310);
  ctx.lineTo(590, 295);
  ctx.closePath();
  ctx.fill();

  // Damaged / Fabricated Dent region (Bumper area)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(360, 350, 110, 65, -0.2, 0, Math.PI * 2);
  const dentGrad = ctx.createRadialGradient(360, 350, 10, 360, 350, 110);
  dentGrad.addColorStop(0, '#1e293b');
  dentGrad.addColorStop(0.4, '#334155');
  dentGrad.addColorStop(0.8, '#475569');
  dentGrad.addColorStop(1, '#94a3b8');
  ctx.fillStyle = dentGrad;
  ctx.fill();

  // Scratch lines in dent
  ctx.strokeStyle = '#f1f5f9';
  ctx.lineWidth = 2.5;
  for (let i = 0; i < 5; i++) {
    ctx.beginPath();
    ctx.moveTo(310 + i * 20, 330 + (i % 2) * 10);
    ctx.bezierCurveTo(340 + i * 15, 345, 370 + i * 12, 360, 410 + i * 10, 365);
    ctx.stroke();
  }
  ctx.restore();

  // Wheel arch
  ctx.fillStyle = '#1e293b';
  ctx.beginPath();
  ctx.arc(220, 420, 70, Math.PI, 0, false);
  ctx.fill();

  // Timestamp watermark
  ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
  ctx.font = '14px monospace';
  ctx.fillText('CAM_FRONT_R 2026-09-28 14:22:08 UTC', 20, 530);

  ctx.restore();
  return canvas.toDataURL('image/png');
}

export function createHeatmapUrl(): string {
  // Grayscale heatmap: white = manipulated, black = authentic
  const canvas = document.createElement('canvas');
  canvas.width = 800;
  canvas.height = 550;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // Background low noise
  ctx.fillStyle = '#0a0a0a';
  ctx.fillRect(0, 0, 800, 550);

  // Manipulated zone anomaly (hot white core)
  const grad = ctx.createRadialGradient(360, 350, 15, 360, 350, 130);
  grad.addColorStop(0, '#ffffff'); // 100% white = 1.0 probability
  grad.addColorStop(0.5, '#c0c0c0');
  grad.addColorStop(0.8, '#404040');
  grad.addColorStop(1, '#000000');

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.ellipse(360, 350, 130, 85, -0.2, 0, Math.PI * 2);
  ctx.fill();

  return canvas.toDataURL('image/png');
}

export function createReconstructionUrl(): string {
  // Autoencoder reconstruction map
  const canvas = document.createElement('canvas');
  canvas.width = 800;
  canvas.height = 550;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  ctx.fillStyle = '#101010';
  ctx.fillRect(0, 0, 800, 550);

  // Elevated patch reconstruction error in bumper region
  const grad = ctx.createRadialGradient(360, 350, 20, 360, 350, 120);
  grad.addColorStop(0, '#ffffff');
  grad.addColorStop(0.4, '#a0a0a0');
  grad.addColorStop(0.7, '#252525');
  grad.addColorStop(1, '#000000');

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(360, 350, 120, 0, Math.PI * 2);
  ctx.fill();

  return canvas.toDataURL('image/png');
}

export function createCleanCarUrl(): string {
  const canvas = document.createElement('canvas');
  canvas.width = 800;
  canvas.height = 550;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  ctx.fillStyle = '#64748b';
  ctx.fillRect(0, 0, 800, 550);

  // Clean authentic windshield scratch
  ctx.fillStyle = '#38bdf8';
  ctx.beginPath();
  ctx.moveTo(150, 150);
  ctx.lineTo(650, 150);
  ctx.lineTo(720, 450);
  ctx.lineTo(80, 450);
  ctx.closePath();
  ctx.fill();

  // Small genuine crack
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(350, 280);
  ctx.lineTo(390, 310);
  ctx.lineTo(440, 300);
  ctx.lineTo(460, 340);
  ctx.stroke();

  return canvas.toDataURL('image/png');
}

export function createInvoiceDocUrl(): string {
  const canvas = document.createElement('canvas');
  canvas.width = 650;
  canvas.height = 840;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // Clean white paper with subtle border
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 650, 840);
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 2;
  ctx.strokeRect(10, 10, 630, 820);

  // Header
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 22px Inter, sans-serif';
  ctx.fillText('APEX AUTO COLLISION & BODYWORK', 50, 60);

  ctx.font = '12px Inter, sans-serif';
  ctx.fillStyle = '#64748b';
  ctx.fillText('1440 Industrial Parkway, Suite 400 • Ph: (555) 019-2834', 50, 85);
  ctx.fillText('Tax ID / License: #CA-9029182', 50, 105);

  ctx.strokeStyle = '#cbd5e1';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(50, 125);
  ctx.lineTo(600, 125);
  ctx.stroke();

  // Invoice Details
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 15px Inter, sans-serif';
  ctx.fillText('INVOICE / REPAIR ESTIMATE', 50, 160);
  ctx.font = '13px monospace';
  ctx.fillText('Invoice #: INV-2026-9041', 50, 185);
  ctx.fillText('Date: 2026-09-29', 50, 205);
  ctx.fillText('Claim Ref: CLM-8491-01', 50, 225);

  // Customer info
  ctx.font = '13px Inter, sans-serif';
  ctx.fillText('Claimant: Marcus Vance', 380, 185);
  ctx.fillText('Vehicle: 2024 Honda Civic Sport', 380, 205);
  ctx.fillText('VIN: 1HGCR2F83PA019482', 380, 225);

  // Table header
  ctx.fillStyle = '#f8fafc';
  ctx.fillRect(50, 260, 550, 32);
  ctx.strokeStyle = '#e2e8f0';
  ctx.strokeRect(50, 260, 550, 32);

  ctx.fillStyle = '#334155';
  ctx.font = 'bold 12px Inter, sans-serif';
  ctx.fillText('DESCRIPTION', 65, 281);
  ctx.fillText('LABOR (HRS)', 340, 281);
  ctx.fillText('PARTS', 440, 281);
  ctx.fillText('TOTAL', 530, 281);

  // Items
  const items = [
    { desc: 'Rear Bumper Cover OEM Replacement', hrs: '2.5', parts: '$890.00', total: '$1,140.00' },
    { desc: 'Paint / Clearcoat blend quarter panel', hrs: '4.0', parts: '$320.00', total: '$720.00' },
    { desc: 'Rear Impact Absorber Structure', hrs: '1.8', parts: '$440.00', total: '$620.00' },
    { desc: 'Parking Sensor Calibration & Mounts', hrs: '3.0', parts: '$580.00', total: '$880.00' },
    { desc: 'Subframe Straightening & Alignment', hrs: '5.5', parts: '$940.00', total: '$1,490.00' },
  ];

  ctx.font = '13px Inter, sans-serif';
  ctx.fillStyle = '#1e293b';
  let y = 320;
  items.forEach((it) => {
    ctx.fillText(it.desc, 65, y);
    ctx.fillText(it.hrs, 350, y);
    ctx.fillText(it.parts, 440, y);
    ctx.fillText(it.total, 530, y);
    ctx.strokeStyle = '#f1f5f9';
    ctx.beginPath();
    ctx.moveTo(50, y + 12);
    ctx.lineTo(600, y + 12);
    ctx.stroke();
    y += 40;
  });

  // Total Box
  ctx.fillStyle = '#f1f5f9';
  ctx.fillRect(380, 550, 220, 80);
  ctx.strokeStyle = '#cbd5e1';
  ctx.strokeRect(380, 550, 220, 80);

  ctx.fillStyle = '#64748b';
  ctx.font = '13px Inter, sans-serif';
  ctx.fillText('Subtotal:', 400, 575);
  ctx.fillText('Tax (8.25%):', 400, 595);
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 15px Inter, sans-serif';
  ctx.fillText('FINAL TOTAL:', 400, 620);

  ctx.font = 'bold 16px Inter, sans-serif';
  ctx.fillStyle = '#dc2626'; // Alert color on modified final amount
  ctx.fillText('$4,850.00', 510, 620);

  // Digital Signature section
  ctx.fillStyle = '#64748b';
  ctx.font = 'italic 12px Inter, sans-serif';
  ctx.fillText('Certified Authorized Signature: Apex Auto Claims Dept.', 50, 720);
  ctx.fillText('Note: PDF modified 2 days after initial issuance', 50, 745);

  return canvas.toDataURL('image/png');
}

export function createIdPhotoUrl(): string {
  const canvas = document.createElement('canvas');
  canvas.width = 400;
  canvas.height = 260;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  ctx.fillStyle = '#e2e8f0';
  ctx.fillRect(0, 0, 400, 260);

  // State Banner
  ctx.fillStyle = '#1e3a8a';
  ctx.fillRect(0, 0, 400, 45);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 16px Inter, sans-serif';
  ctx.fillText('STATE IDENTIFICATION CARD', 65, 30);

  // Photo box
  ctx.fillStyle = '#94a3b8';
  ctx.fillRect(25, 65, 110, 140);
  // Avatar outline
  ctx.fillStyle = '#f8fafc';
  ctx.beginPath();
  ctx.arc(80, 115, 30, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(80, 185, 45, 35, 0, Math.PI, 0);
  ctx.fill();

  // Details
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 13px Inter, sans-serif';
  ctx.fillText('NAME: VANCE, MARCUS', 155, 90);
  ctx.font = '12px Inter, sans-serif';
  ctx.fillStyle = '#475569';
  ctx.fillText('DOB: 1988-06-14', 155, 115);
  ctx.fillText('EXP: 2028-06-14', 155, 135);
  ctx.fillText('ID: #D8291048-A', 155, 155);
  ctx.fillText('CLASS: C - REGULAR', 155, 175);

  return canvas.toDataURL('image/png');
}

export function createSelfiePhotoUrl(): string {
  const canvas = document.createElement('canvas');
  canvas.width = 400;
  canvas.height = 400;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // Background
  const grad = ctx.createLinearGradient(0, 0, 400, 400);
  grad.addColorStop(0, '#f1f5f9');
  grad.addColorStop(1, '#cbd5e1');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 400, 400);

  // Face portrait graphic
  ctx.fillStyle = '#fed7aa';
  ctx.beginPath();
  ctx.arc(200, 180, 85, 0, Math.PI * 2);
  ctx.fill();

  // Hair
  ctx.fillStyle = '#332924';
  ctx.beginPath();
  ctx.arc(200, 140, 90, Math.PI, 0, false);
  ctx.fill();

  // Eyes
  ctx.fillStyle = '#1e293b';
  ctx.beginPath();
  ctx.arc(170, 175, 7, 0, Math.PI * 2);
  ctx.arc(230, 175, 7, 0, Math.PI * 2);
  ctx.fill();

  // Gentle smile
  ctx.strokeStyle = '#c2410c';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(200, 205, 30, 0.1 * Math.PI, 0.9 * Math.PI, false);
  ctx.stroke();

  // Shoulders
  ctx.fillStyle = '#2563eb';
  ctx.beginPath();
  ctx.ellipse(200, 360, 140, 90, 0, Math.PI, 0);
  ctx.fill();

  return canvas.toDataURL('image/png');
}
