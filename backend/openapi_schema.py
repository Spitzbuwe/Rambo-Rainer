"""
OpenAPI 3.0 Schema fuer die wichtigsten Direct-Mode Endpoints.
"""

OPENAPI_SCHEMA = {
    "openapi": "3.0.0",
    "info": {
        "title": "Rainer Build API",
        "version": "1.0.0",
        "description": "Builder-Agent fuer Rambo-Rainer Entwicklung",
    },
    "servers": [{"url": "http://localhost:5002", "description": "Development"}],
    "paths": {
        "/api/direct-run": {
            "post": {
                "summary": "Start a direct execution",
                "tags": ["Direct Mode"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "task": {"type": "string", "example": "Erstelle config.json mit app rainer"},
                                    "scope": {"type": "string", "enum": ["local", "project"], "example": "local"},
                                    "mode": {"type": "string", "enum": ["safe", "apply"], "example": "safe"},
                                },
                                "required": ["task"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Direct preview generated",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {"type": "string"},
                                        "runState": {"type": "string", "example": "waiting_user_decision"},
                                        "autoContinueAllowed": {"type": "boolean"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/direct-confirm": {
            "post": {
                "summary": "Confirm a direct run decision",
                "tags": ["Direct Mode"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "token": {"type": "string", "example": "abc123"},
                                    "confirm": {"type": "boolean", "example": True},
                                },
                                "required": ["token", "confirm"],
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Decision processed"}},
            }
        },
    },
}
