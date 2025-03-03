from openai import OpenAI
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.models.post import Post
import re
import tiktoken

# Constants
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI's embedding model
EMBEDDING_DIMENSION = 1536  # Dimension of embeddings from this model
TIKTOKEN_ENCODING = "cl100k_base"  # This encoding works with text-embedding-3 models
MAX_TOKENS = 8192  # Maximum tokens allowed for the embedding model

# Common stopwords in both Indonesian and English
STOPWORDS = {
    # Indonesian stopwords
    "yang", "dan", "di", "ini", "dengan", "untuk", "tidak", "dari", "dalam", "akan",
    "pada", "juga", "saya", "ke", "karena", "tersebut", "bisa", "ada", "mereka", 
    "sudah", "atau", "seperti", "oleh", "sebagai", "dapat", "bahwa", "kita", "itu",
    "anda", "dia", "nya", "kami", "kamu", "kalian", "dimana", "kemana", "kenapa",
    "kapan", "siapa", "mengapa", "bagaimana", "tentang", "sejak", "ketika", "menurut",
    "hampir", "dimana", "bagi", "sambil", "setelah", "yakni", "mengenai", "hampir",
    "dimana", "bagi", "sambil", "setelah", "yakni", "mengenai", "selama", "maka",
    "apabila", "sebelum", "selain", "sesudah", "melainkan", "semua", "sendiri",
    "setiap", "sedang", "selagi", "sementara", "tetap", "harus", "namun", "lagi",
    "telah", "sekarang", "masih", "oleh", "tentang", "bahkan", "meski", "yakni",
    
    # English stopwords
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her",
    "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "can", "will", "just", "don", "should", "now", "would", "could",
    "might", "must", "well", "also", "much", "many", "back", "even", "still", "way",
    "take", "every", "since", "another", "however", "two", "three", "four", "five",
    "first", "second", "third", "one", "new", "old", "high", "long"
}

def get_tiktoken_encoder():
    """Get or create a tiktoken encoder for the specified encoding."""
    try:
        return tiktoken.get_encoding(TIKTOKEN_ENCODING)
    except Exception as e:
        # Fall back to cl100k_base if the specified encoding is not available
        return tiktoken.get_encoding("cl100k_base")

def truncate_text_to_token_limit(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """
    Truncate text to stay within token limit
    
    Args:
        text: The text to truncate
        max_tokens: Maximum number of tokens allowed
        
    Returns:
        Truncated text that fits within token limit
    """
    encoder = get_tiktoken_encoder()
    tokens = encoder.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
        
    # Truncate tokens and decode back to text
    truncated_tokens = tokens[:max_tokens]
    return encoder.decode(truncated_tokens)

def tokenize_text(text: str, remove_stopwords: bool = False) -> str:
    """
    Tokenize text to prepare it for embedding using tiktoken
    
    Args:
        text: The input text to tokenize
        remove_stopwords: Whether to remove common stopwords (default: False)
        
    Returns:
        Preprocessed and tokenized text
    """
    if not text:
        return ""
        
    # Clean the text: replace newlines with spaces and standardize whitespace
    text = text.lower()
    text = text.replace("\n", " ")
    text = re.sub(r'\s+', ' ', text)
    
    # Remove URLs and HTML tags
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'<.*?>', '', text)
    
    # Get tiktoken encoder
    encoder = get_tiktoken_encoder()
    
    # Tokenize with tiktoken and ensure we stay within limit
    tokens = encoder.encode(text)
    if len(tokens) > MAX_TOKENS:
        tokens = tokens[:MAX_TOKENS]
    
    # Decode back to text
    decoded_text = encoder.decode(tokens)
    
    # If stopwords should be removed, we need to post-process
    if remove_stopwords:
        # Split into words and filter out stopwords
        words = decoded_text.split()
        filtered_words = [word for word in words if word.lower() not in STOPWORDS]
        decoded_text = ' '.join(filtered_words)
    
    return decoded_text

def generate_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector for a given text using OpenAI's API
    
    Args:
        text: The text to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    try:
        # Tokenize the text before embedding using tiktoken
        preprocessed_text = tokenize_text(text)
        
        if not preprocessed_text:
            return [0.0] * EMBEDDING_DIMENSION
        
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Create embedding
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=preprocessed_text
        )
        
        # Extract embedding from response
        embedding = response.data[0].embedding
        
        return embedding
    except Exception as e:
        return [0.0] * EMBEDDING_DIMENSION

def generate_post_embedding(title: str, excerpt: str, content: str = None) -> List[float]:
    """
    Generate an embedding for a blog post using title and excerpt, with optional content
    
    Args:
        title: The post title
        excerpt: The post excerpt
        content: The post content (optional, first part will be used if provided)
        
    Returns:
        List of floats representing the embedding vector
    """
    # Combine title, excerpt, and content
    combined_text = f"{title} {excerpt} {content}"
    
    # Ensure we stay within token limit
    truncated_text = truncate_text_to_token_limit(combined_text)
    
    # Generate embedding for the truncated text
    return generate_embedding(truncated_text)

def update_all_post_embeddings(db: Session, batch_size: int = 50, force_update: bool = False) -> None:
    """
    Update embeddings for posts in the database
    
    Args:
        db: Database session
        batch_size: Number of posts to process in each batch
        force_update: If True, update all posts regardless of whether they already have embeddings
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
                excerpt=post.excerpt,
                content=post.content
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
    similarity_threshold: float = 0.7,
    published_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Search for posts using vector similarity
    
    Args:
        query: The search query
        db: Database session
        limit: Maximum number of results to return
        similarity_threshold: Minimum similarity score (0-1)
        published_only: Whether to only return published posts
        
    Returns:
        List of posts with their similarity scores
    """
    # Handle empty queries
    if not query or query.strip() == "":
        return []
        
    # Get encoder for token counting
    encoder = get_tiktoken_encoder()
    
    # Preprocess the query
    tokenized_query = tokenize_text(query)
    
    # Get query tokens using tiktoken
    tokens = encoder.encode(tokenized_query)
    query_length = len(tokens)
    
    # Adjust similarity threshold based on query length
    adjusted_threshold = similarity_threshold
    
    if query_length <= 5:  # Tiktoken tokenizes differently than simple word splitting
        # For very short queries, use a much lower threshold
        adjusted_threshold = min(similarity_threshold, similarity_threshold - 0.4)
            
    elif query_length <= 10:
        # For short queries, use a slightly lower threshold
        adjusted_threshold = min(similarity_threshold, similarity_threshold - 0.2)
    
    # Generate embedding for the search query
    query_embedding = generate_embedding(tokenized_query)
    
    # Create SQL query using the cosine_similarity function
    published_filter = "AND posts.published = TRUE" if published_only else ""
    sql = text(f"""
    SELECT 
        posts.id, 
        posts.title,
        posts.slug,
        posts.excerpt,
        posts.tags,
        posts.reading_time,
        posts.published,
        posts.created_at,
        users.id as author_id,
        users.username as author_username,
        users.email as author_email,
        cosine_similarity(posts.embedding, :query_embedding) as similarity
    FROM 
        posts
    JOIN
        users ON posts.author_id = users.id
    WHERE 
        posts.embedding IS NOT NULL
        {published_filter}
    ORDER BY 
        similarity DESC
    LIMIT :limit
    """)
    
    # Execute query
    result = db.execute(
        sql, 
        {"query_embedding": query_embedding, "limit": limit}
    )
    
    # Process results
    posts = []
    for row in result:
        if row.similarity >= adjusted_threshold:
            post_dict = {
                "id": row.id,
                "title": row.title,
                "slug": row.slug,
                "excerpt": row.excerpt,
                "tags": row.tags,
                "reading_time": row.reading_time,
                "published": row.published,
                "created_at": row.created_at,
                "author": {
                    "id": row.author_id,
                    "username": row.author_username,
                    "email": row.author_email
                },
                "similarity": float(row.similarity)
            }
            posts.append(post_dict)
    
    return posts 