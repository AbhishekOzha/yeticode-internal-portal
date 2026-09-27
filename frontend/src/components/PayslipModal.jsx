import { useEffect, useState } from 'react'
import { PrinterOutlined } from '@ant-design/icons'
import { App, Button, Flex, Modal, Skeleton, Typography } from 'antd'
import { api } from '../api'
import { displayName } from '../people'
import { monthLabel } from '../payroll'

function rupees(value) {
  return Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function whole(value) {
  return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

// One person's payslip for a month, laid out like the company's salary sheet.
export function PayslipModal({ staff, month, onClose }) {
  const { message } = App.useApp()
  const [slip, setSlip] = useState(null)

  useEffect(() => {
    if (!staff) return
    api
      .payslip(staff.id, month)
      .then(setSlip)
      .catch((err) => message.error(err.message))
  }, [staff, month, message])

  const monthName = monthLabel(month).split(' ')[0]
  const rows = slip
    ? [
        ['Employee Name', <strong key="n">{slip.employee.name}</strong>],
        ['Role', slip.employee.role],
        ['Monthly salary', rupees(slip.monthly_salary)],
        ['Per day income', whole(slip.per_day)],
        [`Total days in ${monthName}`, `${slip.total_days} Days`],
        ['Working Days', `${slip.working_days} Days`],
        [`Credit of ${monthName}`, `${slip.credits} cr`],
        ['Credit Amount', rupees(slip.credit_amount)],
        ...(Number(slip.performance) ? [['Performance bonus', rupees(slip.performance)]] : []),
        ...(Number(slip.effort) ? [['Effort bonus', rupees(slip.effort)]] : []),
        ['Leave', `${slip.leave_days} Days`],
        ['Salary Amount', rupees(slip.salary_amount)],
        ['Deducted Amount of Leave', rupees(slip.leave_deduction)],
      ]
    : []

  return (
    <Modal
      open={Boolean(staff)}
      onCancel={onClose}
      destroyOnHidden
      width={620}
      title={staff ? `Payslip · ${displayName(staff)} · ${monthLabel(month)}` : ''}
      footer={
        <Flex justify="space-between" align="center">
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Per day = salary ÷ 30, rounded up · leave = approved leave this month
          </Typography.Text>
          <Button type="primary" icon={<PrinterOutlined />} disabled={!slip} onClick={() => window.print()}>
            Print
          </Button>
        </Flex>
      }
    >
      {!slip ? (
        <Skeleton active />
      ) : (
        <div className="payslip-print">
          <table className="payslip">
            <tbody>
              <tr className="payslip-head">
                <th>Company Name</th>
                <th>{slip.company}</th>
              </tr>
              <tr className="payslip-month">
                <td>Month</td>
                <td>{monthLabel(month)}</td>
              </tr>
              {rows.map(([label, value]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{value}</td>
                </tr>
              ))}
              <tr className="payslip-total">
                <th>Gross Amount</th>
                <th>{rupees(slip.gross)}</th>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
