import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "E-YAY BrainChain",
  description: "Paper-safe market intelligence system — NO EXECUTION",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className="min-h-screen bg-eyay-bg text-eyay-text antialiased">
        {children}
      </body>
    </html>
  );
}
