import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarOutlined, DeleteOutlined, LeftOutlined, PlusOutlined, RightOutlined, SettingOutlined } from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Drawer,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { api } from '../api'
import DailyLogDrawer from '../components/DailyLogDrawer'
import { PersonCell } from '../components/People'
import { displayName } from '../people'
import {
  EXTRA_KINDS,
  count,
  currentMonth,
  monthBounds,
  monthLabel,
  npr,
  rateAmount,
  shiftMonth,
  todayISO,
} from '../payroll'

const OWN_PAY = 'Only a Super Admin can change your own pay.'

// The rate a new words or hours extra starts from: the person's pay setup.
function ratesFor(pay, kind) {
  return kind === 'hours'
    ? { per_quantity: Number(pay.hours_per_rate), per_amount: Number(pay.hours_rate_amount) }
    : { per_quantity: pay.words_per_rate, per_amount: Number(pay.words_rate_amount) }
}

function RateInputs({ quantityName, amountName, unit }) {
  return (
    <Space.Compact block>
      <Form.Item name={quantityName} noStyle rules={[{ required: true, message: `Enter the ${unit}` }]}>
        <InputNumber min={0.01} style={{ width: '50%' }} suffix={unit} />
      </Form.Item>
      <Form.Item name={amountName} noStyle rules={[{ required: true, message: 'Enter the amount' }]}>
        <InputNumber min={0} style={{ width: '50%' }} prefix="= NPR" />
      </Form.Item>
    </Space.Compact>
  )
}

function PaySetupDrawer({ staff, month, onClose, onSaved }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!staff) return
    const pay = staff.pay
    form.setFieldsValue({
      ...pay,
      monthly_salary: pay.monthly_salary === null ? null : Number(pay.monthly_salary),
      words_rate_amount: Number(pay.words_rate_amount),
      hours_per_rate: Number(pay.hours_per_rate),
      hours_rate_amount: Number(pay.hours_rate_amount),
    })
  }, [staff, form])

  async function handleFinish(values) {
    setBusy(true)
    try {
      const saved = await api.updateStaffPay(staff.id, month, { ...values, note: (values.note || '').trim() })
      message.success(`Pay setup saved for ${displayName(staff)}.`)
      onSaved(saved)
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer
      open={Boolean(staff)}
      onClose={onClose}
      size={480}
      destroyOnHidden
      title={staff ? `Pay setup for ${displayName(staff)}` : ''}
      extra={
        <Button type="primary" loading={busy} onClick={() => form.submit()}>
          Save
        </Button>
      }
    >
      <Form form={form} layout="vertical" requiredMark="optional" onFinish={handleFinish}>
        <Typography.Paragraph type="secondary">
          Every field is optional. The rates are used as the starting point whenever you add a words or hours extra, and
          can still be changed for a single extra.
        </Typography.Paragraph>
        <Form.Item label="Monthly salary" name="monthly_salary" extra="Leave empty if they are paid only for extras.">
          <InputNumber min={0} prefix="NPR" style={{ width: '100%' }} placeholder="Not set" />
        </Form.Item>
        <Form.Item label="Words rate" extra="For example 6,000 words = NPR 1,000, so 3,000 words earns NPR 500." required>
          <RateInputs quantityName="words_per_rate" amountName="words_rate_amount" unit="words" />
        </Form.Item>
        <Form.Item label="Hours rate" extra="For example 8 hours = NPR 1,000." required>
          <RateInputs quantityName="hours_per_rate" amountName="hours_rate_amount" unit="hours" />
        </Form.Item>
        <Form.Item
          label="Daily extras"
          name="daily_extra"
          valuePropName="checked"
          extra="Turn on for people who earn extras day by day. Their Daily log button is highlighted, and single extras default to today's date."
        >
          <Switch />
        </Form.Item>
        <Form.Item label="Note" name="note">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} maxLength={255} placeholder="Bank details, agreement, …" />
        </Form.Item>
      </Form>
    </Drawer>
  )
}

function ExtraModal({ staff, month, onClose, onSaved }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const kind = Form.useWatch('kind', form) ?? 'words'
  const quantity = Form.useWatch('quantity', form)
  const perQuantity = Form.useWatch('per_quantity', form)
  const perAmount = Form.useWatch('per_amount', form)
  const measured = kind === 'words' || kind === 'hours'
  const bounds = monthBounds(month)

  useEffect(() => {
    if (!staff) return
    form.resetFields()
    const today = todayISO()
    const inMonth = today >= bounds.min && today <= bounds.max
    form.setFieldsValue({ kind: 'words', date: staff.pay.daily_extra && inMonth ? today : '', ...ratesFor(staff.pay, 'words') })
  }, [staff, form, bounds.min, bounds.max])

  async function handleFinish(values) {
    setBusy(true)
    const payload = { staff: staff.id, month, kind: values.kind, note: (values.note || '').trim(), date: values.date || null }
    if (measured) Object.assign(payload, { quantity: values.quantity, per_quantity: values.per_quantity, per_amount: values.per_amount })
    else payload.amount = values.amount
    try {
      const saved = await api.addPayExtra(payload)
      message.success(`${npr(saved.amount)} added for ${displayName(staff)}.`)
      onSaved()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const unit = EXTRA_KINDS[kind]?.unit
  const preview = measured ? rateAmount(quantity, perQuantity, perAmount) : null

  return (
    <Modal
      open={Boolean(staff)}
      title={staff ? `Add an extra for ${displayName(staff)} · ${monthLabel(month)}` : ''}
      okText="Add extra"
      confirmLoading={busy}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
      width={560}
    >
      {staff && (
        <Form form={form} layout="vertical" requiredMark="optional" onFinish={handleFinish} style={{ marginTop: 16 }}>
          <Form.Item name="kind" label="Type of extra">
            <Segmented
              block
              options={Object.entries(EXTRA_KINDS).map(([value, k]) => ({ value, label: k.short }))}
              onChange={(next) => form.setFieldsValue(next === 'words' || next === 'hours' ? ratesFor(staff.pay, next) : {})}
            />
          </Form.Item>
          {measured ? (
            <>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item
                    label={kind === 'words' ? 'Words written' : 'Hours worked'}
                    name="quantity"
                    rules={[{ required: true, message: `Enter the ${unit} done` }]}
                  >
                    <InputNumber min={0.01} style={{ width: '100%' }} suffix={unit} autoFocus />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Day" name="date" extra={staff.pay.daily_extra ? 'Daily extras: one per day.' : 'Optional.'}>
                    <Input type="date" min={bounds.min} max={bounds.max} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="Rate" required extra="Starts from this person's pay setup; change it for this extra only if needed.">
                <RateInputs quantityName="per_quantity" amountName="per_amount" unit={unit} />
              </Form.Item>
              <Alert
                type={preview === null ? 'info' : 'success'}
                showIcon
                title={
                  preview === null
                    ? `Enter the ${unit} to see the amount.`
                    : `${count(quantity)} ${unit} × NPR ${count(perAmount)} ÷ ${count(perQuantity)} = ${npr(preview)}`
                }
                style={{ marginBottom: 16 }}
              />
            </>
          ) : (
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item label="Amount" name="amount" rules={[{ required: true, message: 'Enter the amount' }]}>
                  <InputNumber min={0.01} prefix="NPR" style={{ width: '100%' }} autoFocus />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="Day" name="date" extra="Optional.">
                  <Input type="date" min={bounds.min} max={bounds.max} />
                </Form.Item>
              </Col>
            </Row>
          )}
          <Form.Item label="Note" name="note" style={{ marginBottom: 0 }}>
            <Input maxLength={255} placeholder={kind === 'words' ? 'Order or assignment reference' : 'Reason'} />
          </Form.Item>
        </Form>
      )}
    </Modal>
  )
}

function ExtrasList({ extras, locked, onDelete }) {
  if (!extras.length) {
    return <Typography.Text type="secondary">No extras this month.</Typography.Text>
  }
  const columns = [
    {
      title: 'Day',
      key: 'date',
      width: 120,
      render: (_, e) => (e.date ? new Date(`${e.date}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : 'Month'),
    },
    {
      title: 'Type',
      key: 'kind',
      render: (_, e) => (
        <Tag color={EXTRA_KINDS[e.kind].color} variant="filled">
          {EXTRA_KINDS[e.kind].label}
        </Tag>
      ),
    },
    {
      title: 'Details',
      key: 'details',
      render: (_, e) => (
        <div>
          {e.quantity !== null && (
            <div>
              {count(e.quantity)} {EXTRA_KINDS[e.kind].unit} at {count(e.per_quantity)} = {npr(e.per_amount)}
            </div>
          )}
          {e.note && <Typography.Text type="secondary">{e.note}</Typography.Text>}
        </div>
      ),
    },
    { title: 'Amount', key: 'amount', align: 'right', className: 'nowrap', render: (_, e) => <strong>{npr(e.amount)}</strong> },
    {
      title: '',
      key: 'actions',
      width: 48,
      render: (_, e) =>
        locked ? null : (
          <Popconfirm title="Delete this extra?" okText="Delete" okButtonProps={{ danger: true }} onConfirm={() => onDelete(e)}>
            <Button type="text" danger size="small" icon={<DeleteOutlined />} aria-label="Delete extra" />
          </Popconfirm>
        ),
    },
  ]
  return <Table rowKey="id" size="small" columns={columns} dataSource={extras} pagination={false} />
}

export default function Payroll({ user }) {
  const { message } = App.useApp()
  const [month, setMonth] = useState(currentMonth)
  const [staff, setStaff] = useState(null)
  const [extras, setExtras] = useState([])
  const [setup, setSetup] = useState(null)
  const [adding, setAdding] = useState(null)
  const [daily, setDaily] = useState(null)

  const load = useCallback(() => {
    Promise.all([api.payrollStaff(month), api.payrollExtras(month)])
      .then(([s, e]) => {
        setStaff(s.staff)
        setExtras(e)
      })
      .catch((err) => message.error(err.message))
  }, [month, message])

  useEffect(load, [load])

  const extrasByStaff = useMemo(() => {
    const grouped = new Map()
    for (const e of extras) grouped.set(e.staff, [...(grouped.get(e.staff) ?? []), e])
    return grouped
  }, [extras])

  const totals = useMemo(() => {
    const rows = staff ?? []
    const sum = (pick) => rows.reduce((acc, r) => acc + Number(pick(r) || 0), 0)
    return {
      salaries: sum((r) => r.pay.monthly_salary),
      extras: sum((r) => r.extras_total),
      total: sum((r) => r.total),
    }
  }, [staff])

  async function deleteExtra(extra) {
    try {
      await api.deletePayExtra(extra.id)
      message.success('Extra deleted.')
      load()
    } catch (err) {
      message.error(err.message)
    }
  }

  const isOwn = (row) => row.id === user.id && !user.is_super_admin

  const columns = [
    { title: 'Staff', key: 'name', render: (_, r) => <PersonCell person={r} />, sorter: (a, b) => displayName(a).localeCompare(displayName(b)) },
    {
      title: 'Role',
      key: 'role',
      responsive: ['md'],
      render: (_, r) => (
        <Flex vertical gap={4} align="flex-start">
          {r.role}
          {r.pay.daily_extra && <Tag variant="filled" color="cyan">Daily extras</Tag>}
        </Flex>
      ),
    },
    {
      title: 'Monthly salary',
      key: 'salary',
      align: 'right',
      className: 'nowrap',
      render: (_, r) =>
        r.pay.monthly_salary === null ? <Typography.Text type="secondary">Not set</Typography.Text> : npr(r.pay.monthly_salary),
    },
    {
      title: 'Extras',
      key: 'extras',
      align: 'right',
      className: 'nowrap',
      render: (_, r) =>
        r.extras_count ? (
          <Tooltip
            title={Object.entries(r.extras_by_kind)
              .filter(([, v]) => Number(v))
              .map(([k, v]) => `${EXTRA_KINDS[k].short}: ${npr(v)}`)
              .join(' · ')}
          >
            {npr(r.extras_total)} <Typography.Text type="secondary">({r.extras_count})</Typography.Text>
          </Tooltip>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    { title: 'Total', key: 'total', align: 'right', className: 'nowrap', render: (_, r) => <strong>{npr(r.total)}</strong>, sorter: (a, b) => a.total - b.total },
    {
      title: '',
      key: 'actions',
      align: 'right',
      width: 260,
      render: (_, r) => {
        const own = isOwn(r)
        return (
          <Tooltip title={own ? OWN_PAY : undefined}>
            <Space>
              <Button
                size="small"
                type={r.pay.daily_extra ? 'primary' : 'default'}
                ghost={r.pay.daily_extra}
                icon={<CalendarOutlined />}
                disabled={own}
                onClick={() => setDaily(r)}
              >
                Daily log
              </Button>
              <Button size="small" icon={<PlusOutlined />} disabled={own} onClick={() => setAdding(r)}>
                Extra
              </Button>
              <Tooltip title={own ? undefined : 'Pay setup'}>
                <Button size="small" icon={<SettingOutlined />} disabled={own} onClick={() => setSetup(r)} aria-label={`Pay setup for ${displayName(r)}`} />
              </Tooltip>
            </Space>
          </Tooltip>
        )
      },
    },
  ]

  const tiles = [
    { title: 'Staff', value: staff?.length ?? 0, formatter: (v) => v },
    { title: 'Salaries', value: totals.salaries },
    { title: 'Extras', value: totals.extras },
    { title: 'Total payable', value: totals.total },
  ]

  return (
    <Flex vertical gap={20}>
      <Flex justify="space-between" align="flex-end" wrap gap={16}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            Academic Content Writing payroll
          </Typography.Title>
          <Typography.Text type="secondary">
            Monthly salaries plus extras for words, hours, performance and effort. Every amount is optional.
          </Typography.Text>
        </div>
        <Space.Compact>
          <Button icon={<LeftOutlined />} aria-label="Previous month" onClick={() => setMonth((m) => shiftMonth(m, -1))} />
          <Button style={{ minWidth: 170, fontWeight: 600 }} onClick={() => setMonth(currentMonth())}>
            {monthLabel(month)}
          </Button>
          <Button icon={<RightOutlined />} aria-label="Next month" onClick={() => setMonth((m) => shiftMonth(m, 1))} />
        </Space.Compact>
      </Flex>

      <Row gutter={[16, 16]}>
        {tiles.map((t) => (
          <Col key={t.title} xs={12} lg={6}>
            <Card className="stat-card payroll-stat">
              <Statistic title={t.title} value={t.value} formatter={t.formatter ?? ((v) => npr(v))} loading={!staff} />
            </Card>
          </Col>
        ))}
      </Row>

      <Card styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          loading={!staff}
          columns={columns}
          dataSource={staff ?? []}
          pagination={false}
          locale={{ emptyText: 'No active staff in Academic Content Writing yet.' }}
          scroll={{ x: 760 }}
          expandable={{
            expandRowByClick: false,
            rowExpandable: (r) => r.extras_count > 0,
            expandedRowRender: (r) => (
              <ExtrasList extras={extrasByStaff.get(r.id) ?? []} locked={isOwn(r)} onDelete={deleteExtra} />
            ),
          }}
        />
      </Card>

      <PaySetupDrawer
        staff={setup}
        month={month}
        onClose={() => setSetup(null)}
        onSaved={() => {
          setSetup(null)
          load()
        }}
      />
      <DailyLogDrawer
        key={daily ? `${daily.id}-${month}` : 'closed'}
        staff={daily}
        month={month}
        onClose={() => setDaily(null)}
        onSaved={() => {
          setDaily(null)
          load()
        }}
      />
      <ExtraModal
        staff={adding}
        month={month}
        onClose={() => setAdding(null)}
        onSaved={() => {
          setAdding(null)
          load()
        }}
      />
    </Flex>
  )
}
