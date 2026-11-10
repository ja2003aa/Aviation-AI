import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aviation AI · KKIA",
  description:
    "Smart airport assistant for King Khalid International Airport with live flight lookup.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
