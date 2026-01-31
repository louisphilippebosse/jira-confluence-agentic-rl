# JQL Query Examples

Reference for generating valid Jira Query Language (JQL) queries.

## Basic Syntax

```
field OPERATOR value
```

Operators: `=`, `!=`, `~`, `!~`, `IN`, `NOT IN`, `IS`, `IS NOT`, `<`, `>`, `<=`, `>=`

## Common Patterns

### By Status
```jql
status = "In Progress"
status IN ("To Do", "In Progress")
status != Done
```

### By Type
```jql
type = Bug
type IN (Task, Epic)
issuetype = Story
```

### By Text Content
```jql
text ~ "keyword"
summary ~ "bug"
description ~ "error"
```

### By User
```jql
assignee = currentUser()
reporter = "john.doe"
creator = currentUser()
```

### By Project
```jql
project = ACTHUB
project IN (ACTHUB, LIFEOPS)
```

### Combining Criteria
```jql
project = ACTHUB AND status = "In Progress"
type = Bug AND priority = High
text ~ "climbing" AND creator = currentUser()
```

## Sorting
```jql
ORDER BY updated DESC
ORDER BY created ASC
ORDER BY priority DESC, updated DESC
```

## Tips

1. **Quote values with spaces**: `status = "In Progress"`
2. **Use ~ for text search**: `text ~ "keyword"` (fuzzy match)
3. **currentUser()** for user-specific queries
4. **Multiple keywords**: Use AND between text searches
   ```jql
   text ~ "climbing" AND text ~ "epic"
   ```

## Common Mistakes

❌ **Wrong**: `text = "keyword"` (= requires exact match)  
✅ **Right**: `text ~ "keyword"` (~ does text search)

❌ **Wrong**: `status = In Progress` (missing quotes for spaces)  
✅ **Right**: `status = "In Progress"`

❌ **Wrong**: `type = task` (case sensitive)  
✅ **Right**: `type = Task`
