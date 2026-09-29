import { initialsFor } from '../../utils/initials'

interface AvatarProps {
  name: string
  avatarUrl?: string | null
  size?: number
}

export function Avatar({ name, avatarUrl, size = 28 }: AvatarProps) {
  const dimension = `${size}px`
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt=""
        width={size}
        height={size}
        style={{ width: dimension, height: dimension }}
        className="rounded-full object-cover"
      />
    )
  }
  return (
    <span
      style={{ width: dimension, height: dimension }}
      className="flex items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent-strong)]"
      aria-hidden="true"
    >
      {initialsFor(name)}
    </span>
  )
}
