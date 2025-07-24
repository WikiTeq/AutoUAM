# AutoUAM Testing Guide

This document provides comprehensive information about testing the AutoUAM project, including unit tests, integration tests, and end-to-end testing strategies.

## Test Structure

```
tests/
├── test_config.py          # Configuration validation tests
├── test_monitor.py         # Load monitoring tests
├── test_integration.py     # Integration tests
└── mock_cloudflare_server.py  # Mock Cloudflare API server
```

## Running Tests

### Prerequisites

```bash
# Install development dependencies
pip install -e ".[dev]"

# Activate virtual environment (if using one)
source venv/bin/activate
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=autouam --cov-report=term-missing --cov-report=html

# Run specific test categories
pytest tests/test_monitor.py      # Unit tests only
pytest tests/test_integration.py  # Integration tests only
pytest tests/test_config.py       # Configuration tests only

# Run with verbose output
pytest -v

# Run with async support
pytest --asyncio-mode=auto
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=autouam --cov-report=html --cov-report=xml

# View coverage in browser
open htmlcov/index.html
```

## Unit Tests

### Configuration Tests (`test_config.py`)

Tests for configuration validation and management:

- **CloudflareConfig**: API token and zone ID validation
- **LoadThresholds**: Threshold validation and constraints
- **MonitoringConfig**: Monitoring parameters validation
- **LoggingConfig**: Logging configuration validation
- **Settings**: Complete configuration object validation
- **Validators**: Configuration validation functions

**Key Test Cases:**
- Valid configuration acceptance
- Invalid parameter rejection
- Environment variable substitution
- File loading and parsing
- Configuration serialization

### Load Monitor Tests (`test_monitor.py`)

Tests for system load monitoring functionality:

- **LoadAverage**: Load average data structure
- **LoadMonitor**: System load monitoring logic

**Key Test Cases:**
- Load average parsing from `/proc/loadavg`
- CPU count detection from `/proc/cpuinfo`
- Normalized load calculation
- Load threshold evaluation
- Error handling for invalid data
- Platform-specific behavior

## Integration Tests

### UAM Manager Integration (`test_integration.py`)

Tests for the core UAM management functionality:

- **Initialization**: UAM manager setup and Cloudflare client initialization
- **Manual Control**: Manual UAM enable/disable operations
- **Single Check**: One-time load evaluation and action
- **Error Handling**: API error and rate limiting scenarios
- **Rate Limiting**: Cloudflare API rate limit handling

**Key Test Cases:**
- Successful UAM manager initialization
- Manual UAM enable/disable operations
- Load-based automatic UAM control
- Cloudflare API error handling
- Rate limiting and retry logic

### Health Checker Integration

Tests for health monitoring functionality:

- **All Systems Healthy**: Normal operation scenario
- **API Unhealthy**: Cloudflare API connectivity issues

**Key Test Cases:**
- Complete health check with all systems operational
- Health check failure when Cloudflare API is unavailable
- System load monitoring integration
- UAM state monitoring integration

### Configuration Integration

Tests for configuration system integration:

- **File Loading**: Configuration file parsing and validation
- **Environment Variables**: Environment variable substitution

**Key Test Cases:**
- YAML configuration file loading
- Environment variable substitution in configuration
- Configuration validation and error handling

### State Persistence Integration

Tests for state management functionality:

- **File Persistence**: State saving and loading from files
- **Minimum Duration**: UAM minimum duration enforcement

**Key Test Cases:**
- State persistence to JSON files
- State loading from files
- Minimum UAM duration logic
- State transition tracking

## Mock Cloudflare Server

The project includes a mock Cloudflare API server for testing:

### Features

- **Authentication**: Token validation
- **Rate Limiting**: Simulated rate limiting responses
- **Error Handling**: Various error response scenarios
- **Security Level Management**: UAM enable/disable operations

### Usage

```python
from tests.mock_cloudflare_server import MockCloudflareServer

# Start mock server
server = MockCloudflareServer(port=8081)
await server.start()

# Use in tests
# ... test code ...

# Stop server
await server.stop()
```

## End-to-End Testing

### Test Script (`test_end_to_end.py`)

A comprehensive end-to-end test script that:

1. **Starts Mock Server**: Launches the mock Cloudflare API server
2. **Runs AutoUAM**: Executes AutoUAM against the mock server
3. **Simulates Scenarios**: Tests various load and error conditions
4. **Validates Results**: Ensures correct behavior in all scenarios

### Test Scenarios

- **Initialization**: System startup and configuration loading
- **Health Checks**: Health monitoring functionality
- **Manual Control**: Manual UAM enable/disable
- **High Load**: Automatic UAM activation under high load
- **Low Load**: Automatic UAM deactivation under normal load
- **Error Handling**: System behavior during API failures

## Testing Best Practices

### Mocking Strategy

1. **Import-Level Patching**: Mock at the import location where classes are used
2. **Async Context Managers**: Properly mock `__aenter__` and `__aexit__` methods
3. **State Isolation**: Use temporary directories for state persistence tests
4. **Time Mocking**: Mock `time.time()` for time-dependent tests

### Test Data Management

```python
# Use fixtures for common test data
@pytest.fixture
def mock_settings():
    return Settings(
        cloudflare={
            "api_token": "test_token",
            "zone_id": "test_zone_id"
        },
        # ... other settings
    )

# Use temporary files/directories
with tempfile.TemporaryDirectory() as temp_dir:
    # Test code here
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_function():
    # Async test code
    result = await some_async_function()
    assert result == expected_value
```

### Error Testing

```python
# Test for specific exceptions
with pytest.raises(ValueError, match="Invalid configuration"):
    Settings(cloudflare={"api_token": ""})

# Test error handling
result = await function_that_might_fail()
assert result["error"] == "Expected error message"
```

## Continuous Integration

### GitHub Actions

The project includes GitHub Actions workflows for:

- **Test Execution**: Run all tests on push/PR
- **Code Quality**: Linting, formatting, and type checking
- **Coverage Reporting**: Generate and publish coverage reports
- **Release Management**: Automated releases

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Debugging Tests

### Verbose Output

```bash
# Enable verbose pytest output
pytest -v -s

# Show local variables on failure
pytest --tb=long
```

### Debugging Specific Tests

```bash
# Run single test with debug output
pytest tests/test_integration.py::TestUAMManagerIntegration::test_uam_manager_initialization -v -s

# Run tests matching pattern
pytest -k "test_uam_manager" -v
```

### Coverage Analysis

```bash
# Generate detailed coverage report
pytest --cov=autouam --cov-report=term-missing --cov-report=html

# Focus on specific modules
pytest --cov=autouam.core --cov-report=term-missing
```

## Test Maintenance

### Adding New Tests

1. **Unit Tests**: Add to appropriate test file in `tests/`
2. **Integration Tests**: Add to `tests/test_integration.py`
3. **Fixtures**: Create reusable fixtures for common test data
4. **Documentation**: Update this guide for new test patterns

### Test Naming Conventions

- **Unit Tests**: `test_<function_name>_<scenario>`
- **Integration Tests**: `test_<component>_<operation>_<scenario>`
- **Test Classes**: `Test<ComponentName>`

### Test Data

- Use realistic but safe test data
- Avoid hardcoded credentials
- Use environment variables for sensitive data
- Clean up test artifacts

## Performance Testing

### Load Testing

```bash
# Run performance benchmarks
pytest tests/test_performance.py

# Monitor resource usage during tests
pytest --durations=10
```

### Memory Testing

```bash
# Check for memory leaks
pytest --memray
```

## Security Testing

### Input Validation

- Test boundary conditions
- Test invalid input handling
- Test injection attacks
- Test authentication bypass attempts

### Configuration Security

- Test secure credential handling
- Test file permission validation
- Test environment variable security

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Async Test Failures**: Check `@pytest.mark.asyncio` decorators
3. **Mock Failures**: Verify import paths for patching
4. **State Persistence**: Check file permissions and paths

### Test Environment

```bash
# Clean test environment
rm -rf .pytest_cache/
rm -rf htmlcov/
rm -rf .coverage

# Reinstall dependencies
pip install -e ".[dev]"
```

## Contributing to Tests

When contributing to the test suite:

1. **Follow Patterns**: Use existing test patterns and conventions
2. **Add Coverage**: Ensure new code is adequately tested
3. **Update Documentation**: Keep this guide current
4. **Review Coverage**: Aim for high test coverage
5. **Performance**: Ensure tests run efficiently

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
