---
# Kiro: Always include this file
inclusion: always

# Windsurf: Apply to documentation files
applies_to:
  - "**/*.md"
  - "**/*.rst"

# GitHub Copilot: Apply to documentation files
applyTo:
  - "**/*.md"
  - "**/*.rst"
---

# Documentation Standards for PGMob

## Task completion documents

NEVER create LLM activity report files in the repository, other than plans. Show the results in the chat instead.

This includes any files ending with `_COMPLETE.md`, `_SUMMARY.md`, `_PLAN.md`, `_REPORT.md`. These are temporary working documents created during development and will not be committed to the repository.

**CRITICAL**: Never reference or link temporary LLM activity report files in official documentation.

## Official Documentation Files

Only reference these files in official documentation:

- `README.md` - Main project README
- `CONTRIBUTING.md` - Contribution guidelines
- `LICENSE` - License file
- `docs/**/*.rst` - Sphinx documentation
- `.windsurf/rules/README.md` - Steering rules documentation (internal)

## Documentation Best Practices

### README.md
- Keep it concise and user-focused
- Include: Installation, Quick Start, Features, Links to full docs
- No internal planning or migration details
- No references to temporary files

### CONTRIBUTING.md
- Development setup instructions
- Code style guidelines
- Testing requirements
- PR process

### Sphinx Documentation (docs/)
- Comprehensive API documentation
- Tutorials and guides
- Architecture overview
- No internal planning documents

## When Creating Documentation

1. **User-facing docs** (README, CONTRIBUTING, docs/):
   - Focus on what users need to know
   - Clear, concise, actionable
   - No internal planning or temporary files

2. **Internal docs** (steering rules, planning):
   - Can reference temporary files
   - Not linked from user-facing docs
   - Clearly marked as internal

3. **Temporary files** (reports, summaries, plans):
   - Use for AI agent context only
   - Never commit to repository
   - Never reference in official docs
   - Add to `.gitignore` if needed

## Examples

### ❌ Bad - Don't Do This
```markdown
# README.md

For migration details, see [MIGRATION_TO_UV.md](MIGRATION_TO_UV.md)
For the optimization plan, see [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)
```

### ✅ Good - Do This
```markdown
# README.md

## Development

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest
```

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md)
```

## Checking Documentation

Before committing documentation changes:

1. Search for references to temporary files
2. Ensure only official docs are linked
3. Verify all links point to committed files
4. Remove any internal planning references
