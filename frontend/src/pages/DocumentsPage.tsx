import { useEffect, useState } from 'react'
import { listDocuments } from '../api/documents'
import type { UploadedDocument } from '../api/documents'
import { useNavigate } from 'react-router-dom'

export default function DocumentsPage() {
  const [docs, setDocs]     = useState<UploadedDocument[]>([])
  const [loading, setLoading] = useState(true)
  const navigate            = useNavigate()

  useEffect(() => {
    listDocuments()
      .then(setDocs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Documents</h1>
        <button
          onClick={() => navigate('/upload')}
          className="bg-green-600 text-white px-4 py-2 rounded-md text-sm
                     font-medium hover:bg-green-700 transition-colors"
        >
          Upload new
        </button>
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Loading documents…</p>
      )}

      {!loading && docs.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-8
                        text-center">
          <p className="text-gray-500">No documents uploaded yet.</p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-3 text-green-600 text-sm underline"
          >
            Upload your first bill
          </button>
        </div>
      )}

      <div className="space-y-3">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="bg-white border border-gray-200 rounded-lg px-5 py-4
                       flex items-center justify-between"
          >
            <div>
              <p className="text-sm font-medium text-gray-800">
                {doc.original_filename}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {doc.document_type.replace(/_/g, ' ')} —{' '}
                {new Date(doc.created_at).toLocaleDateString('en-IN')}
              </p>
            </div>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
              doc.status === 'EXTRACTED'
                ? 'bg-green-100 text-green-700'
                : doc.status === 'FAILED'
                ? 'bg-red-100 text-red-700'
                : 'bg-yellow-100 text-yellow-700'
            }`}>
              {doc.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}