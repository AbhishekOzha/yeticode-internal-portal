import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CloseOutlined,
  CommentOutlined,
  DeleteOutlined,
  EyeOutlined,
  HeartFilled,
  HeartOutlined,
  PictureOutlined,
  PlusOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons'
import { App, Button, Card, Empty, Flex, Input, List, Modal, Popconfirm, Skeleton, Typography } from 'antd'
import { feedApi } from '../api'
import { PersonAvatar } from '../components/People'
import { displayName } from '../people'

const STORY_MS = 5000

function ago(iso) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}m`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

// Stories: tap a bubble to watch; they move on by themselves every 5 seconds.
function StoryViewer({ groups, start, meId, onClose }) {
  const [group, setGroup] = useState(start)
  const [index, setIndex] = useState(0)
  const [viewers, setViewers] = useState(null)
  const { message } = App.useApp()
  const story = groups[group].stories[index]
  const mine = groups[group].user.id === meId

  const next = useCallback(() => {
    if (index < groups[group].stories.length - 1) setIndex(index + 1)
    else if (group < groups.length - 1) {
      setGroup(group + 1)
      setIndex(0)
    } else onClose()
  }, [index, group, groups, onClose])

  const previous = () => {
    if (index > 0) setIndex(index - 1)
    else if (group > 0) {
      setGroup(group - 1)
      setIndex(groups[group - 1].stories.length - 1)
    }
  }

  useEffect(() => {
    if (!mine) feedApi.viewStory(story.id).catch(() => {})
    if (viewers) return undefined
    const timer = setTimeout(next, STORY_MS)
    return () => clearTimeout(timer)
  }, [story, mine, next, viewers])

  async function showViewers() {
    try {
      setViewers((await feedApi.storyViewers(story.id)).results)
    } catch (err) {
      message.error(err.message)
    }
  }

  async function remove() {
    try {
      await feedApi.deleteStory(story.id)
      onClose(true)
    } catch (err) {
      message.error(err.message)
    }
  }

  const user = groups[group].user
  return (
    <Modal open footer={null} closable={false} centered width={420} onCancel={() => onClose()} styles={{ body: { padding: 0 } }}>
      <div style={{ position: 'relative', background: '#000', borderRadius: 8, overflow: 'hidden', height: '78vh', maxHeight: 720 }}>
        <img src={story.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
        <Flex gap={4} style={{ position: 'absolute', top: 8, left: 8, right: 8 }}>
          {groups[group].stories.map((s, i) => (
            <div key={s.id} style={{ flex: 1, height: 3, background: 'rgba(255,255,255,.35)', borderRadius: 2, overflow: 'hidden' }}>
              <div
                key={i === index ? story.id : s.id}
                style={{
                  height: '100%',
                  background: '#fff',
                  width: i < index ? '100%' : 0,
                  animation: i === index && !viewers ? `story-fill ${STORY_MS}ms linear forwards` : 'none',
                }}
              />
            </div>
          ))}
        </Flex>
        <Flex align="center" gap={8} style={{ position: 'absolute', top: 20, left: 12, right: 12, color: '#fff' }}>
          <PersonAvatar person={user} size={32} />
          <Typography.Text style={{ color: '#fff', fontWeight: 600 }}>{mine ? 'Your story' : displayName(user)}</Typography.Text>
          <Typography.Text style={{ color: 'rgba(255,255,255,.7)' }}>{ago(story.created_at)}</Typography.Text>
          <span style={{ flex: 1 }} />
          {mine && (
            <Popconfirm title="Delete this story?" onConfirm={remove}>
              <Button type="text" icon={<DeleteOutlined style={{ color: '#fff' }} />} aria-label="Delete story" />
            </Popconfirm>
          )}
          <Button type="text" icon={<CloseOutlined style={{ color: '#fff' }} />} onClick={() => onClose()} aria-label="Close" />
        </Flex>
        <div onClick={previous} style={{ position: 'absolute', left: 0, top: 70, bottom: 70, width: '30%', cursor: 'pointer' }} />
        <div onClick={next} style={{ position: 'absolute', right: 0, top: 70, bottom: 70, width: '70%', cursor: 'pointer' }} />
        {story.caption && (
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: mine ? 44 : 0, background: 'rgba(0,0,0,.55)', color: '#fff', padding: 12, textAlign: 'center' }}>
            {story.caption}
          </div>
        )}
        {mine && (
          <Button type="text" icon={<EyeOutlined />} onClick={showViewers} style={{ position: 'absolute', bottom: 4, left: 8, color: '#fff' }}>
            Seen by
          </Button>
        )}
      </div>
      <Modal open={Boolean(viewers)} onCancel={() => setViewers(null)} footer={null} title={`Seen by ${viewers?.length ?? 0}`}>
        <List
          dataSource={viewers ?? []}
          locale={{ emptyText: 'Nobody yet' }}
          renderItem={(p) => (
            <List.Item>
              <List.Item.Meta avatar={<PersonAvatar person={p} size={32} />} title={displayName(p)} />
            </List.Item>
          )}
        />
      </Modal>
    </Modal>
  )
}

// Pick a photo, add an optional caption, then share it to your story.
function AddStoryModal({ file, onClose, onShared }) {
  const { message } = App.useApp()
  const [caption, setCaption] = useState('')
  const [busy, setBusy] = useState(false)
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  async function share() {
    setBusy(true)
    try {
      await feedApi.addStory(file, caption.trim())
      setCaption('')
      onShared()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(file)}
      title="Add to your story"
      onCancel={onClose}
      okText="Share to story"
      onOk={share}
      confirmLoading={busy}
      destroyOnHidden
    >
      {preview && <img src={preview} alt="" style={{ width: '100%', maxHeight: 360, objectFit: 'contain', background: '#000', borderRadius: 8 }} />}
      <Input
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        maxLength={200}
        showCount
        placeholder="Add a caption (optional)"
        style={{ marginTop: 12 }}
        onPressEnter={share}
      />
    </Modal>
  )
}

function Comments({ postId, onAdded }) {
  const [comments, setComments] = useState(null)
  const [text, setText] = useState('')
  const { message } = App.useApp()

  useEffect(() => {
    feedApi.comments(postId).then((r) => setComments(r.results)).catch(() => setComments([]))
  }, [postId])

  async function send() {
    const body = text.trim()
    if (!body) return
    try {
      const comment = await feedApi.comment(postId, body)
      setComments((c) => [...(c ?? []), comment])
      setText('')
      onAdded()
    } catch (err) {
      message.error(err.message)
    }
  }

  return (
    <div style={{ padding: '4px 16px 12px' }}>
      {comments === null ? (
        <Skeleton active paragraph={{ rows: 1 }} />
      ) : (
        comments.map((c) => (
          <Flex key={c.id} gap={8} style={{ margin: '8px 0' }}>
            <PersonAvatar person={c.author} size={28} />
            <div>
              <Typography.Text strong style={{ fontSize: 13 }}>
                {displayName(c.author)}
              </Typography.Text>{' '}
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {ago(c.created_at)}
              </Typography.Text>
              <div>{c.body}</div>
            </div>
          </Flex>
        ))
      )}
      <Flex gap={8}>
        <Input value={text} onChange={(e) => setText(e.target.value)} onPressEnter={send} placeholder="Write a comment…" maxLength={1000} />
        <Button type="primary" onClick={send}>
          Send
        </Button>
      </Flex>
    </div>
  )
}

function Post({ post: initial, meId, onDeleted }) {
  const { message } = App.useApp()
  const [post, setPost] = useState(initial)
  const [showComments, setShowComments] = useState(false)

  async function like() {
    const liked = post.liked
    setPost({ ...post, liked: !liked, like_count: post.like_count + (liked ? -1 : 1) })
    try {
      setPost(await (liked ? feedApi.unlike(post.id) : feedApi.like(post.id)))
    } catch (err) {
      setPost(post)
      message.error(err.message)
    }
  }

  async function remove() {
    try {
      await feedApi.deletePost(post.id)
      onDeleted(post.id)
    } catch (err) {
      message.error(err.message)
    }
  }

  return (
    <Card styles={{ body: { padding: 0 } }} style={{ marginBottom: 16 }}>
      <Flex align="center" gap={12} style={{ padding: 16 }}>
        <PersonAvatar person={post.author} size={40} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Typography.Text strong>{displayName(post.author)}</Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {post.author.role} · {ago(post.created_at)}
            </Typography.Text>
          </div>
        </div>
        {post.author.id === meId && (
          <Popconfirm title="Delete this post?" onConfirm={remove}>
            <Button type="text" icon={<DeleteOutlined />} aria-label="Delete post" />
          </Popconfirm>
        )}
      </Flex>
      {post.body && <div style={{ padding: '0 16px 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{post.body}</div>}
      {post.image && (
        <img
          src={post.image}
          alt=""
          style={{ width: '100%', maxHeight: 520, objectFit: 'cover', display: 'block' }}
          loading="lazy"
          onDoubleClick={() => !post.liked && like()}
        />
      )}
      <Flex gap={4} style={{ padding: '4px 8px' }}>
        <Button
          type="text"
          onClick={like}
          icon={post.liked ? <HeartFilled className="like-pop" style={{ color: '#e03131' }} /> : <HeartOutlined />}
        >
          {post.like_count}
        </Button>
        <Button type="text" icon={<CommentOutlined />} onClick={() => setShowComments(!showComments)}>
          {post.comment_count}
        </Button>
      </Flex>
      {showComments && <Comments postId={post.id} onAdded={() => setPost((p) => ({ ...p, comment_count: p.comment_count + 1 }))} />}
    </Card>
  )
}

function Composer({ onPosted }) {
  const { message } = App.useApp()
  const [text, setText] = useState('')
  const [photo, setPhoto] = useState(null)
  const [busy, setBusy] = useState(false)
  const input = useRef(null)

  async function submit() {
    setBusy(true)
    try {
      await feedApi.post(text.trim(), photo)
      setText('')
      setPhoto(null)
      onPosted()
    } catch (err) {
      message.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card style={{ marginBottom: 16 }}>
      <Input.TextArea value={text} onChange={(e) => setText(e.target.value)} autoSize={{ minRows: 2, maxRows: 8 }} maxLength={4000} placeholder="What's happening?" />
      {photo && (
        <Flex align="center" gap={8} style={{ marginTop: 8 }}>
          <img src={URL.createObjectURL(photo)} alt="" style={{ height: 64, borderRadius: 6 }} />
          <Button size="small" onClick={() => setPhoto(null)}>
            Remove
          </Button>
        </Flex>
      )}
      <Flex justify="space-between" style={{ marginTop: 12 }}>
        <Button icon={<PictureOutlined />} onClick={() => input.current.click()}>
          Photo
        </Button>
        <input ref={input} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={(e) => setPhoto(e.target.files[0] ?? null)} />
        <Button type="primary" loading={busy} disabled={!text.trim() && !photo} onClick={submit}>
          Post
        </Button>
      </Flex>
    </Card>
  )
}

const STORY_RING = 'linear-gradient(45deg, #f9a825, #e91e63 50%, #7b1fa2)'

function StoryBubble({ person, label, ring, onOpen, plus, onPlus }) {
  return (
    <div style={{ textAlign: 'center', width: 76, flexShrink: 0 }}>
      <button type="button" onClick={onOpen} style={{ background: 'none', border: 0, cursor: 'pointer', padding: 0, position: 'relative' }} aria-label={label}>
        <span style={{ display: 'inline-block', padding: 3, borderRadius: '50%', background: ring === 'new' ? STORY_RING : ring === 'seen' ? '#ced4da' : 'transparent' }}>
          <span style={{ display: 'block', padding: 2, borderRadius: '50%', background: 'var(--ant-color-bg-container, #fff)' }}>
            <PersonAvatar person={person} size={56} />
          </span>
        </span>
        {plus && (
          <span
            role="button"
            tabIndex={0}
            aria-label="Add to your story"
            onClick={(e) => {
              e.stopPropagation()
              onPlus()
            }}
            onKeyDown={(e) => e.key === 'Enter' && onPlus()}
            style={{ position: 'absolute', right: 0, bottom: 2, width: 22, height: 22, borderRadius: '50%', background: '#1677ff', color: '#fff', border: '2px solid var(--ant-color-bg-container, #fff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}
          >
            <PlusOutlined />
          </span>
        )}
      </button>
      <div style={{ fontSize: 12, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</div>
    </div>
  )
}

export default function Feed({ user }) {
  const { message } = App.useApp()
  const [posts, setPosts] = useState(null)
  const [more, setMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [stories, setStories] = useState([])
  const [open, setOpen] = useState(null)
  const [newStoryFile, setNewStoryFile] = useState(null)
  const [fresh, setFresh] = useState(false) // newer posts exist than the ones shown
  const storyInput = useRef(null)
  const sentinel = useRef(null)
  const topId = useRef(null)
  const meId = user.id

  const load = useCallback(() => {
    Promise.all([feedApi.posts(), feedApi.stories()])
      .then(([p, s]) => {
        setPosts(p.results)
        setMore(p.has_more)
        setStories(s.results)
        setFresh(false)
        topId.current = p.results[0]?.id ?? null
      })
      .catch((err) => {
        message.error(err.message)
        setPosts((current) => current ?? [])
      })
  }, [message])

  useEffect(load, [load])

  // Like Facebook: keep checking for newer posts and offer a "New posts" button, and refresh when you come back to the tab.
  useEffect(() => {
    const check = () => {
      if (document.visibilityState !== 'visible') return
      feedApi
        .posts()
        .then((p) => {
          if (topId.current && p.results[0] && p.results[0].id !== topId.current) setFresh(true)
        })
        .catch(() => {})
      feedApi.stories().then((s) => setStories(s.results)).catch(() => {})
    }
    const timer = setInterval(check, 30000)
    document.addEventListener('visibilitychange', check)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', check)
    }
  }, [])

  const loadMore = useCallback(() => {
    if (loadingMore || !posts?.length) return
    setLoadingMore(true)
    feedApi
      .posts(posts[posts.length - 1].id)
      .then((res) => {
        setPosts((p) => [...p, ...res.results])
        setMore(res.has_more)
      })
      .catch((err) => message.error(err.message))
      .finally(() => setLoadingMore(false))
  }, [loadingMore, posts, message])

  // Endless scrolling: load the next page as you near the end.
  useEffect(() => {
    if (!more || !sentinel.current) return undefined
    const observer = new IntersectionObserver((entries) => entries[0].isIntersecting && loadMore(), { rootMargin: '600px' })
    observer.observe(sentinel.current)
    return () => observer.disconnect()
  }, [more, loadMore])

  function showNew() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    document.querySelector('.ant-layout-content')?.scrollTo({ top: 0, behavior: 'smooth' })
    load()
  }

  function pickStory() {
    storyInput.current?.click()
  }

  const mineIndex = stories.findIndex((g) => g.user.id === meId)
  const hasMine = mineIndex >= 0

  return (
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      <Flex gap={8} style={{ overflowX: 'auto', paddingBottom: 12, marginBottom: 8 }}>
        <StoryBubble
          person={user}
          label="Your story"
          ring={hasMine ? (stories[mineIndex].all_seen ? 'seen' : 'new') : 'none'}
          onOpen={() => (hasMine ? setOpen(mineIndex) : pickStory())}
          plus
          onPlus={pickStory}
        />
        <input
          ref={storyInput}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          hidden
          onChange={(e) => {
            setNewStoryFile(e.target.files[0] ?? null)
            e.target.value = ''
          }}
        />
        {stories.map((g, i) =>
          i === mineIndex ? null : (
            <StoryBubble
              key={g.user.id}
              person={g.user}
              label={displayName(g.user).split(' ')[0]}
              ring={g.all_seen ? 'seen' : 'new'}
              onOpen={() => setOpen(i)}
            />
          ),
        )}
      </Flex>
      {fresh && (
        <div style={{ position: 'sticky', top: 8, zIndex: 5, textAlign: 'center', marginBottom: 8 }}>
          <Button type="primary" shape="round" icon={<ArrowUpOutlined />} onClick={showNew}>
            New posts
          </Button>
        </div>
      )}
      <Composer onPosted={load} />
      {posts === null ? (
        <Skeleton active />
      ) : posts.length === 0 ? (
        <Empty description="No posts yet. Be the first!" />
      ) : (
        posts.map((p) => <Post key={p.id} post={p} meId={meId} onDeleted={(id) => setPosts((all) => all.filter((x) => x.id !== id))} />)
      )}
      {more && <div ref={sentinel} style={{ textAlign: 'center', padding: 16 }}>{loadingMore ? <Skeleton active paragraph={{ rows: 2 }} /> : null}</div>}
      {!more && posts?.length > 0 && <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>You're all caught up</Typography.Paragraph>}
      <AddStoryModal
        file={newStoryFile}
        onClose={() => setNewStoryFile(null)}
        onShared={() => {
          setNewStoryFile(null)
          load()
        }}
      />
      {open !== null && (
        <StoryViewer
          groups={stories}
          start={open}
          meId={meId}
          onClose={() => {
            setOpen(null)
            load()
          }}
        />
      )}
    </div>
  )
}
