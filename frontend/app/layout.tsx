import type { Metadata } from "next";
import { Host_Grotesk } from "next/font/google";
import { GeistPixelSquare } from "geist/font/pixel";
import "./globals.css";

const hostGrotesk = Host_Grotesk({
  variable: "--font-host-grotesk",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GateKeep Health",
  description:
    "Clinical access management — credential, monitor, and offboard healthcare staff across every connected system.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${hostGrotesk.variable} ${GeistPixelSquare.variable} h-full`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
