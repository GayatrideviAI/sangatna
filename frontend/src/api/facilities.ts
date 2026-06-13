import api from './client'

export interface Facility {
  id: string
  name: string
  facility_type: string
  city: string | null
  state: string
}

export async function listFacilities(): Promise<Facility[]> {
  const { data } = await api.get<{ items: Facility[] }>('/facilities/')
  return data.items
}
