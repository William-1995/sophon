"""Cowork validation agent: completeness, format, and optional schema checks."""

from typing import Any, Dict, List
import json

from core.cowork import AgentContext, AgentResult, AgentExecutor


class ValidationExecutor(AgentExecutor):
    """Score in-memory or file-backed payloads against ``criteria``."""

    async def execute(
        self,
        context: AgentContext,
        task: Dict[str, Any],
    ) -> AgentResult:
        """Validate ``data`` or load ``file_path``, then apply configured checks.

        Args:
            context (AgentContext): Agent runtime context.
            task (dict[str, Any]): ``data`` and/or ``file_path``; ``criteria`` for checks and ``threshold``.

        Returns:
            AgentResult: ``output`` with score, issues, and pass/fail.
        """
        data = task.get("data")
        file_path = task.get("file_path")
        criteria = task.get("criteria", {})
        
        if not data and not file_path:
            return AgentResult(
                success=False,
                error_message="No data or file path provided for validation",
            )
        
        try:
            # Load data if file path provided
            if file_path and not data:
                data = await self._load_file(file_path)
                if isinstance(data, AgentResult):  # Error case
                    return data
            
            # Run validations
            issues = []
            score = 1.0
            
            # Check completeness
            if criteria.get("check_completeness", True):
                completeness_issues = self._check_completeness(data)
                issues.extend(completeness_issues)
            
            # Check format
            if criteria.get("check_format"):
                format_issues = self._check_format(data, criteria["check_format"])
                issues.extend(format_issues)
            
            # Check schema
            if criteria.get("schema"):
                schema_issues = self._check_schema(data, criteria["schema"])
                issues.extend(schema_issues)
            
            # Calculate score
            if issues:
                # Deduct score based on issue severity
                critical = sum(1 for i in issues if i.get("severity") == "critical")
                warning = sum(1 for i in issues if i.get("severity") == "warning")
                score = max(0.0, 1.0 - (critical * 0.3) - (warning * 0.1))
            
            # Determine if passed
            threshold = criteria.get("threshold", 0.8)
            passed = score >= threshold
            
            return AgentResult(
                success=passed,
                output={
                    "passed": passed,
                    "score": round(score, 2),
                    "threshold": threshold,
                    "total_issues": len(issues),
                    "critical_issues": sum(1 for i in issues if i.get("severity") == "critical"),
                    "warning_issues": sum(1 for i in issues if i.get("severity") == "warning"),
                    "issues": issues,
                    "summary": self._generate_summary(issues, score, passed),
                },
            )
            
        except Exception as e:
            import traceback
            print(f"[VALIDATOR] Exception: {e}")
            print(traceback.format_exc())
            return AgentResult(
                success=False,
                error_message=f"Validation failed: {str(e)}",
            )
    
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "data_validation",
            "quality_checking",
            "schema_validation",
            "completeness_check",
            "format_verification",
        ]
    
    async def _load_file(self, file_path: str) -> Any:
        """Load data from file."""
        from core.execution.bridge import execute_skill
        
        # Try to read as JSON first
        result = await execute_skill(
            skill_name="filesystem",
            action="read",
            arguments={"path": file_path},
        )
        
        if result.get("error"):
            return AgentResult(
                success=False,
                error_message=f"Failed to load file: {result['error']}",
            )
        
        content = result.get("content", "")
        
        # Try parsing as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Return as string
            return content
    
    def _check_completeness(self, data: Any) -> List[Dict[str, Any]]:
        """Check for missing/null values."""
        issues = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None or value == "":
                    issues.append({
                        "type": "missing_value",
                        "field": key,
                        "severity": "critical",
                        "message": f"Field '{key}' is empty or null",
                    })
                elif isinstance(value, (dict, list)):
                    nested_issues = self._check_completeness(value)
                    for issue in nested_issues:
                        issue["field"] = f"{key}.{issue.get('field', '')}"
                        issues.append(issue)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                item_issues = self._check_completeness(item)
                for issue in item_issues:
                    issue["field"] = f"[{i}].{issue.get('field', '')}"
                    issues.append(issue)
        
        return issues
    
    def _check_format(self, data: Any, format_spec: str) -> List[Dict[str, Any]]:
        """Check data format against specification."""
        issues = []
        
        format_spec = format_spec.lower()
        
        if format_spec == "email":
            if isinstance(data, str) and "@" not in data:
                issues.append({
                    "type": "format_error",
                    "field": "root",
                    "severity": "critical",
                    "message": "Invalid email format",
                })
        
        elif format_spec == "url":
            if isinstance(data, str) and not data.startswith(("http://", "https://")):
                issues.append({
                    "type": "format_error",
                    "field": "root",
                    "severity": "critical",
                    "message": "Invalid URL format",
                })
        
        elif format_spec == "date":
            # Basic date format check
            if isinstance(data, str):
                import re
                if not re.match(r"\d{4}-\d{2}-\d{2}", data):
                    issues.append({
                        "type": "format_error",
                        "field": "root",
                        "severity": "warning",
                        "message": "Date should be in YYYY-MM-DD format",
                    })
        
        return issues
    
    def _check_schema(self, data: Any, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate against JSON schema-like specification."""
        issues = []
        
        if not isinstance(data, dict):
            issues.append({
                "type": "schema_error",
                "field": "root",
                "severity": "critical",
                "message": "Data should be an object",
            })
            return issues
        
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                issues.append({
                    "type": "missing_field",
                    "field": field,
                    "severity": "critical",
                    "message": f"Required field '{field}' is missing",
                })
        
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                field_type = field_schema.get("type")
                value = data[field]
                
                # Type checking
                if field_type == "string" and not isinstance(value, str):
                    issues.append({
                        "type": "type_error",
                        "field": field,
                        "severity": "critical",
                        "message": f"Field '{field}' should be string",
                    })
                elif field_type == "number" and not isinstance(value, (int, float)):
                    issues.append({
                        "type": "type_error",
                        "field": field,
                        "severity": "critical",
                        "message": f"Field '{field}' should be number",
                    })
                elif field_type == "array" and not isinstance(value, list):
                    issues.append({
                        "type": "type_error",
                        "field": field,
                        "severity": "critical",
                        "message": f"Field '{field}' should be array",
                    })
                
                # Pattern checking
                pattern = field_schema.get("pattern")
                if pattern and isinstance(value, str):
                    import re
                    if not re.match(pattern, value):
                        issues.append({
                            "type": "pattern_error",
                            "field": field,
                            "severity": "warning",
                            "message": f"Field '{field}' does not match pattern",
                        })
        
        return issues
    
    def _generate_summary(
        self,
        issues: List[Dict[str, Any]],
        score: float,
        passed: bool,
    ) -> str:
        """Generate human-readable summary."""
        if not issues:
            return "Validation passed. No issues found."
        
        critical = sum(1 for i in issues if i.get("severity") == "critical")
        warning = sum(1 for i in issues if i.get("severity") == "warning")
        
        parts = [
            f"Validation {'passed' if passed else 'failed'} with score {score:.0%}",
            f"Found {len(issues)} issues:",
        ]
        
        if critical > 0:
            parts.append(f"  - {critical} critical")
        if warning > 0:
            parts.append(f"  - {warning} warnings")
        
        return "\n".join(parts)