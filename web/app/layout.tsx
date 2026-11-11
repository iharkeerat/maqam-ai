import type { Metadata } from "next";
import "./globals.css";
import "./layout-polish.css";
import "./design-system-v10.5.css";

export const metadata: Metadata = {
  title: "MAQAM AI — Research & Evaluation Edition",
  description: "A neuro-symbolic computational-musicology workbench for Punjabi, Hindi and Urdu poetry, structured semantic analysis, independent Raag and Taal ranking, editable Bhatkhande notation, grammar validation, audio synthesis and a protected 120-record historical Taal observatory, reproducible ML baselines, ablation studies, calibration analysis and expert-review infrastructure.",
  keywords: ["computational musicology", "Hindustani music", "Bhatkhande notation", "Punjabi poetry", "Urdu poetry", "Raag", "Taal"],
};


export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}
