import { useState, useRef, useEffect } from 'react'
import { smartUpload, smartUploadConfirm } from '../api/documents'
import { getEmissionByDocument } from '../api/emissions'
import type {
  DocumentType,
  ExtractedBillData,
  SmartUploadResult,
} from '../api/documents'
import type { EmissionRecord } from '../api/emissions'

const DOC_TYPES: { value: DocumentType; label: string }[] = [
  { value: 'ELECTRICITY_BILL',     label: 'Electricity Bill' },
  { value: 'FUEL_RECEIPT',         label: 'Fuel Receipt' },
  { value: 'WATER_BILL',           label: 'Water Bill' },
  { value: 'WATER_QUALITY_REPORT', label: 'Water Quality Report' },
  { value: 'GENERATOR_LOG',        label: 'Generator Log' },
  { value: 'OTHER',                label: 'Other Document' },
]

type Step =
  | 'SELECT'       // choose file + type
  | 'EXTRACTING'   // Claude reading
  | 'CONFIRM'      // user confirms match
  | 'NEW_FACILITY' // user reviews new facility
  | 'NEW_COMPANY'  // user reviews new company
  | 'DONE'         // saved

export default function UploadPage() {
  const [file, setFile]           = useState<File | null>(null)
  const [docType, setDocType]     = useState<DocumentType>('ELECTRICITY_BILL')
  const [step, setStep]           = useState<Step>('SELECT')
  const [result, setResult]       = useState<SmartUploadResult | null>(null)
  const [emission, setEmission]   = useState<EmissionRecord | null>(null)
  const [saved, setSaved]         = useState<{
    document_id: string; company_id: string; facility_id: string
  } | null>(null)
  const [error, setError]         = useState<string | null>(null)
  const [dragOver, setDragOver]   = useState(false)

  // Editable fields for new company/facility
  const [newCompanyName, setNewCompanyName]   = useState('')
  const [newCompanyCity, setNewCompanyCity]   = useState('')
  const [newCompanyState, setNewCompanyState] = useState('')
  const [newFacilityName, setNewFacilityName] = useState('')
  const [newFacilityCity, setNewFacilityCity] = useState('')

  const inputRef = useRef<HTMLInputElement>(null)

  // ----------------------------------------------------------------
  // Step 1 — upload and extract
  // ----------------------------------------------------------------
  async function handleUpload() {
    if (!file) return
    setStep('EXTRACTING')
    setError(null)
    try {
      const res = await smartUpload(file, docType)
      setResult(res)

      if (res.action === 'AUTO_MAPPED') {
        // Perfect match — save immediately
        await confirmAndSave(res, 'CONFIRMED')
      } else if (res.action === 'CONFIRM_MATCH') {
        setStep('CONFIRM')
      } else if (res.action === 'NEW_FACILITY_NEEDED') {
        setNewFacilityName(res.suggested_facility?.name || '')
        setNewFacilityCity(res.suggested_facility?.city || '')
        setStep('NEW_FACILITY')
      } else {
        // NEW_COMPANY_NEEDED
        setNewCompanyName(res.suggested_company?.name || '')
        setNewCompanyCity(res.suggested_company?.city || '')
        setNewCompanyState(res.suggested_company?.state || '')
        setNewFacilityName(res.suggested_facility?.name || res.extracted_city || '')
        setStep('NEW_COMPANY')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed.')
      setStep('SELECT')
    }
  }

  // ----------------------------------------------------------------
  // Step 2 — confirm or create
  // ----------------------------------------------------------------
  async function confirmAndSave(
    res: SmartUploadResult,
    action: 'CONFIRMED' | 'CREATE_FACILITY' | 'CREATE_COMPANY',
    overrides?: {
      company_id?: string | null
      facility_id?: string | null
    }
  ) {
    try {
      const payload: any = {
        file_key:        res.file_key,
        file_name:       res.file_name,
        file_size_bytes: res.file_size_bytes,
        mime_type:       res.mime_type,
        document_type:   res.document_type,
        extracted:       res.extracted,
        action,
        company_id:  overrides?.company_id  ?? res.company_id,
        facility_id: overrides?.facility_id ?? res.facility_id,
      }

      if (action === 'CREATE_FACILITY') {
        payload.new_facility = {
          name:    newFacilityName,
          city:    newFacilityCity,
          state:   res.extracted_state || newCompanyState,
          address: res.extracted_address,
        }
      }

      if (action === 'CREATE_COMPANY') {
        payload.new_company = {
          name:  newCompanyName,
          city:  newCompanyCity,
          state: newCompanyState,
        }
        payload.new_facility = {
          name:    newFacilityName,
          city:    newFacilityCity || newCompanyCity,
          state:   newCompanyState,
          address: res.extracted_address,
        }
      }

      const saved = await smartUploadConfirm(payload)
      setSaved(saved)
      setStep('DONE')

      // Fetch emission record
      if (
        saved.facility_id &&
        (docType === 'ELECTRICITY_BILL' || docType === 'FUEL_RECEIPT')
      ) {
        await new Promise(r => setTimeout(r, 500))
        const em = await getEmissionByDocument(saved.document_id)
        setEmission(em)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save document.')
    }
  }

  function reset() {
    setFile(null)
    setStep('SELECT')
    setResult(null)
    setSaved(null)
    setEmission(null)
    setError(null)
    setNewCompanyName('')
    setNewCompanyCity('')
    setNewCompanyState('')
    setNewFacilityName('')
    setNewFacilityCity('')
  }

  // ----------------------------------------------------------------
  // Render helpers
  // ----------------------------------------------------------------
  const extracted = result?.extracted as ExtractedBillData | null

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">

      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Upload Document</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload a bill or report. SANGATNA reads it and maps it to the right company automatically.
        </p>
      </div>

      {/* ── STEP: SELECT ── */}
      {step === 'SELECT' && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">

          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center
                        cursor-pointer transition-colors ${
              dragOver ? 'border-green-500 bg-green-50'
              : file   ? 'border-green-400 bg-green-50'
                       : 'border-gray-300 hover:border-gray-400'
            }`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault(); setDragOver(false)
              const f = e.dataTransfer.files[0]
              if (f) setFile(f)
            }}
          >
            <input
              ref={inputRef} type="file" className="hidden"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file ? (
              <div className="space-y-1">
                <div className="text-2xl">📄</div>
                <p className="font-medium text-gray-800">{file.name}</p>
                <p className="text-sm text-gray-500">
                  {(file.size / 1024).toFixed(1)} KB — click to change
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-3xl">⬆️</div>
                <p className="font-medium text-gray-700">
                  Drop your file here or click to browse
                </p>
                <p className="text-sm text-gray-400">PDF, JPG, or PNG</p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Document type
            </label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              {DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200
                          rounded-md px-3 py-2">{error}</p>
          )}

          <button
            onClick={handleUpload}
            disabled={!file}
            className="w-full bg-green-600 text-white py-2.5 rounded-md font-medium
                       hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            Upload and extract
          </button>
        </div>
      )}

      {/* ── STEP: EXTRACTING ── */}
      {step === 'EXTRACTING' && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center
                        space-y-3">
          <div className="text-3xl animate-pulse">🤖</div>
          <p className="font-medium text-gray-800">Claude is reading the document…</p>
          <p className="text-sm text-gray-500">
            Extracting data and matching to your companies
          </p>
        </div>
      )}

      {/* ── STEP: CONFIRM MATCH ── */}
      {step === 'CONFIRM' && result && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔍</span>
            <div>
              <h2 className="font-semibold text-gray-900">We found a match</h2>
              <p className="text-sm text-gray-600 mt-1">{result.message}</p>
            </div>
          </div>

          {/* Extracted info */}
          <div className="bg-gray-50 rounded-md p-4 space-y-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide">
              From the document
            </p>
            <p className="text-sm font-medium text-gray-800">
              {result.extracted_name}
            </p>
            <p className="text-sm text-gray-500">{result.extracted_address}</p>
          </div>

          {/* Matched to */}
          <div className="bg-green-50 border border-green-200 rounded-md p-4 space-y-1">
            <p className="text-xs text-green-600 uppercase tracking-wide">
              Matched to
            </p>
            <p className="text-sm font-semibold text-green-800">
              {result.company_name}
            </p>
            <p className="text-sm text-green-700">
              {result.facility_name}
            </p>
            <p className="text-xs text-green-500">
              Confidence: {Math.round(result.confidence * 100)}%
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => confirmAndSave(result, 'CONFIRMED')}
              className="flex-1 bg-green-600 text-white py-2.5 rounded-md
                         font-medium hover:bg-green-700 transition-colors"
            >
              Yes, that's correct
            </button>
            <button
              onClick={() => {
                setNewCompanyName(result.extracted_name)
                setNewCompanyCity(result.extracted_city)
                setNewCompanyState(result.extracted_state)
                setNewFacilityName(result.extracted_city)
                setStep('NEW_COMPANY')
              }}
              className="flex-1 border border-gray-300 text-gray-700 py-2.5
                         rounded-md font-medium hover:bg-gray-50 transition-colors"
            >
              No, create new company
            </button>
          </div>
        </div>
      )}

      {/* ── STEP: NEW FACILITY NEEDED ── */}
      {step === 'NEW_FACILITY' && result && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🏭</span>
            <div>
              <h2 className="font-semibold text-gray-900">New facility found</h2>
              <p className="text-sm text-gray-600 mt-1">{result.message}</p>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
            <p className="text-xs text-blue-600 uppercase tracking-wide mb-1">
              Adding to company
            </p>
            <p className="text-sm font-semibold text-blue-800">
              {result.company_name}
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-700">
              New facility details — edit if needed:
            </p>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Facility name
              </label>
              <input
                value={newFacilityName}
                onChange={(e) => setNewFacilityName(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2
                           text-sm focus:outline-none focus:ring-2
                           focus:ring-green-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">City</label>
              <input
                value={newFacilityCity}
                onChange={(e) => setNewFacilityCity(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2
                           text-sm focus:outline-none focus:ring-2
                           focus:ring-green-500"
                placeholder={result.extracted_city}
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-3">
            <button
              onClick={() => confirmAndSave(result, 'CREATE_FACILITY')}
              className="flex-1 bg-green-600 text-white py-2.5 rounded-md
                         font-medium hover:bg-green-700 transition-colors"
            >
              Add facility and save
            </button>
            <button
              onClick={reset}
              className="flex-1 border border-gray-300 text-gray-700 py-2.5
                         rounded-md font-medium hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── STEP: NEW COMPANY NEEDED ── */}
      {step === 'NEW_COMPANY' && result && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🏢</span>
            <div>
              <h2 className="font-semibold text-gray-900">
                Company not found
              </h2>
              <p className="text-sm text-gray-600 mt-1">{result.message}</p>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium text-gray-700">
              Review and confirm new company details:
            </p>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Company name
              </label>
              <input
                value={newCompanyName}
                onChange={(e) => setNewCompanyName(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2
                           text-sm focus:outline-none focus:ring-2
                           focus:ring-green-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">City</label>
                <input
                  value={newCompanyCity}
                  onChange={(e) => setNewCompanyCity(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2
                             text-sm focus:outline-none focus:ring-2
                             focus:ring-green-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">State</label>
                <input
                  value={newCompanyState}
                  onChange={(e) => setNewCompanyState(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2
                             text-sm focus:outline-none focus:ring-2
                             focus:ring-green-500"
                />
              </div>
            </div>

            <div className="border-t border-gray-100 pt-3">
              <p className="text-sm font-medium text-gray-700 mb-2">
                First facility:
              </p>
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  Facility name
                </label>
                <input
                  value={newFacilityName}
                  onChange={(e) => setNewFacilityName(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2
                             text-sm focus:outline-none focus:ring-2
                             focus:ring-green-500"
                />
              </div>
            </div>
          </div>

          {/* Similar companies */}
          {result.suggestions && result.suggestions.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
              <p className="text-xs text-amber-700 font-medium mb-2">
                Similar companies already in system — is this one of these?
              </p>
              {result.suggestions.map((s) => (
                <button
                  key={s.company_id}
                  onClick={() => confirmAndSave(result, 'CONFIRMED', {
                    company_id: s.company_id,
                    facility_id: null,
                  })}
                  className="w-full text-left px-3 py-2 text-sm text-amber-800
                             hover:bg-amber-100 rounded-md transition-colors"
                >
                  {s.company_name}
                  {s.city && ` — ${s.city}`}
                  <span className="text-xs text-amber-500 ml-2">
                    {Math.round(s.score * 100)}% match
                  </span>
                </button>
              ))}
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-3">
            <button
              onClick={() => confirmAndSave(result, 'CREATE_COMPANY')}
              className="flex-1 bg-green-600 text-white py-2.5 rounded-md
                         font-medium hover:bg-green-700 transition-colors"
            >
              Create company and save
            </button>
            <button
              onClick={reset}
              className="flex-1 border border-red-200 text-red-600 py-2.5
                         rounded-md font-medium hover:bg-red-50 transition-colors"
            >
              This was uploaded by mistake
            </button>
          </div>
        </div>
      )}

      {/* ── STEP: DONE ── */}
      {step === 'DONE' && result && saved && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">

          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <h2 className="font-semibold text-gray-900">
                Document saved successfully
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {result.file_name}
              </p>
            </div>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 gap-3">
            {extracted?.units_consumed_kwh != null && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-xs text-green-600 uppercase tracking-wide
                              font-medium">Units consumed</p>
                <p className="text-2xl font-bold text-green-800 mt-1">
                  {extracted.units_consumed_kwh.toLocaleString('en-IN')}
                </p>
                <p className="text-xs text-green-600 mt-0.5">kWh</p>
              </div>
            )}
            {extracted?.quantity_kl != null && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-xs text-blue-600 uppercase tracking-wide
                              font-medium">Water consumed</p>
                <p className="text-2xl font-bold text-blue-800 mt-1">
                  {extracted.quantity_kl.toLocaleString('en-IN')}
                </p>
                <p className="text-xs text-blue-600 mt-0.5">Kilolitres (KL)</p>
              </div>
            )}
            {extracted?.quantity != null && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <p className="text-xs text-orange-600 uppercase tracking-wide
                              font-medium">Fuel quantity</p>
                <p className="text-2xl font-bold text-orange-800 mt-1">
                  {extracted.quantity.toLocaleString('en-IN')}
                </p>
                <p className="text-xs text-orange-600 mt-0.5">
                  {extracted.quantity_unit_fuel || 'litres'}
                </p>
              </div>
            )}
            {extracted?.billing_period_start && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide
                              font-medium">Billing period</p>
                <p className="text-sm font-semibold text-gray-800 mt-1">
                  {extracted.billing_period_start}
                </p>
                <p className="text-xs text-gray-500">
                  to {extracted.billing_period_end}
                </p>
              </div>
            )}
          </div>

          {/* Emission result */}
          {emission && (
            <div className={`rounded-md p-3 border ${
              emission.scope === 'Scope 2'
                ? 'bg-green-50 border-green-200'
                : 'bg-orange-50 border-orange-200'
            }`}>
              <p className={`text-sm ${
                emission.scope === 'Scope 2'
                  ? 'text-green-700' : 'text-orange-700'
              }`}>
                <span className="font-semibold">{emission.scope}: </span>
                {emission.co2e_tonnes.toFixed(4)} tonnes CO₂e
                <span className="ml-1 opacity-70">
                  ({emission.emission_factor} {emission.ef_unit}
                  — {emission.ef_source})
                </span>
              </p>
            </div>
          )}

          {/* Notes */}
          {extracted?.notes && (
            <div className="bg-gray-50 rounded-md p-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                Notes from Claude
              </p>
              <p className="text-sm text-gray-700">{extracted.notes}</p>
            </div>
          )}

          <button
            onClick={reset}
            className="w-full border border-gray-300 text-gray-700 py-2.5
                       rounded-md font-medium hover:bg-gray-50 transition-colors"
          >
            Upload another document
          </button>
        </div>
      )}

    </div>
  )
}