/** Query-parameter routes so the UI can be statically exported (served by the backend). */
export const analysisHref = (id: string) => `/analysis/?id=${encodeURIComponent(id)}`;
export const structureHref = (documentId: string, analysisId?: string) =>
  `/structure/?id=${encodeURIComponent(documentId)}${analysisId ? `&analysis=${encodeURIComponent(analysisId)}` : ""}`;
