---
name: validation-agent
description: Validates data quality, format, and schema compliance.
metadata:
  type: agent
  dependencies: "filesystem"
---

## Capabilities

- Data completeness checking
- Schema validation
- Format verification (email, URL, date)
- Quality scoring
- Issue reporting

## Input Schema

```json
{
  "data": "any - Data to validate (optional if file_path provided)",
  "file_path": "string - Path to data file (optional)",
  "criteria": {
    "check_completeness": "boolean - Check for null/empty values",
    "check_format": "string - Format to validate (email/url/date)",
    "schema": "object - JSON schema for validation",
    "threshold": "number - Minimum score to pass (default: 0.8)"
  }
}
```

## Output Schema

```json
{
  "passed": "boolean",
  "score": "number - 0.0 to 1.0",
  "threshold": "number",
  "total_issues": "number",
  "critical_issues": "number",
  "warning_issues": "number",
  "issues": [
    {
      "type": "string",
      "field": "string",
      "severity": "critical|warning",
      "message": "string"
    }
  ],
  "summary": "string"
}
```