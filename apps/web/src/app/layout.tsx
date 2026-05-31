import type { Metadata } from "next";
import "../styles/osint-caseops.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fraud Monitor",
  description: "Local-first fraud keyword monitoring dashboard.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}
