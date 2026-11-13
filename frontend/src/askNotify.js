// "Tell them about this change?" Resolves true (notify), false (save quietly).
export function askNotify(modal, who, what) {
  return new Promise((resolve) => {
    modal.confirm({
      title: `Notify ${who}?`,
      content: `Send ${who} a notification about ${what}.`,
      okText: 'Yes, notify',
      cancelText: 'No, just save',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
}
