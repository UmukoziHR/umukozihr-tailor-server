#!/bin/bash
# UmukoziHR Resume Tailor v1.2 - Comprehensive curl API Testing
# This script tests all API endpoints with curl commands

set -e  # Exit on any error

BASE_URL="http://localhost:8000"
TEMP_DIR="/tmp/umukozihr_test"
mkdir -p "$TEMP_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print test headers
print_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}Testing: $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to check response and print result
check_response() {
    local response_file="$1"
    local expected_status="$2"
    local test_name="$3"
    
    if [ -f "$response_file" ]; then
        local status=$(head -n1 "$response_file" | grep -o '[0-9]\{3\}')
        if [ "$status" = "$expected_status" ]; then
            echo -e "${GREEN}✅ $test_name - Status: $status${NC}"
            return 0
        else
            echo -e "${RED}❌ $test_name - Expected: $expected_status, Got: $status${NC}"
            echo -e "${YELLOW}Response:${NC}"
            cat "$response_file"
            return 1
        fi
    else
        echo -e "${RED}❌ $test_name - No response file${NC}"
        return 1
    fi
}

# Test 1: Health Check
print_test "Health Endpoint"
curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X GET "$BASE_URL/health" \
    -H "Content-Type: application/json" \
    > "$TEMP_DIR/health_response.txt"

if check_response "$TEMP_DIR/health_response.txt" "200" "Health Check"; then
    echo -e "${YELLOW}Response Body:${NC}"
    grep -v "HTTP_STATUS:" "$TEMP_DIR/health_response.txt"
fi

# Test 2: User Signup
print_test "User Signup"
SIGNUP_DATA='{
    "email": "testcurl@umukozihr.com",
    "password": "securepassword123"
}'

curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X POST "$BASE_URL/api/v1/auth/signup" \
    -H "Content-Type: application/json" \
    -d "$SIGNUP_DATA" \
    > "$TEMP_DIR/signup_response.txt"

if check_response "$TEMP_DIR/signup_response.txt" "200" "User Signup"; then
    echo -e "${YELLOW}Response Body:${NC}"
    SIGNUP_RESPONSE=$(grep -v "HTTP_STATUS:" "$TEMP_DIR/signup_response.txt")
    echo "$SIGNUP_RESPONSE"
    
    # Extract access token for later use
    ACCESS_TOKEN=$(echo "$SIGNUP_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    echo -e "${BLUE}Extracted Access Token: ${ACCESS_TOKEN:0:20}...${NC}"
fi

# Test 3: User Login
print_test "User Login"
LOGIN_DATA='{
    "email": "testcurl@umukozihr.com",
    "password": "securepassword123"
}'

curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "$LOGIN_DATA" \
    > "$TEMP_DIR/login_response.txt"

if check_response "$TEMP_DIR/login_response.txt" "200" "User Login"; then
    echo -e "${YELLOW}Response Body:${NC}"
    LOGIN_RESPONSE=$(grep -v "HTTP_STATUS:" "$TEMP_DIR/login_response.txt")
    echo "$LOGIN_RESPONSE"
    
    # Extract access token (use login token as primary)
    LOGIN_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$LOGIN_TOKEN" ]; then
        ACCESS_TOKEN="$LOGIN_TOKEN"
        echo -e "${BLUE}Using Login Token: ${ACCESS_TOKEN:0:20}...${NC}"
    fi
fi

# Test 4: Profile Save (with authentication)
print_test "Profile Save (Authenticated)"
PROFILE_DATA='{
    "name": "Jason Quist",
    "contacts": {
        "email": "jason@umukozihr.com",
        "phone": "+1-555-0123",
        "location": "San Francisco, CA",
        "links": [
            "https://linkedin.com/in/jasonquist",
            "https://github.com/jasonquist"
        ]
    },
    "summary": "Experienced CTO and AI Engineer with 8+ years building scalable HR tech systems",
    "skills": [
        "Python", "FastAPI", "React", "Next.js", "PostgreSQL", 
        "Docker", "AWS", "Machine Learning", "System Architecture"
    ],
    "experience": [
        {
            "title": "CTO & VP Engineering",
            "company": "UmukoziHR",
            "location": "San Francisco, CA",
            "start_date": "2024-01",
            "end_date": "Present",
            "bullets": [
                "Leading technical vision for AI-powered HR solutions serving 10,000+ users",
                "Built scalable resume tailoring system processing 1000+ documents daily",
                "Architected microservices infrastructure with FastAPI, PostgreSQL, and Redis",
                "Implemented JWT authentication and multi-tenant database architecture"
            ]
        },
        {
            "title": "Senior AI Engineer",
            "company": "OpenAI",
            "location": "San Francisco, CA",
            "start_date": "2022-06",
            "end_date": "2023-12",
            "bullets": [
                "Developed LLM integration patterns for enterprise applications",
                "Optimized model performance achieving 40% latency reduction",
                "Led cross-functional team of 12 engineers on AI infrastructure"
            ]
        }
    ],
    "education": [
        {
            "degree": "MS Computer Science",
            "school": "Stanford University",
            "location": "Stanford, CA",
            "graduation_date": "2019-06",
            "gpa": "3.9/4.0"
        }
    ],
    "projects": [
        {
            "name": "UmukoziHR Resume Tailor v1.2",
            "description": "AI-powered resume and cover letter generation platform",
            "technologies": ["Python", "FastAPI", "React", "PostgreSQL", "Gemini", "LaTeX"],
            "bullets": [
                "Processes resumes with 95% success rate and ATS optimization",
                "Supports multiple regional formats with LaTeX compilation",
                "Features JWT authentication and background job processing"
            ]
        }
    ]
}'

if [ -n "$ACCESS_TOKEN" ]; then
    curl -s -w "HTTP_STATUS:%{http_code}\n" \
        -X POST "$BASE_URL/api/v1/profile/profile" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -d "$PROFILE_DATA" \
        > "$TEMP_DIR/profile_response.txt"
    
    if check_response "$TEMP_DIR/profile_response.txt" "200" "Profile Save (Authenticated)"; then
        echo -e "${YELLOW}Response Body:${NC}"
        grep -v "HTTP_STATUS:" "$TEMP_DIR/profile_response.txt"
    fi
else
    echo -e "${RED}❌ Skipping authenticated profile save - no access token${NC}"
fi

# Test 5: Profile Save (without authentication - v1.1 compatibility)
print_test "Profile Save (No Auth - v1.1 Compatibility)"
curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X POST "$BASE_URL/api/v1/profile/profile" \
    -H "Content-Type: application/json" \
    -d "$PROFILE_DATA" \
    > "$TEMP_DIR/profile_noauth_response.txt"

if check_response "$TEMP_DIR/profile_noauth_response.txt" "200" "Profile Save (No Auth)"; then
    echo -e "${YELLOW}Response Body:${NC}"
    grep -v "HTTP_STATUS:" "$TEMP_DIR/profile_noauth_response.txt"
fi

# Test 6: Document Generation (Simple Test Job)
print_test "Document Generation"
GENERATION_DATA='{
    "profile": {
        "name": "Jason Quist",
        "contacts": {
            "email": "jason@umukozihr.com",
            "phone": "+1-555-0123",
            "location": "San Francisco, CA",
            "links": ["https://linkedin.com/in/jasonquist"]
        },
        "summary": "Experienced CTO and AI Engineer with 8+ years in tech leadership",
        "skills": ["Python", "FastAPI", "React", "AI/ML", "System Architecture"],
        "experience": [
            {
                "title": "CTO & VP Engineering",
                "company": "UmukoziHR",
                "location": "San Francisco, CA",
                "start_date": "2024-01",
                "end_date": "Present",
                "bullets": [
                    "Leading technical vision for AI-powered HR solutions",
                    "Built scalable resume tailoring system processing 1000+ documents",
                    "Architected microservices infrastructure with modern tech stack"
                ]
            }
        ],
        "education": [
            {
                "degree": "MS Computer Science",
                "school": "Stanford University",
                "location": "Stanford, CA",
                "graduation_date": "2019-06"
            }
        ],
        "projects": []
    },
    "jobs": [
        {
            "id": "test-senior-eng",
            "region": "US",
            "company": "Google",
            "title": "Senior Software Engineer - AI/ML",
            "jd_text": "We are looking for a Senior Software Engineer to join our AI/ML team. You will work on large-scale systems using Python, develop APIs with modern frameworks like FastAPI, and lead technical initiatives. Experience with machine learning, system architecture, and team leadership is highly valued. Join us to build the future of AI-powered applications."
        }
    ],
    "prefs": {}
}'

echo -e "${YELLOW}⚠️  Note: This test requires Gemini API and may take 30-60 seconds${NC}"

if [ -n "$ACCESS_TOKEN" ]; then
    curl -s -w "HTTP_STATUS:%{http_code}\n" \
        -X POST "$BASE_URL/api/v1/generate/generate" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -d "$GENERATION_DATA" \
        --max-time 90 \
        > "$TEMP_DIR/generation_response.txt"
    
    if check_response "$TEMP_DIR/generation_response.txt" "200" "Document Generation (Authenticated)"; then
        echo -e "${YELLOW}Response Body:${NC}"
        GENERATION_RESPONSE=$(grep -v "HTTP_STATUS:" "$TEMP_DIR/generation_response.txt")
        echo "$GENERATION_RESPONSE"
        
        # Extract ZIP path for download test
        ZIP_PATH=$(echo "$GENERATION_RESPONSE" | grep -o '"/artifacts/[^"]*\.zip"' | tr -d '"')
        if [ -n "$ZIP_PATH" ]; then
            echo -e "${BLUE}Generated ZIP: $ZIP_PATH${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Skipping authenticated generation - no access token${NC}"
fi

# Test 7: Document Generation (No Auth - v1.1 Compatibility)  
print_test "Document Generation (No Auth)"
echo -e "${YELLOW}⚠️  Note: This test requires Gemini API and may take 30-60 seconds${NC}"

curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X POST "$BASE_URL/api/v1/generate/generate" \
    -H "Content-Type: application/json" \
    -d "$GENERATION_DATA" \
    --max-time 90 \
    > "$TEMP_DIR/generation_noauth_response.txt"

if check_response "$TEMP_DIR/generation_noauth_response.txt" "200" "Document Generation (No Auth)"; then
    echo -e "${YELLOW}Response Body:${NC}"
    GENERATION_NOAUTH_RESPONSE=$(grep -v "HTTP_STATUS:" "$TEMP_DIR/generation_noauth_response.txt")
    echo "$GENERATION_NOAUTH_RESPONSE"
    
    # Extract ZIP path for download test
    ZIP_PATH_NOAUTH=$(echo "$GENERATION_NOAUTH_RESPONSE" | grep -o '"/artifacts/[^"]*\.zip"' | tr -d '"')
    if [ -n "$ZIP_PATH_NOAUTH" ]; then
        echo -e "${BLUE}Generated ZIP: $ZIP_PATH_NOAUTH${NC}"
        ZIP_PATH="$ZIP_PATH_NOAUTH"  # Use this for download test
    fi
fi

# Test 8: Artifact Download
if [ -n "$ZIP_PATH" ]; then
    print_test "Artifact Download"
    echo -e "${BLUE}Testing download of: $ZIP_PATH${NC}"
    
    curl -s -w "HTTP_STATUS:%{http_code}\n" \
        -X GET "$BASE_URL$ZIP_PATH" \
        -o "$TEMP_DIR/downloaded_bundle.zip" \
        > "$TEMP_DIR/download_response.txt"
    
    if check_response "$TEMP_DIR/download_response.txt" "200" "Artifact Download"; then
        if [ -f "$TEMP_DIR/downloaded_bundle.zip" ]; then
            FILE_SIZE=$(stat -f%z "$TEMP_DIR/downloaded_bundle.zip" 2>/dev/null || stat -c%s "$TEMP_DIR/downloaded_bundle.zip" 2>/dev/null || echo "unknown")
            echo -e "${GREEN}✅ ZIP file downloaded successfully (Size: $FILE_SIZE bytes)${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Skipping artifact download - no ZIP path available${NC}"
fi

# Test 9: Invalid Authentication
print_test "Invalid Authentication Test"
curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "invalid@test.com", "password": "wrongpassword"}' \
    > "$TEMP_DIR/invalid_auth_response.txt"

if check_response "$TEMP_DIR/invalid_auth_response.txt" "401" "Invalid Authentication"; then
    echo -e "${YELLOW}Response Body:${NC}"
    grep -v "HTTP_STATUS:" "$TEMP_DIR/invalid_auth_response.txt"
fi

# Test 10: API Documentation
print_test "API Documentation"
curl -s -w "HTTP_STATUS:%{http_code}\n" \
    -X GET "$BASE_URL/docs" \
    > "$TEMP_DIR/docs_response.txt"

check_response "$TEMP_DIR/docs_response.txt" "200" "API Documentation"

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}CURL TEST SUMMARY${NC}"
echo -e "${BLUE}========================================${NC}"

TOTAL_TESTS=10
PASSED_TESTS=0

echo -e "${GREEN}Tests completed. Check individual results above.${NC}"
echo -e "${YELLOW}Generated files in: $TEMP_DIR${NC}"
echo -e "${YELLOW}Server logs available in terminal where uvicorn is running${NC}"

# Cleanup option
echo -e "\n${BLUE}To clean up test files: rm -rf $TEMP_DIR${NC}"
echo -e "${BLUE}To stop server: Ctrl+C in server terminal${NC}"

echo -e "\n${GREEN}🎉 Comprehensive curl testing completed!${NC}"