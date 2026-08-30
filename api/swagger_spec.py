"""
=============================================================================
CampusGuard AI — OpenAPI 3.0.0 REST API Specification Generator
=============================================================================
"""

def get_openapi_spec():
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "CampusGuard AI — Enterprise Campus ERP & Safety REST API",
            "version": "2.0.0",
            "description": "Unified REST API for Student, Faculty, Parent, and Admin operations, emergency response telemetry, and AI intelligence engines."
        },
        "servers": [
            {"url": "http://127.0.0.1:5000", "description": "Local Development Server"}
        ],
        "paths": {
            "/api/v1/student/profile": {
                "get": {
                    "summary": "Get authenticated student profile",
                    "tags": ["Student"],
                    "responses": {
                        "200": {"description": "Student details including CGPA and registered department."}
                    }
                }
            },
            "/api/v1/student/attendance": {
                "get": {
                    "summary": "Get course-wise attendance and safe-miss margin predictions",
                    "tags": ["Attendance AI"],
                    "responses": {
                        "200": {"description": "Course attendance list, aggregate percentage, and risk tier."}
                    }
                }
            },
            "/api/v1/student/timetable": {
                "get": {
                    "summary": "Get weekly or day-wise timetable schedule",
                    "tags": ["Academics"],
                    "responses": {
                        "200": {"description": "List of scheduled lectures with rooms and faculty."}
                    }
                }
            },
            "/api/v1/safety/emergency-sos": {
                "post": {
                    "summary": "Trigger instantaneous campus-wide emergency SOS beacon",
                    "tags": ["Safety & Emergency"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "latitude": {"type": "number"},
                                        "longitude": {"type": "number"},
                                        "location": {"type": "string"},
                                        "emergency_type": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "SOS broadcast confirmation and 5-stage dispatch timeline."}
                    }
                }
            },
            "/api/v1/ai/assistant": {
                "post": {
                    "summary": "Query Context-Aware Smart Campus AI Assistant",
                    "tags": ["AI Intelligence"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"}
                                    },
                                    "required": ["query"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Markdown response with structured citations."}
                    }
                }
            },
            "/api/v1/predictive-risk": {
                "get": {
                    "summary": "Calculate Multi-Dimensional Academic & Retention Risk Index",
                    "tags": ["Predictive ML"],
                    "responses": {
                        "200": {"description": "Composite risk score (0-100), dropout probability, and remediation plan."}
                    }
                }
            },
            "/api/v1/qr-attendance": {
                "post": {
                    "summary": "Verify Anti-Proxy Dynamic QR Attendance Scan",
                    "tags": ["Attendance AI"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "token": {"type": "string"},
                                        "latitude": {"type": "number"},
                                        "longitude": {"type": "number"}
                                    },
                                    "required": ["token"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Attendance verification result."}
                    }
                }
            },
            "/api/v1/knowledge-search": {
                "get": {
                    "summary": "Institutional RAG Policy Search",
                    "tags": ["RAG Knowledge Engine"],
                    "parameters": [
                        {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "Matching institutional regulatory documents with citations."}
                    }
                }
            }
        }
    }
