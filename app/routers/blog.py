from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional, Literal
from app.utils.database import get_db
from app.utils.auth import get_current_user, get_current_superuser
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostResponse, PostList, DeletedPostInfo, DeletePostResponse, PaginatedPostsResponse
from app.schemas.error import (
    ErrorDetail,
    NOT_FOUND_ERROR,
    AUTHOR_PERMISSION_ERROR
)
from app.utils.blog_helpers import (
    generate_slug,
    calculate_reading_time,
    generate_post_content,
    generate_post_embedding,
    search_posts_by_embedding
)
from sqlalchemy import or_, func

router = APIRouter(prefix="/blog", tags=["Blog"])

@router.get(
    "", 
    response_model=PaginatedPostsResponse,
    responses={
        422: {"model": ErrorDetail, "description": "Invalid query parameters"}
    }
)
async def get_posts(
    skip: int = 0,
    limit: int = 3,
    search: str = None,
    tag: str = None,
    published_status: Optional[Literal["published", "unpublished", "all"]] = "published",
    use_rag: bool = False,  # New parameter to enable/disable RAG search
    db: Session = Depends(get_db)
):
    """
    Get posts with various filters and pagination metadata
    - Optional search in title, excerpt, content, and tags
    - Optional filter by tag (case-insensitive)
    - Filter by published status: 'published' (default), 'unpublished', or 'all'
    - Default limit: 3 posts per page
    - Returns total count and has_more flag for better pagination
    - Semantic search using OpenAI embeddings when search is provided
    """
    # If search is provided and RAG is enabled, use vector search
    if search and use_rag:
        # Set published filter based on published_status
        is_published_only = True
        if published_status == "all":
            is_published_only = False
        elif published_status == "unpublished":
            # For unpublished posts, we'll filter after getting results
            is_published_only = False
        
        # Get semantic search results
        similarity_threshold = 0.5  # Minimum similarity score (0-1)
        vector_results = search_posts_by_embedding(
            query=search,
            db=db,
            limit=100,  # Get more results initially for filtering
            similarity_threshold=similarity_threshold,
            published_only=is_published_only
        )
        
        # Filter by published status if needed
        if published_status == "unpublished":
            vector_results = [post for post in vector_results if not post["published"]]
        
        # Filter by tag if provided
        if tag:
            vector_results = [
                post for post in vector_results 
                if post["tags"] and any(t.lower() == tag.lower() for t in post["tags"])
            ]
        
        # Get total count for pagination
        total_count = len(vector_results)
        
        # Apply pagination
        start_idx = min(skip, total_count)
        end_idx = min(skip + limit + 1, total_count)
        paginated_results = vector_results[start_idx:end_idx]
        
        # Check if there are more items
        has_more = len(paginated_results) > limit
        if has_more:
            paginated_results = paginated_results[:limit]
        
        return {
            "items": paginated_results,
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
            "skip": skip
        }
    
    # Otherwise use traditional SQL search
    else:
        # Base query
        query = db.query(Post)
        
        # Apply published status filter
        if published_status == "published":
            query = query.filter(Post.published == True)
        elif published_status == "unpublished":
            query = query.filter(Post.published == False)
        # For "all", no filter is applied
        
        # Apply search filter if provided
        if search:
            query = query.filter(
                or_(
                    Post.title.ilike(f"%{search}%"),
                    Post.excerpt.ilike(f"%{search}%"),
                    Post.content.ilike(f"%{search}%"),
                    # Search within the tags array
                    func.array_to_string(Post.tags, ',').ilike(f"%{search}%")
                )
            )
        
        # Apply tag filter if provided
        if tag:
            # Filter posts that have the specified tag using PostgreSQL array operations with case-insensitive matching
            query = query.filter(func.lower(func.array_to_string(Post.tags, ',', '')).contains(func.lower(tag)))
        
        # Get total count before applying pagination
        total_count = query.count()
        
        # Apply pagination and return results
        items = query.order_by(Post.created_at.desc()).offset(skip).limit(limit+1).all()
        
        # Check if there are more items
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item we fetched
        
        return {
            "items": items,
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
            "skip": skip
        }

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

@router.post(
    "/admin", 
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
    """
    Create new post (authenticated users only)
    
    - Automatically generates post excerpt using AI if not provided
    - Automatically suggests relevant tags using AI if none provided
    - Calculates reading time
    - Creates URL-friendly slug
    - Generates and stores embedding vectors for semantic search
    """
    post_data = post.model_dump()
    
    # Determine what content needs to be generated
    need_excerpt = not post_data.get("excerpt") or post_data["excerpt"].strip() == ""
    need_tags = not post_data.get("tags") or len(post_data["tags"]) == 0
    
    # If we need to generate content, get existing tags for context
    if need_excerpt or need_tags:
        existing_tags = []
        if need_tags:
            # Get existing tags from the database
            tag_results = db.query(Post.tags).all()
            # Flatten the list of lists and remove duplicates
            flat_tags = []
            for tags_list in tag_results:
                if tags_list[0]:  # Check if tags_list[0] is not None
                    flat_tags.extend(tags_list[0])
            existing_tags = list(set(flat_tags))
        
        # Generate content (excerpt and/or tags) in a single LLM call
        generated_content = generate_post_content(
            title=post_data["title"],
            content=post_data["content"],
            existing_tags=existing_tags,
            need_excerpt=need_excerpt,
            need_tags=need_tags
        )
        
        # Update post data with generated content
        if need_excerpt and generated_content["excerpt"]:
            post_data["excerpt"] = generated_content["excerpt"]
        
        if need_tags and generated_content["tags"]:
            post_data["tags"] = generated_content["tags"]
    
    # Create the post
    db_post = Post(
        **post_data,
        slug=generate_slug(post.title),
        reading_time=calculate_reading_time(post.content),
        author_id=current_user.id
    )
    
    # Generate embedding for the post
    if post_data.get("excerpt"):
        db_post.embedding = generate_post_embedding(
            title=db_post.title, 
            excerpt=db_post.excerpt
        )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

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
    """
    Update post by ID (author or superuser only)
    
    - Automatically regenerates post excerpt using AI if not provided
    - Automatically generates tags using AI if none provided
    - Updates slug when title changes
    - Recalculates reading time when content changes
    - Updates embedding vectors for semantic search
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        NOT_FOUND_ERROR("Post").raise_exception()
    
    if post.author_id != current_user.id and not current_user.is_superuser:
        AUTHOR_PERMISSION_ERROR.raise_exception()
    
    # Convert to dict for easier manipulation
    post_data = post_update.model_dump()
    
    # Check if we need to generate an excerpt or tags
    need_excerpt = not post_data.get("excerpt") or post_data["excerpt"].strip() == ""
    need_tags = not post_data.get("tags") or len(post_data.get("tags", [])) == 0
    
    # Generate content using LLM if needed
    if (need_excerpt or need_tags) and post_data.get("content"):
        # If we need to generate tags, get existing tags for context
        existing_tags = []
        if need_tags:
            # Get existing tags from the database
            tag_results = db.query(Post.tags).all()
            # Flatten the list of lists and remove duplicates
            flat_tags = []
            for tags_list in tag_results:
                if tags_list[0]:  # Check if tags_list[0] is not None
                    flat_tags.extend(tags_list[0])
            existing_tags = list(set(flat_tags))
        
        # Generate content with AI
        generated_content = generate_post_content(
            title=post_data.get("title", post.title),
            content=post_data["content"],
            existing_tags=existing_tags,
            need_excerpt=need_excerpt,
            need_tags=need_tags
        )
        
        # Update post data with generated excerpt
        if need_excerpt and generated_content["excerpt"]:
            post_data["excerpt"] = generated_content["excerpt"]
            
        # Update post data with generated tags
        if need_tags and generated_content["tags"]:
            post_data["tags"] = generated_content["tags"]
    
    # Update all fields
    for key, value in post_data.items():
        setattr(post, key, value)
    
    # Update slug if title changed
    if post_update.title:
        post.slug = generate_slug(post_update.title)
    
    # Recalculate reading time if content changed
    if post_update.content:
        post.reading_time = calculate_reading_time(post_update.content)
    
    # Update embedding if title or excerpt changed
    if post_update.title or "excerpt" in post_data:
        post.embedding = generate_post_embedding(
            title=post.title, 
            excerpt=post.excerpt
        )
    
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