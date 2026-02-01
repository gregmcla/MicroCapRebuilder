# Technical Debt Review

Find and catalog technical debt in the codebase, then optionally fix top items.

## Search Areas

### 1. Code Comments
- Find all TODO, FIXME, HACK, XXX comments in `scripts/`
- Categorize by urgency/type
- Note file and line number

### 2. Duplicated Code
- Identify similar code blocks across modules
- Common patterns to look for:
  - Price fetching logic
  - CSV read/write patterns
  - Date handling
  - Error handling patterns

### 3. Configuration Drift
- Find hardcoded values that should be in `data/config.json`
- Examples: magic numbers, thresholds, percentages
- Check for values duplicated between config and code

### 4. Unused Code
- Unused imports
- Dead functions (defined but never called)
- Commented-out code blocks

### 5. Schema Compliance
- Check all CSV operations use `schema.py` constants
- Find raw string column names that should use schema

### 6. Error Handling
- Functions that don't handle yfinance API failures
- Missing try/except around file I/O
- Silent failures that should be logged

### 7. Legacy Patterns
- Use of old column names from LEGACY_COLUMN_MAP
- Deprecated approaches that should be modernized

## Output

1. **Summary table** with count by category
2. **Prioritized list** (High/Medium/Low) with:
   - File:line reference
   - Description
   - Suggested fix
3. **Quick wins** - items that can be fixed in < 5 minutes

## Optional Auto-fix

If invoked with `--fix`:
- Fix top 3 quick wins automatically
- Show diff for each fix
- Leave others as documented TODOs
