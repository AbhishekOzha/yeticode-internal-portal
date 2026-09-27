import { useCallback, useEffect, useState } from 'react'
import { BellOutlined, CheckOutlined, CloseOutlined, InfoCircleOutlined, SendOutlined } from '@ant-design/icons'
import {
  Alert,
  App,
  Avatar,
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Skeleton,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { leaveApi } from '../api'
import { PersonAvatar, PersonCell } from '../components/People'
import { displayName } from '../people'
import { todayISO } from '../payroll'
import { canApproveLeave, inTeam } from '../team'

const STATUS = {
  pending: { color: 'gold', label: 'Pending' },
  approved: { color: 'green', label: 'Approved' },
  rejected: { color: 'red', label: 'Rejected' },
  cancelled: { color: 'default', label: 'Cancelled' },
}

function formatDate(iso) {
  return new Date(`${iso}T00:00`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

function dateRange(leave) {
  if (leave.start_date === leave.end_date) return `${formatDate(leave.start_date)}${leave.half_day ? ' · half day' : ''}`
  return `${formatDate(leave.start_date)} – ${formatDate(leave.end_date)}`
}

// "A", "A and B", "A, B and C"
function listNames(names) {
  return new Intl.ListFormat('en', { style: 'long', type: 'conjunction' }).format(names)
}

function days(n) {
  return `${n} day${n === 1 ? '' : 's'}`
}

function StatusTag({ leave }) {
  const s = STATUS[leave.status]
  const tag = (
    <Tag color={s.color} variant="filled" style={{ marginInlineEnd: 0 }}>
      {s.label}
    </Tag>
  )
  if (!leave.decided_by) return tag
  return (
    <Tooltip title={`${s.label} by ${leave.decided_by}${leave.decision_note ? `: “${leave.decision_note}”` : ''}`}>{tag}</Tooltip>
  )
}

function ApplyForm({ approvers, kinds, onApplied }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const start = Form.useWatch('start_date', form)
  const end = Form.useWatch('end_date', form)
  const singleDay = start && end && start === end
  const names = approvers.map((a) => `${displayName(a)} (${a.role})`)
  const notifyText = approvers.length
    ? `${listNames(names)} will be notified automatically.`
    : 'The Production Manager and HR will be notified automatically.'

  async function handleFinish(values) {
    setBusy(true)
    try {
      const saved = await leaveApi.apply({
        ...values,
        half_day: singleDay ? Boolean(values.half_day) : false,
        reason: (values.reason || '').trim(),
      })
      const who = listNames(saved.notified.map((p) => displayName(p)))
      message.success(who ? `Leave requested. ${who} ${saved.notified.length > 1 ? 'have' : 'has'} been notified.` : 'Leave requested.')
      form.resetFields()
      onApplied()
    } catch (err) {
      const data = err.data && !err.data.detail ? err.data : null
      if (data) form.setFields(Object.entries(data).map(([name, errors]) => ({ name, errors: [].concat(errors) })))
      else message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Apply for leave">
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        onFinish={handleFinish}
        initialValues={{ kind: 'casual', start_date: todayISO(), end_date: todayISO(), half_day: false }}
      >
        <Form.Item label="Type" name="kind">
          <Select options={kinds} />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item label="From" name="start_date" rules={[{ required: true, message: 'Pick the first day' }]}>
              <Input
                type="date"
                onChange={(e) => {
                  // Keep the end date from falling before the start.
                  if (!end || e.target.value > end) form.setFieldsValue({ end_date: e.target.value })
                }}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="To" name="end_date" rules={[{ required: true, message: 'Pick the last day' }]}>
              <Input type="date" min={start} />
            </Form.Item>
          </Col>
        </Row>
        {singleDay && (
          <Form.Item label="Half day" name="half_day" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
        <Form.Item label="Reason" name="reason">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} maxLength={1000} placeholder="e.g. Family function, doctor's appointment" />
        </Form.Item>
        <Alert
          type="info"
          showIcon
          icon={<BellOutlined />}
          title={
            <Flex align="center" gap={8} wrap>
              <Avatar.Group size="small" max={{ count: 3 }}>
                {approvers.map((a) => (
                  <PersonAvatar key={a.id} person={a} size={24} />
                ))}
              </Avatar.Group>
              <span>{notifyText}</span>
            </Flex>
          }
          style={{ marginBottom: 16 }}
        />
        <Tooltip title={notifyText}>
          <Button type="primary" htmlType="submit" icon={<SendOutlined />} loading={busy} block>
            Apply for leave
          </Button>
        </Tooltip>
      </Form>
    </Card>
  )
}

function MyLeave() {
  const { message } = App.useApp()
  const [data, setData] = useState(null)

  const load = useCallback(() => {
    leaveApi
      .mine()
      .then(setData)
      .catch((err) => message.error(err.message))
  }, [message])

  useEffect(load, [load])

  async function cancel(leave) {
    try {
      await leaveApi.cancel(leave.id)
      message.success('Leave request cancelled.')
      load()
    } catch (err) {
      message.error(err.message)
    }
  }

  if (!data) return <Skeleton active />

  const columns = [
    { title: 'Dates', key: 'dates', render: (_, l) => dateRange(l) },
    { title: 'Type', dataIndex: 'kind_label', key: 'kind', responsive: ['md'] },
    { title: 'Days', key: 'days', render: (_, l) => days(l.days), className: 'nowrap' },
    { title: 'Status', key: 'status', render: (_, l) => <StatusTag leave={l} /> },
    {
      title: '',
      key: 'actions',
      align: 'right',
      render: (_, l) =>
        l.status === 'pending' ? (
          <Popconfirm title="Cancel this leave request?" okText="Cancel request" cancelText="Keep" onConfirm={() => cancel(l)}>
            <Button size="small" type="text" danger>
              Cancel
            </Button>
          </Popconfirm>
        ) : null,
    },
  ]

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={9}>
        <ApplyForm approvers={data.approvers} kinds={data.kinds} onApplied={load} />
      </Col>
      <Col xs={24} lg={15}>
        <Card title="My requests" styles={{ body: { padding: 0 } }}>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={data.requests}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No leave requests yet." /> }}
            expandable={{
              rowExpandable: (l) => Boolean(l.reason || l.decision_note),
              expandedRowRender: (l) => (
                <Flex vertical gap={4}>
                  {l.reason && <Typography.Text>Reason: {l.reason}</Typography.Text>}
                  {l.decision_note && (
                    <Typography.Text type="secondary">
                      {l.decided_by}: “{l.decision_note}”
                    </Typography.Text>
                  )}
                </Flex>
              ),
            }}
            scroll={{ x: 480 }}
          />
        </Card>
      </Col>
    </Row>
  )
}

function DecideModal({ decision, onClose, onDone }) {
  const { message } = App.useApp()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const leave = decision?.leave
  const approve = decision?.kind === 'approve'

  async function submit() {
    setBusy(true)
    try {
      await leaveApi.decide(leave.id, decision.kind, note.trim())
      message.success(`${displayName(leave.user)}'s leave ${approve ? 'approved' : 'rejected'}. They've been notified.`)
      setNote('')
      onDone()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(decision)}
      title={leave ? `${approve ? 'Approve' : 'Reject'} ${displayName(leave.user)}'s leave` : ''}
      okText={approve ? 'Approve' : 'Reject'}
      okButtonProps={{ danger: !approve, icon: approve ? <CheckOutlined /> : <CloseOutlined /> }}
      confirmLoading={busy}
      onOk={submit}
      onCancel={() => {
        setNote('')
        onClose()
      }}
      destroyOnHidden
    >
      {leave && (
        <Flex vertical gap={12} style={{ marginTop: 12 }}>
          <Typography.Text>
            {leave.kind_label} · {dateRange(leave)} · {days(leave.days)}
          </Typography.Text>
          {leave.reason && <Typography.Text type="secondary">“{leave.reason}”</Typography.Text>}
          <Input.TextArea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            autoSize={{ minRows: 2, maxRows: 4 }}
            maxLength={500}
            placeholder={approve ? 'Note (optional)' : 'Reason for rejecting (optional, they will see it)'}
          />
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            <InfoCircleOutlined /> {displayName(leave.user)} will be notified of your decision.
          </Typography.Text>
        </Flex>
      )}
    </Modal>
  )
}

function TeamRequests({ onPending }) {
  const { message } = App.useApp()
  const [status, setStatus] = useState('pending')
  const [data, setData] = useState(null)
  const [decision, setDecision] = useState(null)

  const load = useCallback(() => {
    leaveApi
      .team(status)
      .then((d) => {
        setData(d)
        onPending(d.pending)
      })
      .catch((err) => message.error(err.message))
  }, [status, message, onPending])

  useEffect(load, [load])

  const columns = [
    { title: 'Person', key: 'person', render: (_, l) => <PersonCell person={l.user} /> },
    { title: 'Dates', key: 'dates', render: (_, l) => dateRange(l) },
    { title: 'Type', dataIndex: 'kind_label', key: 'kind', responsive: ['lg'] },
    { title: 'Days', key: 'days', render: (_, l) => days(l.days), className: 'nowrap' },
    {
      title: 'Reason',
      key: 'reason',
      responsive: ['md'],
      render: (_, l) =>
        l.reason ? (
          <Typography.Paragraph ellipsis={{ rows: 2, tooltip: l.reason }} style={{ margin: 0, maxWidth: 260 }}>
            {l.reason}
          </Typography.Paragraph>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: '',
      key: 'actions',
      align: 'right',
      render: (_, l) =>
        l.can_decide ? (
          <Flex gap={8} justify="flex-end">
            <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => setDecision({ leave: l, kind: 'approve' })}>
              Approve
            </Button>
            <Button size="small" danger icon={<CloseOutlined />} onClick={() => setDecision({ leave: l, kind: 'reject' })}>
              Reject
            </Button>
          </Flex>
        ) : (
          <StatusTag leave={l} />
        ),
    },
  ]

  return (
    <Flex vertical gap={16}>
      <Segmented
        value={status}
        onChange={setStatus}
        options={[
          { label: `Waiting for a decision${data ? ` (${data.pending})` : ''}`, value: 'pending' },
          { label: 'All requests', value: 'all' },
        ]}
        style={{ alignSelf: 'flex-start' }}
      />
      <Card styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          loading={!data}
          columns={columns}
          dataSource={data?.requests ?? []}
          pagination={{ pageSize: 15, hideOnSinglePage: true }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={status === 'pending' ? 'Nothing waiting for a decision.' : 'No leave requests yet.'}
              />
            ),
          }}
          scroll={{ x: 640 }}
        />
      </Card>
      <DecideModal
        decision={decision}
        onClose={() => setDecision(null)}
        onDone={() => {
          setDecision(null)
          load()
        }}
      />
    </Flex>
  )
}

export default function Leave({ user }) {
  const member = inTeam(user)
  const approver = canApproveLeave(user)
  const [pending, setPending] = useState(0)
  const [chosenTab, setTab] = useState(null)
  // Approvers land on the requests waiting for them; everyone else on their own leave.
  const tab = chosenTab ?? (approver && (pending > 0 || !member) ? 'requests' : 'mine')

  // Load the pending count for the tab badge even before the tab is opened.
  useEffect(() => {
    if (approver) leaveApi.team('pending').then((d) => setPending(d.pending)).catch(() => {})
  }, [approver])

  const tabs = [
    member && { key: 'mine', label: 'My leave', children: <MyLeave /> },
    approver && {
      key: 'requests',
      label: (
        <Flex align="center" gap={8}>
          Team requests
          <Badge count={pending} size="small" />
        </Flex>
      ),
      children: <TeamRequests onPending={setPending} />,
    },
  ].filter(Boolean)

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Leave
        </Typography.Title>
        <Typography.Text type="secondary">
          Leave for the Academic Content Writing team. Requests go to the Production Manager and HR, who approve or
          reject them.
        </Typography.Text>
      </div>
      {tabs.length === 1 ? tabs[0].children : <Tabs activeKey={tab} onChange={setTab} items={tabs} />}
    </Flex>
  )
}
