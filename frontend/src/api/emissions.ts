import api from './client'

export interface EmissionRecord {
  id:              string
  facility_id:     string
  source_type:     string
  scope:           string
  activity_data:   number
  activity_unit:   string
  emission_factor: number
  ef_source:       string
  ef_unit:         string
  co2e_kg:         number
  co2e_tonnes:     number
  period_start:    string
  period_end:      string
}

export interface EmissionRecordList {
  items:     EmissionRecord[]
  total:     number
  page:      number
  page_size: number
  pages:     number
}

export async function getEmissionByDocument(
  documentId: string,
): Promise<EmissionRecord | null> {
  try {
    const { data } = await api.get<EmissionRecord>(
      `/emissions/by-document/${documentId}`
    )
    return data
  } catch {
    return null
  }
}

export async function getLatestEmission(
  facilityId: string,
  scope: string,
): Promise<EmissionRecord | null> {
  try {
    const { data } = await api.get<EmissionRecordList>(
      `/emissions/?facility_id=${facilityId}&scope=${encodeURIComponent(scope)}&page_size=1`
    )
    return data.items[0] ?? null
  } catch {
    return null
  }
}

export async function getEmissionsSummary(
  periodStart: string,
  periodEnd: string,
  financialYear: string,
) {
  const { data } = await api.get(
    `/emissions/summary?period_start=${periodStart}&period_end=${periodEnd}&financial_year=${financialYear}`
  )
  return data
}