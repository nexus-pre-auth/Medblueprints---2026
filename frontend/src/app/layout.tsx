import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedBlueprints — AI Regulatory Intelligence",
  description: "AI-powered compliance analysis for healthcare facility blueprints",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
