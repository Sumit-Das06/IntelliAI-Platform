"""HTTP layer: routers, request/response schemas, dependencies.

Routers stay thin — parse input, call the service layer, shape output.
Business logic in a router is a review-blocker.
"""
