# Get Skill Based Projects API

## Overview
Retrieves skill-based projects with pagination and filtering capabilities. Projects are ordered by creation date in descending order (newest first).

## Endpoint
```
GET /api/method/solve_ninja.api.v1.skill_based_projects.get_skill_based_projects
```

## Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_length` | Integer | No | 10 | Number of results per page |
| `start` | Integer | No | 0 | Starting index for pagination |
| `city` | String/Array | No | - | Filter by city (can be single city or array of cities) |
| `skill` | String/Array | No | - | Filter by skill/badge (can be single skill or array of skills) |

## Request Examples

### Basic Request
```json
{
    "page_length": 10,
    "start": 0
}
```

### With City Filter
```json
{
    "page_length": 10,
    "start": 0,
    "city": "Mumbai"
}
```

### With Multiple Filters
```json
{
    "page_length": 10,
    "start": 0,
    "city": ["Mumbai", "Delhi"],
    "skill": ["Leadership", "Communication"]
}
```

## Response Format

### Success Response (200)
```json
{
    "message": "Skill-based projects retrieved successfully",
    "data": {
        "result": [
            {
                "name": "PROJ-001",
                "project_title": "Community Garden Initiative",
                "image": "https://example.com/files/project_image.jpg",
                "skill": "Leadership",
                "no_of_members_needed": 5,
                "city": "Mumbai",
                "join_link": "https://example.com/join/project-001",
                "creation": "2025-01-15 10:30:00",
                "modified": "2025-01-15 10:30:00"
            }
        ],
        "total_count": 25,
        "page_length": 10,
        "start": 0,
        "has_next": true,
        "has_prev": false,
        "filters": {
            "city": ["Mumbai"],
            "skill": ["Leadership"]
        }
    },
    "status_code": 200
}
```

### Error Response (500)
```json
{
    "message": "Failed to retrieve skill-based projects",
    "data": null,
    "status_code": 500,
    "error": "Error details here"
}
```

## Response Fields

### Project Object
| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Unique project identifier |
| `project_title` | String | Title of the project |
| `image` | String | Full URL to project image |
| `skill` | String | Required skill/badge for the project |
| `no_of_members_needed` | Integer | Number of members needed |
| `city` | String | Project location city |
| `join_link` | String | URL to join the project |
| `creation` | String | Project creation timestamp |
| `modified` | String | Project last modified timestamp |

### Pagination Object
| Field | Type | Description |
|-------|------|-------------|
| `total_count` | Integer | Total number of projects matching filters |
| `page_length` | Integer | Number of results per page |
| `start` | Integer | Starting index for current page |
| `has_next` | Boolean | Whether there are more results |
| `has_prev` | Boolean | Whether there are previous results |

### Filters Object
| Field | Type | Description |
|-------|------|-------------|
| `city` | Array | Applied city filters |
| `skill` | Array | Applied skill filters |

## Business Logic

1. **Ordering**: Projects are ordered by creation date in descending order (newest first)
2. **Image URLs**: Image paths are automatically converted to full URLs
3. **Filter Parsing**: Single string filters are automatically converted to arrays
4. **Pagination**: Standard offset-based pagination with metadata
5. **Error Handling**: Comprehensive error handling with detailed error messages

## Usage Examples

### Get First Page of All Projects
```bash
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.skill_based_projects.get_skill_based_projects" \
  -H "Content-Type: application/json" \
  -d '{"page_length": 10, "start": 0}'
```

### Get Projects in Specific City
```bash
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.skill_based_projects.get_skill_based_projects" \
  -H "Content-Type: application/json" \
  -d '{"page_length": 10, "start": 0, "city": "Mumbai"}'
```

### Get Projects Requiring Specific Skills
```bash
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.skill_based_projects.get_skill_based_projects" \
  -H "Content-Type: application/json" \
  -d '{"page_length": 10, "start": 0, "skill": ["Leadership", "Communication"]}'
```

## Performance Considerations

- **Indexing**: Ensure proper database indexes on `city`, `skill`, and `creation` fields
- **Pagination**: Use appropriate page sizes to balance performance and user experience
- **Caching**: Consider implementing caching for frequently accessed project lists
- **Image Optimization**: Ensure project images are optimized for web delivery

## Rate Limiting

- Standard API rate limits apply
- Consider implementing request throttling for high-traffic scenarios

## Related APIs

- `get_opportunities_for_youth` - Similar structure for opportunity listings
- `get_upcoming_events` - Event-based listings with similar pagination
- `get_ninjas_in_focus` - User-focused listings

## Use Cases

1. **Project Discovery**: Browse available skill-based projects
2. **Skill Matching**: Find projects matching specific skills
3. **Location-Based Search**: Find projects in specific cities
4. **Project Feeds**: Display latest projects in chronological order
5. **Mobile App Integration**: Provide project data for mobile applications








