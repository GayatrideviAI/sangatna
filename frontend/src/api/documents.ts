import api from './client'

export type DocumentType =
  | 'ELECTRICITY_BILL'
  | 'FUEL_RECEIPT'
  | 'WATER_BILL'
  | 'WATER_QUALITY_REPORT'
  | 'GENERATOR_LOG'
  | 'OTHER'

export interface UploadedDocument {
  id: string
  company_id: string
  facility_id: string | null
  document_type: DocumentType
  original_filename: string
  file_size_bytes: number
  status: 'UPLOADED' | 'PROCESSING' | 'EXTRACTED' | 'FAILED'
  extracted_data: string | null
  error_message: string | null
  created_at: string
}
export interface ExtractedBillData {
  // Common
  billing_period_start: string | null
  billing_period_end:   string | null
  amount_paid_inr:      number | null
  state:                string | null
  notes:                string | null
  document_type:        string | null

  // Electricity
  utility_name:         string | null
  account_number:       string | null
  consumer_name:        string | null
  units_consumed_kwh:   number | null
  meter_number:         string | null
  tariff_category:      string | null
  sanctioned_load_kw:   number | null
  supply_voltage:       string | null

  // Water quantity
  quantity_kl:          number | null
  quantity_unit:        string | null
  water_source:         string | null
  water_category:       string | null
  supply_type:          string | null
  utility_provider:     string | null

  // Fuel
  supplier_name:        string | null
  invoice_number:       string | null
  purchase_date:        string | null
  fuel_type:            string | null
  quantity:             number | null
  quantity_litres:      number | null
  quantity_unit_fuel:   string | null
  rate_per_unit:        number | null
  vehicle_number:       string | null
  equipment_id:         string | null

  // Water quality
  lab_name:             string | null
  lab_report_ref:       string | null
  collection_date:      string | null
  water_type:           string | null
  location_desc:        string | null
  readings:             WaterQualityReading[] | null
}

export interface WaterQualityReading {
  parameter_name:  string
  measured_value:  number | null
  unit:            string | null
  category:        string | null
}

export async function uploadDocument(
  file: File,
  documentType: DocumentType,
  facilityId?: string,
): Promise<UploadedDocument> {
  const form = new FormData()
  form.append('file', file)
  form.append('document_type', documentType)
  if (facilityId) form.append('facility_id', facilityId)

  const { data } = await api.post<UploadedDocument>('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function listDocuments(): Promise<UploadedDocument[]> {
  const { data } = await api.get<UploadedDocument[]>('/documents/')
  return data
}

export async function reExtract(documentId: string): Promise<UploadedDocument> {
  const { data } = await api.post<UploadedDocument>(
    `/documents/${documentId}/extract`
  )
  return data
}

export interface SmartUploadResult {
  file_key:          string
  file_name:         string
  file_size_bytes:   number
  mime_type:         string
  document_type:     string
  extracted:         ExtractedBillData
  match_type:        'EXACT' | 'FUZZY' | 'NO_MATCH'
  confidence:        number
  action:            'AUTO_MAPPED' | 'CONFIRM_MATCH' |
                     'NEW_FACILITY_NEEDED' | 'NEW_COMPANY_NEEDED'
  message:           string
  company_id:        string | null
  company_name:      string | null
  facility_id:       string | null
  facility_name:     string | null
  extracted_name:    string
  extracted_address: string
  extracted_city:    string
  extracted_state:   string
  suggested_company?: {
    name: string; city: string; state: string; address: string
  }
  suggested_facility?: {
    name: string; city: string; state: string; address: string
  }
  suggestions?: {
    company_id: string; company_name: string
    city: string; state: string; score: number
  }[]
}

export async function smartUpload(
  file: File,
  documentType: DocumentType,
): Promise<SmartUploadResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('document_type', documentType)
  const { data } = await api.post<SmartUploadResult>(
    '/documents/smart-upload', form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return data
}

export async function smartUploadConfirm(payload: {
  file_key:        string
  file_name:       string
  file_size_bytes: number
  mime_type:       string
  document_type:   string
  extracted:       ExtractedBillData
  action:          'CONFIRMED' | 'CREATE_FACILITY' | 'CREATE_COMPANY'
  company_id:      string | null
  facility_id:     string | null
  new_facility?: { name: string; city: string; state: string; address: string }
  new_company?:  { name: string; city: string; state: string }
}): Promise<{ document_id: string; company_id: string; facility_id: string }> {
  const { data } = await api.post('/documents/smart-upload/confirm', payload)
  return data
}