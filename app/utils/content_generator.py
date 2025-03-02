from openai import OpenAI
from typing import List, Dict, Tuple
import json
from app.core.config import settings

def generate_post_content(
    title: str, 
    content: str, 
    existing_tags: List[str] = None,
    need_excerpt: bool = True,
    need_tags: bool = True,
    max_tags: int = 5,
    max_excerpt_words: int = 30
) -> Dict:
    """
    Generate both excerpt and tags for a blog post using a single OpenAI API call
    
    Args:
        title: The title of the blog post
        content: The full content of the blog post
        existing_tags: List of tags that already exist in the database
        need_excerpt: Whether to generate an excerpt
        need_tags: Whether to generate tags
        max_tags: Maximum number of tags to generate (default: 5)
        max_excerpt_words: Maximum number of words for the excerpt (default: 20)
        
    Returns:
        A dictionary containing generated excerpt and tags
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
        
        # Build the prompt based on what's needed
        prompt = f"""
I need your help analyzing and enhancing a blog post. 

Title: {title}

Content: 
{content[:2000]}...  # Using first 2000 chars for context

"""
        
        if need_excerpt:
            prompt += f"""
Task 1: Generate a concise and engaging excerpt for this blog post.
- Keep it under {max_excerpt_words} words
- Capture the main value proposition of the post
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
            temperature=0.7,
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
                tags = [str(tag).strip().title() for tag in tags]
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
    Try to extract an excerpt from plain text when JSON parsing fails
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
    Try to extract tags from plain text when JSON parsing fails
    """
    # Look for patterns like ["tag1", "tag2"] or [tag1, tag2]
    import re
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
    Generate a fallback excerpt when API call fails
    """
    # Use first sentence of content
    first_sentence = content.split('.')[0].strip()
    if len(first_sentence) > 150:
        return first_sentence[:147] + "..."
    return first_sentence 