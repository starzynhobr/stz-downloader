import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Stroke({ size = 16, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const LogoMark = (p: IconProps) => (
  <Stroke strokeWidth={2.5} {...p}>
    <path d="M12 4v12" />
    <path d="M6 11l6 6 6-6" />
    <path d="M5 20h14" />
  </Stroke>
)
export const ListIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Stroke>
)
export const DownIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M12 4v12" />
    <path d="M6 11l6 6 6-6" />
  </Stroke>
)
export const ClockIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 8v4l3 2" />
  </Stroke>
)
export const CheckIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M5 12l5 5 9-10" />
  </Stroke>
)
export const AlertIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 8v5M12 16h.01" />
  </Stroke>
)
export const GearIcon = (p: IconProps) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </Stroke>
)
export const LinkIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" />
    <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  </Stroke>
)
export const PauseIcon = (p: IconProps) => (
  <svg width={p.size ?? 14} height={p.size ?? 14} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <rect x="6" y="5" width="4" height="14" rx="1" />
    <rect x="14" y="5" width="4" height="14" rx="1" />
  </svg>
)
export const PlayIcon = (p: IconProps) => (
  <svg width={p.size ?? 14} height={p.size ?? 14} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M7 5l12 7-12 7z" />
  </svg>
)
export const FolderIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M3 7h6l2 2h10v10H3z" />
  </Stroke>
)
export const OpenIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M14 4h6v6" />
    <path d="M20 4l-9 9" />
    <path d="M18 14v5H5V6h5" />
  </Stroke>
)
export const CloseIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Stroke>
)
export const GaugeIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M4 16a8 8 0 1 1 16 0" />
    <path d="M12 16l4-5" />
  </Stroke>
)
export const RetryIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M20 11a8 8 0 1 0-2.3 5.7" />
    <path d="M20 5v6h-6" />
  </Stroke>
)
export const BackIcon = (p: IconProps) => (
  <Stroke {...p}>
    <path d="M15 6l-6 6 6 6" />
  </Stroke>
)
