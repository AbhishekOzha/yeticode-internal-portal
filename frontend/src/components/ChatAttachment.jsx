import {
  DownloadOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FileZipOutlined,
} from '@ant-design/icons'
import { Flex, Typography } from 'antd'
import { formatBytes } from '../team'

const ICONS = [
  [/\.(docx?|odt|rtf)$/i, FileWordOutlined, '#2b579a'],
  [/\.(xlsx?|ods|csv)$/i, FileExcelOutlined, '#217346'],
  [/\.(pptx?|odp)$/i, FilePptOutlined, '#d24726'],
  [/\.pdf$/i, FilePdfOutlined, '#e03131'],
  [/\.(zip|rar|7z)$/i, FileZipOutlined, '#8b3fd9'],
  [/\.(txt|md)$/i, FileTextOutlined, '#64748b'],
  [/\.(png|jpe?g|gif|webp)$/i, FileImageOutlined, '#0b7285'],
]

function iconFor(name) {
  const match = ICONS.find(([pattern]) => pattern.test(name))
  return match ? [match[1], match[2]] : [FileOutlined, '#64748b']
}

// A shared file in a chat bubble: images as a preview, everything else as a download card.
export function ChatAttachment({ file, mine }) {
  if (file.is_image) {
    return (
      <a href={file.url} target="_blank" rel="noreferrer" title={`Open ${file.name}`}>
        <img src={file.url} alt={file.name} className="chat-image" loading="lazy" />
      </a>
    )
  }
  const [Icon, color] = iconFor(file.name)
  return (
    <a href={`${file.url}?download=1`} className={`chat-file ${mine ? 'mine' : ''}`} download={file.name}>
      <span className="chat-file-icon" style={{ color: mine ? '#fff' : color }}>
        <Icon />
      </span>
      <Flex vertical style={{ minWidth: 0, flex: 1 }}>
        <Typography.Text ellipsis strong style={{ color: 'inherit' }}>
          {file.name}
        </Typography.Text>
        <span style={{ fontSize: 12, opacity: 0.7 }}>{formatBytes(file.size)}</span>
      </Flex>
      <DownloadOutlined style={{ opacity: 0.8 }} />
    </a>
  )
}
