import { useEffect, useMemo, useState } from 'react'
import { App, Button, Drawer, Flex, InputNumber, Skeleton, Statistic, Table, Tag, Typography } from 'antd'
import { api } from '../api'
import { displayName } from '../people'
import { count, daysOf, monthLabel, npr, rateAmount, todayISO } from '../payroll'

const blank = { hours: null, words: null }

function sameDay(a, b) {
  return Number(a.hours || 0) === Number(b.hours || 0) && Number(a.words || 0) === Number(b.words || 0)
}

// One row per day: type the extra hours and words worked that day and leave
// the rest empty. Each day is priced on its own.
export default function DailyLogDrawer({ staff, month, onClose, onSaved }) {
  const { message } = App.useApp()
  const [saved, setSaved] = useState(null) // date -> { hours, words, amount } from the server
  const [entries, setEntries] = useState({}) // date -> { hours, words } being edited
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!staff) return
    api
      .dailyLog(staff.id, month)
      .then((log) => {
        const byDate = Object.fromEntries(
          log.days.map((d) => [d.date, { hours: d.hours === null ? null : Number(d.hours), words: d.words, amount: d.amount }]),
        )
        setSaved(byDate)
        setEntries(Object.fromEntries(Object.entries(byDate).map(([date, d]) => [date, { hours: d.hours, words: d.words }])))
      })
      .catch((err) => message.error(err.message))
  }, [staff, month, message])

  const pay = staff?.pay
  const today = todayISO()

  // Unchanged days show what was saved; edited days are priced at the current rate.
  const amountFor = (date) => {
    const entry = entries[date] ?? blank
    const before = saved?.[date]
    if (before && sameDay(before, entry)) return Number(before.amount)
    const hours = rateAmount(entry.hours, pay.hours_per_rate, pay.hours_rate_amount) ?? 0
    const words = rateAmount(entry.words, pay.words_per_rate, pay.words_rate_amount) ?? 0
    return hours + words
  }

  const rows = useMemo(() => (staff ? daysOf(month).map((date) => ({ date })) : []), [staff, month])

  let summary = null
  if (staff && saved) {
    let days = 0
    let hours = 0
    let words = 0
    let amount = 0
    for (const { date } of rows) {
      const e = entries[date] ?? blank
      if (Number(e.hours) || Number(e.words)) days += 1
      hours += Number(e.hours || 0)
      words += Number(e.words || 0)
      amount += amountFor(date)
    }
    summary = { days, hours, words, amount }
  }

  const dirty = useMemo(() => {
    if (!saved) return false
    const dates = new Set([...Object.keys(saved), ...Object.keys(entries)])
    return [...dates].some((date) => !sameDay(saved[date] ?? blank, entries[date] ?? blank))
  }, [saved, entries])

  function change(date, field, value) {
    setEntries((current) => ({ ...current, [date]: { ...(current[date] ?? blank), [field]: value } }))
  }

  async function save() {
    setBusy(true)
    const days = Object.entries(entries)
      .filter(([, e]) => Number(e.hours) || Number(e.words))
      .map(([date, e]) => ({ date, hours: e.hours || null, words: e.words || null }))
    try {
      await api.saveDailyLog(staff.id, month, days)
      message.success(`Daily log saved for ${displayName(staff)}.`)
      onSaved()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    {
      title: 'Day',
      key: 'date',
      width: 110,
      render: (_, { date }) => {
        const day = new Date(`${date}T00:00`)
        return (
          <Flex align="center" gap={6}>
            <span style={{ fontWeight: 500 }}>{day.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</span>
            {date === today && <Tag color="blue" variant="filled" style={{ marginInlineEnd: 0 }}>Today</Tag>}
          </Flex>
        )
      },
    },
    {
      title: 'Extra hours',
      key: 'hours',
      render: (_, { date }) => (
        <InputNumber
          size="small"
          min={0}
          max={24}
          step={0.5}
          placeholder="—"
          value={entries[date]?.hours ?? null}
          onChange={(v) => change(date, 'hours', v)}
          style={{ width: '100%' }}
          aria-label={`Extra hours on ${date}`}
        />
      ),
    },
    {
      title: 'Extra words',
      key: 'words',
      render: (_, { date }) => (
        <InputNumber
          size="small"
          min={0}
          step={500}
          precision={0}
          placeholder="—"
          value={entries[date]?.words ?? null}
          onChange={(v) => change(date, 'words', v)}
          style={{ width: '100%' }}
          aria-label={`Extra words on ${date}`}
        />
      ),
    },
    {
      title: 'Amount',
      key: 'amount',
      align: 'right',
      className: 'nowrap',
      width: 120,
      render: (_, { date }) => {
        const amount = amountFor(date)
        return amount ? <strong>{npr(amount)}</strong> : <Typography.Text type="secondary">—</Typography.Text>
      },
    },
  ]

  return (
    <Drawer
      open={Boolean(staff)}
      onClose={onClose}
      size={620}
      destroyOnHidden
      title={staff ? `Daily log for ${displayName(staff)} · ${monthLabel(month)}` : ''}
      extra={
        <Button type="primary" loading={busy} disabled={!dirty} onClick={save}>
          Save daily log
        </Button>
      }
    >
      {!staff || !saved || !summary ? (
        <Skeleton active />
      ) : (
        <Flex vertical gap={16}>
          <Typography.Text type="secondary">
            Enter the extra hours or words for each day they worked extra and leave other days empty. New days are paid at{' '}
            {count(pay.hours_per_rate)} hours = {npr(pay.hours_rate_amount)} and {count(pay.words_per_rate)} words ={' '}
            {npr(pay.words_rate_amount)}; days already saved keep the rate they were priced at.
          </Typography.Text>
          <Flex gap={24} wrap className="payroll-stat">
            <Statistic title="Days with extras" value={summary.days} />
            <Statistic title="Extra hours" value={count(summary.hours)} />
            <Statistic title="Extra words" value={count(summary.words)} />
            <Statistic title="Daily extras total" value={npr(summary.amount)} />
          </Flex>
          <Table
            rowKey="date"
            size="small"
            columns={columns}
            dataSource={rows}
            pagination={false}
            rowClassName={({ date }) => {
              const e = entries[date] ?? blank
              return Number(e.hours) || Number(e.words) ? 'day-worked' : ''
            }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            Performance, effort and monthly (undated) extras are added with the Extra button and aren't changed here.
          </Typography.Text>
        </Flex>
      )}
    </Drawer>
  )
}
