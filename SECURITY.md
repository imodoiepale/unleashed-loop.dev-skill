# Security Policy

This project ships documentation and agent instructions for a **banking API**. That
raises the stakes above a typical developer tool, so the rules below are deliberately
strict.

## Credential handling

The skill instructs agents to follow these rules. If you contribute changes that
weaken them, they will be rejected.

1. **Never commit credentials.** API keys, client secrets, access tokens, account
   numbers, and business email/password pairs belong in environment variables or a
   secret manager — never in source, never in the skill, never in an example.
2. **Never echo a secret back to the user or into a transcript.** Agent transcripts
   are frequently logged, pasted into issues, and shared. Helper scripts in this repo
   redact anything that looks like a token before printing.
3. **Sandbox by default.** Every example, snippet, and helper defaults to Loop's
   sandbox environment. Switching to production must be an explicit, deliberate act by
   the developer.
4. **No money moves without a human.** Agents using this skill are told not to execute
   payment, transfer, or disbursement calls on their own initiative. They draft the
   request and hand it to a human to run.

## Reporting a vulnerability in this repo

Open a [private security advisory](https://github.com/imodoiepale/unleashed-loop.dev-skill/security/advisories/new)
rather than a public issue. Include the affected file, the impact, and a reproduction
if you have one. Expect an initial response within 7 days.

## Reporting a vulnerability in the Loop API itself

This is an **unofficial, community-maintained** project. It is not operated by NCBA or
Loop. Vulnerabilities in the Loop platform should go to Loop/NCBA through their own
support channels, not here.

## Scope note

Nothing in this repository should include working exploit code, credential-harvesting
helpers, or techniques for bypassing Loop's authentication, rate limits, or fraud
controls. Contributions of that nature will be closed.
