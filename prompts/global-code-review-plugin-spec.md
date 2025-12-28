# Global Codebase Review Plugin - Implementation Prompt

## Context

You are building a Claude Code plugin that performs comprehensive code review on an **entire codebase** (not just PR diffs). This is inspired by Anthropic's official `code-review` plugin but adapted for full project analysis.

## Architectural Insights from Anthropic's code-review Plugin

### 1. Multi-Agent Parallel Architecture
The official plugin uses **5 parallel agents** with different specializations:
- Agent #1: CLAUDE.md/guideline compliance
- Agent #2: Shallow scan for obvious bugs (excluding nitpicks)
- Agent #3: Git blame/history context analysis
- Agent #4: Previous PR comments on same files
- Agent #5: Code comment compliance

**Key insight**: Redundancy improves accuracy. They use TWO agents for compliance checking because it's the most important aspect.

### 2. Model Selection by Task Complexity
- **Haiku** (fast/cheap): Pre-flight checks, eligibility, scoring, filtering
- **Sonnet** (balanced): The actual review analysis work

**Key insight**: Use cheaper models for orchestration/scoring, expensive models for deep analysis.

### 3. Confidence-Based Scoring System
Each issue is scored 0-100:
- 0 = false positive
- 25 = possibly an issue
- 50 = moderate confidence
- 75 = highly likely
- 100 = absolutely certain

Only issues scoring **≥80** are reported. This dramatically reduces noise.

### 4. Explicit False Positive Exclusions
The plugin explicitly filters out:
- Pre-existing issues (not introduced by changes)
- Styling nitpicks
- Compiler-catchable errors
- Linter violations (use a linter instead)
- Undeclared CLAUDE.md requirements
- Likely-intentional changes
- Unmodified lines

**Key insight**: Being explicit about what NOT to report is as important as what to report.

### 5. Output Format Standards
- Brief, emoji-free comments
- Full SHA1 hashes in code links
- Include context lines before/after
- Link format: `https://github.com/owner/repo/blob/[SHA]/path#L[start]-L[end]`

### 6. Pre-flight Eligibility Checks
Before doing expensive work, cheap checks determine if review is needed/possible.

---

## Your Task: Build a Global Codebase Review Plugin

### Plugin Name
`codebase-review` or `project-audit`

### Core Differences from PR Review
| PR Review | Codebase Review |
|-----------|-----------------|
| Reviews diff between branches | Reviews all code in repository |
| Focuses on "what changed" | Focuses on "what exists" |
| Quick (small scope) | Comprehensive (large scope) |
| Runs on PR branches | Runs on any branch/state |

### Proposed Agent Architecture

Use **6-8 parallel specialized agents**:

| Agent | Focus Area | Model |
|-------|------------|-------|
| Agent 1 | **Security vulnerabilities** - OWASP Top 10, secrets in code, injection risks | Sonnet |
| Agent 2 | **Error handling** - Missing try/catch, unhandled promises, silent failures | Sonnet |
| Agent 3 | **Code architecture** - SOLID violations, tight coupling, circular dependencies | Sonnet |
| Agent 4 | **Test coverage gaps** - Untested edge cases, missing unit tests, dead code | Sonnet |
| Agent 5 | **Documentation quality** - Missing docstrings, outdated comments, unclear APIs | Haiku |
| Agent 6 | **Performance concerns** - N+1 queries, memory leaks, inefficient algorithms | Sonnet |
| Agent 7 | **Consistency** - Naming conventions, code style, pattern adherence | Haiku |
| Agent 8 | **Dependencies** - Outdated packages, security vulnerabilities, unused deps | Haiku |

### Orchestration Flow

```
Step 1: [Haiku] Pre-flight checks
        - Is this a valid git repo?
        - What language(s)/framework(s)?
        - How many files? (scope estimation)
        - Any existing CLAUDE.md or guidelines?

Step 2: [Haiku] Build file manifest
        - Group files by type/directory
        - Prioritize: src/ > lib/ > utils/ > tests/
        - Estimate review chunks

Step 3: [Haiku] Gather context
        - Read CLAUDE.md files
        - Read package.json/pyproject.toml/etc.
        - Identify framework conventions

Step 4: [Sonnet x N] Parallel agent reviews
        - Each agent reviews ALL relevant files
        - Each produces structured findings
        - Each scores own findings 0-100

Step 5: [Haiku] Score consolidation
        - Deduplicate overlapping findings
        - Re-score consolidated issues
        - Apply 80+ threshold

Step 6: [Haiku] Categorize and prioritize
        - Group by severity: Critical > High > Medium > Low
        - Group by file/module
        - Create executive summary

Step 7: [Sonnet] Generate final report
        - Executive summary
        - Critical issues (immediate action)
        - Improvement opportunities
        - Architecture recommendations
```

### Confidence Scoring Calibration

Adapt the 0-100 scale for codebase review:

```
0-20:   Stylistic preference, not an issue
21-40:  Minor improvement opportunity
41-60:  Moderate concern, should address
61-80:  Significant issue, prioritize
81-100: Critical issue, fix immediately
```

**Threshold**: Report issues ≥60 (lower than PR review since we're doing comprehensive audit)

### False Positive Exclusions for Codebase Review

Explicitly DO NOT report:
- Issues that linters/formatters catch (ESLint, Black, etc.)
- Type errors that TypeScript/mypy catch
- Import sorting issues
- Trailing whitespace / line length
- TODO comments (unless security-related)
- Vendored/third-party code in vendor/ or node_modules/
- Generated code (*.generated.*, migrations, etc.)
- Test fixtures and mock data
- Configuration files (unless security risk)

### Output Format

```markdown
# Codebase Review Report

## Executive Summary
- **Overall Health Score**: 72/100
- **Critical Issues**: 3
- **High Priority**: 12
- **Medium Priority**: 28
- **Files Reviewed**: 156
- **Review Duration**: 4m 32s

## Critical Issues (Fix Immediately)

### 1. SQL Injection Vulnerability
**Confidence**: 95/100
**File**: src/database/queries.py:45-52

[code block with context]

**Issue**: User input directly concatenated into SQL query.
**Fix**: Use parameterized queries.
**Reference**: https://owasp.org/...

---

## High Priority Issues
...

## Architecture Recommendations
...

## Test Coverage Gaps
...
```

### Plugin File Structure

```
plugins/codebase-review/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── codebase-review.md      # Main command
├── agents/
│   ├── security-agent.md       # Agent prompts
│   ├── error-handling-agent.md
│   ├── architecture-agent.md
│   ├── testing-agent.md
│   ├── documentation-agent.md
│   ├── performance-agent.md
│   ├── consistency-agent.md
│   └── dependencies-agent.md
├── scoring/
│   └── confidence-calibration.md
└── README.md
```

### Key Implementation Considerations

1. **Chunking Strategy**: For large codebases, chunk files intelligently:
   - By directory/module
   - By file type
   - Max ~50 files per agent invocation

2. **Context Window Management**:
   - Don't try to fit entire codebase in one prompt
   - Use file summaries for cross-file analysis
   - Deep-dive only on flagged files

3. **Caching**:
   - Cache file hashes
   - Skip unchanged files on re-runs
   - Store previous review results

4. **Progress Reporting**:
   - Show which agent is running
   - Show completion percentage
   - Estimated time remaining

5. **Configurable Scope**:
   - `--include-tests` flag
   - `--security-only` for quick security audit
   - `--directory src/` to scope to specific path
   - `--severity-threshold 60` to adjust reporting

6. **Integration Options**:
   - Output as Markdown report
   - Output as JSON for CI/CD
   - Create GitHub issues for critical findings
   - Post summary to PR if on branch

### CLI Interface

```bash
# Full codebase review
/codebase-review

# Security-focused quick audit
/codebase-review --security-only

# Review specific directory
/codebase-review --directory src/api/

# Adjust confidence threshold
/codebase-review --threshold 70

# Output as JSON for CI
/codebase-review --format json > review.json

# Create GitHub issues for critical findings
/codebase-review --create-issues
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- Plugin manifest and command structure
- File discovery and chunking logic
- Basic orchestration flow

### Phase 2: Agent Implementation
- Security agent (highest priority)
- Error handling agent
- Architecture agent

### Phase 3: Scoring and Filtering
- Confidence scoring implementation
- Deduplication logic
- Threshold filtering

### Phase 4: Reporting
- Markdown report generation
- Executive summary logic
- Code linking with context

### Phase 5: Advanced Features
- Caching and incremental reviews
- CI/CD integration
- GitHub issue creation

---

## Questions to Resolve During Implementation

1. **Scope limits**: Max files before chunking? Max total review size?
2. **Language detection**: Auto-detect or require config?
3. **Framework awareness**: How deep should framework-specific rules go?
4. **Custom rules**: Allow users to define project-specific checks?
5. **Baseline**: Compare against previous review for delta?

---

## References

- Anthropic's code-review plugin: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review
- OWASP Top 10: https://owasp.org/Top10/
- Claude Code Plugin Docs: https://code.claude.com/docs/en/plugin-marketplaces

---

## Success Criteria

A successful implementation should:
1. Complete review of 500-file codebase in <10 minutes
2. Achieve <20% false positive rate on critical issues
3. Catch common security vulnerabilities (SQLi, XSS, secrets)
4. Produce actionable, specific recommendations
5. Work across Python, JavaScript, TypeScript, Go codebases
6. Integrate cleanly with existing Claude Code workflow
