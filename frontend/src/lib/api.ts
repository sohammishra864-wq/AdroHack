import {
  CaseResult,
  InboxCase,
  ApiConfig,
  HealthStatus,
  AuditRecord,
  Signal,
  ImageResult,
  DocResult,
  ClaimScore,
  Attack,
  SeedItem,
} from '../types';
import { DEFAULT_CONFIG } from './constants';
import {
  MOCK_HEALTH,
  MOCK_INBOX_CASES,
  getMockCaseResult,
  MOCK_AUDIT_HISTORY,
  MOCK_HELDOUT_REPORT,
} from './mockData';
import { createCarPhotoUrl, createHeatmapUrl } from './mockAssets';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface MyClaim {
  case_id: string;
  title: string;
  owner: string;     // account email (or demo persona) that filed it
  filed: string;     // ISO time
}

export interface AuthSession {
  access_token: string | null;
  refresh_token?: string | null;
  expires_in?: number | null;
  message?: string;
  user: { id: string; email: string; full_name: string; organization?: string | null; role: string };
}

// The backend returns picture links as server-relative paths ("/api/cases/x/images/0/photo.png").
// The frontend runs on another origin (:5173), so every such path must point at API_BASE.
export function withAbsoluteUrls<T>(value: T): T {
  if (typeof value === 'string') {
    return (value.startsWith('/api/') ? `${API_BASE}${value}` : value) as T;
  }
  if (Array.isArray(value)) return value.map(withAbsoluteUrls) as T;
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, withAbsoluteUrls(v)])) as T;
  }
  return value;
}

const liveJson = async (res: Response) => withAbsoluteUrls(await res.json());
const sse = (e: Event) => withAbsoluteUrls(JSON.parse((e as MessageEvent).data));

// A live-mode case error the page can act on (404 never scored, 409 still scoring).
export class CaseNotReady extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

class ApiService {
  private useMock: boolean = true;
  private isLiveAvailable: boolean = false;
  private localHistory: Record<string, AuditRecord[]> = {
    b_fraud: [...MOCK_AUDIT_HISTORY],
  };
  private dynamicCases: Map<string, CaseResult> = new Map();

  constructor() {
    // Check initial preference from localStorage if set
    // Live (the real backend) by default; Demo only when the user picks it. If the server is
    // unreachable the header shows a banner offering Demo mode.
    const saved = localStorage.getItem('claimshield_mode');
    this.useMock = saved === 'mock';
    this.checkLiveHealth();
  }

  public getMode(): 'live' | 'mock' {
    return this.useMock ? 'mock' : 'live';
  }

  public setMode(mode: 'live' | 'mock') {
    this.useMock = mode === 'mock';
    localStorage.setItem('claimshield_mode', mode);
  }

  public getIsLiveAvailable(): boolean {
    return this.isLiveAvailable;
  }

  public async checkLiveHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/api/health`, { method: 'GET', signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        this.isLiveAvailable = true;
        return true;
      }
    } catch {
      this.isLiveAvailable = false;
    }
    return false;
  }

  private getReviewerHeader(): Record<string, string> {
    const reviewer = localStorage.getItem('claimshield_reviewer') || 'asha';
    const token = localStorage.getItem('claimshield_token');
    // A Supabase token (real login) is verified by the backend; X-Reviewer is the demo-persona fallback.
    return token ? { 'X-Reviewer': reviewer, Authorization: `Bearer ${token}` } : { 'X-Reviewer': reviewer };
  }

  // Auth (Supabase via the backend, README). Off in mock mode or when the backend has no SUPABASE_URL.
  public async authStatus(): Promise<{ enabled: boolean }> {
    if (this.useMock) return { enabled: false };
    try {
      const res = await fetch(`${API_BASE}/api/auth/status`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) return await res.json();
    } catch {
      // backend unreachable: demo personas only
    }
    return { enabled: false };
  }

  private async authPost(path: string, body?: object): Promise<any> {
    const res = await fetch(`${API_BASE}/api/auth/${path}`, {
      method: 'POST',
      headers: { ...this.getReviewerHeader(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error?.message || `Request failed (${res.status})`);
    return data;
  }

  public login(email: string, password: string): Promise<AuthSession> {
    return this.authPost('login', { email, password });
  }

  public signup(email: string, password: string, fullName: string): Promise<AuthSession> {
    return this.authPost('signup', { email, password, full_name: fullName });
  }

  public async logout(): Promise<void> {
    if (localStorage.getItem('claimshield_token')) {
      await this.authPost('logout').catch(() => undefined);   // revoke server-side; clear locally regardless
    }
  }

  // Meta endpoints
  public async getHealth(): Promise<HealthStatus> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/health`, { headers: this.getReviewerHeader() });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('Live API health check failed, using simulated health status', e);
      }
    }
    return MOCK_HEALTH;
  }

  public async getConfig(): Promise<ApiConfig> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/config`, { headers: this.getReviewerHeader() });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('Failed to fetch /config, using defaults', e);
      }
    }
    return DEFAULT_CONFIG;
  }

  // Cases endpoints
  public async getCases(): Promise<InboxCase[]> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/cases`, { headers: this.getReviewerHeader() });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('Live API /cases failed, falling back to mock cases', e);
      }
    }
    // Return mock cases + any newly uploaded dynamic cases
    const dynamicInbox: InboxCase[] = Array.from(this.dynamicCases.values()).map((c) => ({
      case_id: c.case_id,
      title: c.title,
      counts: {
        photos: c.images.length,
        documents: c.documents.length,
        id: !!c.identity,
        selfie: !!c.identity,
      },
      last_band: c.claim.band,
    }));
    return [...dynamicInbox, ...MOCK_INBOX_CASES];
  }

  public async getCase(caseId: string): Promise<CaseResult> {
    if (!this.useMock && !this.dynamicCases.has(caseId)) {
      // Live mode: never show mock evidence for a real claim. 404 = not scored yet,
      // 409 = scoring in progress; the case page starts / follows live scoring instead.
      const res = await fetch(`${API_BASE}/api/cases/${caseId}`, { headers: this.getReviewerHeader() });
      if (res.ok) return await liveJson(res);
      if (res.status === 404 || res.status === 409) {
        throw new CaseNotReady(res.status, res.status === 409 ? 'Case scoring still in progress' : 'Case not scored yet');
      }
      throw new Error(`GET /api/cases/${caseId} failed (${res.status})`);
    }

    if (this.dynamicCases.has(caseId)) {
      return this.dynamicCases.get(caseId)!;
    }
    return getMockCaseResult(caseId);
  }

  public async scoreCase(caseId: string): Promise<{ case_id: string; job_id: string; events: string }> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/cases/${caseId}/score`, {
          method: 'POST',
          headers: this.getReviewerHeader(),
        });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn(`POST /cases/${caseId}/score failed`, e);
      }
    }
    // Return simulated response
    return {
      case_id: caseId,
      job_id: `job_${Date.now()}`,
      events: `/api/jobs/job_${Date.now()}/events`,
    };
  }

  public async uploadCase(formData: FormData): Promise<{ case_id: string; job_id: string; events: string }> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/cases`, {
          method: 'POST',
          headers: this.getReviewerHeader(),
          body: formData,
        });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('POST /api/cases failed, using mock simulation', e);
      }
    }

    const title = (formData.get('title') as string) || 'New Uploaded Claim';
    const caseId = `upload-${Math.random().toString(16).substring(2, 10)}`;
    const mockCase = getMockCaseResult('b_fraud');
    mockCase.case_id = caseId;
    mockCase.title = title;
    this.dynamicCases.set(caseId, mockCase);

    return {
      case_id: caseId,
      job_id: `job_${Date.now()}`,
      events: `/api/jobs/job_${Date.now()}/events`,
    };
  }

  public async postDecision(caseId: string, action: 'accept' | 'reject' | 'escalate', note: string): Promise<AuditRecord> {
    const reviewer = localStorage.getItem('claimshield_reviewer') || 'asha';
    const currentCase = await this.getCase(caseId);

    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/cases/${caseId}/decision`, {
          method: 'POST',
          headers: { ...this.getReviewerHeader(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, note, reviewer }),
        });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('POST decision failed, storing locally', e);
      }
    }

    const newRecord: AuditRecord = {
      case_id: caseId,
      reviewer,
      action,
      note,
      band: currentCase.claim.band,
      ts: new Date().toISOString(),
    };

    if (!this.localHistory[caseId]) {
      this.localHistory[caseId] = [];
    }
    this.localHistory[caseId].push(newRecord);
    return newRecord;
  }

  public async getHistory(caseId: string): Promise<AuditRecord[]> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/cases/${caseId}/history`, { headers: this.getReviewerHeader() });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('GET /history failed, returning local history', e);
      }
    }
    return this.localHistory[caseId] || [];
  }

  // "My claims" for the client portal: case ids this browser submitted, per account
  public rememberMyClaim(caseId: string, title: string, owner: string) {
    const all = this.myClaims(null);
    if (!all.some((c) => c.case_id === caseId)) {
      all.unshift({ case_id: caseId, title, owner, filed: new Date().toISOString() });
      localStorage.setItem('claimshield_my_claims', JSON.stringify(all.slice(0, 50)));
    }
  }

  public myClaims(owner: string | null): MyClaim[] {
    try {
      const all: MyClaim[] = JSON.parse(localStorage.getItem('claimshield_my_claims') || '[]');
      return owner === null ? all : all.filter((c) => c.owner === owner);
    } catch {
      return [];
    }
  }

  // Arena endpoints
  public async getArenaSeeds(): Promise<SeedItem[]> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/arena/seeds`);
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('GET /arena/seeds failed', e);
      }
    }
    const sampleSeeds: SeedItem[] = [
      { name: 'car_0001_bumper.jpg', url: createCarPhotoUrl() },
      { name: 'car_0002_quarter_panel.jpg', url: createCarPhotoUrl() },
      { name: 'car_0003_hood_dent.jpg', url: createCarPhotoUrl() },
      { name: 'car_0004_door_crease.jpg', url: createCarPhotoUrl() },
    ];
    return sampleSeeds;
  }

  public async scoreArenaOriginal(seedOrPhoto: string | File): Promise<{ arena_id: string; job_id: string; events: string }> {
    if (!this.useMock) {
      try {
        const formData = new FormData();
        if (typeof seedOrPhoto === 'string') {
          formData.append('seed', seedOrPhoto);
        } else {
          formData.append('photo', seedOrPhoto);
        }
        const res = await fetch(`${API_BASE}/api/arena`, { method: 'POST', body: formData });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('POST /arena failed', e);
      }
    }
    const arenaId = `arena_${Date.now()}`;
    return {
      arena_id: arenaId,
      job_id: `job_arena_${Date.now()}`,
      events: `/api/jobs/arena_${Date.now()}/events`,
    };
  }

  public async attackArena(arenaId: string, kind: string, prompt?: string): Promise<{ job_id: string; events: string }> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/arena/${arenaId}/attack`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind, prompt }),
        });
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('POST /arena/attack failed', e);
      }
    }
    return {
      job_id: `job_attack_${Date.now()}`,
      events: `/api/jobs/attack_${Date.now()}/events`,
    };
  }

  public async getArenaResult(arenaId: string): Promise<{ before: ImageResult; after: ImageResult | null; attack: Attack | null }> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/arena/${arenaId}`);
        if (res.ok) return await liveJson(res);
      } catch (e) {
        console.warn('GET /arena/:id failed', e);
      }
    }
    const mockCase = getMockCaseResult('b_fraud');
    return {
      before: mockCase.images[0],
      after: {
        ...mockCase.images[0],
        urls: {
          photo: createCarPhotoUrl(),
          heatmap: createHeatmapUrl(),
          reconstruction: null,
        },
      },
      attack: {
        kind: 'inpaint',
        method: 'nova',
        note: 'Painted a dent with Amazon Nova Canvas.',
        seconds: 18.2,
      },
    };
  }

  // Reports
  public async getHeldoutReport() {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/reports/heldout`);
        if (res.ok) return await liveJson(res);
        if (res.status === 404) return { families: {}, robustness: {} };   // live: not measured yet, never sample numbers
      } catch (e) {
        console.warn('GET /reports/heldout failed', e);
      }
    }
    return MOCK_HELDOUT_REPORT;
  }

  public async getReportMarkdown(reportType: 'eval' | 'latency' | 'medical_billing' | 'damage_story'): Promise<string> {
    if (!this.useMock) {
      try {
        const res = await fetch(`${API_BASE}/api/reports/${reportType}`);
        if (res.ok) return await res.text();
        if (res.status === 404) return '';   // live: not measured yet, never sample numbers
      } catch (e) {
        console.warn(`GET /reports/${reportType} failed`, e);
      }
    }
    if (reportType === 'medical_billing') {
      return `### Medical billing check (health-insurance upcoding)
Generated discharge summaries, 200 per row, read back from real PDFs.
- **Clean reports flagged**: \`0 / 200\` (0.0 %)
- **Procedure the diagnosis doesn't need**: \`200 / 200\` caught
- **Stay too long for the diagnosis**: \`200 / 200\` caught
- **More days billed than stayed**: \`200 / 200\` caught
Synthetic (generator and check share the care table): measures parsing + rules end to end.`;
    }
    if (reportType === 'damage_story') {
      return `### Damage vs story check
200 real damage photos (VehiDE seeds), CLIP ViT-L/14 zero-shot.
- **Legit stories flagged** (vague / 30 km/h / dent): \`0 / 200\` each
- **"70 km/h, totalled" on these photos**: \`47 / 200\` flagged
- **"Parked, light scratch"**: \`2 / 200\` flagged
Fires only on clear contradictions; confidence capped at 0.5.`;
    }
    if (reportType === 'eval') {
      return `### ClaimShield Evaluation Summary (Latest Run)
- **Overall AUC (Cross-Generator)**: \`0.941\`
- **TPR @ 1% FPR**: \`82.4%\`
- **Quality Robustness**: Maintained AUC > \`0.86\` even through heavy WhatsApp compression and resize.
- **Evaluation Blindspots**:
  - *Flux.1*: Never trained or calibrated on; demonstrates partial generalization with 0.886 AUC.
  - *StyleGAN (Face)*: Eval-only benchmark (reconstruction blind spot detected in high frequency teeth regions).`;
    }
    return `### Latency Benchmark (p95 on NVIDIA RTX 4090 / 8-core CPU)
- **First Signal Card**: \`1.4 s\` (Target ≤ 2.0 s)
- **Fast Tier (Image + Doc + Exif)**: \`6.1 s\` (Target ≤ 8.0 s)
- **Deep Tier (Autoencoder Reconstruction)**: \`24.0 s\` (Target ≤ 30.0 s)
- **Full Case Assembly & Decision Enablement**: \`24.8 s\``;
  }

  // Live SSE Stream Connector with Intelligent Fallback Simulator
  public subscribeToEvents(
    eventsUrl: string,
    caseId: string,
    callbacks: {
      onCard: (data: { lane: string; index: number; signal: Signal }) => void;
      onImageFastDone: (data: { index: number; result: ImageResult }) => void;
      onDocDone: (data: { index: number; result: DocResult }) => void;
      onProvisional: (data: { claim: ClaimScore }) => void;
      onDeepDone: (data: { index: number; signal: Signal; result: ImageResult }) => void;
      onFinal: (data: CaseResult) => void;
      onError: (err: { message: string }) => void;
    }
  ): () => void {
    if (!this.useMock) {
      try {
        const es = new EventSource(`${API_BASE}${eventsUrl}`);
        es.addEventListener('card', (e) => callbacks.onCard(sse(e)));
        es.addEventListener('image_fast_done', (e) => callbacks.onImageFastDone(sse(e)));
        es.addEventListener('document_done', (e) => callbacks.onDocDone(sse(e)));
        es.addEventListener('provisional', (e) => callbacks.onProvisional(sse(e)));
        es.addEventListener('deep_done', (e) => callbacks.onDeepDone(sse(e)));
        es.addEventListener('final', (e) => {
          callbacks.onFinal(sse(e));
          es.close();
        });
        es.addEventListener('error', (e) => {
          let msg = 'Connection error on event stream';
          try {
            msg = JSON.parse((e as MessageEvent).data).message;
          } catch {
            // fallback
          }
          callbacks.onError({ message: msg });
          es.close();
        });
        return () => es.close();
      } catch (err) {
        console.warn('Real EventSource failed, switching to simulated SSE stream', err);
      }
    }

    // --- Intelligent Fallback Simulator ---
    const targetCase = this.dynamicCases.get(caseId) || getMockCaseResult(caseId);
    let isCancelled = false;
    const timeouts: any[] = [];

    // Progressive timeline of cards matching the timing contract
    const allSignals = [...targetCase.claim.signals];

    // Card 1: 1.2s
    if (allSignals[0]) {
      timeouts.push(
        setTimeout(() => {
          if (!isCancelled) callbacks.onCard({ lane: allSignals[0].tier, index: 0, signal: allSignals[0] });
        }, 1200)
      );
    }

    // Card 2: 2.2s
    if (allSignals[1]) {
      timeouts.push(
        setTimeout(() => {
          if (!isCancelled) callbacks.onCard({ lane: allSignals[1].tier, index: 0, signal: allSignals[1] });
        }, 2200)
      );
    }

    // Card 3 & Doc done: 3.4s
    if (allSignals[2]) {
      timeouts.push(
        setTimeout(() => {
          if (!isCancelled) {
            callbacks.onCard({ lane: allSignals[2].tier, index: 0, signal: allSignals[2] });
            if (targetCase.documents[0]) {
              callbacks.onDocDone({ index: 0, result: targetCase.documents[0] });
            }
          }
        }, 3400)
      );
    }

    // Fast tier done & Provisional score: 4.8s
    timeouts.push(
      setTimeout(() => {
        if (!isCancelled) {
          if (targetCase.images[0]) {
            callbacks.onImageFastDone({ index: 0, result: targetCase.images[0] });
          }
          callbacks.onProvisional({
            claim: {
              ...targetCase.claim,
              pending_deep: true,
            },
          });
        }
      }, 4800)
    );

    // Deep check done: 8.5s
    const deepSignal = allSignals.find((s) => s.tier === 'deep') || allSignals[0];
    timeouts.push(
      setTimeout(() => {
        if (!isCancelled) {
          callbacks.onDeepDone({
            index: 0,
            signal: deepSignal,
            result: targetCase.images[0],
          });
        }
      }, 8500)
    );

    // Final result: 10.0s
    timeouts.push(
      setTimeout(() => {
        if (!isCancelled) {
          callbacks.onFinal(targetCase);
        }
      }, 10000)
    );

    return () => {
      isCancelled = true;
      timeouts.forEach(clearTimeout);
    };
  }
}

export const api = new ApiService();
