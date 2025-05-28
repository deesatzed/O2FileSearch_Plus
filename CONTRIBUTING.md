# Contributing to O2FileSearchPlus Enhanced

Thank you for your interest in contributing to O2FileSearchPlus Enhanced! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+ with pip
- Node.js 18+ with npm
- Git
- Linux environment (recommended)

### Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/yourusername/O2FileSearchPlus.git
   cd O2FileSearchPlus
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Start development servers**:
   ```bash
   ./start_all.sh
   ```

## 🏗️ Project Structure

```
O2FileSearchPlus/
├── backend/           # FastAPI backend
├── frontend/          # Next.js frontend
├── legacy/           # Original Streamlit applications
├── setup.sh          # Automated setup script
└── docs/             # Documentation
```

## 🔧 Development Workflow

### Backend Development

1. **Navigate to backend directory**:
   ```bash
   cd backend
   source venv/bin/activate
   ```

2. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run backend with auto-reload**:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **API Documentation**: Available at `http://localhost:8000/docs`

### Frontend Development

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```

4. **Build for production**:
   ```bash
   npm run build
   ```

## 📝 Coding Standards

### Python (Backend)
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for functions and classes
- Use meaningful variable and function names
- Keep functions focused and small

**Example**:
```python
from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    """Request model for file search operations."""
    extensions: Optional[List[str]] = None
    min_size: int = 0
    max_size: int = 1073741824  # 1GB
    
def search_files(request: SearchRequest) -> List[FileResult]:
    """
    Search files based on provided criteria.
    
    Args:
        request: Search parameters and filters
        
    Returns:
        List of matching files
    """
    # Implementation here
    pass
```

### TypeScript/React (Frontend)
- Use TypeScript for type safety
- Follow React best practices and hooks patterns
- Use functional components over class components
- Implement proper error boundaries
- Use meaningful component and variable names

**Example**:
```typescript
interface SearchFormProps {
  onSearch: (criteria: SearchCriteria) => void;
  isLoading: boolean;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, isLoading }) => {
  const [criteria, setCriteria] = useState<SearchCriteria>({
    extensions: [],
    minSize: 0,
    maxSize: 1073741824,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(criteria);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form implementation */}
    </form>
  );
};
```

## 🧪 Testing

### Backend Testing
```bash
cd backend
python -m pytest tests/ -v
```

### Frontend Testing
```bash
cd frontend
npm test
npm run test:e2e  # End-to-end tests
```

## 📋 Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**:
   ```bash
   # Backend tests
   cd backend && python -m pytest

   # Frontend tests
   cd frontend && npm test

   # Integration test
   ./setup.sh && ./start_all.sh
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new search filter functionality"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format
Use conventional commits format:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Environment information**:
   - OS version
   - Python version
   - Node.js version
   - Browser (for frontend issues)

2. **Steps to reproduce**:
   - Clear, numbered steps
   - Expected vs actual behavior
   - Screenshots if applicable

3. **Error messages**:
   - Full error logs
   - Console output
   - Network errors (if applicable)

## 💡 Feature Requests

For new features:

1. **Check existing issues** to avoid duplicates
2. **Describe the problem** the feature would solve
3. **Propose a solution** with implementation details
4. **Consider alternatives** and their trade-offs

## 🎯 Areas for Contribution

### High Priority
- **Performance optimization** for large file sets
- **AI/LLM integration** for semantic search
- **File content preview** functionality
- **Advanced duplicate management**
- **Search history and saved searches**

### Medium Priority
- **Additional file format support**
- **Cloud storage integration**
- **Mobile app development**
- **Advanced filtering options**
- **Batch file operations**

### Documentation
- **API documentation improvements**
- **User guides and tutorials**
- **Architecture documentation**
- **Deployment guides**
- **Video tutorials**

## 🔒 Security

### Reporting Security Issues
- **Do not** create public issues for security vulnerabilities
- Email security issues to: [security@yourproject.com]
- Include detailed reproduction steps
- Allow time for fixes before public disclosure

### Security Guidelines
- Validate all user inputs
- Use parameterized queries for database operations
- Implement proper authentication and authorization
- Follow OWASP security guidelines
- Regular dependency updates

## 📚 Resources

### Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [SQLite Documentation](https://sqlite.org/docs.html)
- [React Documentation](https://react.dev/)

### Tools
- [Python Black](https://black.readthedocs.io/) - Code formatting
- [ESLint](https://eslint.org/) - JavaScript linting
- [Prettier](https://prettier.io/) - Code formatting
- [TypeScript](https://www.typescriptlang.org/) - Type checking

## 🤝 Community

### Communication
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Pull Requests**: Code contributions and reviews

### Code of Conduct
- Be respectful and inclusive
- Provide constructive feedback
- Help newcomers get started
- Focus on the project's goals
- Maintain professional communication

## 📄 License

By contributing to O2FileSearchPlus Enhanced, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes for significant contributions
- Project documentation

Thank you for contributing to O2FileSearchPlus Enhanced! 🚀
