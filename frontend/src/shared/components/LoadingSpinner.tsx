interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingSpinner({ size = 'md' }: LoadingSpinnerProps) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  return (
    <div className="flex items-center justify-center">
      <div className={`${sizes[size]} animate-spin rounded-full border-2 border-gray-300 border-t-blue-600`} />
    </div>
  )
}

interface LoadingOverlayProps {
  message?: string
}

export function LoadingOverlay({ message = 'Loading...' }: LoadingOverlayProps) {
  return (
    <div className="absolute inset-0 bg-white/80 flex flex-col items-center justify-center z-10">
      <LoadingSpinner size="lg" />
      {message && (
        <p className="mt-4 text-sm text-gray-600">{message}</p>
      )}
    </div>
  )
}