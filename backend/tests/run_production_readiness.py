import asyncio
import json
import os
import sys
import subprocess
from datetime import datetime
from typing import List, Dict

class ProductionReadinessTestSuite:
    """
    Master orchestrator for Cephly Production Readiness Tests.
    Executes various test suites and generates a consolidated report.
    """
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        self.report_path = None

    async def run_all_tests(self):
        """Execute complete test suite across all categories."""
        self.start_time = datetime.utcnow()
        print(f"\n{'='*80}")
        print(f"🚀 CEPHLY PRODUCTION READINESS TEST SUITE - STARTING AT {self.start_time}")
        print(f"{'='*80}\n")

        test_categories = [
            ("Authentication & Authorization", self.run_pytest_category, "category1"),
            ("API Security & Rate Limiting", self.run_pytest_category, "category2"),
            ("Data Consistency & Integrity", self.run_pytest_category, "category3"),
            ("Agent Intelligence", self.run_pytest_category, "category4"),
            ("External Integration Resilience", self.run_pytest_category, "category6"),
            ("Business Logic & Edge Cases", self.run_pytest_category, "category8"),
            ("Security Penetration Testing", self.run_pytest_category, "category9"),
            ("Data Privacy & Compliance", self.run_pytest_category, "category10"),
            ("Monitoring & Observability", self.run_pytest_category, "category11"),
            ("Performance Benchmark", self.run_performance_test, None),
        ]

        for category_name, runner_func, category_id in test_categories:
            print(f"\nRunning Category: {category_name}...")
            category_results = await runner_func(category_id)
            self.results.append({
                "category": category_name,
                "results": category_results,
                "pass_rate": self._calculate_pass_rate(category_results)
            })

        self.end_time = datetime.utcnow()
        self._generate_report()

    async def run_performance_test(self, _=None) -> List[Dict]:
        """Runs headless Locust performance test."""
        try:
            # Use the venv python if available
            venv_python = os.path.join(os.getcwd(), "..", ".venv", "Scripts", "python.exe")
            # Locust is likely in venv/Scripts/locust.exe or can be run via python -m locust
            locust_cmd = [venv_python, "-m", "locust", "-f", "tests/performance/locustfile.py", "--headless", "-u", "5", "-r", "1", "--run-time", "10s", "--host", "http://localhost:8000"]
            
            print("  (Simulating 5 concurrent users for 10s...)")
            process = await asyncio.create_subprocess_exec(
                *locust_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return [{"test_name": "Locust Load Test", "status": "PASS", "reason": "Completed successfully"}]
            else:
                return [{"test_name": "Locust Load Test", "status": "FAIL", "reason": stderr.decode()}]
        except Exception as e:
            return [{"test_name": "Locust Load Test", "status": "FAIL", "reason": str(e)}]

    async def run_pytest_category(self, category_id: str) -> List[Dict]:
        """Runs pytest for a specific category marker."""
        try:
            # Use the venv python if available, otherwise fallback to sys.executable
            venv_python = os.path.join(os.getcwd(), "..", ".venv", "Scripts", "python.exe")
            python_cmd = venv_python if os.path.exists(venv_python) else sys.executable
            
            # Ensure PYTHONPATH is set so 'app' can be found
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()
            
            # We'll use pytest markers to run specific categories in test_production_readiness.py
            cmd = [python_cmd, "-m", "pytest", "tests/test_production_readiness.py", "-m", category_id, "--json-report", "--json-report-file=.pytest_report.json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
                # Removed cwd="backend" since we are already in the backend directory
            )
            stdout, stderr = await process.communicate()
            
            # Parse the json report if it exists
            report_file = ".pytest_report.json"
            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    data = json.load(f)
                
                parsed_results = []
                for test in data.get('tests', []):
                    status = "PASS" if test.get('outcome') == 'passed' else "FAIL"
                    parsed_results.append({
                        "test_name": test.get('nodeid'),
                        "status": status,
                        "reason": test.get('call', {}).get('longrepr', "N/A") if status == "FAIL" else None
                    })
                return parsed_results
            else:
                return [{"test_name": f"Pytest {category_id}", "status": "FAIL", "reason": "Report not generated"}]
        except Exception as e:
            return [{"test_name": f"Pytest {category_id}", "status": "FAIL", "reason": str(e)}]

    def _calculate_pass_rate(self, results: List[Dict]) -> float:
        total = len(results)
        if total == 0: return 0.0
        passed = sum(1 for r in results if r["status"] == "PASS")
        return (passed / total) * 100

    def _generate_report(self):
        """Generate comprehensive test report and output summary."""
        total_tests = sum(len(cat["results"]) for cat in self.results)
        total_passed = sum(sum(1 for r in cat["results"] if r["status"] == "PASS") for cat in self.results)
        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_tests - total_passed,
                "pass_rate": overall_pass_rate,
                "duration_seconds": duration,
                "timestamp": self.end_time.isoformat(),
            },
            "categories": self.results,
            "recommendation": self._get_recommendation(overall_pass_rate)
        }
        
        self.report_path = f"readiness_report_{self.end_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(self.report_path, "w") as f:
            json.dump(report, f, indent=2)
            
        print("\n" + "="*80)
        print("PRODUCTION READINESS TEST RESULTS")
        print("="*80)
        print(f"Pass Rate: {overall_pass_rate:.1f}% ({total_passed}/{total_tests})")
        print(f"Duration: {duration:.1f}s")
        print(f"Recommendation: {report['recommendation']}")
        print("="*80 + "\n")

    def _get_recommendation(self, pass_rate: float) -> str:
        if pass_rate >= 95: return "✅ PRODUCTION READY"
        if pass_rate >= 85: return "⚠️ MOSTLY READY - Fix minor failures"
        return "❌ NOT READY - Critical failures detected"

if __name__ == "__main__":
    suite = ProductionReadinessTestSuite()
    asyncio.run(suite.run_all_tests())
