import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { clerkAppearance } from "@/lib/clerk-appearance";
import { DEV_MOCK_AUTH } from "@/lib/dev-mode";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "QuotePulse GMC",
  description: "Group Medical Cover quote preparation workbench",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const page = (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
  // Dev mock mode runs without Clerk keys, so there is no ClerkProvider (lib/dev-mode.ts).
  return DEV_MOCK_AUTH ? (
    page
  ) : (
    <ClerkProvider appearance={clerkAppearance}>{page}</ClerkProvider>
  );
}
