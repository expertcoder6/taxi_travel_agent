import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Acme Mobility AI | Corporate Ride Booking & Fleet Operations",
  description:
    "AI-Powered corporate ride booking platform with real-time Voice Call, SMS/WhatsApp channels, and Model Context Protocol (MCP) tool orchestration.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
