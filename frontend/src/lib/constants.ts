import { Band } from '../types';

export const FRIENDLY_SIGNAL_NAMES: Record<string, string> = {
  c2pa: 'Content Credentials',
  exif: 'Camera metadata',
  jpeg_qtables: 'JPEG compression',
  copy_move: 'Copy-move',
  noise_residual: 'Noise pattern',
  clip_probe: 'AI-image probe',
  family_map: 'Generator family',
  localizer: 'Edit localizer',
  ae_reconstruction: 'Reconstruction test',
  pdf_incremental_update: 'PDF version history',
  pdf_producer_mismatch: 'PDF metadata',
  pdf_font_anomaly: 'Fonts',
  ocr_confidence_dip: 'OCR confidence',
  field_arithmetic: 'Arithmetic',
  field_dates: 'Dates',
  field_format: 'Formats',
  face_match: 'Face match',
  selfie_synthetic: 'Selfie authenticity',
  invoice_before_photo: 'Invoice vs photo date',
  camera_model_mismatch: 'Camera mismatch',
  name_mismatch: 'Name mismatch',
  cross_claim: 'Linked claims (fraud ring)',
  damage_story: 'Damage vs story',
  medical_billing: 'Medical billing vs diagnosis',
};

export function getFriendlyName(name: string): string {
  return FRIENDLY_SIGNAL_NAMES[name] || name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export const BAND_CONFIG: Record<Band, { label: string; color: string; bg: string; text: string; border: string }> = {
  LOW: {
    label: 'Low risk',
    color: '#2e7d32',
    bg: 'bg-emerald-50',
    text: 'text-emerald-800 font-bold',
    border: 'border-emerald-300',
  },
  MEDIUM: {
    label: 'Medium risk',
    color: '#ef6c00',
    bg: 'bg-amber-50',
    text: 'text-amber-800 font-bold',
    border: 'border-amber-300',
  },
  HIGH: {
    label: 'High risk',
    color: '#c62828',
    bg: 'bg-rose-50',
    text: 'text-rose-800 font-bold',
    border: 'border-rose-300',
  },
  UNCERTAIN: {
    label: 'Uncertain: image quality too low',
    color: '#757575',
    bg: 'bg-stone-100',
    text: 'text-stone-700 font-bold',
    border: 'border-stone-300',
  },
};

export const DEFAULT_CONFIG = {
  bands: {
    low_max: 0.35,
    medium_max: 0.65,
  },
  weights: {
    image: { localizer: 0.30, clip_probe: 0.25, noise_residual: 0.15 },
    document: { pdf_incremental_update: 0.40, ocr_confidence_dip: 0.25, medical_billing: 0.50 },
    identity: { face_match: 0.50, selfie_synthetic: 0.50 },
    claim: { invoice_before_photo: 0.10, camera_model_mismatch: 0.05, name_mismatch: 0.10, damage_story: 0.40, cross_claim: 0.55 },
  },
  arena_attacks: ['inpaint', 'recompress_q70'],
  arena_default_prompt: 'large dent and scratched paint, photorealistic, matching lighting',
  accepted_types: {
    image: ['jpg', 'jpeg', 'png', 'heic', 'heif', 'webp'],
    document: ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif', 'webp'],
  },
};

export const REVIEWERS = ['asha', 'marcus', 'elena', 'david'];
