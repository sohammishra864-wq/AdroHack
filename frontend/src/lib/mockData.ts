import { CaseResult, InboxCase, ApiConfig, HealthStatus, AuditRecord } from '../types';
import {
  createCarPhotoUrl,
  createHeatmapUrl,
  createReconstructionUrl,
  createCleanCarUrl,
  createInvoiceDocUrl,
  createIdPhotoUrl,
  createSelfiePhotoUrl,
} from './mockAssets';

export const MOCK_HEALTH: HealthStatus = {
  ok: true,
  problems: [],
  device: 'cuda:0 (NVIDIA RTX 4090)',
};

export const MOCK_HEALTH_WITH_PROBLEMS: HealthStatus = {
  ok: false,
  problems: ['clip_probe: missing heads (weights fallback)', 'ae_reconstruction: running on CPU fallback'],
  device: 'cpu',
};

export const MOCK_INBOX_CASES: InboxCase[] = [
  {
    case_id: 'b_fraud',
    title: 'Bumper claim - 2024 Honda Civic',
    counts: { photos: 1, documents: 1, id: true, selfie: true },
    last_band: 'HIGH',
  },
  {
    case_id: 'a_clean',
    title: 'Windshield repair - 2022 Toyota RAV4',
    counts: { photos: 1, documents: 1, id: true, selfie: true },
    last_band: 'LOW',
  },
  {
    case_id: 'c_uncertain',
    title: 'Tailgate dent - 2020 Ford F-150',
    counts: { photos: 1, documents: 0, id: false, selfie: false },
    last_band: 'UNCERTAIN',
  },
];

export function getMockCaseResult(caseId: string): CaseResult {
  const photoUrl = createCarPhotoUrl();
  const heatmapUrl = createHeatmapUrl();
  const reconstructionUrl = createReconstructionUrl();
  const docUrl = createInvoiceDocUrl();
  const idUrl = createIdPhotoUrl();
  const selfieUrl = createSelfiePhotoUrl();
  const cleanCarUrl = createCleanCarUrl();

  if (caseId === 'a_clean') {
    return {
      case_id: 'a_clean',
      title: 'Windshield repair - 2022 Toyota RAV4',
      status: 'done',
      claim: {
        image_score: 0.12,
        document_score: 0.08,
        identity_score: 0.05,
        overall: 0.09,
        band: 'LOW',
        waterfall: [
          ['baseline', 0.50],
          ['c2pa', -0.15],
          ['exif', -0.12],
          ['jpeg_qtables', -0.08],
          ['localizer', -0.06],
        ],
        regions: [],
        signals: [
          {
            name: 'c2pa',
            score: 0.05,
            confidence: 0.95,
            reason: 'Valid C2PA cryptographic signature from Apple iPhone 14 Pro.',
            evidence: { created: '2026-09-28T14:10:00Z', actions: ['c2pa.created'] },
            abstained: false,
            applicable: true,
            tier: 'fast',
          },
          {
            name: 'exif',
            score: 0.08,
            confidence: 0.92,
            reason: 'EXIF metadata is consistent with camera sensor specs.',
            evidence: { make: 'Apple', model: 'iPhone 14 Pro', datetime_original: '2026-09-28T14:10:00Z' },
            abstained: false,
            applicable: true,
            tier: 'fast',
          },
          {
            name: 'localizer',
            score: 0.11,
            confidence: 0.88,
            reason: 'No localized editing patterns detected across pixel surface.',
            evidence: { integrity: 0.96 },
            abstained: false,
            applicable: true,
            tier: 'fast',
          },
        ],
        pending_deep: false,
      },
      images: [
        {
          index: 0,
          name: 'windshield_front.jpg',
          sha256: '9f83ab293412cbef...',
          claim: {
            image_score: 0.12,
            document_score: null,
            identity_score: null,
            overall: 0.12,
            band: 'LOW',
            waterfall: [['baseline', 0.50], ['localizer', -0.38]],
            regions: [],
            signals: [],
            pending_deep: false,
          },
          quality_flag: false,
          quality_reasons: [],
          timing: { first_card_s: 1.2, fast_tier_s: 4.8, deep_s: 18.2 },
          urls: { photo: cleanCarUrl, heatmap: null, reconstruction: null },
        },
      ],
      documents: [
        {
          index: 0,
          name: 'safelite_invoice.pdf',
          sha256: 'd893284021...',
          doc_type: 'invoice',
          from_ocr: false,
          text: 'Safelite AutoGlass Repair Order #89281. Genuine glass replacement.',
          claim: {
            image_score: null,
            document_score: 0.08,
            identity_score: null,
            overall: 0.08,
            band: 'LOW',
            waterfall: [['baseline', 0.50], ['pdf_producer_mismatch', -0.42]],
            regions: [],
            signals: [],
            pending_deep: false,
          },
          timing: { total_s: 2.4 },
          urls: { page: docUrl },
        },
      ],
      identity: {
        signals: [
          {
            name: 'face_match',
            score: 0.04,
            confidence: 0.98,
            reason: 'Strong facial landmark match between government ID and live selfie.',
            evidence: { cosine: 0.94 },
            abstained: false,
            applicable: true,
            tier: 'identity',
          },
          {
            name: 'selfie_synthetic',
            score: 0.06,
            confidence: 0.91,
            reason: 'Live selfie exhibits natural biological skin texture and lighting.',
            evidence: { image_score: 0.06 },
            abstained: false,
            applicable: true,
            tier: 'identity',
          },
        ],
        urls: { id: idUrl, selfie: selfieUrl },
      },
      narrative: {
        text: 'All photographic and documentary evidence is authentic. EXIF headers and C2PA credentials verify physical camera capture without post-processing. Facial verification passed with 98% confidence.',
        source: 'template',
      },
      hashes: ['9f83ab293412cbef...', 'd893284021...'],
    };
  }

  // Default: b_fraud
  return {
    case_id: 'b_fraud',
    title: 'Bumper claim - 2024 Honda Civic',
    status: 'done',
    claim: {
      image_score: 0.78,
      document_score: 0.66,
      identity_score: 0.12,
      overall: 0.74,
      band: 'HIGH',
      waterfall: [
        ['baseline', 0.50],
        ['localizer', 0.21],
        ['clip_probe', 0.15],
        ['pdf_incremental_update', 0.14],
        ['noise_residual', 0.08],
        ['exif', -0.02],
        ['c2pa', -0.32],
      ],
      regions: [
        {
          box: [280, 290, 480, 420],
          area_frac: 0.12,
          signals: { localizer: 0.91, noise_residual: 0.74, ae_reconstruction: 0.88 },
          reason: 'Region A (12%): localizer anomaly 0.91, noise mismatch 0.74 (rear bumper dent & scratch cluster)',
          stage: 2,
        },
      ],
      signals: [
        {
          name: 'localizer',
          score: 0.91,
          confidence: 0.80,
          reason: 'An area covering 12% of the photo looks edited (bumper).',
          evidence: { integrity: 0.14, peak_anomaly: 0.93 },
          abstained: false,
          applicable: true,
          tier: 'fast',
        },
        {
          name: 'clip_probe',
          score: 0.84,
          confidence: 0.78,
          reason: 'Feature embeddings indicate synthetic inpainting within damage zone.',
          evidence: { p_fake: 0.84 },
          abstained: false,
          applicable: true,
          tier: 'fast',
        },
        {
          name: 'family_map',
          score: 0.79,
          confidence: 0.72,
          reason: 'Artifact signatures most consistent with Stable Diffusion XL / Inpainting model.',
          evidence: {
            probs: { sdv15: 0.12, sdxl: 0.68, flux: 0.14, real: 0.06 },
            sunburst: {
              ids: ['root', 'diffusion', 'gan', 'sdxl', 'sdv15', 'flux', 'stylegan'],
              labels: ['Generators', 'Diffusion', 'GAN', 'SDXL Inpaint', 'SD 1.5', 'Flux.1', 'StyleGAN'],
              parents: ['', 'root', 'root', 'diffusion', 'diffusion', 'diffusion', 'gan'],
              values: [100, 85, 15, 68, 12, 5, 15],
            },
          },
          abstained: false,
          applicable: true,
          tier: 'fast',
        },
        {
          name: 'noise_residual',
          score: 0.74,
          confidence: 0.75,
          reason: 'PRNU sensor noise pattern disrupted in bumper region.',
          evidence: { block_variance: '0.042 vs baseline 0.011', discontinuity: 'High' },
          abstained: false,
          applicable: true,
          tier: 'fast',
        },
        {
          name: 'exif',
          score: 0.42,
          confidence: 0.65,
          reason: 'EXIF timestamp precedes invoice issue date by 2 days.',
          evidence: { make: 'Samsung', model: 'Galaxy S23', software: 'Adobe Photoshop 25.1' },
          abstained: false,
          applicable: true,
          tier: 'fast',
        },
        {
          name: 'c2pa',
          score: null,
          confidence: 0.0,
          reason: 'No Content Credentials manifest found in image container.',
          evidence: {},
          abstained: false,
          applicable: false,
          tier: 'fast',
        },
        {
          name: 'ae_reconstruction',
          score: 0.88,
          confidence: 0.82,
          reason: 'High reconstruction loss in bumper area during autoencoder cycle test.',
          evidence: { patch_error_max: 0.88 },
          abstained: false,
          applicable: true,
          tier: 'deep',
        },
        {
          name: 'camera_model_mismatch',
          score: 0.82,
          confidence: 0.85,
          reason: 'Claim header states iPhone 15 Pro, but photo metadata indicates Samsung Galaxy S23.',
          evidence: { declared: 'Apple iPhone 15 Pro', detected: 'Samsung SM-S911B' },
          abstained: false,
          applicable: true,
          tier: 'claim',
        },
        {
          name: 'invoice_before_photo',
          score: 0.76,
          confidence: 0.90,
          reason: 'Repair invoice creation timestamp predates the accident photo timestamp.',
          evidence: { invoice_time: '2026-09-27T09:00:00Z', photo_time: '2026-09-28T14:22:08Z' },
          abstained: false,
          applicable: true,
          tier: 'claim',
        },
        {
          name: 'cross_claim',
          score: 1.0,
          confidence: 0.9,
          reason: 'Shares the same photo (or a resized / recompressed copy) with earlier claim r1_first (2026-10-04).',
          evidence: {
            links: [
              { kind: 'photo', value: 'c3a1f09e7d2b4485', case_id: 'r1_first', ts: '2026-10-04T03:40:12+00:00' },
              { kind: 'vendor', value: 'Speedline Auto Repairs', case_id: 'r1_first', ts: '2026-10-04T03:40:12+00:00' },
            ],
            entities: { photo: 1, vin: 1, vendor: 1, claimant: 1, stay: 0 },
          },
          abstained: false,
          applicable: true,
          tier: 'claim',
        },
        {
          name: 'damage_story',
          score: 0.6,
          confidence: 0.5,
          reason: 'Damage does not fit the story: the story implies a severe crash but the photo looks like a light scratch.',
          evidence: {
            expected_severity: 1.02,
            severity_probs: [0.04, 0.88, 0.07, 0.01],
            location_probs: { front: 0.62, rear: 0.38 },
            story_location: 'rear',
            story_severity: 3,
            photos: 1,
          },
          abstained: false,
          applicable: true,
          tier: 'claim',
        },
      ],
      pending_deep: false,
    },
    images: [
      {
        index: 0,
        name: 'photo_0_bumper.jpg',
        sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        claim: {
          image_score: 0.78,
          document_score: null,
          identity_score: null,
          overall: 0.78,
          band: 'HIGH',
          waterfall: [
            ['baseline', 0.50],
            ['localizer', 0.21],
            ['clip_probe', 0.15],
            ['ae_reconstruction', 0.12],
          ],
          regions: [
            {
              box: [280, 290, 480, 420],
              area_frac: 0.12,
              signals: { localizer: 0.91, noise_residual: 0.74, ae_reconstruction: 0.88 },
              reason: 'Region A (12%): localizer anomaly 0.91, noise mismatch 0.74 (bumper)',
              stage: 2,
            },
          ],
          signals: [],
          pending_deep: false,
        },
        quality_flag: false,
        quality_reasons: [],
        timing: { first_card_s: 1.4, fast_tier_s: 6.1, deep_s: 24.0 },
        urls: {
          photo: photoUrl,
          heatmap: heatmapUrl,
          reconstruction: reconstructionUrl,
        },
      },
    ],
    documents: [
      {
        index: 0,
        name: 'estimate_invoice_revised.pdf',
        sha256: '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945',
        doc_type: 'invoice',
        from_ocr: false,
        text: 'APEX AUTO COLLISION & BODYWORK. Total: $4,850.00. Subframe alignment and rear bumper replacement.',
        claim: {
          image_score: null,
          document_score: 0.66,
          identity_score: null,
          overall: 0.66,
          band: 'HIGH',
          waterfall: [
            ['baseline', 0.50],
            ['pdf_incremental_update', 0.28],
            ['pdf_producer_mismatch', 0.12],
            ['field_arithmetic', -0.24],
          ],
          regions: [],
          signals: [
            {
              name: 'pdf_incremental_update',
              score: 0.89,
              confidence: 0.95,
              reason: 'Incremental PDF revision replaced original total $1,250.00 with $4,850.00.',
              evidence: {
                diff: [
                  ['Subtotal: $1,150.00', 'Subtotal: $4,480.00'],
                  ['Total Amount: $1,250.00', 'Total Amount: $4,850.00'],
                  ['Labor: 3.5 hrs', 'Labor: 16.8 hrs'],
                ],
              },
              abstained: false,
              applicable: true,
              tier: 'doc',
            },
            {
              name: 'pdf_producer_mismatch',
              score: 0.72,
              confidence: 0.88,
              reason: 'PDF producer altered from QuickBooks 2024 to iText 7.1 with 2 days delta.',
              evidence: {
                producer: 'iText 7.1.16',
                creator: 'QuickBooks Desktop 2024',
                created: '2026-09-27T10:15:00Z',
                modified: '2026-09-29T16:42:00Z',
                days_between: 2.26,
              },
              abstained: false,
              applicable: true,
              tier: 'doc',
            },
            {
              name: 'ocr_confidence_dip',
              score: 0.64,
              confidence: 0.82,
              reason: 'OCR confidence dips to 48% around modified numerical characters in total box.',
              evidence: {
                words: [
                  { text: 'APEX', conf: 98, page: 0, box: [50, 40, 120, 65] },
                  { text: 'AUTO', conf: 96, page: 0, box: [130, 40, 180, 65] },
                  { text: 'TOTAL:', conf: 92, page: 0, box: [400, 600, 480, 625] },
                  { text: '$4,850.00', conf: 48, page: 0, box: [510, 600, 600, 625] },
                ],
              },
              abstained: false,
              applicable: true,
              tier: 'doc',
            },
            {
              name: 'field_arithmetic',
              score: 0.75,
              confidence: 0.90,
              reason: 'Sum of itemized labor and parts ($3,850.00 + tax) fails to equal stated total ($4,850.00).',
              evidence: { problems: ['Item sum ($4,168.12 with tax) does not match printed Total ($4,850.00). Difference: +$681.88'] },
              abstained: false,
              applicable: true,
              tier: 'doc',
            },
          ],
          pending_deep: false,
        },
        timing: { total_s: 3.2 },
        urls: { page: docUrl },
      },
    ],
    identity: {
      signals: [
        {
          name: 'face_match',
          score: 0.12,
          confidence: 0.94,
          reason: 'State driver license matches claimant selfie portrait with high fidelity.',
          evidence: { cosine: 0.89 },
          abstained: false,
          applicable: true,
          tier: 'identity',
        },
        {
          name: 'selfie_synthetic',
          score: 0.14,
          confidence: 0.86,
          reason: 'Selfie exhibits natural skin specular reflection and realistic biological depth.',
          evidence: { image_score: 0.14 },
          abstained: false,
          applicable: true,
          tier: 'identity',
        },
      ],
      urls: { id: idUrl, selfie: selfieUrl },
    },
    narrative: {
      text: 'Suspicious claim: The damage area in photo_0 (covering ~12% of the bumper) demonstrates high-confidence local inpainting and localized noise disruption. Additionally, the submitted repair invoice PDF contains an incremental update altering the total from $1,250.00 to $4,850.00 with conflicting arithmetic.',
      source: 'llm',
    },
    hashes: [
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945',
    ],
  };
}

export const MOCK_AUDIT_HISTORY: AuditRecord[] = [
  {
    case_id: 'b_fraud',
    reviewer: 'asha',
    action: 'reject',
    note: 'Dent pasted in; invoice edited after issue with +$3,600 inflation.',
    band: 'HIGH',
    ts: '2026-10-03T10:12:00Z',
  },
];

export const MOCK_HELDOUT_REPORT = {
  families: {
    sd15: { n: 500, auc: 0.942, tpr_at_1fpr: 0.812, flagged_high: 420 },
    sdxl: { n: 500, auc: 0.958, tpr_at_1fpr: 0.864, flagged_high: 445 },
    nova: { n: 400, auc: 0.925, tpr_at_1fpr: 0.778, flagged_high: 330 },
    flux: { n: 500, auc: 0.886, tpr_at_1fpr: 0.694, flagged_high: 360 },
    gan: { n: 400, auc: 0.741, tpr_at_1fpr: 0.425, flagged_high: 195 },
  },
  robustness: {
    orig: 0.954,
    q90: 0.948,
    q70: 0.912,
    q50: 0.864,
    dn512: 0.895,
    whatsapp: 0.871,
  },
};
