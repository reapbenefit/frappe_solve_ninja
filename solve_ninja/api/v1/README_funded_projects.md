# Funded Projects API Documentation

## Overview
This document provides comprehensive documentation for the Funded Projects API endpoints. These APIs allow you to retrieve funded project information with pagination, filtering, and detailed project data.

## API Endpoints

### 1. Get Funded Projects

**Endpoint**: `/api/method/solve_ninja.api.v1.project.get_funded_projects`

**Method**: `GET`

**Description**: Retrieves funded projects with pagination and filtering capabilities, ordered by creation date in descending order (newest first).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_length` | integer | No | 10 | Number of results per page |
| `start` | integer | No | 0 | Starting index for pagination |
| `city` | string/array | No | null | Filter by city (can be single city or array of cities) |
| `project_type` | string/array | No | null | Filter by project type (can be single type or array of types) |
| `status` | string/array | No | null | Filter by project status (can be single status or array of statuses) |

#### Request Examples

**Get all funded projects**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects
```

**Get projects with pagination**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?page_length=20&start=0
```

**Get projects by city**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai
```

**Get projects by multiple cities**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai&city=Delhi&city=Bangalore
```

**Get projects by project type**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?project_type=environmental
```

**Get projects by status**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?status=completed
```

**Combined filters**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai&project_type=environmental&status=completed&page_length=15&start=0
```

#### Response Format

**Success Response (200)**:
```json
{
  "message": "Funded projects retrieved successfully",
  "data": {
    "data": [
      {
        "name": "FP-001",
        "title": "Zero Waste Park Initiative",
        "lead_ninja_name": "Ananya Sharma",
        "city": "Mumbai",
        "description": "Transforming neighborhood park into a zero-waste zone with community participation",
        "grant_amount": "₹25,000",
        "funded_date": "2024-01-15",
        "theme": "Environmental Sustainability",
        "media_link": "https://your-domain.com/files/project-media.jpg",
        "outcome_summary": "2T waste diverted from landfill, 500+ community members engaged",
        "testimonial": "We transformed our neighborhood park into a zero-waste zone. The impact has been incredible!"
      },
      {
        "name": "FP-002",
        "title": "Plastic-Free Community Drive",
        "lead_ninja_name": "Rajesh Kumar",
        "city": "Delhi",
        "description": "Community-wide plastic collection and awareness campaign",
        "grant_amount": "₹30,000",
        "funded_date": "2024-02-01",
        "theme": "Waste Management",
        "media_link": "https://your-domain.com/files/plastic-free-media.jpg",
        "outcome_summary": "500+ households reached, 1T plastic collected and recycled",
        "testimonial": "Our plastic collection drive reached 500+ households. The community response was overwhelming!"
      }
    ],
    "pagination": {
      "total_count": 50,
      "page_length": 10,
      "start": 0,
      "has_next": true,
      "has_prev": false
    },
    "filters": {
      "city": ["Mumbai"],
      "project_type": ["environmental"],
      "status": ["completed"]
    }
  },
  "status_code": 200,
  "error": null
}
```

**Error Response (500)**:
```json
{
  "message": "Failed to retrieve funded projects",
  "data": null,
  "status_code": 500,
  "error": "Database connection error"
}
```

### 2. Get Funded Project Details

**Endpoint**: `/api/method/solve_ninja.api.v1.project.get_funded_project_details`

**Method**: `GET`

**Description**: Retrieves detailed information for a specific funded project.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_name` | string | Yes | - | Name/ID of the funded project |

#### Request Examples

**Get specific project details**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_project_details?project_name=FP-001
```

#### Response Format

**Success Response (200)**:
```json
{
  "message": "Project details retrieved successfully",
  "data": {
    "name": "FP-001",
    "title": "Zero Waste Park Initiative",
    "lead_ninja_name": "Ananya Sharma",
    "city": "Mumbai",
    "description": "Transforming neighborhood park into a zero-waste zone with community participation",
    "grant_amount": "₹25,000",
    "funded_date": "2024-01-15",
    "theme": "Environmental Sustainability",
    "media_link": "https://your-domain.com/files/project-media.jpg",
    "outcome_summary": "2T waste diverted from landfill, 500+ community members engaged",
    "testimonial": "We transformed our neighborhood park into a zero-waste zone. The impact has been incredible!",
    "creation": "2024-01-10 09:30:00",
    "modified": "2024-01-15 14:20:00",
    "owner": "Administrator",
    "docstatus": 0
  },
  "status_code": 200,
  "error": null
}
```

**Error Response (404)**:
```json
{
  "message": "Project not found",
  "data": null,
  "status_code": 404,
  "error": "Funded Project 'FP-999' does not exist"
}
```

### 3. Get Funded Projects by Status

**Endpoint**: `/api/method/solve_ninja.api.v1.project.get_funded_projects_by_status`

**Method**: `GET`

**Description**: Retrieves funded projects filtered by specific status, ordered by creation date in descending order.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | Yes | - | Project status to filter by |
| `page_length` | integer | No | 10 | Number of results per page |
| `start` | integer | No | 0 | Starting index for pagination |

#### Request Examples

**Get completed projects**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects_by_status?status=completed
```

**Get ongoing projects with pagination**:
```bash
GET /api/method/solve_ninja.api.v1.project.get_funded_projects_by_status?status=ongoing&page_length=20&start=0
```

#### Response Format

**Success Response (200)**:
```json
{
  "message": "Funded projects with status 'completed' retrieved successfully",
  "data": {
    "data": [
      {
        "name": "FP-001",
        "title": "Zero Waste Park Initiative",
        "lead_ninja_name": "Ananya Sharma",
        "city": "Mumbai",
        "description": "Transforming neighborhood park into a zero-waste zone",
        "grant_amount": "₹25,000",
        "funded_date": "2024-01-15",
        "theme": "Environmental Sustainability",
        "media_link": "https://your-domain.com/files/project-media.jpg",
        "outcome_summary": "2T waste diverted from landfill",
        "testimonial": "We transformed our neighborhood park into a zero-waste zone."
      }
    ],
    "pagination": {
      "total_count": 25,
      "page_length": 10,
      "start": 0,
      "has_next": true,
      "has_prev": false
    },
    "filters": {
      "status": "completed"
    }
  },
  "status_code": 200,
  "error": null
}
```

## Response Fields

### Project Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique project identifier |
| `title` | string | Project title |
| `lead_ninja_name` | string | Name of the lead ninja |
| `city` | string | Project location city |
| `description` | string | Project description |
| `grant_amount` | string | Amount of grant received |
| `funded_date` | date | Date when project was funded |
| `theme` | string | Project theme/category |
| `media_link` | string | Full URL to project media/image |
| `outcome_summary` | string | Summary of project outcomes |
| `testimonial` | string | Testimonial from project lead |

### Pagination Object

| Field | Type | Description |
|-------|------|-------------|
| `total_count` | integer | Total number of projects matching criteria |
| `page_length` | integer | Number of results per page |
| `start` | integer | Starting index for current page |
| `has_next` | boolean | Whether there are more results |
| `has_prev` | boolean | Whether there are previous results |

### Filters Object

| Field | Type | Description |
|-------|------|-------------|
| `city` | array | Applied city filters |
| `project_type` | array | Applied project type filters |
| `status` | array/string | Applied status filters |

## Common Project Statuses

The following are common status values that can be used for filtering:

- `completed` - Project has been completed successfully
- `ongoing` - Project is currently in progress
- `planning` - Project is in planning phase
- `funded` - Project has been funded but not started
- `on_hold` - Project is temporarily on hold
- `cancelled` - Project has been cancelled

## Common Project Types

- `environmental` - Environmental sustainability projects
- `social` - Social impact projects
- `education` - Educational initiatives
- `health` - Health and wellness projects
- `technology` - Technology-based solutions
- `community` - Community development projects

## Usage Examples

### JavaScript/Fetch

```javascript
// Get all funded projects
fetch('/api/method/solve_ninja.api.v1.project.get_funded_projects')
  .then(response => response.json())
  .then(data => {
    console.log('Projects:', data.data.data);
    console.log('Total count:', data.data.pagination.total_count);
  });

// Get projects by city with pagination
fetch('/api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai&page_length=5&start=0')
  .then(response => response.json())
  .then(data => {
    data.data.data.forEach(project => {
      console.log(`${project.title} - ${project.lead_ninja_name}`);
    });
  });

// Get specific project details
fetch('/api/method/solve_ninja.api.v1.project.get_funded_project_details?project_name=FP-001')
  .then(response => response.json())
  .then(data => {
    console.log('Project details:', data.data);
  });

// Get completed projects
fetch('/api/method/solve_ninja.api.v1.project.get_funded_projects_by_status?status=completed')
  .then(response => response.json())
  .then(data => {
    console.log('Completed projects:', data.data.data);
  });
```

### Python/Requests

```python
import requests

# Get all funded projects
response = requests.get('/api/method/solve_ninja.api.v1.project.get_funded_projects')
data = response.json()
projects = data['data']['data']

# Get projects with filters
params = {
    'city': 'Mumbai',
    'project_type': 'environmental',
    'page_length': 20,
    'start': 0
}
response = requests.get('/api/method/solve_ninja.api.v1.project.get_funded_projects', params=params)
data = response.json()

# Get specific project details
response = requests.get('/api/method/solve_ninja.api.v1.project.get_funded_project_details', 
                       params={'project_name': 'FP-001'})
project_details = response.json()['data']

# Get projects by status
response = requests.get('/api/method/solve_ninja.api.v1.project.get_funded_projects_by_status',
                       params={'status': 'completed', 'page_length': 10})
completed_projects = response.json()['data']['data']
```

### cURL

```bash
# Get all funded projects
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.project.get_funded_projects"

# Get projects by city
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai"

# Get projects with multiple filters
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.project.get_funded_projects?city=Mumbai&project_type=environmental&status=completed&page_length=15&start=0"

# Get specific project details
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.project.get_funded_project_details?project_name=FP-001"

# Get completed projects
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.project.get_funded_projects_by_status?status=completed&page_length=10&start=0"
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- **200**: Success
- **400**: Bad Request (invalid parameters)
- **404**: Not Found (project doesn't exist)
- **500**: Internal Server Error

Always check the `status_code` field in the response and handle errors appropriately:

```javascript
fetch('/api/method/solve_ninja.api.v1.project.get_funded_projects')
  .then(response => response.json())
  .then(data => {
    if (data.status_code === 200) {
      // Handle success
      console.log('Projects:', data.data.data);
    } else {
      // Handle error
      console.error('Error:', data.message, data.error);
    }
  })
  .catch(error => {
    console.error('Network error:', error);
  });
```

## Performance Considerations

- **Pagination**: Always use pagination for large datasets to improve performance
- **Filtering**: Use specific filters to reduce the dataset size
- **Caching**: Consider implementing client-side caching for frequently accessed data
- **Rate Limiting**: Be mindful of API rate limits in production environments

## Business Logic

1. **Ordering**: Projects are ordered by creation date in descending order (newest first)
2. **Media URLs**: Media link paths are automatically converted to full URLs
3. **Filter Parsing**: Single string filters are automatically converted to arrays
4. **Pagination**: Standard offset-based pagination with metadata
5. **Error Handling**: Comprehensive error handling with detailed error messages

## Related APIs

- `get_solve_events` - Similar structure for event listings
- `get_skill_based_projects` - Similar structure for skill-based projects

## Changelog

- **v1.0.0** (2024-01-XX): Initial release of Funded Projects APIs
  - Added `get_funded_projects` with filtering and pagination
  - Added `get_funded_project_details` for single project details
  - Added `get_funded_projects_by_status` for status-specific filtering
  - Added creation date ordering (desc)
  - Added comprehensive error handling

---

## Support

For technical support or questions about this API, please contact the development team or refer to the main project documentation.







