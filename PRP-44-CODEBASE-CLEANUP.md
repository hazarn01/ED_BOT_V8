# PRP-44: Critical Codebase Cleanup & API Stabilization

## Problem Statement
ED Bot v8 frontend experiencing connectivity issues due to:
- API server unresponsiveness (timeout on health checks)
- Import path inconsistencies causing module resolution failures
- Duplicate API endpoint definitions creating route conflicts
- Multiple response formatters causing output inconsistency

## Impact Assessment
- **Severity**: Critical (🔴)
- **Frontend**: Complete loss of functionality
- **API**: Server running but unresponsive
- **Development**: Blocked until resolved

## Root Cause Analysis
1. **Import Chain Failures**: Mixed relative/absolute imports preventing proper module initialization
2. **Route Conflicts**: Duplicate `/query` endpoints causing FastAPI routing errors
3. **Resource Competition**: Multiple database connection patterns causing conflicts
4. **Initialization Cascade**: Import failures preventing full API startup despite uvicorn process running

## Resolution Plan

### Phase 1: Emergency Stabilization (15 minutes)
**Objective**: Restore API functionality

#### Step 1.1: Clean API Restart
- Kill existing uvicorn process
- Clear Python bytecode cache
- Restart with minimal configuration

#### Step 1.2: Import Path Standardization
- Fix critical import paths in `src/pipeline/query_processor.py`
- Standardize to absolute imports from `src.`
- Test import resolution

#### Step 1.3: Endpoint Deduplication
- Remove duplicate query endpoint in `src/api/endpoints.py`
- Keep only modular endpoint in `src/api/endpoints/query.py`
- Update router configuration

### Phase 2: Code Architecture Cleanup (30 minutes)
**Objective**: Remove technical debt causing instability

#### Step 2.1: Response Formatter Consolidation
- Deprecate legacy `response_formatter.py`
- Standardize on `medical_response_formatter.py`
- Update all references

#### Step 2.2: Database Connection Standardization
- Audit database import patterns
- Ensure consistent async/sync usage
- Remove redundant connection factories

#### Step 2.3: Import Path Standardization
- Convert all relative imports to absolute
- Update import statements across codebase
- Verify no circular dependencies

### Phase 3: Validation & Testing (15 minutes)
**Objective**: Confirm stability and functionality

#### Step 3.1: API Health Verification
- Confirm `/health-simple` responds
- Test `/api/v1/query` endpoint
- Verify frontend connectivity

#### Step 3.2: Import Resolution Testing
- Import all major modules
- Check for ImportError exceptions
- Verify circular dependency resolution

#### Step 3.3: Frontend Integration Test
- Load frontend interface
- Submit test query
- Confirm response receipt

## Implementation Checklist

### Emergency Fixes (Priority 1)
- [ ] Kill uvicorn process (PID 28407)
- [ ] Clear `__pycache__` directories
- [ ] Fix imports in `query_processor.py`
- [ ] Remove duplicate endpoint in `endpoints.py`
- [ ] Restart API server
- [ ] Test basic connectivity

### Code Cleanup (Priority 2)
- [ ] Standardize imports to `src.` pattern
- [ ] Remove `response_formatter.py` references
- [ ] Audit database connection usage
- [ ] Update router configurations
- [ ] Test all endpoint routes

### Validation (Priority 3)
- [ ] API health check passes
- [ ] Frontend loads without errors
- [ ] Query processing functional
- [ ] Response formatting consistent
- [ ] No import warnings in logs

## Files Requiring Changes

### Critical Path Files
1. `src/pipeline/query_processor.py` - Import fixes
2. `src/api/endpoints.py` - Remove duplicate endpoints
3. `src/api/app.py` - Router configuration
4. `src/api/endpoints/__init__.py` - Update imports

### Secondary Cleanup Files
5. `src/pipeline/router.py` - Import standardization
6. `src/pipeline/rag_retriever.py` - Import fixes
7. `src/models/database.py` - Connection audit
8. `src/models/async_database.py` - Connection audit

## Risk Mitigation
- **Backup Strategy**: Git commit before changes
- **Rollback Plan**: Revert specific commits if issues arise
- **Testing Protocol**: Incremental testing after each phase
- **Monitoring**: Watch server logs during restart

## Success Criteria
1. ✅ API server responds to health checks within 1 second
2. ✅ Frontend can submit queries and receive responses
3. ✅ No ImportError exceptions in server logs
4. ✅ All endpoint routes function correctly
5. ✅ Response formatting is consistent

## Timeline
- **Phase 1**: 15 minutes (Emergency stabilization)
- **Phase 2**: 30 minutes (Architecture cleanup)  
- **Phase 3**: 15 minutes (Validation & testing)
- **Total**: 60 minutes

## Next Steps
Execute Phase 1 immediately to restore API functionality, then proceed systematically through cleanup phases.