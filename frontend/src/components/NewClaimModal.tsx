import React, { useState } from 'react';
import {
  X,
  UploadCloud,
  FileText,
  Image as ImageIcon,
  UserCheck,
  Shield,
  AlertCircle,
  Camera,
  RotateCcw,
  Trash2,
  Check,
} from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { CameraModal } from './CameraModal';

interface NewClaimModalProps {
  isOpen: boolean;
  onClose: () => void;
  onClaimCreated: (caseId: string, eventsUrl: string) => void;
}

export const NewClaimModal: React.FC<NewClaimModalProps> = ({
  isOpen,
  onClose,
  onClaimCreated,
}) => {
  const { user } = useAuth();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [photos, setPhotos] = useState<File[]>([]);
  const [documents, setDocuments] = useState<File[]>([]);
  const [idFile, setIdFile] = useState<File | null>(null);
  const [selfieFile, setSelfieFile] = useState<File | null>(null);
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const canSubmit = photos.length > 0 || documents.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('title', title || 'New Insurance Claim');
      if (description.trim()) formData.append('description', description.trim());
      photos.forEach((p) => formData.append('photos', p));
      documents.forEach((d) => formData.append('documents', d));
      if (idFile) formData.append('id', idFile);
      if (selfieFile) formData.append('selfie', selfieFile);

      const res = await api.uploadCase(formData);
      api.rememberMyClaim(res.case_id, title || 'New Insurance Claim', user?.email || 'guest');
      onClaimCreated(res.case_id, res.events);
      onClose();
    } catch (err: any) {
      alert(`Upload failed: ${err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="w-full max-w-2xl bg-white rounded-3xl border border-[#EAE5DC] shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#EAE5DC] bg-[#FAF8F5] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-stone-900 flex items-center justify-center text-white shadow-xs">
              <Shield className="w-4 h-4 text-amber-300" />
            </div>
            <div>
              <h3 className="text-base font-bold text-stone-900">
                Submit New Claim For Review
              </h3>
              <p className="text-xs text-stone-500">
                AI and cryptographic forensics will analyze evidence in parallel.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Form */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-5 flex-1 text-xs">
          {/* Title */}
          <div>
            <label className="font-bold text-stone-700 block mb-1.5">
              Claim Reference / Title (Optional)
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. 2024 Honda Civic Rear Collision - Policy #98124"
              className="w-full p-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 pencil-hover focus:outline-hidden focus:ring-2 focus:ring-stone-400 text-xs"
            />
          </div>

          {/* What happened (feeds the damage-vs-story check) */}
          <div>
            <label className="font-bold text-stone-700 block mb-1.5">
              What happened? (Optional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. I was rear-ended at about 30 km/h at a junction"
              className="w-full p-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 pencil-hover focus:outline-hidden focus:ring-2 focus:ring-stone-400 text-xs font-sans"
            />
          </div>

          {/* 4 Drop Zones Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Zone 1: Damage Photos (Multiple) */}
            <div className="p-4 rounded-2xl border-2 border-dashed border-stone-200 hover:border-stone-400 transition-colors bg-stone-50/60 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <ImageIcon className="w-4 h-4 text-blue-600" />
                  <span className="font-bold text-stone-900">
                    Damage Photos (Multiple) *
                  </span>
                </div>
                <p className="text-[11px] text-stone-500 mb-2">
                  JPG, PNG, HEIC, WEBP. Evaluated for inpainting, noise & C2PA.
                </p>
              </div>

              <label className="cursor-pointer flex flex-col items-center justify-center p-3 rounded-xl bg-white border border-[#EAE5DC] hover:bg-stone-50 transition-colors pencil-hover shadow-xs">
                <UploadCloud className="w-5 h-5 text-stone-400 mb-1" />
                <span className="text-[11px] font-bold text-stone-800">
                  {photos.length > 0 ? `${photos.length} photo(s) selected` : 'Choose photos'}
                </span>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={(e) => setPhotos(Array.from(e.target.files || []))}
                  className="hidden"
                />
              </label>
            </div>

            {/* Zone 2: Documents (Multiple) */}
            <div className="p-4 rounded-2xl border-2 border-dashed border-stone-200 hover:border-stone-400 transition-colors bg-stone-50/60 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <FileText className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-stone-900">
                    Repair Invoices / Scans *
                  </span>
                </div>
                <p className="text-[11px] text-stone-500 mb-2">
                  PDF or scans. Evaluated for PDF revision history and OCR dips.
                </p>
              </div>

              <label className="cursor-pointer flex flex-col items-center justify-center p-3 rounded-xl bg-white border border-[#EAE5DC] hover:bg-stone-50 transition-colors pencil-hover shadow-xs">
                <UploadCloud className="w-5 h-5 text-stone-400 mb-1" />
                <span className="text-[11px] font-bold text-stone-800">
                  {documents.length > 0 ? `${documents.length} doc(s) selected` : 'Choose documents'}
                </span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,image/*"
                  onChange={(e) => setDocuments(Array.from(e.target.files || []))}
                  className="hidden"
                />
              </label>
            </div>

            {/* Zone 3: ID (One) */}
            <div className="p-4 rounded-2xl border-2 border-dashed border-stone-200 hover:border-stone-400 transition-colors bg-stone-50/60 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <UserCheck className="w-4 h-4 text-indigo-600" />
                  <span className="font-bold text-stone-900">
                    Claimant ID (One)
                  </span>
                </div>
                <p className="text-[11px] text-stone-500 mb-2">
                  Government driver's license or passport photo.
                </p>
              </div>

              <label className="cursor-pointer flex flex-col items-center justify-center p-3 rounded-xl bg-white border border-[#EAE5DC] hover:bg-stone-50 transition-colors pencil-hover shadow-xs">
                <UploadCloud className="w-5 h-5 text-stone-400 mb-1" />
                <span className="text-[11px] font-bold text-stone-800 truncate max-w-[200px]">
                  {idFile ? idFile.name : 'Choose ID photo'}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setIdFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
              </label>
            </div>

            {/* Zone 4: Selfie (One) */}
            <div className="p-4 rounded-2xl border-2 border-dashed border-stone-200 hover:border-stone-400 transition-colors bg-stone-50/60 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <UserCheck className="w-4 h-4 text-purple-600" />
                  <span className="font-bold text-stone-900">
                    Live Selfie (One)
                  </span>
                </div>
                <p className="text-[11px] text-stone-500 mb-2">
                  Claimant live portrait for biometric matching.
                </p>
              </div>

              {selfiePreview || selfieFile ? (
                <div className="flex items-center gap-3 p-2.5 rounded-xl bg-white border border-[#EAE5DC] shadow-xs">
                  {selfiePreview ? (
                    <img
                      src={selfiePreview}
                      alt="Selfie preview"
                      className="w-12 h-12 rounded-lg object-cover border border-stone-200 shrink-0"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-lg bg-violet-100 text-violet-700 flex items-center justify-center shrink-0">
                      <Camera className="w-5 h-5" />
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-stone-800">
                      <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span className="truncate">{selfieFile?.name || 'Selfie Attached'}</span>
                    </div>
                    <span className="text-[10px] text-stone-500 block">
                      Ready for facial verification
                    </span>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsCameraOpen(true)}
                      className="p-1.5 rounded-lg text-stone-500 hover:text-stone-800 hover:bg-stone-100 transition-colors cursor-pointer"
                      title="Retake selfie with camera"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelfieFile(null);
                        setSelfiePreview(null);
                      }}
                      className="p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer"
                      title="Remove selfie"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => setIsCameraOpen(true)}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs shadow-xs pencil-hover transition-all active:scale-95 cursor-pointer"
                  >
                    <Camera className="w-4 h-4" />
                    <span>Take Selfie with Camera</span>
                  </button>

                  <label className="cursor-pointer flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-xl bg-white border border-[#EAE5DC] hover:bg-stone-50 transition-colors pencil-hover shadow-xs text-[11px] font-semibold text-stone-600">
                    <UploadCloud className="w-3.5 h-3.5 text-stone-400" />
                    <span>Or upload photo</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setSelfieFile(file);
                          setSelfiePreview(URL.createObjectURL(file));
                        }
                      }}
                      className="hidden"
                    />
                  </label>
                </div>
              )}
            </div>
          </div>

          {/* Privacy Note (§ 7.7) */}
          <div className="p-3 rounded-xl bg-stone-100 text-stone-600 flex items-center gap-2 text-[11px]">
            <AlertCircle className="w-4 h-4 text-stone-500 shrink-0" />
            <span>Files are deleted from the server right after scoring. Only SHA-256 hashes are persisted.</span>
          </div>

          {/* Footer Submit */}
          <div className="pt-2 flex items-center justify-end gap-3 border-t border-[#EAE5DC]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-stone-600 hover:bg-stone-100 font-semibold cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit || loading}
              className="px-6 py-2.5 rounded-full font-bold text-white bg-stone-900 hover:bg-black apple-btn pencil-hover transition-all shadow-md disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {loading ? 'Initializing Stream…' : 'Score Claim'}
            </button>
          </div>
        </form>
      </div>

      <CameraModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onCapture={(file, previewUrl) => {
          setSelfieFile(file);
          setSelfiePreview(previewUrl);
        }}
        title="Live Biometric Selfie Capture"
        subtitle="Position your face within the oval guide to verify identity."
      />
    </div>
  );
};
