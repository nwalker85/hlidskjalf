---
name: file-editing
description: Safe file editing workflow using workspace tools with read-plan-write-verify pattern
version: 1.0.0
author: Norns
roles:
  - sre
  - devops
  - technical_writer
summary: >
  Safely edit files using workspace tools: read → plan → write → verify,
  preserving existing formatting and style. Always verify changes after writing.
tags:
  - file-operations
  - workspace
  - editing
  - verification
triggers:
  - edit file
  - modify file
  - update file
  - change file
  - write to file
---

# File Editing Workflow

When editing files, follow this safe, structured sequence to prevent errors and ensure changes are applied correctly.

## The Read-Plan-Write-Verify Pattern

### 1. Read
**Before making any changes, inspect the current state:**

```python
# Use workspace_list to confirm the path exists
workspace_list(path="path/to/directory")

# Use workspace_read to inspect current contents
current_content = workspace_read(path="path/to/file.py")
```

**Why?** Understanding the current state prevents:
- Overwriting existing logic
- Syntax errors from mismatched context
- Losing important comments or TODOs

### 2. Plan
**Decide what to change and document your approach:**

Think through:
- What lines need to change?
- What is the expected outcome?
- Are there dependencies (imports, function calls)?

Summarize the change in 1–3 bullets:
- Example: "Add error handling to fetch_data function"
- Example: "Update API endpoint URL from v1 to v2"
- Example: "Add type hints to function parameters"

### 3. Write
**Make the changes using workspace_write:**

```python
workspace_write(
    path="path/to/file.py",
    content=new_content,
    create_dirs=True  # Create parent directories if needed
)
```

**Important:**
- Preserve existing formatting and style (tabs vs spaces, line endings)
- Maintain the original indentation level
- Keep existing comments unless they're now incorrect
- Follow the project's coding conventions

### 4. Verify
**Always confirm the write succeeded:**

```python
# Re-read the file to verify changes
updated_content = workspace_read(path="path/to/file.py")

# Check specific changes were applied
assert "new_feature" in updated_content
```

**Report in your answer:**
- What changed (e.g., "Added error handling on line 45")
- Key diffs or additions
- Any potential side effects

## Common Patterns

### Add a New Function
```python
# 1. Read existing file
content = workspace_read("module.py")

# 2. Plan: Insert new function after imports, before main()
# 3. Write: Append function to content
new_content = content + "\n\ndef new_function():\n    pass\n"
workspace_write("module.py", new_content)

# 4. Verify
updated = workspace_read("module.py")
assert "def new_function" in updated
```

### Update Configuration Value
```python
# 1. Read config
config = workspace_read("config.yaml")

# 2. Plan: Change port from 8080 to 9090
# 3. Write: Replace value
new_config = config.replace("port: 8080", "port: 9090")
workspace_write("config.yaml", new_config)

# 4. Verify
updated = workspace_read("config.yaml")
assert "port: 9090" in updated
```

### Fix a Bug
```python
# 1. Read the buggy file
code = workspace_read("buggy.py")

# 2. Plan: Replace incorrect variable name
#    - OLD: `reuslt = process()`
#    - NEW: `result = process()`

# 3. Write
fixed_code = code.replace("reuslt =", "result =")
workspace_write("buggy.py", fixed_code)

# 4. Verify and report
updated = workspace_read("buggy.py")
print("Fixed typo: 'reuslt' → 'result' on line 23")
```

## Error Prevention Checklist

Before writing:
- ☑ Did you read the current file contents?
- ☑ Do you understand the existing structure?
- ☑ Are you preserving the correct indentation?
- ☑ Did you check for imports/dependencies?

After writing:
- ☑ Did you re-read to confirm the write succeeded?
- ☑ Are the changes exactly what you intended?
- ☑ Did you report the key changes in your response?

## When NOT to Edit Files

- ❌ Don't edit files you haven't read first
- ❌ Don't make changes without a clear plan
- ❌ Don't skip verification after writing
- ❌ Don't modify generated files (e.g., `package-lock.json`, `.pyc`)
- ❌ Don't edit binary files or images

## Integration with Other Skills

- **Git Operations**: After editing, consider committing changes
- **Terminal Commands**: After config changes, may need to restart services
- **Docker Operations**: After Dockerfile edits, rebuild images

## Troubleshooting

**Problem**: Write failed silently
- **Solution**: Check file permissions with `workspace_list`
- **Solution**: Verify parent directory exists (use `create_dirs=True`)

**Problem**: Changes were lost
- **Solution**: Always re-read to verify
- **Solution**: Check if another process is overwriting the file

**Problem**: Syntax error after edit
- **Solution**: Read first to understand context
- **Solution**: Use language-specific linters after editing

## Examples

### Example 1: Add Environment Variable
```python
# Task: Add DATABASE_URL to .env file

# 1. Read
env_content = workspace_read(".env")

# 2. Plan: Append new variable at end
# 3. Write
new_env = env_content + "\nDATABASE_URL=postgresql://localhost/db\n"
workspace_write(".env", new_env)

# 4. Verify
updated = workspace_read(".env")
print("✓ Added DATABASE_URL to .env")
```

### Example 2: Update Import Statement
```python
# Task: Change from `from old_module import func` to `from new_module import func`

# 1. Read
code = workspace_read("main.py")

# 2. Plan: Replace old import with new import
# 3. Write
updated_code = code.replace("from old_module import func", "from new_module import func")
workspace_write("main.py", updated_code)

# 4. Verify and report
final = workspace_read("main.py")
assert "from new_module import func" in final
print("✓ Updated import from old_module → new_module")
```

### Example 3: Multi-File Refactor
```python
# Task: Rename a function across multiple files

files_to_update = ["module_a.py", "module_b.py", "tests.py"]

for file_path in files_to_update:
    # 1. Read
    content = workspace_read(file_path)
    
    # 2. Plan: Replace old_function_name with new_function_name
    # 3. Write
    updated = content.replace("old_function_name", "new_function_name")
    workspace_write(file_path, updated)
    
    # 4. Verify
    final = workspace_read(file_path)
    assert "new_function_name" in final
    print(f"✓ Updated {file_path}")
```

## Summary

**Always follow the Read-Plan-Write-Verify pattern:**
1. **Read** current contents
2. **Plan** your changes explicitly
3. **Write** with `workspace_write`
4. **Verify** by re-reading

This workflow ensures safe, predictable file modifications with full visibility into what changed.

