import type { Metadata } from "next";
import "../styles/osint-caseops.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSINT CaseOps",
  description: "Local-first OSINT case workbench foundation.",
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
