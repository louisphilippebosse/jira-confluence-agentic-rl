# Security Policy

## Security Principles

This project is built with a **security-first** approach:

1. **Read-Only Access**: All Jira and Confluence integrations are read-only by design
2. **No Data Storage**: Jira/Confluence data is never persisted (only conversation history)
3. **Environment-Based Secrets**: All sensitive data in environment variables
4. **Minimal Permissions**: Services only request necessary permissions
5. **CORS Protection**: Configurable allowed origins
6. **Input Validation**: All inputs validated and sanitized

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email security concerns to the maintainers
3. Include detailed steps to reproduce
4. Allow time for a fix before public disclosure

## Security Best Practices

### For Deployment

1. **Change Default Secrets**
   ```bash
   # Generate a strong secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Use Environment Variables**
   - Never commit `.env` files
   - Use secret management services in production
   - Rotate API keys regularly

3. **Configure CORS Properly**
   ```env
   ALLOWED_ORIGINS=https://your-domain.com
   ```

4. **Use HTTPS**
   - Always use HTTPS in production
   - Configure proper SSL/TLS certificates

5. **Limit API Token Permissions**
   - Use API tokens with minimal permissions
   - Create dedicated service accounts
   - Audit token usage regularly

### For Development

1. **Keep Dependencies Updated**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

2. **Review Code Changes**
   - Never commit secrets
   - Use `.gitignore` properly
   - Review all external dependencies

3. **Test Security Features**
   - Verify read-only behavior
   - Test CORS restrictions
   - Validate input sanitization

## Security Checklist

Before deploying to production:

- [ ] All secrets in environment variables
- [ ] `.env` file not committed to git
- [ ] Strong SECRET_KEY generated
- [ ] CORS configured for your domain
- [ ] HTTPS enabled
- [ ] API tokens have minimal permissions
- [ ] Dependencies updated to latest versions
- [ ] Logs don't contain sensitive data
- [ ] Database file permissions are restricted
- [ ] Health check endpoint is public only

## Known Limitations

1. **Authentication**: No built-in user authentication (add OAuth/JWT for multi-user)
2. **Rate Limiting**: No rate limiting on API endpoints (add in production)
3. **Audit Logging**: Basic logging only (enhance for compliance)

## Incident Response

If a security incident occurs:

1. Immediately rotate all API tokens
2. Review logs for suspicious activity
3. Update affected systems
4. Document the incident
5. Notify affected users

## Compliance

This system:
- ✅ Uses read-only API access
- ✅ Doesn't store sensitive Jira/Confluence data
- ✅ Encrypts data in transit (when HTTPS is used)
- ✅ Provides audit trail (conversation logs)
- ⚠️ Doesn't include built-in authentication (add as needed)
- ⚠️ Doesn't include data encryption at rest (add as needed)

## Security Updates

- Check for security advisories regularly
- Subscribe to security mailing lists for dependencies
- Keep Python and all packages updated
- Monitor CVE databases for vulnerabilities

---

Last updated: 2026-01-26
