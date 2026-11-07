import "./globals.css";
import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { Sidebar } from "@/components/sidebar";

export const metadata: Metadata = {
  title: "Predictive DevOps Intelligence Platform",
  description: "Operational memory, root cause synthesis, and pre-deployment predictive intelligence.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground flex flex-col min-h-screen">
        <Navbar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-background via-card/10 to-background">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
