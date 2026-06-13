# SANGATNA — Project Context

## What we're building
AI-powered ESG measurement platform for Indian MSMEs.
Focuses on energy, water, and emissions tracking with BRSR reporting.

## Tech stack
- Backend: FastAPI + PostgreSQL + SQLAlchemy + Anthropic claude-sonnet-4-6
- Frontend: React + TypeScript + Vite + Tailwind
- Project: ~/code/sangatna/
- GitHub: https://github.com/GayatrideviAI/sangatna

## Database (12 tables)
companies, users, facilities, documents, energy_activities,
water_quantity_records, water_quality_samples, water_quality_readings,
emission_records, reports, utility_connections, production_records,
consultant_clients

## Key business rules
- Indian FY = April 1 to March 31 (e.g. FY 2025-26)
- Grid EF: CEA state-wise factors (Tamil Nadu = 0.82 kg CO2e/kWh)
- Fuel EF: IPCC AR6 (Diesel = 2.68 kg CO2e/litre)
- Compliance: BIS IS:10500 (drinking water), CPCB (effluent)
- Multi-tenancy: consultant manages N MSME clients via X-Client-Company-ID header
- Primary buyer: ESG consultant
- Bill cycle: bi-monthly (6 bills per year per connection)

## Modules built
✅ Auth (JWT), Companies, Facilities
✅ Document upload + Claude extraction (electricity, water, fuel, lab reports)
✅ Smart document matching (auto-maps bills to companies/facilities)
✅ Scope 1 + 2 calculation engines
✅ Water quality compliance checker
✅ Emissions summary endpoint
✅ Utility auto-connect (consumer number registry + gap detection)
✅ Production records
✅ Intelligence: intensity calculator, gap estimator, BRSR readiness

## Next to build
⬜ BRSR Excel report generation
⬜ Emissions dashboard (charts + KPIs)
⬜ Consultant dashboard
⬜ Email ingestion for utility bills
