export const metadata = { title: 'KI_ana – App', description: 'KI_ana Next.js App' };

import './globals.css';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="bg-gray-100 text-gray-900">
        {children}
      </body>
    </html>
  );
}
