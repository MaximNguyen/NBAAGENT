# Setup Guide

Complete setup instructions for the NBA Betting Agent system.

## Prerequisites

- **Python 3.11+** - Required for modern type hints and async features
- **pip** or **pipx** - For package installation
- **Git** - For cloning the repository

Verify your Python version:
```bash
python --version
# Should output: Python 3.11.x or higher
```

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/nba-betting-agent.git
cd nba-betting-agent

# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
nba-ev --help
```

### Dependencies Installed

The following packages are automatically installed:
- `langgraph` - Workflow orchestration
- `langchain-core` - LangChain utilities
- `typer` - CLI framework
- `pydantic` - Data validation
- `httpx` - Async HTTP client
- `tenacity` - Retry logic
- `circuitbreaker` - Fault tolerance
- `nba_api` - NBA statistics
- `diskcache` - Persistent caching
- `scikit-learn` - Probability calibration
- `anthropic` - Claude LLM client
- `langsmith` - Observability
- `structlog` - Structured logging

## API Keys Required

| Service | Required | Free Tier | Get Key |
|---------|----------|-----------|---------|
| The Odds API | Yes | 500 requests/month | [the-odds-api.com](https://the-odds-api.com) |
| Anthropic | Yes | Pay-per-use (~$0.003/query) | [console.anthropic.com](https://console.anthropic.com) |
| LangSmith | No | 5,000 traces/month | [smith.langchain.com](https://smith.langchain.com) |

### Getting The Odds API Key

1. Go to [the-odds-api.com](https://the-odds-api.com)
2. Sign up for a free account
3. Navigate to your dashboard
4. Copy your API key
5. Free tier includes 500 requests/month (sufficient for testing)

### Getting Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account or sign in
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the key (it won't be shown again)

### Getting LangSmith API Key (Optional)

LangSmith provides tracing and debugging for LangGraph workflows.

1. Go to [smith.langchain.com](https://smith.langchain.com)
2. Sign up with your email or GitHub
3. Navigate to Settings > API Keys
4. Create a new API key
5. Create a project for your traces (e.g., "nba-betting-agent")

## Environment Configuration

### Setting Up Your Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual API keys
# On Windows: notepad .env
# On Mac/Linux: nano .env
```

### Environment Variables Reference

#### Required Variables

```bash
# The Odds API - Required for odds data
# Get your key at: https://the-odds-api.com
ODDS_API_KEY=your_odds_api_key_here

# Anthropic API - Required for Claude LLM analysis
# Get your key at: https://console.anthropic.com
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

#### Optional Variables (LangSmith Tracing)

```bash
# Enable LangSmith tracing (disabled by default)
# Set to 'true' to enable - all workflow executions will be traced
LANGSMITH_TRACING=true

# Your LangSmith API key (required if tracing enabled)
LANGSMITH_API_KEY=your_langsmith_api_key_here

# Project name for organizing traces (defaults to 'nba-betting-agent')
# Recommended: Use separate projects for dev/prod
LANGSMITH_PROJECT=nba-betting-agent

# LangSmith API endpoint (defaults to https://api.smith.langchain.com)
# Only change if using self-hosted LangSmith
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

#### Logging Configuration

```bash
# Log mode: 'development' (colored console) or 'production' (JSON)
LOG_MODE=development
```

#### Using Ollama for Free Local Testing

You can use Ollama instead of Claude for development/testing to avoid API costs.

**Step 1: Install Ollama**

Download and install from [ollama.ai](https://ollama.ai):
- Windows: Download installer
- Mac: `brew install ollama`
- Linux: `curl -fsSL https://ollama.ai/install.sh | sh`

**Step 2: Pull a model**

```bash
# Recommended: Llama 3.1 8B (good balance of quality and speed)
ollama pull llama3.1

# Alternative: Smaller/faster model
ollama pull llama3.2

# Alternative: Larger/better quality (requires 16GB+ RAM)
ollama pull llama3.1:70b
```

**Step 3: Configure environment**

```bash
# In your .env file:
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
# OLLAMA_HOST=http://localhost:11434  # Default, only change if needed
```

**Step 4: Run Ollama**

```bash
# Start Ollama service (runs in background)
ollama serve
```

**Switching between providers:**

| Environment | LLM_PROVIDER | Notes |
|-------------|--------------|-------|
| Development | `ollama` | Free, local, faster iteration |
| Production | `anthropic` | Better quality analysis |

```bash
# Quick switch via command line (without editing .env)
LLM_PROVIDER=ollama nba-ev "find best bets tonight"
```

## Verifying Setup

### Test Odds API Connection

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('ODDS_API_KEY')
if key and key != 'your_odds_api_key_here':
    print('Odds API key configured')
else:
    print('ERROR: ODDS_API_KEY not set')
"
```

### Test Anthropic API Connection

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('ANTHROPIC_API_KEY')
if key and key != 'your_anthropic_api_key_here':
    print('Anthropic API key configured')
else:
    print('ERROR: ANTHROPIC_API_KEY not set')
"
```

### Run a Test Query

```bash
# Simple test query
nba-ev analyze "find games tonight" --verbose
```

If everything is configured correctly, you should see:
- Parsed query information
- Odds data from multiple sportsbooks
- Expected value calculations
- Formatted recommendations

## Sportsbook Coverage

The Odds API provides odds from major US sportsbooks:

**Included in Free Tier:**
- DraftKings
- FanDuel
- BetMGM
- Bovada
- PointsBet
- Caesars
- BetRivers
- Unibet
- WynnBET

**May Require Paid Tier:**
- Pinnacle (sharp book - important for edge detection)
- Circa
- Bookmaker
- BetOnline

**Note:** Sharp book access (Pinnacle, Circa) is important for accurate market efficiency analysis. The free tier includes major retail sportsbooks, which is sufficient for finding discrepancies between books.

## Logging Configuration

### Development Mode (Default)

Colored console output optimized for readability:

```bash
LOG_MODE=development
```

Output example:
```
2026-01-29 10:15:23 [info] odds_api_request_completed duration_ms=245
2026-01-29 10:15:24 [info] lines_agent_completed games_count=5
```

### Production Mode

JSON output for log aggregation systems (Datadog, Splunk, etc.):

```bash
LOG_MODE=production
```

Output example:
```json
{"timestamp":"2026-01-29T10:15:23Z","level":"info","event":"odds_api_request_completed","duration_ms":245}
```

## Cache Configuration

The system uses disk-based caching to reduce API calls:

- **Cache Location:** `.cache/nba_stats/`
- **Default TTL:** 5 minutes for odds, 30 minutes for stats
- **Thread-safe:** Multiple processes can read safely

### Clearing the Cache

```bash
# Remove all cached data
rm -rf .cache/nba_stats/

# On Windows PowerShell
Remove-Item -Recurse -Force .cache/nba_stats/
```

## Next Steps

1. Run `nba-ev analyze "find +ev games tonight"` to test the system
2. Check [Troubleshooting](TROUBLESHOOTING.md) if you encounter errors
3. Enable LangSmith tracing to debug workflow execution
4. Review logs to understand agent behavior

## Updating

```bash
# Pull latest changes
git pull origin main

# Reinstall dependencies
pip install -e ".[dev]"
```
