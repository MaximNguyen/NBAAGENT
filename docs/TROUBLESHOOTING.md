# Troubleshooting Guide

Solutions to common issues with the NBA Betting Agent system.

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ODDS_API_KEY not found` | Missing .env file or environment variable | Copy `.env.example` to `.env` and add your key |
| `ANTHROPIC_API_KEY not found` | Missing Anthropic API key | Add your Anthropic key to `.env` |
| `401 Unauthorized` from Odds API | Invalid or expired API key | Verify your key at [the-odds-api.com](https://the-odds-api.com) |
| `429 Too Many Requests` | Rate limit exceeded | Wait 1 minute, then reduce request frequency |
| `No games found` | No NBA games scheduled | Check NBA schedule - may be off-season or off day |
| `Circuit breaker open` | Repeated API failures | Wait 5 minutes for automatic recovery |
| `ModuleNotFoundError` | Missing dependency | Run `pip install -e ".[dev]"` |
| `Connection timeout` | Network issue or API down | Check internet connection and API status |

## API Issues

### The Odds API

**Empty Response (No Games)**
- Verify NBA season is active (October through June)
- Check if there are games scheduled today
- Verify region parameter is set to "us"
- Check remaining API credits in response headers

**401 Unauthorized**
```bash
# Verify your API key is set correctly
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Key starts with:', os.getenv('ODDS_API_KEY', 'NOT_SET')[:8])
"
```
- Key should start with a valid prefix
- Regenerate key at the-odds-api.com if needed

**429 Rate Limited**
- Free tier: 500 requests/month
- Check remaining quota in API response headers
- Consider upgrading to paid tier for more requests

**Missing Sportsbooks**
- Some books may not be available in your region
- Sharp books (Pinnacle) may require paid tier
- Check API documentation for available books

### Anthropic Claude API

**401 Invalid API Key**
- Verify key at [console.anthropic.com](https://console.anthropic.com)
- Regenerate if key was revoked
- Check for extra whitespace in .env file

**Rate Limit Errors**
- Default tier has per-minute limits
- Implement backoff in heavy usage scenarios
- Contact Anthropic to increase limits

**API Status**
- Check [status.anthropic.com](https://status.anthropic.com) for outages
- Claude API may have maintenance windows

**Model Errors**
- System uses `claude-sonnet-4-20250514` model
- Ensure your API key has access to this model

## Cache Issues

### Stale Data Being Used

The system returns cached data when available to reduce API calls.

**Cache Location:** `.cache/nba_stats/`

**Clear All Cache:**
```bash
# Mac/Linux
rm -rf .cache/nba_stats/

# Windows PowerShell
Remove-Item -Recurse -Force .cache/nba_stats/

# Windows Command Prompt
rmdir /s /q .cache\nba_stats
```

**Check Cache Age:**
Look for timestamps in log output to verify freshness.

### Cache Lock Errors

**Symptom:** `PermissionError` or `LockError` when accessing cache

**Cause:** Multiple processes accessing cache simultaneously

**Solutions:**
1. Run only one instance of nba-ev at a time
2. Clear cache and restart
3. Increase cache timeout in configuration

### Disk Space

**Symptom:** Cache write failures

**Solution:**
```bash
# Check cache size
du -sh .cache/nba_stats/  # Mac/Linux
```

Clear old cache files if disk is full.

## LangSmith Issues

### Traces Not Appearing

1. **Verify tracing is enabled:**
   ```bash
   echo $LANGSMITH_TRACING  # Should be 'true'
   ```

2. **Check API key:**
   ```bash
   python -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   key = os.getenv('LANGSMITH_API_KEY', 'NOT_SET')
   print('LangSmith key configured:', key != 'NOT_SET' and len(key) > 10)
   "
   ```

3. **Verify project exists:**
   - Log into [smith.langchain.com](https://smith.langchain.com)
   - Check that your project name matches `LANGSMITH_PROJECT`
   - Create the project if it doesn't exist

4. **Check for errors in output:**
   Enable verbose mode to see tracing errors:
   ```bash
   nba-ev analyze "test" --verbose
   ```

### Quota Exceeded

**Free Tier Limits:** 5,000 traces/month

**Solutions:**
- Use separate projects for dev/prod
- Disable tracing for local development:
  ```bash
  LANGSMITH_TRACING=false
  ```
- Upgrade to paid tier for more traces

### Connection Issues

If traces upload slowly or fail:
- Check network connectivity
- Verify firewall allows outbound HTTPS
- Try alternative endpoint if using self-hosted

## Performance Issues

### Slow Response Times

**Normal Execution Time:** 5-15 seconds

**If slower than expected:**

1. **Check cache hit rate** in logs:
   ```
   cache_hit=true  # Good - using cached data
   cache_hit=false # Cache miss - making API call
   ```

2. **Verify parallel execution:**
   Lines and Stats agents should run concurrently.
   Look for timing in verbose output.

3. **API rate limits:**
   Throttled requests take longer due to backoff.

4. **Network latency:**
   Test direct API calls to isolate:
   ```bash
   curl -I https://api.the-odds-api.com
   ```

### High Memory Usage

**Causes:**
- Large response caching
- Many concurrent requests
- Memory leaks in long-running sessions

**Solutions:**
- Clear cache periodically
- Restart between large batch operations
- Reduce cache size in configuration

### CPU Spikes

**Cause:** Probability calculations and model inference

**Normal behavior:** Brief spikes during analysis phase

**If sustained:**
- Check for infinite loops in custom code
- Verify scikit-learn version compatibility

## Environment Issues

### Wrong Python Version

```bash
# Check version
python --version

# Use specific version
python3.11 -m pip install -e ".[dev]"
```

### Virtual Environment Conflicts

```bash
# Create fresh virtual environment
python -m venv venv

# Activate (Mac/Linux)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate

# Install fresh
pip install -e ".[dev]"
```

### PATH Issues

If `nba-ev` command not found after installation:

```bash
# Check if scripts directory is in PATH
pip show nba-betting-agent | grep Location

# Or run as module
python -m nba_betting_agent.cli.main analyze "test"
```

## Getting Help

### Collecting Debug Information

When reporting issues, include:

1. **Python version:** `python --version`
2. **Package versions:** `pip list | grep -E "(langgraph|langchain|anthropic)"`
3. **Full error traceback**
4. **Steps to reproduce**
5. **Relevant log output** (with sensitive keys redacted)

### Log Files

Enable detailed logging:
```bash
LOG_MODE=development nba-ev analyze "test" --verbose
```

JSON logs for production debugging:
```bash
LOG_MODE=production nba-ev analyze "test" 2>&1 | tee debug.log
```

### Filing Issues

When creating a GitHub issue:

1. Use a descriptive title
2. Include environment information
3. Provide minimal reproduction steps
4. Attach relevant log output
5. Describe expected vs actual behavior

### Common Fixes Checklist

Before filing an issue, try:
- [ ] Clear cache: `rm -rf .cache/nba_stats/`
- [ ] Reinstall: `pip install -e ".[dev]" --force-reinstall`
- [ ] Check .env file has correct keys
- [ ] Verify APIs are up (status pages)
- [ ] Try fresh virtual environment
- [ ] Check NBA schedule for games
