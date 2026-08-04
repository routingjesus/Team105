import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dataset Creation Wizard — Team105",
  description: "Generate import-ready DirectRoute datasets through a guided wizard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="container">
            <span className="brand">Team105 · Dataset Creation Wizard</span>
          </div>
        </header>
        <main id="main" className="container">
          {children}
        </main>
      </body>
    </html>
  );
}
