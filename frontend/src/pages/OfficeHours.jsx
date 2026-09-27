import { useCallback, useEffect, useState } from 'react'
import { BellOutlined, ClockCircleOutlined, EditOutlined } from '@ant-design/icons'
import { App, Button, Card, Checkbox, Col, Flex, Form, Input, Modal, Row, Segmented, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import { teamApi } from '../api'
import { PersonCell } from '../components/People'
import { displayName } from '../people'
import { DEFAULT_WORK_DAYS, SHIFT_PRESETS, WEEKDAYS, daysLabel, shiftLabel } from '../team'

const CUSTOM = 'custom'

function presetFor(start, end) {
  return SHIFT_PRESETS.find((p) => p.start === start && p.end === end)?.key ?? CUSTOM
}

function ShiftModal({ staff, onClose, onSaved }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const start = Form.useWatch('start_time', form)
  const end = Form.useWatch('end_time', form)

  useEffect(() => {
    if (!staff) return
    const hours = staff.office_hours
    form.setFieldsValue(
      hours
        ? { start_time: hours.start_time, end_time: hours.end_time, work_days: hours.work_days, reminders: hours.reminders }
        : { start_time: '09:00', end_time: '17:00', work_days: DEFAULT_WORK_DAYS, reminders: true },
    )
  }, [staff, form])

  async function handleFinish(values) {
    setBusy(true)
    try {
      await teamApi.saveOfficeHours(staff.id, values)
      message.success(`Office hours saved for ${displayName(staff)}.`)
      onSaved()
    } catch (err) {
      const data = err.data && !err.data.detail ? err.data : null
      if (data) form.setFields(Object.entries(data).map(([name, errors]) => ({ name, errors: [].concat(errors) })))
      else message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const preset = start && end ? presetFor(start, end) : CUSTOM

  return (
    <Modal
      open={Boolean(staff)}
      title={staff ? `Office hours for ${displayName(staff)}` : ''}
      okText="Save"
      confirmLoading={busy}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
      width={520}
    >
      <Form form={form} layout="vertical" onFinish={handleFinish} style={{ marginTop: 16 }}>
        <Form.Item label="Shift">
          <Segmented
            block
            value={preset}
            options={[...SHIFT_PRESETS.map((p) => ({ value: p.key, label: p.label })), { value: CUSTOM, label: 'Custom' }]}
            onChange={(key) => {
              const p = SHIFT_PRESETS.find((x) => x.key === key)
              if (p) form.setFieldsValue({ start_time: p.start, end_time: p.end })
            }}
          />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item label="Starts" name="start_time" rules={[{ required: true, message: 'Pick a start time' }]}>
              <Input type="time" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="Ends (log-out time)" name="end_time" rules={[{ required: true, message: 'Pick an end time' }]}>
              <Input type="time" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item label="Work days" name="work_days" rules={[{ required: true, message: 'Pick at least one day' }]}>
          <Checkbox.Group options={WEEKDAYS} />
        </Form.Item>
        <Form.Item
          label="Reminders"
          name="reminders"
          valuePropName="checked"
          extra="30, 15 and 5 minutes before the shift starts, and 5 minutes before log-out time, while they have the app open."
          style={{ marginBottom: 0 }}
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default function OfficeHours({ user }) {
  const { message, modal } = App.useApp()
  const [staff, setStaff] = useState(null)
  const [editing, setEditing] = useState(null)

  const load = useCallback(() => {
    teamApi
      .officeHours()
      .then((data) => setStaff(data.staff))
      .catch((err) => message.error(err.message))
  }, [message])

  useEffect(load, [load])

  function confirmClear(row) {
    modal.confirm({
      title: `Clear office hours for ${displayName(row)}?`,
      content: 'They will stop getting shift reminders.',
      okText: 'Clear',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await teamApi.clearOfficeHours(row.id)
          load()
        } catch (err) {
          message.error(err.message)
        }
      },
    })
  }

  const columns = [
    { title: 'Staff', key: 'name', render: (_, r) => <PersonCell person={r} /> },
    { title: 'Role', dataIndex: 'role', key: 'role', responsive: ['md'] },
    {
      title: 'Shift',
      key: 'shift',
      className: 'nowrap',
      render: (_, r) =>
        r.office_hours ? (
          <Flex align="center" gap={6}>
            <ClockCircleOutlined />
            <strong>{shiftLabel(r.office_hours)}</strong>
          </Flex>
        ) : (
          <Typography.Text type="secondary">Not set</Typography.Text>
        ),
    },
    {
      title: 'Days',
      key: 'days',
      responsive: ['lg'],
      render: (_, r) => (r.office_hours ? daysLabel(r.office_hours.work_days) : null),
    },
    {
      title: 'Reminders',
      key: 'reminders',
      responsive: ['md'],
      render: (_, r) =>
        r.office_hours ? (
          r.office_hours.reminders ? (
            <Tag icon={<BellOutlined />} color="blue" variant="filled">On</Tag>
          ) : (
            <Tag variant="filled">Off</Tag>
          )
        ) : null,
    },
    {
      title: '',
      key: 'actions',
      align: 'right',
      width: 170,
      render: (_, r) => {
        const own = r.id === user.id && !user.is_super_admin
        return (
          <Tooltip title={own ? 'Your own office hours are set by someone else.' : undefined}>
            <Flex gap={8} justify="flex-end">
              <Button size="small" icon={<EditOutlined />} disabled={own} onClick={() => setEditing(r)}>
                {r.office_hours ? 'Edit' : 'Set hours'}
              </Button>
              {r.office_hours && (
                <Button size="small" type="text" danger disabled={own} onClick={() => confirmClear(r)}>
                  Clear
                </Button>
              )}
            </Flex>
          </Tooltip>
        )
      },
    },
  ]

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Office hours
        </Typography.Title>
        <Typography.Text type="secondary">
          Each Academic Content Writing staff member's shift. They are reminded 30, 15 and 5 minutes before it starts and 5
          minutes before log-out time.
        </Typography.Text>
      </div>
      <Card styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          loading={!staff}
          columns={columns}
          dataSource={staff ?? []}
          pagination={false}
          locale={{ emptyText: 'No active staff in Academic Content Writing yet.' }}
          scroll={{ x: 640 }}
        />
      </Card>
      <ShiftModal
        staff={editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          load()
        }}
      />
    </Flex>
  )
}
