# Leave System Test Suite

Comprehensive unit and integration tests for the Michaelhouse Leave System.

## Test Structure

```
tests/
├── __init__.py                 # Test package
├── conftest.py                 # Pytest configuration and fixtures
├── test_leave_parser.py        # Parser tests (50+ tests)
├── test_leave_processor.py     # Business logic tests (40+ tests)
├── test_api.py                 # API endpoint tests (20+ tests)
└── README.md                   # This file
```

## Running Tests

### Run All Tests

```bash
cd leave-system
pytest tests/ -v
```

### Run Specific Test File

```bash
# Parser tests
pytest tests/test_leave_parser.py -v

# Processor tests
pytest tests/test_leave_processor.py -v

# API tests
pytest tests/test_api.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=processors --cov=models --cov-report=html
```

This generates an HTML coverage report in `htmlcov/`.

### Run Specific Test

```bash
pytest tests/test_leave_parser.py::TestLeaveRequestParser::test_extract_admin_number -v
```

## Test Categories

### 1. Parser Tests (`test_leave_parser.py`)

Tests the natural language processing:
- Student identifier extraction (admin number, names)
- Leave type determination
- Date parsing (relative and absolute)
- Time application
- Edge cases

**Coverage:** 50+ test cases

### 2. Processor Tests (`test_leave_processor.py`)

Tests the core business logic:
- Parent authentication (WhatsApp & email)
- Student linkage verification
- Leave eligibility checks
- Balance management
- Restriction checking
- Housemaster functions
- Message formatting

**Coverage:** 40+ test cases

### 3. API Tests (`test_api.py`)

Tests the REST API:
- Health check endpoint
- Parent request endpoint
- Housemaster request endpoint
- Error handling
- Response formats
- Input validation

**Coverage:** 20+ test cases

## Writing New Tests

### Example Test Structure

```python
def test_feature_name(self, processor):
    """Test description"""
    # Arrange
    input_data = "test input"

    # Act
    result = processor.some_function(input_data)

    # Assert
    assert result['status'] == 'success'
    assert 'expected_value' in result
```

### Using Fixtures

```python
@pytest.fixture
def processor(self):
    """Create processor for tests"""
    return LeaveProcessor()

def test_with_fixture(self, processor):
    """Test using the fixture"""
    result = processor.process_parent_request(...)
    assert result is not None
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch

def test_with_mock(self, processor, mock_tools):
    """Test with mocked tools"""
    processor.tools = mock_tools
    mock_tools.tool_parent_phone_check.return_value = "PARENT_001"

    result = processor._authenticate_parent("27603174174", "whatsapp")
    assert result['authenticated'] is True
```

## Test Data

All test data uses placeholder values:

### Parents
- `27603174174` → PARENT_001 (John Smith)
- `jane.doe@example.com` → PARENT_002 (Jane Doe)

### Students
- `12345` → James Smith (C Block, Finningley)
- `67890` → Michael Doe (E Block, Shepstone)

### Housemasters
- `hm.finningley@michaelhouse.org` → HM_001
- `27831112222` → HM_001 (phone)

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ -v --cov
```

## Coverage Goals

Target coverage levels:
- **Overall:** > 80%
- **Core processors:** > 90%
- **Models:** 100%
- **API:** > 85%

## Known Issues

1. Database integration tests require running PostgreSQL
2. Some date-dependent tests may fail near term boundaries
3. Mock tests don't validate actual database queries

## Future Tests

Planned test additions:
- [ ] Integration tests with real database
- [ ] Load tests (concurrent requests)
- [ ] Security tests (SQL injection, XSS)
- [ ] Performance benchmarks
- [ ] End-to-end WhatsApp integration tests
- [ ] Email parsing tests

## Debugging Failed Tests

### View Test Output

```bash
pytest tests/ -v -s  # -s shows print statements
```

### Run with Debugger

```bash
pytest tests/test_leave_processor.py --pdb
```

This drops into debugger on first failure.

### Check Test Logs

```bash
pytest tests/ -v --log-cli-level=DEBUG
```

## Best Practices

1. **Test one thing per test** - Each test should verify a single behavior
2. **Use descriptive names** - Test names should explain what's being tested
3. **Arrange-Act-Assert** - Follow the AAA pattern
4. **Don't test implementation** - Test behavior, not internal details
5. **Use fixtures** - Share setup code between tests
6. **Mock external dependencies** - Tests should be fast and isolated

## Performance

Typical test run times:
- Parser tests: ~2 seconds
- Processor tests: ~3 seconds
- API tests: ~2 seconds
- **Total:** < 10 seconds

## Support

For test-related questions:
- Check pytest documentation: https://docs.pytest.org/
- Review existing tests for patterns
- See `conftest.py` for available fixtures

---

**Status:** 110+ tests implemented
**Coverage:** > 80% of core code
