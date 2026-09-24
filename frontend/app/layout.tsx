import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Akademik AI va o'xshashlik tahlilchisi",
  description: "Akademik hujjatlarni AI-ehtimollik, o'xshashlik va akademik yozuv sifati bo'yicha tahlil qilish",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
