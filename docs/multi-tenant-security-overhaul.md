# Plan: Multi-Tenant Security Overhaul (Platform + Tenant Scopes)

## Context

The current system has a critical security gap: any tenant "admin" can list, modify, and delete ALL tenants in the system. There is no separation between platform-level administration and tenant-level administration. The proposed model introduces two scopes — **platform** (super_admin, cross-tenant) and **tenant** (admin/user, single-tenant) — with strict enforcement.

### Key Security Gaps Being Fixed
1. **CRITICAL**: Tenant CRUD endpoints (`/tenants`) have no tenant filter — any admin sees all tenants
2. **CRITICAL**: No super_admin concept — "admin" has excessive power
3. **HIGH**: X-Tenant-Id header sent by frontend but backend ignores it
4. **HIGH**: ML service accepts tenant_id from request body with no auth
5. Role rename: "operator" → "user" for clarity

### Scope Model

```
PLATFORM SCOPE                          TENANT SCOPE
─────────────────                       ─────────────────
role: "super_admin"                     role: "admin" | "user"
tenant_id: null                         tenant_id: <non-null>
scope: "platform"                       scope: "tenant"
Can access ALL tenants                  Can ONLY access own tenant
Must provide X-Tenant-Id header         Cannot override tenant context
```

### JWT Token Structure

```json
{
  "sub": "<email>",
  "user_id": "<uuid>",
  "role": "super_admin | admin | user",
  "tenant_id": "<uuid or null>",
  "tenant_code": "<string or null>",
  "scope": "platform | tenant"
}
```

### Tenant Resolution Logic

```
IF role == super_admin:
    effective_tenant_id = X-Tenant-Id header (must be provided for tenant operations)
ELSE:
    effective_tenant_id = token.tenant_id (ignore any override attempts)

All database queries: WHERE tenant_id = effective_tenant_id
```

---

## Phase 1: Backend Core Security

### Batch 1.1 — Schema & Model Changes

**`backend-api/app/auth/security.py`** — Add `role` and `scope` to TokenData:
```python
class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None  # None for super_admin
    tenant_code: Optional[str] = None
    role: Optional[str] = None
    scope: Optional[str] = None  # "platform" | "tenant"
```
Update `verify_token()` to extract `role` and `scope` from JWT payload.

**`backend-api/app/auth/schemas.py`**:
- `UserOut.tenant_id`: change `UUID` → `Optional[UUID] = None`
- Add `scope: str = "tenant"` and `effective_tenant_id: Optional[UUID] = None` to `UserOut`
- `AdminUserCreate`: add optional `tenant_id: Optional[UUID] = None` (for super_admin creating users in any tenant), validate `role` is one of `["super_admin", "admin", "user"]`

**`backend-api/app/db/models.py`**:
- `User.tenant_id`: change to `nullable=True`
- `User.role`: change default from `"operator"` to `"user"`

### Batch 1.2 — Alembic Migration

**NEW `backend-api/app/db/migrations/versions/003_security_overhaul.py`**:
1. `ALTER TABLE users ALTER COLUMN tenant_id DROP NOT NULL`
2. `UPDATE users SET role = 'user' WHERE role = 'operator'`
3. Add partial unique indexes for NULL tenant_id:
   ```sql
   CREATE UNIQUE INDEX uq_users_null_tenant_username ON users (username) WHERE tenant_id IS NULL;
   CREATE UNIQUE INDEX uq_users_null_tenant_email ON users (email) WHERE tenant_id IS NULL;
   ```
4. Seed super_admin user: `superadmin@aastreli.local` / `superadmin123`, role=`super_admin`, tenant_id=`NULL`

### Batch 1.3 — Core Dependencies (the heart of the change)

**`backend-api/app/common/dependencies.py`**:

Redesign `get_current_user()` — add `Request` parameter, populate `effective_tenant_id` on UserOut:
- If `user.role == "super_admin"` and `user.tenant_id is None`:
  - Set `scope = "platform"`
  - Read `X-Tenant-Id` header → validate tenant exists & is active → set `effective_tenant_id`
  - If no header → `effective_tenant_id` stays `None` (endpoints requiring tenant will fail-safe)
- Else (tenant-scoped user):
  - Set `scope = "tenant"`, `effective_tenant_id = user.tenant_id`
  - If `X-Tenant-Id` header present and differs from `user.tenant_id` → raise `ForbiddenError("Cross-tenant access denied")`

**Key drop-in design**: Since all 41 endpoint references use `current_user.tenant_id`, we do a global rename to `current_user.effective_tenant_id`. For tenant-scoped users this equals `tenant_id` (no behavior change). For super_admin it equals the X-Tenant-Id value.

Add `get_current_user_with_tenant()` — wrapper that requires `effective_tenant_id` is not None:
```python
async def get_current_user_with_tenant(current_user = Depends(get_current_user)) -> UserOut:
    if current_user.effective_tenant_id is None:
        raise ForbiddenError(detail="X-Tenant-Id header required for platform-scoped users")
    return current_user
```

Update `require_role()` — super_admin implicitly satisfies any role check:
```python
def require_role(*allowed_roles):
    async def _check(current_user = Depends(get_current_user)):
        if current_user.role == "super_admin":
            return current_user  # super_admin passes all role checks
        if current_user.role not in allowed_roles:
            raise ForbiddenError(...)
        return current_user
    return _check
```

Update `TenantContext` and `get_current_tenant()` to handle platform scope.

### Batch 1.4 — Auth Endpoints

**`backend-api/app/auth/router.py`**:
- Login: handle super_admin (tenant_id=None, scope="platform" in JWT)
- Register: always creates tenant-scoped users, rename default role "operator"→"user", block super_admin role in registration

**`backend-api/app/auth/tenant_router.py`**:
- Change ALL `require_role("admin")` → `require_role("super_admin")`
- This is the **single most critical fix**: only super_admin can manage tenants

**`backend-api/app/auth/user_router.py`**:
- Keep `require_role("admin")` (super_admin auto-passes via hierarchy)
- Replace `current_user.tenant_id` → `current_user.effective_tenant_id`
- For `create_user`: if super_admin, accept `tenant_id` from `AdminUserCreate`; if admin, force own tenant_id
- For `list_users`: super_admin can pass `?tenant_id=` query param to filter

---

## Phase 2: Endpoint Migration

### Batch 2.1 — Global rename (41 occurrences across 5 files)

Search-and-replace `current_user.tenant_id` → `current_user.effective_tenant_id` in:
| File | Count |
|------|-------|
| `backend-api/app/site_setup/router.py` | 30 |
| `backend-api/app/auth/user_router.py` | 5 |
| `backend-api/app/predictions/router.py` | 4 |
| `backend-api/app/dashboard/router.py` | 1 |
| `backend-api/app/ml_management/router.py` | 1 |

### Batch 2.2 — Add tenant-required guards

Replace `Depends(get_current_user)` with `Depends(get_current_user_with_tenant)` in all tenant-data endpoints. Exceptions (keep `get_current_user`):
- `/me`, `/login`, `/register`
- `/tenants` endpoints (super_admin manages all tenants without needing a specific tenant context)

---

## Phase 3: Audit Logging

### Batch 3.1 — Audit infrastructure

**NEW `backend-api/app/common/audit.py`**:
- `log_platform_action(user, action, target_tenant_id, resource_type, resource_id, details)` — structured logger for super_admin cross-tenant actions

**NEW ORM model `AuditLog`** in `models.py`:
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    scope = Column(String(20), nullable=False)
    action = Column(String(100), nullable=False)
    target_tenant_id = Column(UUID, nullable=True)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

Add to migration `003_security_overhaul.py`. Integrate logging in `tenant_router.py` and `user_router.py` for super_admin actions.

---

## Phase 4: Service Hardening

### Batch 4.1 — ML Service internal auth

**`ml-service/app/prediction/router.py`** and **`ml-service/app/feedback/router.py`**:
- Add `INTERNAL_API_KEY` env var
- Add dependency checking `X-Internal-Key` header
- Backend-api and mqtt-ingestion send this key when calling ML service

### Batch 4.2 — MQTT WebSocket

**`mqtt-ingestion/app/streaming/websocket.py`**:
- Handle `scope == "platform"` in JWT: accept `tenant_id` query param for super_admin WebSocket connections

---

## Phase 5: Frontend Changes

### Batch 5.1 — Auth & TenantContext

**`frontend/src/api/auth.ts`**:
- Extract `scope` and `role` to localStorage on login
- Handle `tenant_id` being null for super_admin

**`frontend/src/contexts/TenantContext.tsx`**:
- Add `isSuperAdmin: boolean`, `scope: "platform"|"tenant"` to context
- If `scope === "platform"`: fetch ALL tenants, require selection before proceeding
- If `scope === "tenant"`: existing behavior
- `isAdmin = role === "admin"`, `isSuperAdmin = role === "super_admin"`
- Remove tenant switcher for regular admins (they stay in their tenant)

### Batch 5.2 — Layout & Navigation

**`frontend/src/components/Layout.tsx`**:
- Update `getNavSections(isAdmin, isSuperAdmin)`:
  - super_admin: show "Administration" with Tenants + Users
  - admin: show "Administration" with Users only
  - user: no Administration section
- Tenant switcher: always show for super_admin, hide for others

### Batch 5.3 — Admin Pages

**`frontend/src/features/admin/pages/TenantsPage.tsx`**:
- Add frontend guard: redirect if not super_admin

**`frontend/src/features/admin/pages/UsersPage.tsx`**:
- For super_admin: add tenant filter dropdown at top
- Role dropdown: admin sees `["user", "admin"]`; super_admin sees `["user", "admin", "super_admin"]`

**`frontend/src/App.tsx`** + **`frontend/src/components/ProtectedRoute.tsx`**:
- Add optional `requiredRoles` prop to ProtectedRoute
- `/tenants` route requires `["super_admin"]`

### Batch 5.4 — Tenant Selection Enforcer

**NEW `frontend/src/components/TenantSelector.tsx`**:
- Dialog shown when `isSuperAdmin && !tenantId`
- Dropdown of all tenants + "Select Tenant to Continue" button
- Prevents navigating to tenant-data pages without a selected tenant

---

## Security Enforcement Rules

1. **Never** allow tenant override for non-super_admin
2. **Never** perform tenant-level operation without resolved `effective_tenant_id`
3. **Log** all super_admin cross-tenant actions with: `{actor_id, action, target_tenant_id, scope: "platform_impersonation"}`
4. **Fail-safe**: If tenant context is unclear → DENY the request
5. **Security > Convenience**: Always err on the side of denying access

---

## Files Summary

| File | Action |
|------|--------|
| `backend-api/app/auth/security.py` | Add role/scope to TokenData + verify_token |
| `backend-api/app/auth/schemas.py` | UserOut: Optional tenant_id, add scope/effective_tenant_id |
| `backend-api/app/db/models.py` | User.tenant_id nullable, role default "user", AuditLog model |
| `backend-api/app/db/migrations/versions/003_security_overhaul.py` | NEW — migration + seed |
| `backend-api/app/common/dependencies.py` | Redesign get_current_user, add get_current_user_with_tenant, update require_role |
| `backend-api/app/common/audit.py` | NEW — audit logging |
| `backend-api/app/auth/router.py` | Login handles super_admin, register blocks super_admin role |
| `backend-api/app/auth/tenant_router.py` | require_role("admin") → require_role("super_admin") |
| `backend-api/app/auth/user_router.py` | Support super_admin cross-tenant user management |
| `backend-api/app/site_setup/router.py` | Rename tenant_id → effective_tenant_id (30 refs) |
| `backend-api/app/predictions/router.py` | Rename tenant_id → effective_tenant_id (4 refs) |
| `backend-api/app/dashboard/router.py` | Rename tenant_id → effective_tenant_id (1 ref) |
| `backend-api/app/ml_management/router.py` | Rename tenant_id → effective_tenant_id (1 ref) |
| `ml-service/app/prediction/router.py` | Add internal API key auth |
| `ml-service/app/feedback/router.py` | Add internal API key auth |
| `mqtt-ingestion/app/streaming/websocket.py` | Handle platform scope |
| `frontend/src/api/auth.ts` | Extract scope to localStorage |
| `frontend/src/contexts/TenantContext.tsx` | Platform scope, isSuperAdmin, mandatory tenant selection |
| `frontend/src/api/client.ts` | X-Tenant-Id from TenantContext state |
| `frontend/src/components/Layout.tsx` | Nav for super_admin vs admin vs user |
| `frontend/src/components/ProtectedRoute.tsx` | Add requiredRoles prop |
| `frontend/src/components/TenantSelector.tsx` | NEW — mandatory tenant selection overlay |
| `frontend/src/features/admin/pages/TenantsPage.tsx` | Super_admin guard |
| `frontend/src/features/admin/pages/UsersPage.tsx` | Tenant filter dropdown for super_admin |
| `frontend/src/App.tsx` | Route-level role guards |

---

## Verification Checklist

1. **Migration**: Run Alembic upgrade, verify operator→user rename, super_admin seeded, nullable tenant_id works
2. **Login as super_admin**: JWT has `scope:"platform"`, `tenant_id:null`
3. **Super_admin without X-Tenant-Id**: GET `/sites` → 403 "X-Tenant-Id header required"
4. **Super_admin with X-Tenant-Id**: GET `/sites` → returns that tenant's sites
5. **Regular admin**: GET `/tenants` → 403 "Role 'admin' not permitted"
6. **Regular admin with X-Tenant-Id override**: → 403 "Cross-tenant access denied"
7. **Frontend**: super_admin sees tenant selector, can switch tenants, sees Administration with Tenants+Users
8. **Frontend**: admin sees Administration with Users only, no tenant switcher
9. **Frontend**: user sees no Administration section
10. **Audit**: super_admin cross-tenant actions logged with actor/target/action details
