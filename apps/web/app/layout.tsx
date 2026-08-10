import type { Metadata } from "next";
import { Geist_Mono, Source_Sans_3 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DocForge AI",
  description: "Upload invoice PDFs, extract fields, review, and export.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${sourceSans.variable} ${geistMono.variable} antialiased`}>
        <div className="min-h-screen">
          <header className="border-b border-[var(--border)] bg-[var(--panel)]">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
              <Link href="/" className="text-lg font-semibold tracking-tight">
                DocForge AI
              </Link>
              <span className="text-sm text-[var(--muted)]">v0.1 invoice extraction</span>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
