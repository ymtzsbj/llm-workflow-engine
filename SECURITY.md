# Security Policy

## Supported Versions

This project is in early alpha. Security fixes are applied to the latest
release.

## Reporting a Vulnerability

Please do not publish exploit details in a public issue. Use GitHub's private
vulnerability reporting feature for this repository.

## Security Model

The built-in engine is deliberately local-first:

- file operations are restricted to the selected workspace;
- write steps require explicit approval;
- run evidence stores hashes and metadata instead of copied file contents;
- shell execution, network requests, and publishing actions are not built in.

New action proposals that add external side effects must document their threat
model and least-privilege behavior.
