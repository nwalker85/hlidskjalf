import type { Metadata } from "next";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hliðskjálf — Odin's High Seat",
  description: "From Hliðskjálf, observe all Nine Realms. Huginn reports. Muninn remembers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gradient-norse">
        <NuqsAdapter>
          <Providers>
            <div className="grid-bg min-h-screen">
              {children}
            </div>
          </Providers>
        </NuqsAdapter>
      </body>
    </html>
  );
}

