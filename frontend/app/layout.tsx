export const metadata = { title: 'KI_ana', description: 'KI_ana 2.0' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body style={{fontFamily:'Inter, system-ui, Arial', margin:0}}>
        <header style={{padding:'10px 16px', borderBottom:'1px solid #eee'}}>KI_ana</header>
        <main style={{maxWidth:980, margin:'24px auto', padding:'0 16px'}}>{children}</main>
      </body>
    </html>
  );
}
