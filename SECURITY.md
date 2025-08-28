# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it to the maintainers immediately.

## Security Measures Implemented

### 1. Environment Variables & Secrets Management
- All sensitive credentials stored in environment variables
- `.env` file properly gitignored to prevent credential exposure
- GitHub Actions uses encrypted secrets for CI/CD
- No hardcoded API keys or passwords in source code

### 2. HTTPS/TLS Enforcement
- All external API calls use HTTPS with certificate verification (`verify=True`)
- OpenAI API: HTTPS enforced
- Slack webhooks: HTTPS enforced  
- Push notification services: HTTPS enforced
- Supabase: HTTPS enforced

### 3. Input Validation & Sanitization
- URL validation with allowed schemes (http/https only)
- Trusted domain allowlist for RSS feeds
- Content sanitization using `html.escape()`
- Maximum URL length limits (2048 chars)
- SQL injection prevention via parameterized queries

### 4. Database Security
- Uses Supabase REST API (no direct SQL injection risk)
- Connection string password injection protection
- Automatic cleanup of old records to prevent data accumulation

### 5. Dependencies
- Regular dependency updates
- Cryptography library for secure operations
- No known vulnerable packages

## Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` for templates
2. **Rotate API keys regularly** - Especially after any potential exposure
3. **Use GitHub Secrets** - For all CI/CD credentials
4. **Monitor logs** - Check for suspicious activity
5. **Update dependencies** - Keep all packages current

## Incident Response

If credentials are compromised:
1. Immediately rotate all affected API keys
2. Review access logs for unauthorized usage
3. Update GitHub repository secrets
4. Notify all team members
