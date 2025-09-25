import './globals.css'
import { ToasterProvider } from './_components/ui/toaster'

export const metadata = {
  title: "Forgent Checklist 2",
  description: "Generate a checklist from PDFs with AI",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: 'ui-sans-serif, system-ui' }}>
        <ToasterProvider>
          {children}
        </ToasterProvider>
      </body>
    </html>
  )
}
