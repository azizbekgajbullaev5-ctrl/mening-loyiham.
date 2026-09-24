// Must match backend/app/reporting/plagiarism_report.py SOURCE_COLORS (light text backgrounds).
export const SOURCE_COLORS = ["#fde68a", "#bfdbfe", "#fecaca", "#bbf7d0", "#e9d5ff", "#fed7aa", "#a5f3fc", "#fbcfe8", "#d9f99d", "#c7d2fe", "#fef08a", "#99f6e4"];
export const CITATION_COLOR = "#e5e7eb";
export const colorFor = (idx: number) => (idx >= 0 ? SOURCE_COLORS[idx % SOURCE_COLORS.length] : SOURCE_COLORS[0]);
export const RESULT_COLORS = { originality: "#1f9d55", borrowing: "#e8590c", citation: "#2a78d6" };
