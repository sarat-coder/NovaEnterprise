import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NovaEnterprise — Knowledge & Decision Intelligence",
  description: "Enterprise research platform powered by Vector RAG, Graph RAG, and SQL retrieval.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
