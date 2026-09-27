import { useEffect, useState } from 'react'
import { DeleteOutlined, UploadOutlined } from '@ant-design/icons'
import { App, Button, Card, Col, Flex, Form, Input, Popconfirm, Row, Skeleton, Typography, Upload } from 'antd'
import { api, fileForm } from '../api'
import { useBranding } from '../branding'
import { Logo, LogoMark } from '../components/Logo'
import { IMAGE_ACCEPT, imageProblem } from '../uploads'

function LogoCard({ onSaved }) {
  const { message } = App.useApp()
  const { branding } = useBranding()
  const [busy, setBusy] = useState(false)

  async function save(data, success) {
    setBusy(true)
    try {
      onSaved(await api.updateCompanySettings(data))
      message.success(success)
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  function upload(file) {
    const problem = imageProblem(file)
    if (problem) message.error(problem)
    else save(fileForm('logo', file), 'Logo updated.')
    return Upload.LIST_IGNORE
  }

  return (
    <Card title="Logo" style={{ height: '100%' }}>
      <Flex vertical gap={16}>
        <Flex align="center" gap={16}>
          <LogoMark size={88} />
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            Shown in the sidebar, on the sign-in page and as the browser tab icon. PNG, JPG or WebP, up to 2 MB. A
            square image with some padding works best.
          </Typography.Text>
        </Flex>
        <div className="brand-preview">
          <Logo />
        </div>
        <Flex gap={8} wrap>
          <Upload accept={IMAGE_ACCEPT} showUploadList={false} beforeUpload={upload}>
            <Button type="primary" icon={<UploadOutlined />} loading={busy}>
              {branding.logo ? 'Replace logo' : 'Upload logo'}
            </Button>
          </Upload>
          {branding.logo && (
            <Popconfirm
              title="Remove the logo?"
              description="The built-in Yeticode mark will be shown instead."
              okText="Remove"
              onConfirm={() => save({ logo: null }, 'Logo removed.')}
            >
              <Button icon={<DeleteOutlined />} disabled={busy}>
                Remove
              </Button>
            </Popconfirm>
          )}
        </Flex>
      </Flex>
    </Card>
  )
}

export default function CompanySettings() {
  const { message } = App.useApp()
  const { setBranding } = useBranding()
  const [form] = Form.useForm()
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)

  function applySaved(settings) {
    form.setFieldsValue(settings)
    setBranding({
      name: settings.name,
      tagline: settings.tagline,
      domain: settings.domain,
      logo: settings.logo,
      updated_at: settings.updated_at,
    })
  }

  useEffect(() => {
    api
      .companySettings()
      .then((settings) => {
        form.setFieldsValue(settings)
        setLoaded(true)
      })
      .catch((err) => message.error(err.message))
  }, [form, message])

  async function handleFinish(values) {
    setBusy(true)
    try {
      const trimmed = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, (v ?? '').trim()]))
      applySaved(await api.updateCompanySettings(trimmed))
      message.success('Company details saved.')
    } catch (err) {
      const data = err.data && typeof err.data === 'object' && !err.data.detail ? err.data : null
      if (data) form.setFields(Object.entries(data).map(([name, errors]) => ({ name, errors: [].concat(errors) })))
      else message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Flex vertical gap={20}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Company settings
        </Typography.Title>
        <Typography.Text type="secondary">
          The company name and logo appear to everyone, including on the sign-in page. Only Super Admins can change
          them.
        </Typography.Text>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={9}>
          <LogoCard onSaved={applySaved} />
        </Col>
        <Col xs={24} lg={15}>
          <Card
            title="Company details"
            extra={
              <Button type="primary" loading={busy} disabled={!loaded} onClick={() => form.submit()}>
                Save changes
              </Button>
            }
          >
            {!loaded && <Skeleton active />}
            <Form
              form={form}
              layout="vertical"
              requiredMark="optional"
              onFinish={handleFinish}
              style={{ display: loaded ? undefined : 'none' }}
            >
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item
                    label="Company name"
                    name="name"
                    rules={[{ required: true, whitespace: true, message: 'Enter the company name' }]}
                  >
                    <Input maxLength={120} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="Tagline" name="tagline" extra="Shown under the name on the sign-in page.">
                    <Input maxLength={120} placeholder="Staff portal" />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item
                    label="Organisation domain"
                    name="domain"
                    extra="Completes everyone's username: with corecontent.com, the username abhishekojha signs in as abhishekojha@corecontent.com."
                    rules={[
                      {
                        pattern: /^\s*@?[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+\s*$/,
                        message: 'Enter a domain like corecontent.com',
                      },
                    ]}
                  >
                    <Input prefix="@" placeholder="corecontent.com" maxLength={120} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="Contact email" name="email" rules={[{ type: 'email', message: 'Enter a valid email address' }]}>
                    <Input placeholder="hello@yeticode.com" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="Phone" name="phone">
                    <Input maxLength={40} />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item label="Website" name="website" rules={[{ type: 'url', message: 'Enter a full URL, e.g. https://yeticode.com' }]}>
                    <Input placeholder="https://yeticode.com" />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item label="Address" name="address" style={{ marginBottom: 0 }}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Card>
        </Col>
      </Row>
    </Flex>
  )
}
