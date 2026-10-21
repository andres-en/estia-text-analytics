import { Navigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { ShieldCheck } from 'lucide-react'
import { GOOGLE_LOGIN_URL } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { fadeIn, materialize, springDrawer, springSettle } from '../lib/motionPresets'

const FEATURES = [
  'Classify WhatsApp conversations with rules and AI',
  'Real-time dashboard and trends',
  'Export full reports to Excel',
]

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.68-3.87 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33Z" />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97L3.95 7.3C4.66 5.17 6.65 3.58 9 3.58Z"
      />
    </svg>
  )
}

export default function LoginPage() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (user) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen flex bg-bg">
      {/* Panel de marca — oculto en pantallas chicas, donde el logo compacto de
          la tarjeta de login (abajo) ya cubre la identidad de marca. */}
      <div className="hidden lg:flex relative flex-1 items-center justify-center overflow-hidden border-r border-line-soft px-16">
        <div aria-hidden className="absolute -top-28 -left-28 w-[28rem] h-[28rem] rounded-full bg-[#1baf7a]/15 blur-3xl" />
        <div aria-hidden className="absolute -bottom-40 -right-24 w-[30rem] h-[30rem] rounded-full bg-[#2a78d6]/15 blur-3xl" />
        <div aria-hidden className="absolute top-1/3 -right-20 w-72 h-72 rounded-full bg-[#22d3ee]/10 blur-3xl" />
        <div aria-hidden className="absolute bottom-16 left-8 w-64 h-64 rounded-full bg-[#1baf7a]/10 blur-3xl" />

        <motion.div
          initial={fadeIn.initial}
          animate={fadeIn.animate}
          transition={springSettle}
          className="relative max-w-lg text-center flex flex-col items-center"
        >
          <img src="/logo-estia.png" alt="ESTIA — Conversation Intelligence" className="w-96 mb-10" />
          <p className="text-xl text-ink-2 leading-relaxed mb-10">
            Classify and analyze WhatsApp conversations with AI — rules and language models working
            together to understand your customers.
          </p>
          <ul className="space-y-4 flex flex-col items-center">
            {FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-3 text-base text-ink">
                <span className="w-5 h-5 rounded-full border-2 border-accent flex items-center justify-center shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                </span>
                {f}
              </li>
            ))}
          </ul>
        </motion.div>
      </div>

      {/* Panel de login */}
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <motion.div
          initial={materialize.initial}
          animate={materialize.animate}
          transition={springDrawer}
          className="w-full max-w-sm"
        >
          <img src="/logo-estia-icon.png" alt="ESTIA" className="w-12 h-12 mx-auto mb-6 lg:hidden" />
          <h1 className="text-2xl font-semibold tracking-tight text-ink mb-1">Welcome</h1>
          <p className="text-sm text-ink-2 mb-6">Sign in with your Google account to continue.</p>

          <div className="surface p-5">
            <div className="flex items-start gap-2.5 bg-accent-soft border border-accent/15 rounded-lg p-3 text-xs text-ink-2 mb-4">
              <ShieldCheck size={15} className="text-accent shrink-0 mt-0.5" />
              Access is limited to emails pre-approved by an administrator.
            </div>

            <a
              href={GOOGLE_LOGIN_URL}
              className="w-full flex items-center justify-center gap-2.5 border border-line rounded-full py-2.5 text-sm font-medium text-ink bg-surface hover:bg-bg hover:border-ink-3 transition-colors"
            >
              <GoogleIcon />
              Sign in with Google
            </a>
          </div>

          <p className="text-xs text-ink-3 mt-6 text-center">Trouble signing in? Contact your administrator.</p>
        </motion.div>
      </div>
    </div>
  )
}
