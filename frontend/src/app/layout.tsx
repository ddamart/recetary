import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Recetary",
  description: "Recetario personal",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <header className="border-b border-border bg-card sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <Link href="/" className="font-semibold tracking-tight text-lg">
              <span className="text-accent">🍳</span> Recetary
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link
                href="/add"
                className="px-3 py-1.5 rounded-md border border-border hover:bg-accent-soft hover:border-accent transition"
              >
                + Añadir
              </Link>
              <Link
                href="/random"
                className="px-3 py-1.5 rounded-md bg-accent text-white hover:opacity-90 transition"
              >
                🎲 Random
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-8">
          {children}
        </main>
        <footer className="text-center text-xs text-muted py-6 border-t border-border">
          Recetary · personal recipe collection
        </footer>
      </body>
    </html>
  );
}
