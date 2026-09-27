import { Avatar, Flex, Tag, Typography } from 'antd'
import { unitColor } from '../colors'
import { colorFor, displayName, initials } from '../people'

export function PersonAvatar({ person, size = 36 }) {
  const name = displayName(person)
  return (
    <Avatar
      size={size}
      src={person.avatar || undefined}
      alt={name}
      style={{ background: person.avatar ? undefined : colorFor(name), fontWeight: 600, flexShrink: 0 }}
    >
      {initials(name)}
    </Avatar>
  )
}

// Name with email underneath. The username is only shown when it isn't the email.
export function PersonCell({ person, muted = false }) {
  const name = displayName(person)
  const secondary = person.email || (person.username !== name ? person.username : '')
  return (
    <Flex align="center" gap={12} style={{ minWidth: 0 }}>
      <PersonAvatar person={person} />
      <div style={{ minWidth: 0 }}>
        <Typography.Text strong type={muted ? 'secondary' : undefined} ellipsis style={{ display: 'block' }}>
          {name}
        </Typography.Text>
        {secondary && secondary !== name && (
          <Typography.Text type="secondary" ellipsis style={{ fontSize: 13, display: 'block' }}>
            {secondary}
          </Typography.Text>
        )}
      </div>
    </Flex>
  )
}

export function UnitTag({ code, name }) {
  return (
    <Tag color={unitColor(code).tag} variant="filled" style={{ marginInlineEnd: 0 }}>
      {name}
    </Tag>
  )
}
