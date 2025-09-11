#!/usr/bin/env python3
"""
Mock Elasticsearch server for testing in environments without Docker.
This simulates ES responses for development and testing.
"""

import asyncio
import json
import logging
from datetime import datetime

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for mock ES
mock_indices = {}
mock_documents = {}

async def health_check(request):
    """Simulate cluster health endpoint."""
    return web.json_response({
        "cluster_name": "mock-elasticsearch",
        "status": "green",
        "timed_out": False,
        "number_of_nodes": 1,
        "number_of_data_nodes": 1,
        "active_primary_shards": 3,
        "active_shards": 3,
        "relocating_shards": 0,
        "initializing_shards": 0,
        "unassigned_shards": 0,
        "delayed_unassigned_shards": 0,
        "number_of_pending_tasks": 0,
        "number_of_in_flight_fetch": 0,
        "task_max_waiting_in_queue_millis": 0,
        "active_shards_percent_as_number": 100.0
    })

async def cat_indices(request):
    """Simulate cat indices endpoint."""
    indices_info = []
    for index_name in mock_indices:
        doc_count = len(mock_documents.get(index_name, {}))
        indices_info.append(f"green open {index_name} uuid 1 0 {doc_count} 0 0kb 0kb")
    
    if not indices_info:
        return web.Response(text="")
    
    return web.Response(text="\n".join(indices_info))

async def create_index(request):
    """Simulate index creation."""
    index_name = request.match_info['index']
    
    if index_name in mock_indices:
        return web.json_response(
            {"error": {"type": "resource_already_exists_exception"}},
            status=400
        )
    
    body = await request.json() if request.body_exists else {}
    mock_indices[index_name] = body
    mock_documents[index_name] = {}
    
    logger.info(f"Created index: {index_name}")
    
    return web.json_response({
        "acknowledged": True,
        "shards_acknowledged": True,
        "index": index_name
    })

async def check_index_exists(request):
    """Check if index exists."""
    index_name = request.match_info['index']
    
    if index_name in mock_indices:
        return web.Response(status=200)
    else:
        return web.Response(status=404)

async def delete_index(request):
    """Delete an index."""
    index_pattern = request.match_info['index']
    
    deleted = []
    if index_pattern.endswith('*'):
        prefix = index_pattern[:-1]
        for index_name in list(mock_indices.keys()):
            if index_name.startswith(prefix):
                del mock_indices[index_name]
                if index_name in mock_documents:
                    del mock_documents[index_name]
                deleted.append(index_name)
    else:
        if index_pattern in mock_indices:
            del mock_indices[index_pattern]
            if index_pattern in mock_documents:
                del mock_documents[index_pattern]
            deleted.append(index_pattern)
    
    logger.info(f"Deleted indices: {deleted}")
    
    return web.json_response({
        "acknowledged": True
    })

async def bulk_operation(request):
    """Simulate bulk indexing."""
    body = await request.text()
    lines = body.strip().split('\n')
    
    operations = []
    errors = []
    
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
            
        action_line = json.loads(lines[i])
        
        if 'index' in action_line:
            index_info = action_line['index']
            index_name = index_info['_index']
            doc_id = index_info.get('_id', str(datetime.now().timestamp()))
            
            if i + 1 < len(lines):
                doc_source = json.loads(lines[i + 1])
                
                if index_name not in mock_documents:
                    mock_documents[index_name] = {}
                
                mock_documents[index_name][doc_id] = doc_source
                
                operations.append({
                    "index": {
                        "_index": index_name,
                        "_id": doc_id,
                        "_version": 1,
                        "result": "created",
                        "_shards": {"total": 1, "successful": 1, "failed": 0},
                        "status": 201
                    }
                })
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    logger.info(f"Bulk indexed {len(operations)} documents")
    
    return web.json_response({
        "took": 30,
        "errors": len(errors) > 0,
        "items": operations
    })

async def count_documents(request):
    """Count documents in an index."""
    index_name = request.match_info['index']
    
    if index_name not in mock_documents:
        return web.json_response({"count": 0})
    
    count = len(mock_documents[index_name])
    
    return web.json_response({"count": count})

async def index_stats(request):
    """Get index statistics."""
    index_name = request.match_info['index']
    
    if index_name not in mock_indices:
        return web.json_response(
            {"error": {"type": "index_not_found_exception"}},
            status=404
        )
    
    doc_count = len(mock_documents.get(index_name, {}))
    
    return web.json_response({
        "_shards": {"total": 1, "successful": 1, "failed": 0},
        "_all": {
            "primaries": {
                "docs": {"count": doc_count},
                "store": {"size_in_bytes": doc_count * 1024}
            },
            "total": {
                "docs": {"count": doc_count},
                "store": {"size_in_bytes": doc_count * 1024}
            }
        },
        "indices": {
            index_name: {
                "primaries": {
                    "docs": {"count": doc_count},
                    "store": {"size_in_bytes": doc_count * 1024}
                },
                "total": {
                    "docs": {"count": doc_count},
                    "store": {"size_in_bytes": doc_count * 1024}
                }
            }
        }
    })

async def put_mapping(request):
    """Update index mapping."""
    index_name = request.match_info['index']
    
    if index_name not in mock_indices:
        return web.json_response(
            {"error": {"type": "index_not_found_exception"}},
            status=404
        )
    
    body = await request.json()
    
    if 'mappings' not in mock_indices[index_name]:
        mock_indices[index_name]['mappings'] = {}
    
    mock_indices[index_name]['mappings'].update(body)
    
    return web.json_response({"acknowledged": True})

async def force_merge(request):
    """Simulate force merge (optimization)."""
    index_name = request.match_info['index']
    
    if index_name not in mock_indices:
        return web.json_response(
            {"error": {"type": "index_not_found_exception"}},
            status=404
        )
    
    return web.json_response({
        "_shards": {"total": 1, "successful": 1, "failed": 0}
    })

async def info_handler(request):
    """Simulate ES info endpoint."""
    return web.json_response({
        "name": "mock-node-1",
        "cluster_name": "mock-elasticsearch",
        "cluster_uuid": "mock-uuid-123",
        "version": {
            "number": "8.10.0",
            "build_flavor": "default",
            "build_type": "docker",
            "build_hash": "mock-hash",
            "build_date": "2023-10-01T00:00:00.000Z",
            "build_snapshot": False,
            "lucene_version": "9.7.0",
            "minimum_wire_compatibility_version": "7.17.0",
            "minimum_index_compatibility_version": "7.0.0"
        },
        "tagline": "You Know, for Search"
    })

async def default_handler(request):
    """Default handler for unmatched routes."""
    logger.warning(f"Unhandled request: {request.method} {request.path}")
    return web.json_response(
        {"error": "Not implemented in mock server"},
        status=501
    )

def create_app():
    """Create the mock Elasticsearch application."""
    app = web.Application()
    
    # Info endpoint
    app.router.add_get('/', info_handler)
    app.router.add_head('/', lambda r: web.Response(status=200))
    
    # Health and cluster endpoints
    app.router.add_get('/_cluster/health', health_check)
    app.router.add_get('/_cluster/health/{index}', health_check)
    app.router.add_get('/_cat/indices', cat_indices)
    
    # Index management
    app.router.add_put('/{index}', create_index)
    app.router.add_head('/{index}', check_index_exists)
    app.router.add_delete('/{index}', delete_index)
    
    # Document operations
    app.router.add_post('/_bulk', bulk_operation)
    app.router.add_get('/{index}/_count', count_documents)
    
    # Index statistics and optimization
    app.router.add_get('/{index}/_stats', index_stats)
    app.router.add_put('/{index}/_mapping', put_mapping)
    app.router.add_post('/{index}/_forcemerge', force_merge)
    
    # Default handler
    app.router.add_route('*', '/{path:.*}', default_handler)
    
    return app

async def main():
    """Run the mock Elasticsearch server."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', 9200)
    await site.start()
    
    logger.info("🎭 Mock Elasticsearch server running on http://localhost:9200")
    logger.info("Press Ctrl+C to stop")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down mock server...")
        await runner.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass