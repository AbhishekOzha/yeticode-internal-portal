import { useEffect, useMemo, useState } from 'react'
import { SearchOutlined } from '@ant-design/icons'
import { Card, Flex, Input, Segmented, Table, Typography } from 'antd'
import { api } from '../api'
import { PersonCell, UnitTag } from '../components/People'

export default function Directory({ user }) {
  const companyWide = user.capabilities.includes('view_all_employee_records')
  const [people, setPeople] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [unit, setUnit] = useState('all')

  useEffect(() => {
    const load = companyWide ? api.companyMembers : api.unitMembers
    load()
      .then(setPeople)
      .catch((err) => setError(err.message))
  }, [companyWide])

  const units = useMemo(() => {
    const seen = new Map()
    for (const p of people ?? []) if (p.unit) seen.set(p.unit_code ?? 'company', p.unit_code ? p.unit : 'Company-wide')
    return [...seen.entries()]
  }, [people])

  const rows = (people ?? []).filter((p) => {
    if (unit !== 'all' && (p.unit_code ?? 'company') !== unit) return false
    return `${p.full_name} ${p.username} ${p.email} ${p.role}`.toLowerCase().includes(query.trim().toLowerCase())
  })

  const columns = [
    { title: 'Name', key: 'name', render: (_, p) => <PersonCell person={p} /> },
    { title: 'Role', dataIndex: 'role', key: 'role' },
    ...(companyWide
      ? [{ title: 'Unit', key: 'unit', render: (_, p) => <UnitTag code={p.unit_code} name={p.unit} /> }]
      : []),
  ]

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          {companyWide ? 'Everyone at Yeticode' : `People in ${user.unit.name}`}
        </Typography.Title>
        <Typography.Text type="secondary">
          {companyWide ? 'All active staff and students across the three units.' : 'Colleagues in your unit and their roles.'}
        </Typography.Text>
      </div>
      <Card styles={{ body: { padding: 0 } }}>
        <Flex gap={12} wrap align="center" style={{ padding: 16 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Search people"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 320 }}
          />
          {companyWide && units.length > 1 && (
            <Segmented
              value={unit}
              onChange={setUnit}
              options={[{ label: 'All', value: 'all' }, ...units.map(([code, name]) => ({ label: name, value: code }))]}
            />
          )}
        </Flex>
        <Table
          rowKey="id"
          loading={!people && !error}
          columns={columns}
          dataSource={rows}
          pagination={{ pageSize: 20, hideOnSinglePage: true }}
          locale={{ emptyText: error || 'No one matches your search.' }}
          scroll={{ x: 560 }}
        />
      </Card>
    </Flex>
  )
}
