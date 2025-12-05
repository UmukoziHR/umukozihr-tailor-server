# UmukoziHR Resume Tailor - Backend API v1.2

🚀 **AI-Powered Resume & Cover Letter Generation Backend**

A FastAPI-based backend service that generates perfectly tailored resumes and cover letters using Google Gemini 2.5 Flash LLM, with LaTeX compilation and PDF generation.

## ✨ Features

- 🤖 **AI-Powered Content Generation** - Google Gemini 2.5 Flash integration
- 🔐 **JWT Authentication** - Secure user authentication with bcrypt/SHA256 fallback
- 📄 **Multi-Format Support** - US, EU, and Global resume formats
- 🎯 **ATS Optimization** - Keyword matching and formatting optimization
- 📊 **LaTeX Compilation** - Local latexmk + Docker fallback for PDF generation
- 🗃️ **SQLite Database** - User profiles and job management
- 📦 **ZIP Bundling** - Download all documents in one package
- 🌐 **CORS Enabled** - Frontend integration ready
- 📝 **Comprehensive Logging** - Full request/response tracking

## 🛠️ Tech Stack

- **Framework**: FastAPI 0.104+
- **AI/LLM**: Google Gemini 2.5 Flash
- **Database**: SQLite (PostgreSQL ready)
- **Authentication**: JWT + bcrypt
- **Document Generation**: LaTeX + Jinja2 templates
- **PDF Compilation**: latexmk + Docker fallback
- **Testing**: pytest + requests

## 📋 Prerequisites

### Required:
- Python 3.9+
- Google Gemini API Key ([Get one here](https://ai.google.dev/))

### Optional (for PDF generation):
- Docker (for LaTeX compilation fallback)
- LaTeX distribution (TeXLive, MiKTeX, etc.) for local compilation

## 🚀 Quick Start

### 1. Clone and Navigate
```bash
cd server
```

### 2. Set Up Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the server directory:
```env
# Required: Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Authentication (defaults provided)
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional: Database (SQLite by default)
DATABASE_URL=sqlite:///./app.db

# Optional: Redis (for future async processing)
REDIS_URL=redis://localhost:6379/0
```

### 5. Initialize Database
```bash
python migrate.py
```

### 6. Start the Server
```bash
# Development mode (with auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

🎉 **Server running at: http://localhost:8000**

## 📡 API Endpoints

### Health Check
```http
GET /health
```

### Authentication
```http
POST /api/v1/auth/signup    # Create account
POST /api/v1/auth/login     # Login
```

### Profile Management
```http
POST /api/v1/profile/profile    # Save user profile
```

### Document Generation
```http
POST /api/v1/generate/generate     # Generate documents
GET  /api/v1/generate/status/{id}  # Check generation status
```

### File Downloads
```http
GET /artifacts/{filename}    # Download generated files
```

## 🧪 Testing

### Run All Tests
```bash
# Run comprehensive test suite
python tests/run_all_tests.py

# Run specific test categories
python tests/test_components.py    # Component tests
python tests/test_api.py           # API tests
python tests/full_api_test.py      # End-to-end tests
```

### Manual API Testing
```bash
# Test with curl commands
bash curl_test.sh

# Interactive Python testing
python curl_like_test.py
```

## 📁 Project Structure

```
server/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── auth/
│   │   └── auth.py          # Authentication logic
│   ├── core/
│   │   ├── llm.py           # Gemini LLM integration
│   │   ├── tailor.py        # Resume tailoring logic
│   │   └── tex_compile.py   # LaTeX compilation
│   ├── db/
│   │   ├── database.py      # Database setup
│   │   └── models.py        # SQLAlchemy models
│   ├── routes/
│   │   ├── v1_auth.py       # Authentication routes
│   │   ├── v1_profile.py    # Profile management
│   │   └── v1_generate.py   # Document generation
│   └── templates/           # LaTeX templates
├── tests/                   # Test suite
├── artifacts/               # Generated files
└── requirements.txt         # Dependencies
```

## 🔧 Configuration

### LaTeX Setup (Optional)
For local PDF compilation:

**Windows:**
```bash
# Install MiKTeX or TeXLive
winget install MiKTeX.MiKTeX
```

**macOS:**
```bash
brew install --cask mactex
```

**Linux:**
```bash
sudo apt-get install texlive-full
```

### Docker Setup (Recommended)
For reliable PDF compilation:
```bash
# Pull LaTeX Docker image
docker pull texlive/texlive:latest
```

## 🐛 Troubleshooting

### Common Issues

**1. bcrypt Installation Error (Windows)**
```
Fallback authentication (SHA256) will be used automatically
```

**2. LaTeX Compilation Fails**
```
Docker fallback will be used automatically
Check Docker installation if PDFs aren't generated
```

**3. Gemini API Errors**
```
Verify GEMINI_API_KEY in .env file
Check API quota and billing status
```

**4. Port Already in Use**
```bash
# Use different port
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Debug Mode
```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

## 📊 Performance

- **Generation Time**: 20-60 seconds per job (depends on LLM response time)
- **Concurrent Users**: Supports multiple simultaneous requests
- **File Sizes**: PDFs typically 50-200KB, TEX files 5-15KB

## 🔒 Security

- JWT token authentication
- CORS protection
- Input validation and sanitization
- Secure file handling
- Password hashing (bcrypt preferred, SHA256 fallback)

## 🚀 Deployment

### Docker Deployment
```dockerfile
# Dockerfile example
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations
- Use PostgreSQL for production database
- Set up Redis for async job processing
- Configure proper environment variables
- Set up reverse proxy (nginx)
- Enable HTTPS

## 📝 API Documentation

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## 📄 License

Private - UmukoziHR Internal Use

## 🆘 Support

For issues and questions:
- Check the troubleshooting section
- Run the test suite to verify setup
- Review server logs in `umukozihr.log`

---

**Built with ❤️ by the UmukoziHR Team**