"""The team feed (posts, likes, comments) and 24-hour stories, for the Academic Content Writing unit.

Everything is visible to the whole team and to nobody else. Photos live in
PRIVATE_MEDIA_ROOT and are only served through these views.
"""

import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .files import ALLOWED, IMAGES, check_attachment
from .models import Post, PostComment, Story
from .views import IsTeamMember, person

PAGE_SIZE = 20
STORY_HOURS = 24


def check_photo(file):
    try:
        extension = check_attachment(file)
    except DjangoValidationError as error:
        raise ValidationError({"image": error.messages})
    if extension not in IMAGES:
        raise ValidationError({"image": "Only PNG, JPG, GIF or WebP photos can be posted."})
    return extension


def photo_response(field, name):
    if not field:
        raise Http404
    extension = field.name.rsplit(".", 1)[-1].lower()
    try:
        return FileResponse(field.open("rb"), content_type=ALLOWED.get(extension, "application/octet-stream"))
    except FileNotFoundError:
        raise Http404


def post_data(post, me):
    return {
        "id": post.pk,
        "author": person(post.author),
        "body": post.body,
        "image": f"/api/feed/posts/{post.pk}/image/" if post.image else None,
        "like_count": post.like_count,
        "liked": post.liked_by_me,
        "comment_count": post.comment_count,
        "created_at": post.created_at.isoformat(),
    }


def comment_data(comment):
    return {
        "id": comment.pk,
        "author": person(comment.author),
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
    }


def annotated_posts(me):
    from django.db.models import Exists, OuterRef

    return (
        Post.objects.select_related("author", "author__role")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=Exists(Post.likes.through.objects.filter(post=OuterRef("pk"), user=me)),
        )
    )


class FeedPostsView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request):
        posts = annotated_posts(request.user)
        before = request.query_params.get("before")
        if before:
            cursor = get_object_or_404(Post, pk=before)
            posts = posts.filter(created_at__lt=cursor.created_at)
        page = list(posts.order_by("-created_at")[: PAGE_SIZE + 1])
        return Response({
            "results": [post_data(p, request.user) for p in page[:PAGE_SIZE]],
            "has_more": len(page) > PAGE_SIZE,
        })

    def post(self, request):
        body = (request.data.get("body") or "").strip()
        image = request.FILES.get("image")
        if len(body) > 4000:
            raise ValidationError({"body": "Posts can be at most 4000 characters."})
        if not body and not image:
            raise ValidationError({"body": "Write something or add a photo."})
        if image:
            check_photo(image)
        post = Post.objects.create(author=request.user, body=body, image=image or "")
        return Response(post_data(annotated_posts(request.user).get(pk=post.pk), request.user), status=status.HTTP_201_CREATED)


class FeedPostView(APIView):
    permission_classes = [IsTeamMember]

    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.author_id != request.user.pk:
            raise PermissionDenied("You can only delete your own posts.")
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedPostImageView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        return photo_response(get_object_or_404(Post, pk=pk).image, "image")


class FeedLikeView(APIView):
    """POST likes the post, DELETE removes your like."""

    permission_classes = [IsTeamMember]

    def _set(self, request, pk, liked):
        post = get_object_or_404(Post, pk=pk)
        (post.likes.add if liked else post.likes.remove)(request.user)
        return Response(post_data(annotated_posts(request.user).get(pk=pk), request.user))

    def post(self, request, pk):
        return self._set(request, pk, True)

    def delete(self, request, pk):
        return self._set(request, pk, False)


class FeedCommentsView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        comments = post.comments.select_related("author", "author__role")
        return Response({"results": [comment_data(c) for c in comments]})

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        body = (request.data.get("body") or "").strip()
        if not body:
            raise ValidationError({"body": "Write a comment."})
        if len(body) > 1000:
            raise ValidationError({"body": "Comments can be at most 1000 characters."})
        comment = PostComment.objects.create(post=post, author=request.user, body=body)
        return Response(comment_data(comment), status=status.HTTP_201_CREATED)


# Stories -----------------------------------------------------------------------

def live_stories():
    return Story.objects.filter(created_at__gte=timezone.now() - datetime.timedelta(hours=STORY_HOURS))


def story_data(story, me, seen_ids):
    return {
        "id": story.pk,
        "image": f"/api/feed/stories/{story.pk}/image/",
        "caption": story.caption,
        "created_at": story.created_at.isoformat(),
        "seen": story.pk in seen_ids,
    }


class StoriesView(APIView):
    """Everyone's live stories grouped by person (yours first, then ones you haven't seen)."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        me = request.user
        stories = list(live_stories().select_related("author", "author__role"))
        seen_ids = set(Story.viewers.through.objects.filter(user=me, story__in=stories).values_list("story_id", flat=True))
        groups = {}
        for story in stories:
            groups.setdefault(story.author_id, {"user": person(story.author), "stories": []})["stories"].append(
                story_data(story, me, seen_ids)
            )
        rows = list(groups.values())
        for row in rows:
            row["all_seen"] = all(s["seen"] for s in row["stories"])
        rows.sort(key=lambda r: (r["user"]["id"] != me.pk, r["all_seen"]))
        return Response({"results": rows})

    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            raise ValidationError({"image": "Choose a photo."})
        check_photo(image)
        caption = (request.data.get("caption") or "").strip()[:200]
        story = Story.objects.create(author=request.user, image=image, caption=caption)
        return Response(story_data(story, request.user, set()), status=status.HTTP_201_CREATED)


class StoryView(APIView):
    permission_classes = [IsTeamMember]

    def delete(self, request, pk):
        story = get_object_or_404(Story, pk=pk)
        if story.author_id != request.user.pk:
            raise PermissionDenied("You can only delete your own stories.")
        story.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StoryImageView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, pk):
        return photo_response(get_object_or_404(live_stories(), pk=pk).image, "image")


class StoryViewedView(APIView):
    """POST marks a story seen; its author can GET who has seen it."""

    permission_classes = [IsTeamMember]

    def post(self, request, pk):
        story = get_object_or_404(live_stories(), pk=pk)
        if story.author_id != request.user.pk:
            story.viewers.add(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request, pk):
        story = get_object_or_404(live_stories(), pk=pk)
        if story.author_id != request.user.pk:
            raise PermissionDenied("Only the author can see who viewed a story.")
        return Response({"results": [person(u) for u in story.viewers.select_related("role")]})
