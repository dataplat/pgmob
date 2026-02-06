# Agent Steering Rules

This directory contains the source of truth for all AI agent steering rules used across different IDEs.

## File Structure

- `api-standards.md` - API design patterns, method naming, return types, error handling
- `code-conventions.md` - Code formatting, naming conventions, type hints, logging
- `testing-standards.md` - Test organization, AAA pattern, fixtures, coverage requirements
- `security-guidelines.md` - SQL injection prevention, credential management, security best practices
- `project-patterns.md` - Project-specific patterns (adapters, SQL composition, lazy loading, mixins)
- `cicd-workflow.md` - CI/CD workflows, UV commands, Docker builds, release process
- `copilot-instructions.md` - Comprehensive project overview and instructions

## IDE Integration

### Windsurf/Cascade
- Reads directly from `.windsurf/rules/` directory
- Uses `applies_to` frontmatter to scope rules to specific file patterns
- Automatically discovers all `.md` files in the rules directory

### GitHub Copilot
- Symlinks in `.github/instructions/` directory point to `.windsurf/rules/`
- Uses `applyTo` frontmatter to scope rules to specific file patterns
- All rule files are automatically discovered in the instructions directory

### Kiro
- Include files in `.kiro/steering/` use `#[[file:...]]` syntax
- Example: `#[[file:../../.windsurf/rules/api-standards.md]]`
- Frontmatter `inclusion: always` ensures files are always loaded

## Frontmatter Format

Each rule file uses YAML frontmatter with directives for all three IDEs:

```yaml
---
# Kiro: Always include this file
inclusion: always

# Windsurf: Apply to Python files
applies_to:
  - "**/*.py"

# GitHub Copilot: Apply to Python files
applyTo:
  - "**/*.py"
---
```

## Editing Rules

1. Edit files in `.windsurf/rules/` directory (source of truth)
2. Changes automatically propagate to:
   - Windsurf (reads directly)
   - GitHub Copilot (via symlinks in `.github/instructions/`)
   - Kiro (via include syntax)
3. No need to update files in `.kiro/steering/` or `.github/instructions/` manually

## Adding New Rules

1. Create new file in `.windsurf/rules/`
2. Add appropriate frontmatter with `inclusion`, `applies_to`, and `applyTo`
3. Create symlink in `.github/instructions/`: `ln -s ../../.windsurf/rules/newfile.md .github/instructions/newfile.md`
4. Create include file in `.kiro/steering/` with `#[[file:../../.windsurf/rules/newfile.md]]`
5. All three IDEs will automatically discover and use the new rule

## Testing

After making changes:
- Windsurf: Rules apply immediately
- GitHub Copilot: Restart Copilot or reload window
- Kiro: Rules apply on next agent invocation
