# Mentor API Documentation

This document provides comprehensive documentation for the Mentor API endpoints in the Solve Ninja application.

## Base URL
```
/api/method/solve_ninja.api.v1.mentor
```

## Authentication
All endpoints are publicly accessible (no authentication required).

---

## Endpoints

### 1. Get Mentors

Retrieves a paginated list of mentors with their expertise, status, and quote information.

#### Endpoint
```
GET /api/method/solve_ninja.api.v1.mentor.get_mentors
```

#### Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_length` | integer | No | 10 | Number of results per page |
| `start` | integer | No | 0 | Starting index for pagination |

#### Example Request
```bash
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.mentor.get_mentors?page_length=5&start=0"
```

#### Response Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User name (same as username) |
| `full_name` | string | Full name from User doctype |
| `username` | string | Username from User doctype |
| `user_image` | string | User image URL from User doctype |
| `is_mentor` | integer | Mentor status from User Metadata (1 = mentor) |
| `mentor_quote` | string | Mentor quote from User Metadata |
| `mentor_expertise` | string | Mentor expertise from User Metadata |
| `mentor_status` | string | Mentor status from User Metadata |
| `profile_url` | string | Generated profile URL for the user |

#### Example Response
```json
{
  "message": "Mentors retrieved successfully",
  "data": {
    "result": [
      {
        "name": "john.doe",
        "full_name": "John Doe",
        "username": "john.doe",
        "user_image": "https://your-domain.com/files/profile.jpg",
        "is_mentor": 1,
        "mentor_quote": "Helping others grow is my passion",
        "mentor_expertise": "Python, JavaScript, Web Development",
        "mentor_status": "Active",
        "profile_url": "https://your-domain.com/user-profile/john.doe"
      }
    ],
    "pagination": {
      "total_count": 25,
      "page_length": 10,
      "start": 0,
      "has_next": true,
      "has_prev": false
    }
  },
  "status_code": 200,
  "error": null
}
```

#### Error Response
```json
{
  "message": "Failed to retrieve mentors",
  "data": null,
  "status_code": 500,
  "error": "Database connection error"
}
```

---

### 2. Get Chapter Leads

Retrieves a paginated list of chapter leads with their achievement and status information.

#### Endpoint
```
GET /api/method/solve_ninja.api.v1.mentor.get_chapter_lead
```

#### Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_length` | integer | No | 10 | Number of results per page |
| `start` | integer | No | 0 | Starting index for pagination |

#### Example Request
```bash
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.mentor.get_chapter_lead?page_length=5&start=0"
```

#### Response Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User name (same as username) |
| `full_name` | string | Full name from User doctype |
| `username` | string | Username from User doctype |
| `user_image` | string | User image URL from User doctype |
| `is_city_chapter_lead` | integer | Chapter lead status from User Metadata (1 = chapter lead) |
| `chapter_lead_achivement` | string | Chapter lead achievement from User Metadata |
| `profile_url` | string | Generated profile URL for the user |

#### Example Response
```json
{
  "message": "Chapter leads retrieved successfully",
  "data": {
    "result": [
      {
        "name": "jane.smith",
        "full_name": "Jane Smith",
        "username": "jane.smith",
        "user_image": "https://your-domain.com/files/jane-profile.jpg",
        "is_city_chapter_lead": 1,
        "chapter_lead_achivement": "Led 5 successful community events",
        "profile_url": "https://your-domain.com/user-profile/jane.smith"
      }
    ],
    "pagination": {
      "total_count": 15,
      "page_length": 10,
      "start": 0,
      "has_next": true,
      "has_prev": false
    }
  },
  "status_code": 200,
  "error": null
}
```

#### Error Response
```json
{
  "message": "Failed to retrieve chapter leads",
  "data": null,
  "status_code": 500,
  "error": "Database connection error"
}
```

---

## Common Response Structure

All API responses follow a consistent structure:

### Success Response
```json
{
  "message": "Success message",
  "data": {
    "result": [...],
    "pagination": {
      "total_count": 100,
      "page_length": 10,
      "start": 0,
      "has_next": true,
      "has_prev": false
    }
  },
  "status_code": 200,
  "error": null
}
```

### Error Response
```json
{
  "message": "Error message",
  "data": null,
  "status_code": 500,
  "error": "Detailed error description"
}
```

---

## Pagination

Both endpoints support pagination with the following parameters:

- `page_length`: Number of items per page (default: 10)
- `start`: Starting index (default: 0)

### Pagination Metadata
The response includes pagination metadata:
- `total_count`: Total number of records
- `page_length`: Number of items per page
- `start`: Current starting index
- `has_next`: Boolean indicating if there are more pages
- `has_prev`: Boolean indicating if there are previous pages

### Example Pagination Usage
```bash
# First page (items 0-9)
GET /api/method/solve_ninja.api.v1.mentor.get_mentors?page_length=10&start=0

# Second page (items 10-19)
GET /api/method/solve_ninja.api.v1.mentor.get_mentors?page_length=10&start=10

# Third page (items 20-29)
GET /api/method/solve_ninja.api.v1.mentor.get_mentors?page_length=10&start=20
```

---

## Data Models

### User Metadata Fields
- `is_mentor`: Boolean flag indicating if user is a mentor
- `is_city_chapter_lead`: Boolean flag indicating if user is a chapter lead
- `mentor_quote`: Quote from the mentor
- `mentor_expertise`: Areas of expertise for mentors
- `mentor_status`: Current status of the mentor
- `chapter_lead_achivement`: Achievements of the chapter lead

### User Fields
- `name`: Unique username
- `full_name`: Display name
- `username`: Username for profile URLs
- `user_image`: Path to user's profile image

---

## Rate Limiting

Currently, no rate limiting is implemented. However, it's recommended to:
- Implement reasonable delays between requests
- Cache responses when possible
- Use pagination to limit data transfer

---

## Error Handling

The API handles errors gracefully and returns appropriate HTTP status codes:

- `200`: Success
- `500`: Internal server error

Common error scenarios:
- Database connection issues
- Invalid parameters
- Missing required fields

---

## Usage Examples

### JavaScript/Fetch
```javascript
// Get mentors
fetch('/api/method/solve_ninja.api.v1.mentor.get_mentors?page_length=5')
  .then(response => response.json())
  .then(data => {
    console.log('Mentors:', data.data.result);
    console.log('Pagination:', data.data.pagination);
  })
  .catch(error => console.error('Error:', error));

// Get chapter leads
fetch('/api/method/solve_ninja.api.v1.mentor.get_chapter_lead?page_length=5')
  .then(response => response.json())
  .then(data => {
    console.log('Chapter Leads:', data.data.result);
  })
  .catch(error => console.error('Error:', error));
```

### Python/Requests
```python
import requests

# Get mentors
response = requests.get(
    'https://your-domain.com/api/method/solve_ninja.api.v1.mentor.get_mentors',
    params={'page_length': 5, 'start': 0}
)
data = response.json()
print('Mentors:', data['data']['result'])

# Get chapter leads
response = requests.get(
    'https://your-domain.com/api/method/solve_ninja.api.v1.mentor.get_chapter_lead',
    params={'page_length': 5, 'start': 0}
)
data = response.json()
print('Chapter Leads:', data['data']['result'])
```

---

## Changelog

### Version 1.0.0
- Initial release
- Added `get_mentors` endpoint
- Added `get_chapter_lead` endpoint
- Implemented pagination support
- Added comprehensive error handling

---

## Support

For technical support or questions about this API, please contact the development team or create an issue in the project repository.






