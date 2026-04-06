import { motion, AnimatePresence } from 'framer-motion'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center"
        >
          <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="relative z-10 w-full max-w-sm rounded-xl p-5"
            style={{
              background: 'var(--surface-container)',
              border: '1px solid var(--outline-variant)',
            }}
          >
            <h3
              className="text-sm font-bold"
              style={{ color: 'var(--on-surface)', fontFamily: 'var(--font-headline)' }}
            >
              {title}
            </h3>
            <p className="mt-2 text-xs" style={{ color: 'var(--on-surface-variant)' }}>
              {message}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={onCancel}
                className="rounded-lg px-3 py-1.5 text-xs font-medium"
                style={{ color: 'var(--on-surface-variant)' }}
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                className="rounded-lg px-3 py-1.5 text-xs font-medium"
                style={{
                  background: danger ? 'var(--error-container)' : 'var(--primary-container)',
                  color: danger ? '#fff' : 'var(--on-primary)',
                }}
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
