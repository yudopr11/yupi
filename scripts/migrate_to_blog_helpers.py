#!/usr/bin/env python
import os
import re
import sys
from pathlib import Path

# Add the parent directory to sys.path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def find_python_files(root_dir):
    """Find all Python files in the project"""
    return list(Path(root_dir).rglob("*.py"))

def read_file_with_fallback_encoding(file_path):
    """Read a file with fallback encodings if utf-8 fails"""
    encodings = ['utf-8', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    
    # If all encodings fail, skip the file
    print(f"Warning: Could not read {file_path} with any encoding. Skipping.")
    return None, None

def update_imports(file_path):
    """Update imports in a single file"""
    content, encoding = read_file_with_fallback_encoding(file_path)
    
    if content is None:
        return False, set()
    
    # Define patterns to search for
    patterns = [
        r'from app\.utils\.slug import ([^;\n]+)',
        r'from app\.utils\.reading_time import ([^;\n]+)',
        r'from app\.utils\.content_generator import ([^;\n]+)',
        r'from app\.utils\.embedding import ([^;\n]+)'
    ]
    
    # Track changes
    changes_made = False
    imported_functions = set()
    
    # Find all imports from the individual utility files
    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            functions = match.group(1).strip()
            # Add each function to the set of imported functions
            for func in functions.split(','):
                func = func.strip()
                if func:
                    imported_functions.add(func)
            # Remove the original import statement
            content = content.replace(match.group(0), '')
            changes_made = True
    
    # If we found any imports, add a new import statement for blog_helpers
    if imported_functions:
        import_list = ', '.join(sorted(imported_functions))
        new_import = f"from app.utils.blog_helpers import {import_list}"
        
        # Find the last import statement to insert after
        import_section_end = 0
        for match in re.finditer(r'^import|^from', content, re.MULTILINE):
            import_line_end = content.find('\n', match.start())
            if import_line_end > import_section_end:
                import_section_end = import_line_end
        
        # Insert the new import statement
        if import_section_end > 0:
            content = content[:import_section_end+1] + new_import + '\n' + content[import_section_end+1:]
        else:
            content = new_import + '\n' + content
    
    # Write the updated content back to the file
    if changes_made:
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            return True, imported_functions
        except Exception as e:
            print(f"Error writing to {file_path}: {e}")
    
    return False, set()

def main():
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Find all Python files
    python_files = find_python_files(project_root)
    
    # Track statistics
    files_updated = 0
    all_imported_functions = set()
    
    # Update imports in each file
    for file_path in python_files:
        # Skip the blog_helpers.py file itself
        if 'blog_helpers.py' in str(file_path):
            continue
        
        # Skip the original utility files
        if any(util in str(file_path) for util in ['slug.py', 'reading_time.py', 'content_generator.py', 'embedding.py']):
            continue
        
        # Skip binary files or very large files
        try:
            if os.path.getsize(file_path) > 1000000:  # Skip files larger than 1MB
                print(f"Skipping large file: {file_path}")
                continue
        except:
            continue
        
        # Update imports in the file
        try:
            changes_made, imported_functions = update_imports(file_path)
            
            if changes_made:
                files_updated += 1
                all_imported_functions.update(imported_functions)
                print(f"Updated imports in {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    # Print summary
    print("\nMigration Summary:")
    print(f"Files updated: {files_updated}")
    print(f"Functions imported from blog_helpers: {', '.join(sorted(all_imported_functions))}")
    
    print("\nNext steps:")
    print("1. Run tests to ensure everything works correctly")
    print("2. Once confirmed, you can delete the original utility files:")
    print("   - app/utils/slug.py")
    print("   - app/utils/reading_time.py")
    print("   - app/utils/content_generator.py")
    print("   - app/utils/embedding.py")

if __name__ == "__main__":
    main() 