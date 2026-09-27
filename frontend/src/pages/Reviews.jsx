import { useCallback, useEffect, useState } from 'react'
import { EditOutlined, LeftOutlined, LockOutlined, RightOutlined, SearchOutlined, StarFilled } from '@ant-design/icons'
import { App, Button, Card, Col, Empty, Flex, Form, Input, Modal, Rate, Row, Skeleton, Space, Table, Tabs, Typography } from 'antd'
import { teamApi } from '../api'
import { PersonAvatar, PersonCell } from '../components/People'
import { displayName } from '../people'
import { currentMonth, monthLabel, shiftMonth } from '../payroll'
import { canReadReviews, inTeam } from '../team'

const RATING_WORDS = ['Poor', 'Needs work', 'Good', 'Very good', 'Excellent']

function ReviewModal({ target, month, onClose, onSaved }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const rating = Form.useWatch('rating', form)
  const existing = target?.my_review

  useEffect(() => {
    if (!target) return
    form.setFieldsValue({ rating: existing?.rating ?? 0, comment: existing?.comment ?? '' })
  }, [target, existing, form])

  async function handleFinish(values) {
    setBusy(true)
    try {
      await teamApi.writeReview({ subject: target.id, month, rating: values.rating, comment: (values.comment || '').trim() })
      message.success(`Review of ${displayName(target)} saved.`)
      onSaved()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function withdraw() {
    setBusy(true)
    try {
      await teamApi.withdrawReview(existing.id)
      message.success('Review withdrawn.')
      onSaved()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(target)}
      title={target ? `Review ${displayName(target)} · ${monthLabel(month)}` : ''}
      onCancel={onClose}
      destroyOnHidden
      footer={
        <Flex justify="space-between">
          {existing ? (
            <Button danger type="text" disabled={busy} onClick={withdraw}>
              Withdraw review
            </Button>
          ) : (
            <span />
          )}
          <Space>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="primary" loading={busy} onClick={() => form.submit()}>
              {existing ? 'Save changes' : 'Submit review'}
            </Button>
          </Space>
        </Flex>
      }
    >
      {target && (
        <Form form={form} layout="vertical" onFinish={handleFinish} style={{ marginTop: 16 }}>
          <Flex align="center" gap={12} style={{ marginBottom: 20 }}>
            <PersonAvatar person={target} size={48} />
            <div>
              <Typography.Text strong style={{ display: 'block' }}>
                {displayName(target)}
              </Typography.Text>
              <Typography.Text type="secondary">{target.role}</Typography.Text>
            </div>
          </Flex>
          <Form.Item
            label="Rating"
            name="rating"
            rules={[{ validator: (_, v) => (v >= 1 ? Promise.resolve() : Promise.reject(new Error('Choose 1 to 5 stars'))) }]}
          >
            <Rate tooltips={RATING_WORDS} style={{ fontSize: 28 }} />
          </Form.Item>
          {rating > 0 && (
            <Typography.Text type="secondary" style={{ display: 'block', marginTop: -12, marginBottom: 16 }}>
              {RATING_WORDS[rating - 1]}
            </Typography.Text>
          )}
          <Form.Item label="Comment (optional)" name="comment">
            <Input.TextArea
              autoSize={{ minRows: 3, maxRows: 8 }}
              maxLength={2000}
              showCount
              placeholder="What went well, and what could be better?"
            />
          </Form.Item>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            <LockOutlined /> {displayName(target)} can't see this. Only Super Admins, HR and the Production Manager read
            reviews, and never the ones about themselves.
          </Typography.Text>
        </Form>
      )}
    </Modal>
  )
}

function WriteReviews({ month }) {
  const { message } = App.useApp()
  const [people, setPeople] = useState(null)
  const [query, setQuery] = useState('')
  const [target, setTarget] = useState(null)

  const load = useCallback(() => {
    teamApi
      .reviewPeople(month)
      .then((data) => setPeople(data.people))
      .catch((err) => message.error(err.message))
  }, [month, message])

  useEffect(load, [load])

  if (!people) return <Skeleton active />
  const done = people.filter((p) => p.my_review).length
  const shown = people.filter((p) => `${displayName(p)} ${p.role}`.toLowerCase().includes(query.trim().toLowerCase()))

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap gap={12}>
        <Typography.Text type="secondary">
          You've reviewed {done} of {people.length} colleagues for {monthLabel(month)}.
        </Typography.Text>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="Search colleagues"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: 280 }}
        />
      </Flex>
      {shown.length === 0 ? (
        <Empty description="No colleagues match." />
      ) : (
        <Row gutter={[16, 16]}>
          {shown.map((p) => (
            <Col key={p.id} xs={24} sm={12} xl={8}>
              <Card className="section-card">
                <Flex vertical gap={12} style={{ height: '100%' }}>
                  <Flex align="center" gap={12}>
                    <PersonAvatar person={p} size={44} />
                    <div style={{ minWidth: 0 }}>
                      <Typography.Text strong ellipsis style={{ display: 'block' }}>
                        {displayName(p)}
                      </Typography.Text>
                      <Typography.Text type="secondary" ellipsis style={{ display: 'block', fontSize: 13 }}>
                        {p.role}
                      </Typography.Text>
                    </div>
                  </Flex>
                  {p.my_review ? (
                    <div>
                      <Rate disabled value={p.my_review.rating} style={{ fontSize: 16 }} />
                      {p.my_review.comment && (
                        <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ margin: '6px 0 0', fontSize: 13 }}>
                          {p.my_review.comment}
                        </Typography.Paragraph>
                      )}
                    </div>
                  ) : (
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      Not reviewed yet this month.
                    </Typography.Text>
                  )}
                  <Button
                    type={p.my_review ? 'default' : 'primary'}
                    icon={p.my_review ? <EditOutlined /> : <StarFilled />}
                    onClick={() => setTarget(p)}
                    style={{ alignSelf: 'flex-start', marginTop: 'auto' }}
                  >
                    {p.my_review ? 'Edit review' : 'Write review'}
                  </Button>
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      )}
      <ReviewModal
        target={target}
        month={month}
        onClose={() => setTarget(null)}
        onSaved={() => {
          setTarget(null)
          load()
        }}
      />
    </Flex>
  )
}

function TeamReviews({ month }) {
  const { message } = App.useApp()
  const [people, setPeople] = useState(null)

  useEffect(() => {
    teamApi
      .reviewSummary(month)
      .then((data) => setPeople(data.people))
      .catch((err) => message.error(err.message))
  }, [month, message])

  const columns = [
    { title: 'Person', key: 'name', render: (_, p) => <PersonCell person={p} /> },
    { title: 'Role', dataIndex: 'role', key: 'role', responsive: ['md'] },
    {
      title: 'Average',
      key: 'average',
      className: 'nowrap',
      sorter: (a, b) => (a.average ?? 0) - (b.average ?? 0),
      render: (_, p) =>
        p.average === null ? (
          <Typography.Text type="secondary">No reviews</Typography.Text>
        ) : (
          <Flex align="center" gap={8}>
            <Rate disabled allowHalf value={Math.round(p.average * 2) / 2} style={{ fontSize: 14 }} />
            <strong>{p.average.toFixed(1)}</strong>
          </Flex>
        ),
    },
    { title: 'Reviews', dataIndex: 'count', key: 'count', align: 'right', sorter: (a, b) => a.count - b.count },
  ]

  return (
    <Card styles={{ body: { padding: 0 } }}>
      <Table
        rowKey="id"
        loading={!people}
        columns={columns}
        dataSource={people ?? []}
        pagination={false}
        scroll={{ x: 560 }}
        expandable={{
          rowExpandable: (p) => p.count > 0,
          expandedRowRender: (p) => (
            <Flex vertical gap={14} style={{ padding: '4px 8px' }}>
              {p.reviews.map((r) => (
                <Flex key={r.id} gap={12} align="flex-start">
                  <PersonAvatar person={r.author} size={32} />
                  <div style={{ minWidth: 0 }}>
                    <Flex align="center" gap={8} wrap>
                      <Typography.Text strong>{displayName(r.author)}</Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        {r.author.role}
                      </Typography.Text>
                      <Rate disabled value={r.rating} style={{ fontSize: 13 }} />
                    </Flex>
                    {r.comment ? (
                      <Typography.Paragraph style={{ margin: '2px 0 0', whiteSpace: 'pre-wrap' }}>{r.comment}</Typography.Paragraph>
                    ) : (
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        No comment.
                      </Typography.Text>
                    )}
                  </div>
                </Flex>
              ))}
            </Flex>
          ),
        }}
      />
    </Card>
  )
}

export default function Reviews({ user }) {
  const [month, setMonth] = useState(currentMonth)
  const writer = inTeam(user)
  const reader = canReadReviews(user)
  const atCurrent = month >= currentMonth()

  const tabs = [
    writer && { key: 'write', label: 'Write reviews', children: <WriteReviews month={month} /> },
    reader && { key: 'team', label: user.is_super_admin ? 'All reviews' : 'Team reviews', children: <TeamReviews month={month} /> },
  ].filter(Boolean)

  return (
    <Flex vertical gap={20}>
      <Flex justify="space-between" align="flex-end" wrap gap={16}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            Reviews
          </Typography.Title>
          <Typography.Text type="secondary">
            Everyone in Academic Content Writing can review their colleagues once a month: writers, supervisors, the
            Production Manager, Sales Manager and HR.
          </Typography.Text>
        </div>
        <Space.Compact>
          <Button icon={<LeftOutlined />} aria-label="Previous month" onClick={() => setMonth((m) => shiftMonth(m, -1))} />
          <Button style={{ minWidth: 170, fontWeight: 600 }} onClick={() => setMonth(currentMonth())}>
            {monthLabel(month)}
          </Button>
          <Button icon={<RightOutlined />} aria-label="Next month" disabled={atCurrent} onClick={() => setMonth((m) => shiftMonth(m, 1))} />
        </Space.Compact>
      </Flex>
      {tabs.length === 1 ? tabs[0].children : <Tabs items={tabs} />}
    </Flex>
  )
}
