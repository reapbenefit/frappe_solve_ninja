# Solve Events API Documentation

## Overview
This document provides comprehensive documentation for the Solve Events API endpoints, including the newly added `get_solve_events` endpoint.

## API Endpoints

### 1. Get Solve Events by Sub Type

**Endpoint**: `/api/method/solve_ninja.api.v1.solve_event.get_solve_events`

**Method**: `GET`

**Description**: Retrieves solve events filtered by sub_type, ordered by creation date in descending order (newest first).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_length` | integer | No | 10 | Number of results per page |
| `start` | integer | No | 0 | Starting index for pagination |
| `sub_type` | string | No | null | Filter events by specific sub_type |

#### Request Examples

**Get all events (no filter)**:
```bash
GET /api/method/solve_ninja.api.v1.solve_event.get_solve_events
```

**Get events with specific sub_type**:
```bash
GET /api/method/solve_ninja.api.v1.solve_event.get_solve_events?sub_type=workshop
```

**With pagination**:
```bash
GET /api/method/solve_ninja.api.v1.solve_event.get_solve_events?page_length=20&start=0&sub_type=conference
```

**Multiple parameters**:
```bash
GET /api/method/solve_ninja.api.v1.solve_event.get_solve_events?page_length=15&start=30&sub_type=seminar
```

#### Response Format

**Success Response (200)**:
```json
{
  "message": "Events retrieved successfully",
  "data": {
    "data": [
      {
        "title": "AI Workshop 2024",
        "description": "Learn about artificial intelligence and machine learning",
        "start_date_time": "2024-02-15 10:00:00",
        "mode": "Online",
        "end_date_time": "2024-02-15 17:00:00",
        "city": "Mumbai",
        "unique_id": "AI-WS-2024-001",
        "sub_type": "workshop",
        "cover_image": "https://your-domain.com/files/ai-workshop.jpg",
        "name": "AI-WS-2024-001",
        "creation": "2024-01-15 09:30:00"
      },
      {
        "title": "Data Science Conference",
        "description": "Annual data science conference",
        "start_date_time": "2024-03-20 09:00:00",
        "mode": "Offline",
        "end_date_time": "2024-03-22 18:00:00",
        "city": "Bangalore",
        "unique_id": "DS-CONF-2024-001",
        "sub_type": "conference",
        "cover_image": "https://your-domain.com/files/ds-conference.jpg",
        "name": "DS-CONF-2024-001",
        "creation": "2024-01-10 14:20:00"
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
      "sub_type": "workshop"
    }
  },
  "status_code": 200,
  "error": null
}
```

**Error Response (500)**:
```json
{
  "message": "Failed to retrieve events",
  "data": null,
  "status_code": 500,
  "error": "Database connection error"
}
```

#### Response Fields

**Event Object Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Event title |
| `description` | string | Event description |
| `start_date_time` | datetime | Event start date and time |
| `mode` | string | Event mode (Online/Offline) |
| `end_date_time` | datetime | Event end date and time |
| `city` | string | Event city |
| `unique_id` | string | Unique event identifier |
| `sub_type` | string | Event sub-type |
| `cover_image` | string | Full URL to cover image |
| `name` | string | Event document name |
| `creation` | datetime | Event creation timestamp |

**Pagination Object**:
| Field | Type | Description |
|-------|------|-------------|
| `total_count` | integer | Total number of events matching criteria |
| `page_length` | integer | Number of results per page |
| `start` | integer | Starting index for current page |
| `has_next` | boolean | Whether there are more results |
| `has_prev` | boolean | Whether there are previous results |

**Filters Object**:
| Field | Type | Description |
|-------|------|-------------|
| `sub_type` | string | Applied sub_type filter (null if no filter) |

#### Common Sub Types

The following are common sub_type values that can be used for filtering:

- `workshop` - Hands-on learning sessions
- `conference` - Large-scale professional gatherings
- `seminar` - Educational presentations
- `meetup` - Community gatherings
- `training` - Skill development sessions
- `webinar` - Online educational events
- `hackathon` - Coding competitions
- `panel` - Discussion panels
- `keynote` - Keynote presentations

#### Usage Examples

**JavaScript/Fetch**:
```javascript
// Get all events
fetch('/api/method/solve_ninja.api.v1.solve_event.get_solve_events')
  .then(response => response.json())
  .then(data => {
    console.log('Events:', data.data.data);
    console.log('Total count:', data.data.pagination.total_count);
  });

// Get workshop events with pagination
fetch('/api/method/solve_ninja.api.v1.solve_event.get_solve_events?sub_type=workshop&page_length=5&start=0')
  .then(response => response.json())
  .then(data => {
    data.data.data.forEach(event => {
      console.log(`${event.title} - ${event.start_date_time}`);
    });
  });
```

**Python/Requests**:
```python
import requests

# Get all events
response = requests.get('/api/method/solve_ninja.api.v1.solve_event.get_solve_events')
data = response.json()
events = data['data']['data']

# Get specific sub_type with pagination
params = {
    'sub_type': 'conference',
    'page_length': 20,
    'start': 0
}
response = requests.get('/api/method/solve_ninja.api.v1.solve_event.get_solve_events', params=params)
data = response.json()
```

**cURL**:
```bash
# Get all events
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.solve_event.get_solve_events"

# Get workshop events
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.solve_event.get_solve_events?sub_type=workshop"

# With pagination
curl -X GET "https://your-domain.com/api/method/solve_ninja.api.v1.solve_event.get_solve_events?page_length=15&start=30&sub_type=seminar"
```

#### Error Handling

The API returns appropriate HTTP status codes and error messages:

- **200**: Success
- **400**: Bad Request (invalid parameters)
- **500**: Internal Server Error

Always check the `status_code` field in the response and handle errors appropriately:

```javascript
fetch('/api/method/solve_ninja.api.v1.solve_event.get_solve_events')
  .then(response => response.json())
  .then(data => {
    if (data.status_code === 200) {
      // Handle success
      console.log('Events:', data.data.data);
    } else {
      // Handle error
      console.error('Error:', data.message, data.error);
    }
  })
  .catch(error => {
    console.error('Network error:', error);
  });
```

#### Performance Considerations

- **Pagination**: Always use pagination for large datasets to improve performance
- **Caching**: Consider implementing client-side caching for frequently accessed data
- **Rate Limiting**: Be mindful of API rate limits in production environments

#### Related APIs

- `get_upcoming_events`: Get events with start_date_time > today
- `get_past_events`: Get events with start_date_time <= today

#### Changelog

- **v1.0.0** (2024-01-XX): Initial release of `get_solve_events` API
  - Added sub_type filtering
  - Added creation date ordering (desc)
  - Added pagination support
  - Added comprehensive error handling

---

## Support

For technical support or questions about this API, please contact the development team or refer to the main project documentation.







