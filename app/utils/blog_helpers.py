from openai import OpenAI
from typing import List, Dict, Any
import json
import re
from sqlalchemy.orm import Session
from sqlalchemy import text
from slugify import slugify
from app.core.config import settings
from app.models.blog import Post

# --- Constants ---
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI's embedding model
EMBEDDING_DIMENSION = 1536  # Dimension of embeddings from this model

# --- Slug Generator ---
def generate_slug(title: str) -> str:
    """
    Generate URL-friendly slug from title
    
    This function converts a blog post title into a URL-friendly slug by
    removing special characters, replacing spaces with hyphens, and
    ensuring the slug is properly formatted for web URLs.
    
    Args:
        title (str): The blog post title to convert to a slug
        
    Returns:
        str: URL-friendly slug version of the title
    """
    return slugify(title)

# --- Reading Time Calculator ---
def calculate_reading_time(content: str) -> int:
    """
    Calculate reading time in minutes based on content length
    
    This function estimates how long it would take an average person
    to read the provided content, based on a reading speed of 300 words
    per minute. The minimum reading time is 1 minute.
    
    Args:
        content (str): The text content to calculate reading time for
        
    Returns:
        int: Estimated reading time in minutes (minimum 1)
    """
    words = len(content.split())
    return max(1, round(words / 300))

# --- Content Generation ---
def truncate_content_for_prompt(content: str, max_chars: int = 2000) -> str:
    """
    Truncate content for prompt by using first and last chunks with ellipsis in between
    
    This function intelligently truncates long content to fit within API prompt
    limits while preserving the most important parts (beginning and end).
    It's particularly useful for API calls with character limits.
    
    Args:
        content (str): The full content text
        max_chars (int): Maximum total characters to include
        
    Returns:
        str: Truncated content with first and last parts preserved
    """
    if len(content) <= max_chars:
        return content
    
    # Use half of max_chars for the first part and half for the last part
    half_max = max_chars // 2
    first_part = content[:half_max].strip()
    last_part = content[-half_max:].strip()
    
    return f"{first_part}\n...\n{last_part}"

def generate_post_content(
    title: str, 
    content: str, 
    existing_tags: List[str] = None,
    need_excerpt: bool = True,
    need_tags: bool = True,
    max_tags: int = 5,
    max_excerpt_words: int = 50
) -> Dict:
    """
    Generate both excerpt and tags for a blog post using AI
    
    This function leverages OpenAI's API to automatically generate an excerpt
    and relevant tags for a blog post based on its title and content. It can
    optionally reuse existing tags from the database and handles API errors
    gracefully with fallback mechanisms.
    
    Args:
        title (str): The title of the blog post
        content (str): The full content of the blog post
        existing_tags (List[str], optional): List of tags that already exist in the database
        need_excerpt (bool): Whether to generate an excerpt
        need_tags (bool): Whether to generate tags
        max_tags (int): Maximum number of tags to generate
        max_excerpt_words (int): Maximum number of words for the excerpt
        
    Returns:
        Dict: A dictionary containing generated excerpt and tags
    """
    if existing_tags is None:
        existing_tags = []
    
    # Default return values
    result = {
        "excerpt": "",
        "tags": []
    }
    
    # If neither excerpt nor tags are needed, return early
    if not need_excerpt and not need_tags:
        return result
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Create prompt with existing tags
        existing_tags_str = ", ".join(existing_tags[:100])  # Limit to first 100 tags for context
        
        # Truncate content to include first 1000 and last 1000 characters
        truncated_content = truncate_content_for_prompt(content, 2000)
        
        # Build the prompt based on what's needed
        prompt = f"""
I need your help analyzing and enhancing a blog post. 

Title: {title}

Content: 
{truncated_content}

"""
        
        if need_excerpt:
            prompt += f"""
Task 1: Generate a comprehensive summary (ringkasan) of this blog post.
- Keep it under {max_excerpt_words} words
- Include the main points and key insights from both the beginning and end of the post
- Highlight the most important concepts and conclusions
- Make it standalone and informative so readers understand what the post is about
- Use active voice and engaging language
- Do not use phrases like "In this blog post" or "This article discusses"
"""
        
        if need_tags:
            prompt += f"""
Task {2 if need_excerpt else 1}: Generate relevant tags for this blog post.
- Generate at most {max_tags} tags
- Each tag should be a single word or short phrase (1-3 words maximum)
- IMPORTANT: Reuse existing tags from our database when they are relevant
- All tags should be properly capitalized (e.g., "Python", "Machine Learning")
- Do not include hashtag symbols (#)
- Focus on specific topics, technologies, concepts or themes

Here are existing tags in our database that you should consider using when appropriate:
{existing_tags_str}
"""
        
        prompt += """
Return your response in the following JSON format:
{
"""
        
        if need_excerpt:
            prompt += """
  "excerpt": "Your generated excerpt here",
"""
        
        if need_tags:
            prompt += """
  "tags": ["Tag1", "Tag2", "Tag3"]
"""
        
        prompt += """
}
"""
        
        # Generate completion
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=1,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the response
        response_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            response_data = json.loads(response_text)
            
            # Extract excerpt if requested
            if need_excerpt and "excerpt" in response_data:
                result["excerpt"] = response_data["excerpt"].strip()
            
            # Extract and process tags if requested
            if need_tags and "tags" in response_data:
                tags = response_data["tags"]
                # Ensure all tags are strings and properly capitalized
                tags = [str(tag).strip() for tag in tags]
                # Remove any empty tags
                tags = [tag for tag in tags if tag]
                # Limit to max_tags
                tags = tags[:max_tags]
                result["tags"] = tags
                
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract data manually
            if need_excerpt:
                # Try to find an excerpt by looking for patterns
                result["excerpt"] = extract_excerpt_from_text(response_text)
                
            if need_tags:
                # Try to find tags by looking for patterns
                result["tags"] = extract_tags_from_text(response_text)
            
    except Exception as e:
        # If API call fails or any other error occurs, use fallbacks
        if need_excerpt:
            result["excerpt"] = fallback_excerpt(content)
            
    return result

def extract_excerpt_from_text(text: str) -> str:
    """
    Extract an excerpt from plain text when JSON parsing fails
    
    This function serves as a fallback mechanism to extract an excerpt from
    unstructured text when the expected JSON format is not available.
    It looks for common indicators of excerpt sections and extracts the
    relevant content.
    
    Args:
        text (str): The raw text to extract an excerpt from
        
    Returns:
        str: The extracted excerpt or an empty string if none found
    """
    # Look for phrases that might indicate an excerpt
    excerpt_indicators = ["excerpt:", "excerpt", "summary:", "summary"]
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        for indicator in excerpt_indicators:
            if indicator.lower() in line.lower():
                # Found a potential excerpt line
                if i+1 < len(lines) and lines[i+1].strip():
                    return lines[i+1].strip()
                # If there's text after the indicator on the same line
                parts = line.lower().split(indicator.lower(), 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
    
    # If no excerpt found, return empty string
    return ""

def extract_tags_from_text(text: str) -> List[str]:
    """
    Extract tags from plain text when JSON parsing fails
    
    This function serves as a fallback mechanism to extract tags from
    unstructured text when the expected JSON format is not available.
    It uses regular expressions to identify tag patterns and formats
    them properly.
    
    Args:
        text (str): The raw text to extract tags from
        
    Returns:
        List[str]: List of extracted tags or empty list if none found
    """
    # Look for patterns like ["tag1", "tag2"] or [tag1, tag2]
    tags_pattern = r'\[(.*?)\]'
    matches = re.search(tags_pattern, text)
    
    if matches:
        tags_text = matches.group(1)
        # Split by commas and clean up
        raw_tags = [t.strip().strip('"\'') for t in tags_text.split(',')]
        # Capitalize and filter empty tags
        tags = [tag.title() for tag in raw_tags if tag]
        return tags[:5]  # Limit to 5 tags
    
    return []

def fallback_excerpt(content: str) -> str:
    """
    Generate a fallback excerpt when API calls fail
    
    This function provides a simple but effective way to create an excerpt
    when the AI generation fails. It extracts the first sentence of the
    content and truncates it if necessary.
    
    Args:
        content (str): The original post content
        
    Returns:
        str: A simple excerpt based on the first sentence
    """
    # Use first sentence of content
    first_sentence = content.split('.')[0].strip()
    if len(first_sentence) > 150:
        return first_sentence[:147] + "..."
    return first_sentence

# --- Embedding Generation and Search ---
def generate_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector for given text
    
    This function uses OpenAI's API to convert text into a high-dimensional
    vector (embedding) that captures the semantic meaning of the text.
    These embeddings can be used for semantic search and recommendations.
    
    Args:
        text (str): The text to convert to an embedding vector
        
    Returns:
        List[float]: Embedding vector (array of floating point values)
        
    Note:
        Returns a zero vector if an error occurs or if text is empty
    """
    try:
        if not text:
            return [0.0] * EMBEDDING_DIMENSION
        
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Create embedding
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        
        # Extract embedding from response
        embedding = response.data[0].embedding
        
        return embedding
    except Exception as e:
        return [0.0] * EMBEDDING_DIMENSION

def generate_post_embedding(title: str, excerpt: str) -> List[float]:
    """
    Generate an embedding for a blog post
    
    This function creates a semantic vector representation of a blog post
    by combining its title and excerpt into a single text and generating
    an embedding. This is used for semantic search and related post
    recommendations.
    
    Args:
        title (str): The post title
        excerpt (str): The post excerpt or summary
        
    Returns:
        List[float]: Embedding vector representing the post's semantic content
    """
    # Combine title and excerpt
    combined_text = f"{title} {excerpt}"
    
    # Generate embedding for the combined text
    return generate_embedding(combined_text)

def update_all_post_embeddings(db: Session, batch_size: int = 50, force_update: bool = False) -> None:
    """
    Update embeddings for all posts in the database
    
    This function processes posts in batches to generate or update their
    embedding vectors. It can either update all posts or only those without
    existing embeddings. The function is designed to be efficient for large
    databases by processing posts in batches.
    
    Args:
        db (Session): Database session
        batch_size (int): Number of posts to process in each batch
        force_update (bool): If True, update all posts regardless of whether
                            they already have embeddings
    """
    # Create query based on force_update parameter
    if force_update:
        # Update all posts if force_update is True
        query = db.query(Post)
        total = query.count()
        print(f"Forcing update of embeddings for all {total} posts")
    else:
        # Otherwise, only update posts without embeddings
        query = db.query(Post).filter(Post.embedding.is_(None))
        total = query.count()
        
        if total == 0:
            print("No posts found without embeddings. All posts are already processed.")
            return
        else:
            print(f"Found {total} posts without embeddings")
        
    processed = 0
    
    while processed < total:
        # Get a batch of posts
        posts = query.offset(processed).limit(batch_size).all()
        
        if not posts:
            break
            
        # Generate and update embeddings
        for post in posts:
            embedding = generate_post_embedding(
                title=post.title, 
                excerpt=post.excerpt
            )
            post.embedding = embedding
        
        # Commit the batch
        db.commit()
        processed += len(posts)
        print(f"Processed {processed}/{total} posts")

def search_posts_by_embedding(
    query: str, 
    db: Session, 
    limit: int = 10, 
    similarity_threshold: float = 0,
    published_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Search for posts using semantic similarity
    
    This function implements semantic search by:
    1. Converting the search query to an embedding vector
    2. Finding posts with similar embeddings using cosine similarity
    3. Ranking results by their semantic similarity to the query
    
    Unlike keyword search, this can find contextually relevant posts even
    when they don't contain the exact search terms.
    
    Args:
        query (str): The search query text
        db (Session): Database session
        limit (int): Maximum number of results to return
        similarity_threshold (float): Minimum similarity score (0-1) for results
        published_only (bool): Whether to only return published posts
        
    Returns:
        List[Dict[str, Any]]: List of matching posts with their similarity scores,
                            sorted by relevance
    """
    # Handle empty queries
    if not query or query.strip() == "":
        return []
    
    # Generate embedding for the search query
    query_embedding = generate_embedding(query)
    
    # Create SQL query using the cosine_similarity function
    published_filter = "AND blog_posts.published = TRUE" if published_only else ""
    
    # Default threshold to 0 if not provided
    similarity_threshold = similarity_threshold if similarity_threshold is not None else 0
    
    sql = text(f"""
    SELECT 
    blog_posts.id as post_id, 
    blog_posts.title,
    blog_posts.slug,
    blog_posts.excerpt,
    blog_posts.content,
    blog_posts.tags,
    blog_posts.reading_time,
    blog_posts.published,
    blog_posts.created_at,
    blog_posts.updated_at,
    auth_users.id as author_id,
    auth_users.username as author_username,
    auth_users.email as author_email,
    1 - (blog_posts.embedding <=> CAST(:query_embedding AS vector)) as similarity
    FROM 
        blog_posts
    JOIN
        auth_users ON blog_posts.author_id = auth_users.id
    WHERE 
        blog_posts.embedding IS NOT NULL
        AND 1 - (blog_posts.embedding <=> CAST(:query_embedding AS vector)) >= :similarity_threshold
        AND blog_posts.published = TRUE
    ORDER BY 
        blog_posts.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :limit
    """)
    
    # Execute query
    result = db.execute(
        sql, 
        {
            "query_embedding": query_embedding, 
            "limit": limit,
            "similarity_threshold": similarity_threshold
        }
    )
    
    # Process results
    posts = []
    for row in result:
        post_dict = {
            "id": row.post_id,
            "title": row.title,
            "slug": row.slug,
            "excerpt": row.excerpt,
            "content": row.content,
            "tags": row.tags,
            "reading_time": row.reading_time,
            "published": row.published,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "author": {
                "id": row.author_id,
                "username": row.author_username,
                "email": row.author_email
            },
            "similarity": float(row.similarity)
        }
        posts.append(post_dict)
    
    return posts 