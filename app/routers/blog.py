from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.utils.database import get_db
from app.utils.auth import get_current_user, get_current_superuser
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostResponse, PostList, DeletedPostInfo, DeletePostResponse
from app.schemas.error import (
    ErrorDetail,
    NOT_FOUND_ERROR,
    AUTHOR_PERMISSION_ERROR
)
from app.utils.slug import generate_slug
from app.utils.reading_time import calculate_reading_time

router = APIRouter(prefix="/blog", tags=["Blog"])

@router.post(
    "", 
    response_model=PostResponse,
    responses={
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def create_post(
    post: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new post (authenticated users only)"""
    db_post = Post(
        **post.model_dump(),
        slug=generate_slug(post.title),
        reading_time=calculate_reading_time(post.content),
        author_id=current_user.id
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

@router.get(
    "", 
    response_model=List[PostList],
    responses={
        422: {"model": ErrorDetail, "description": "Invalid query parameters"}
    }
)
async def get_posts(
    skip: int = 0,
    limit: int = 3,
    search: str = None,
    db: Session = Depends(get_db)
):
    """
    Get all published posts
    - Optional search in title, excerpt, and content
    - Default limit: 3 posts per page
    """
    query = db.query(Post).filter(Post.published == True)
    if search:
        query = query.filter(
            Post.title.ilike(f"%{search}%") |
            Post.excerpt.ilike(f"%{search}%") |
            Post.content.ilike(f"%{search}%")
        )
    
    return query.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()

@router.get(
    "/{slug}", 
    response_model=PostResponse,
    responses={
        404: {"model": ErrorDetail, "description": "Post not found"}
    }
)
async def get_post(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get post by slug"""
    post = db.query(Post).filter(Post.slug == slug).first()
    if not post:
        NOT_FOUND_ERROR("Post").raise_exception()
    return post

@router.put(
    "/admin/{post_id}", 
    response_model=PostResponse,
    responses={
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        403: {"model": ErrorDetail, "description": "Not enough permissions"},
        404: {"model": ErrorDetail, "description": "Post not found"},
        422: {"model": ErrorDetail, "description": "Validation error"}
    }
)
async def update_post(
    post_id: int,
    post_update: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update post by ID (author or superuser only)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        NOT_FOUND_ERROR("Post").raise_exception()
    
    if post.author_id != current_user.id and not current_user.is_superuser:
        AUTHOR_PERMISSION_ERROR.raise_exception()
    
    for key, value in post_update.model_dump().items():
        setattr(post, key, value)
    
    if post_update.title:
        post.slug = generate_slug(post_update.title)
    if post_update.content:
        post.reading_time = calculate_reading_time(post_update.content)
    
    db.commit()
    db.refresh(post)
    return post

@router.delete(
    "/admin/{post_id}", 
    response_model=DeletePostResponse,
    responses={
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        403: {"model": ErrorDetail, "description": "Not enough permissions"},
        404: {"model": ErrorDetail, "description": "Post not found"}
    }
)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Delete post by ID (superuser only)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        NOT_FOUND_ERROR("Post").raise_exception()
    
    post_info = DeletedPostInfo(id=post.id, title=post.title, uuid=post.uuid)
    db.delete(post)
    db.commit()

    return DeletePostResponse(message="Post has been deleted successfully", deleted_item=post_info) 