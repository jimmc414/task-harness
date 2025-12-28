# Session Kickoff: Build Global Codebase Review Plugin

## Your Mission

Build a Claude Code plugin called `codebase-review` that performs comprehensive code review on **entire codebases** (not just PR diffs).

## Read First

Read the detailed specification in `prompts/global-code-review-plugin-spec.md` - it contains:
- Architectural insights extracted from Anthropic's official code-review plugin
- Multi-agent parallel architecture design
- Confidence-based scoring system (0-100 scale)
- False positive exclusion rules
- Proposed 6-8 agent specializations
- Orchestration flow
- Output format standards
- Implementation phases

## Key Patterns to Follow

From Anthropic's code-review plugin:

1. **Model selection by task**: Haiku for orchestration/scoring, Sonnet for analysis
2. **Parallel specialized agents**: Each agent has ONE focus area
3. **Confidence scoring**: 0-100 scale, threshold at 80 for PR (60 for codebase)
4. **Explicit exclusions**: Define what NOT to report to reduce noise
5. **Redundancy for critical checks**: Use 2 agents for security

## Quick Start

```bash
# Create plugin structure
mkdir -p plugins/codebase-review/{.claude-plugin,commands,agents,scoring}

# Start with plugin.json manifest
# Then implement main command
# Then individual agent prompts
# Finally scoring/filtering logic
```

## Deliverables

1. Working plugin installable via `/plugin install codebase-review`
2. Main command `/codebase-review` with options
3. 6-8 specialized agent prompts
4. Confidence scoring and filtering
5. Markdown report generation
6. README with usage docs

## Reference Implementation

Study: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review

Good luck!
