import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AutoAuth Agent | Autonomous Prior Authorization",
  description: "AI-powered autonomous prior authorization platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="flex h-screen">
          <Sidebar />
          <div className="flex-1 flex flex-col min-h-0">
            <Header />
            <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}