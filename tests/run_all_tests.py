#!/usr/bin/env python3
"""
UmukoziHR Resume Tailor v1.2 - Master Test Runner
Runs all tests in sequence and provides comprehensive results
"""
import sys
import os
import subprocess
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_test_file(test_file, description):
    """Run a specific test file and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print('='*60)
    
    try:
        # Change to the server directory to run tests
        server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Run the test file
        result = subprocess.run(
            [sys.executable, f"tests/{test_file}"],
            cwd=server_dir,
            capture_output=False,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        success = result.returncode == 0
        if success:
            print(f"✅ {description} - PASSED")
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
        
        return success
        
    except subprocess.TimeoutExpired:
        print(f"❌ {description} - TIMEOUT (exceeded 5 minutes)")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def check_server_running():
    """Check if the server is running on port 8000"""
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Run all test suites"""
    print("🚀 UmukoziHR Resume Tailor v1.2 - Master Test Runner")
    print("=" * 70)
    
    # Test configuration
    tests = [
        {
            "file": "test_components.py",
            "description": "Component Unit Tests",
            "requires_server": False,
            "category": "Unit Tests"
        },
        {
            "file": "test_system.py", 
            "description": "System Integration Tests",
            "requires_server": False,
            "category": "Integration Tests"
        },
        {
            "file": "full_api_test.py",
            "description": "Full API Integration Tests",
            "requires_server": True,
            "category": "API Tests"
        }
    ]
    
    results = {}
    server_required_tests = []
    
    # Run tests that don't require server first
    print("\\n📋 Running tests that don't require server...")
    for test in tests:
        if not test["requires_server"]:
            success = run_test_file(test["file"], test["description"])
            results[test["file"]] = {
                "success": success,
                "description": test["description"],
                "category": test["category"]
            }
        else:
            server_required_tests.append(test)
    
    # Handle server-dependent tests
    if server_required_tests:
        print("\\n🌐 Checking for running server...")
        server_running = check_server_running()
        
        if server_running:
            print("✅ Server is running on port 8000")
            print("\\n📋 Running API tests...")
            
            for test in server_required_tests:
                success = run_test_file(test["file"], test["description"])
                results[test["file"]] = {
                    "success": success,
                    "description": test["description"],
                    "category": test["category"]
                }
        else:
            print("❌ Server is not running on port 8000")
            print("\\n⚠️  Skipping API tests. To run API tests:")
            print("   1. Start server: uvicorn app.main:app --host 0.0.0.0 --port 8000")
            print("   2. Run: python tests/full_api_test.py")
            
            for test in server_required_tests:
                results[test["file"]] = {
                    "success": False,
                    "description": test["description"] + " (SKIPPED - No server)",
                    "category": test["category"]
                }
    
    # Generate comprehensive report
    print("\\n" + "=" * 70)
    print("COMPREHENSIVE TEST RESULTS")
    print("=" * 70)
    
    categories = {}
    for test_file, result in results.items():
        category = result["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(result)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r["success"])
    
    # Report by category
    for category, category_results in categories.items():
        print(f"\\n{category}:")
        for result in category_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"  {result['description']:40} {status}")
    
    # Overall summary
    print(f"\\n{'='*70}")
    print("OVERALL SUMMARY")
    print(f"{'='*70}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("\\n🎉 ALL TESTS PASSED! System is fully operational.")
        exit_code = 0
    else:
        print(f"\\n⚠️  {total_tests - passed_tests} test(s) failed. System needs attention.")
        exit_code = 1
    
    # Recommendations
    print(f"\\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")
    
    if not check_server_running():
        print("📌 Start the server to run full API tests:")
        print("   uvicorn app.main:app --host 0.0.0.0 --port 8000")
    
    if passed_tests < total_tests:
        print("📌 Review failed tests above for specific error messages")
        print("📌 Check logs for detailed error information")
    
    print("📌 For individual test runs:")
    for test in tests:
        print(f"   python tests/{test['file']}")
    
    print(f"\\n📊 Test run completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)