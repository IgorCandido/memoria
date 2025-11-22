# Agent-Mail Dashboard Design

**Date**: 2025-11-22
**Status**: 🚧 Planned
**Context**: User request to add agent-mail dashboard to main infrastructure dashboard

## Problem Statement

The main infrastructure dashboard at http://localhost:9002/ is missing an agent-mail section in the left sidebar navigation. Agent-mail is a critical infrastructure component (multi-agent work queue system) but has no visibility in the unified dashboard.

### User Feedback

> "Also why is the dashboard for agent mail not on that page as a left side item?"

The agent-mail system is fully operational (HTTP service on port 9007, MCP on port 9004) but lacks monitoring/management UI integration with the main dashboard.

## Current Dashboard State

### Existing Dashboard Infrastructure

**Main Dashboard** (http://localhost:9002/):
- Location: `apps/dashboard/`
- Backend: FastAPI (Python)
- Frontend: React + TypeScript + Vite
- Status: Healthy (Docker health check false positive - uses wget, but service works)

**Other Dashboards**:
- `apps/infrastructure-monitor-dashboard/` (port 9001) - Service health monitoring
- `apps/worker-dashboard/` (unknown port) - Worker monitoring
- Chronos Web UI (port 3000) - Task scheduling management

### Design Inconsistency Issue

User noted: "they are all different looking, seems either a drunk fe developer did them all or thousands different did it"

This dashboard unification is a separate task but affects agent-mail dashboard design - should follow unified design system.

## Agent-Mail System Architecture

### Components

**Agent-Mail HTTP Service** (port 9007):
- FastAPI server with MCP JSON-RPC interface
- Work queue with TTL-based atomic reservations
- Categories: review, debug, test, refactor, docs, implement
- Features: send_work, claim_work, register_agent, get_stats, submit_result

**Agent-Mail MCP** (port 9004):
- MCP wrapper over HTTP service
- 11 tools exposed to Claude Code
- Currently shows "connected" but tools not callable (HTTP bridge issue)

**Agent-Mail Skill** (✅ Production Ready):
- Direct HTTP access to agent-mail service
- Bypasses MCP overhead
- 53 tests passing, 97% domain coverage
- Location: `skills/agent-mail/`

### Data Available

The agent-mail service exposes these stats via `/stats/{category}`:

```python
{
    "category": "review",
    "queue_size": 5,
    "workers_registered": 2,
    "active_work_items": 3,
    "completed_today": 15,
    "avg_completion_time_seconds": 120.5,
    "oldest_work_item_age_seconds": 300
}
```

## Dashboard Requirements

### MVP Features (Phase 1)

**Sidebar Navigation Item**:
- Label: "Agent Mail"
- Icon: Queue/mailbox icon
- Link: `/agent-mail`
- Position: Below existing items in left sidebar

**Main Dashboard View** (`/agent-mail`):
1. **Queue Overview Cards**:
   - One card per category (review, debug, test, refactor, docs, implement)
   - Shows: queue size, active workers, completion rate
   - Color-coded by health (green: healthy, yellow: backing up, red: stalled)

2. **Active Work Items Table**:
   - Columns: Work ID, Category, From, Status, Age, Assigned To
   - Sortable, filterable
   - Click to view details

3. **Worker Registry**:
   - List of registered workers
   - Status: active, idle, offline
   - Last seen timestamp
   - Categories they serve

4. **Basic Stats**:
   - Total work items processed today
   - Average completion time by category
   - Success/failure rates

### Enhanced Features (Phase 2)

**Real-Time Updates**:
- WebSocket connection to agent-mail service
- Live queue size updates
- Worker status changes
- Work item lifecycle events

**Work Item Details Modal**:
- Full work context
- Execution logs
- Result data
- Timeline (created → claimed → completed)

**Performance Graphs**:
- Queue size over time (line chart)
- Completion time distribution (histogram)
- Category workload balance (pie chart)
- Worker utilization heatmap

**Interactive Actions**:
- Cancel stuck work items
- Manually assign work to specific worker
- Trigger worker health check
- View learning system stats (outcomes, adjustments)

### Advanced Features (Phase 3)

**Learning System Dashboard**:
- Agent success rates by type
- Pattern recognition status
- Active adjustments
- Feedback trends

**Historical Analysis**:
- 30-day completion trends
- Capacity planning recommendations
- Bottleneck identification
- Worker performance comparison

**Alerting**:
- Queue backing up (> 10 items)
- No workers available
- High failure rate (> 20%)
- Stuck work items (> TTL)

## Technical Design

### Backend (FastAPI)

**New Route**: `/api/agent-mail/*`

```python
# apps/dashboard/backend/routes/agent_mail.py

from fastapi import APIRouter
import httpx

router = APIRouter(prefix="/api/agent-mail", tags=["agent-mail"])

AGENT_MAIL_SERVICE = "http://localhost:9007"

@router.get("/stats/all")
async def get_all_stats():
    """Get stats for all categories"""
    categories = ["review", "debug", "test", "refactor", "docs", "implement"]
    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(*[
            client.get(f"{AGENT_MAIL_SERVICE}/stats/{cat}")
            for cat in categories
        ])
    return {cat: resp.json() for cat, resp in zip(categories, responses)}

@router.get("/workers")
async def get_workers():
    """Get list of registered workers"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AGENT_MAIL_SERVICE}/workers")
    return response.json()

@router.get("/work/{work_id}")
async def get_work_details(work_id: str):
    """Get details for specific work item"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AGENT_MAIL_SERVICE}/work/{work_id}")
    return response.json()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time updates for queue status"""
    await websocket.accept()
    # Subscribe to agent-mail events
    # Forward to WebSocket client
```

### Frontend (React + TypeScript)

**New Components**:

```typescript
// apps/dashboard/frontend/src/pages/AgentMail.tsx

import React, { useState, useEffect } from 'react';
import { QueueCard } from '../components/agent-mail/QueueCard';
import { WorkItemsTable } from '../components/agent-mail/WorkItemsTable';
import { WorkerRegistry } from '../components/agent-mail/WorkerRegistry';

export const AgentMailDashboard: React.FC = () => {
  const [stats, setStats] = useState<CategoryStats[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);

  useEffect(() => {
    // Fetch initial data
    fetchAllStats();
    fetchWorkers();
    fetchActiveWork();

    // Setup WebSocket for real-time updates
    const ws = new WebSocket('ws://localhost:9002/api/agent-mail/ws');
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      handleRealtimeUpdate(update);
    };

    return () => ws.close();
  }, []);

  return (
    <div className="agent-mail-dashboard">
      <h1>Agent Mail Queue System</h1>

      <section className="queue-overview">
        <h2>Category Queues</h2>
        <div className="queue-cards">
          {stats.map(stat => (
            <QueueCard key={stat.category} stats={stat} />
          ))}
        </div>
      </section>

      <section className="active-work">
        <h2>Active Work Items</h2>
        <WorkItemsTable items={workItems} />
      </section>

      <section className="workers">
        <h2>Registered Workers</h2>
        <WorkerRegistry workers={workers} />
      </section>
    </div>
  );
};
```

**QueueCard Component**:

```typescript
// apps/dashboard/frontend/src/components/agent-mail/QueueCard.tsx

interface QueueCardProps {
  stats: {
    category: string;
    queue_size: number;
    workers_registered: number;
    active_work_items: number;
    completed_today: number;
    avg_completion_time_seconds: number;
  };
}

export const QueueCard: React.FC<QueueCardProps> = ({ stats }) => {
  const healthStatus = getHealthStatus(stats);

  return (
    <div className={`queue-card queue-card--${healthStatus}`}>
      <div className="queue-card__header">
        <h3>{stats.category}</h3>
        <span className={`status-badge status-badge--${healthStatus}`}>
          {healthStatus}
        </span>
      </div>

      <div className="queue-card__metrics">
        <Metric label="Queue Size" value={stats.queue_size} />
        <Metric label="Workers" value={stats.workers_registered} />
        <Metric label="Active" value={stats.active_work_items} />
        <Metric label="Completed Today" value={stats.completed_today} />
        <Metric
          label="Avg Time"
          value={formatDuration(stats.avg_completion_time_seconds)}
        />
      </div>
    </div>
  );
};

function getHealthStatus(stats: CategoryStats): 'healthy' | 'warning' | 'critical' {
  if (stats.queue_size > 20) return 'critical';
  if (stats.queue_size > 10 || stats.workers_registered === 0) return 'warning';
  return 'healthy';
}
```

### Sidebar Integration

**Update Navigation**:

```typescript
// apps/dashboard/frontend/src/components/Sidebar.tsx

const navigationItems = [
  { path: '/', label: 'Overview', icon: HomeIcon },
  { path: '/services', label: 'Services', icon: ServerIcon },
  { path: '/chronos', label: 'Chronos', icon: ClockIcon },
  { path: '/agent-mail', label: 'Agent Mail', icon: MailboxIcon }, // ← NEW
  { path: '/workdiary', label: 'Work Diary', icon: BookIcon },
  { path: '/settings', label: 'Settings', icon: SettingsIcon },
];
```

## Design System Alignment

Since user noted design inconsistency across dashboards, agent-mail dashboard should follow unified design system (to be defined separately).

### Recommended Approach

1. **Audit Existing Dashboards**: Document UI patterns, component libraries, styling approaches
2. **Define Design System**: Colors, typography, spacing, component patterns
3. **Create Component Library**: Reusable React components (cards, tables, charts)
4. **Implement Agent-Mail Dashboard**: Using unified components
5. **Migrate Other Dashboards**: Gradually align to design system

## Implementation Plan

### Phase 1: MVP (2-3 days)

**Day 1**: Backend
- [ ] Create `/api/agent-mail/*` routes
- [ ] Implement stats aggregation endpoint
- [ ] Add worker registry endpoint
- [ ] Test with real agent-mail service

**Day 2**: Frontend Components
- [ ] Create QueueCard component
- [ ] Create WorkItemsTable component
- [ ] Create WorkerRegistry component
- [ ] Create AgentMailDashboard page

**Day 3**: Integration
- [ ] Add sidebar navigation item
- [ ] Wire up routing
- [ ] Connect frontend to backend API
- [ ] Deploy and test

### Phase 2: Real-Time (1-2 days)

- [ ] Implement WebSocket endpoint
- [ ] Subscribe to agent-mail events
- [ ] Add real-time updates to frontend
- [ ] Add work item details modal

### Phase 3: Advanced Features (3-5 days)

- [ ] Add performance graphs (Chart.js or Recharts)
- [ ] Implement learning system dashboard
- [ ] Add historical analysis
- [ ] Implement alerting

## Dog-Fooding Integration

The agent-mail dashboard should be built **using the agent-mail system itself**:

1. **Send Work to Agents**:
   ```python
   # Delegate dashboard implementation to agents
   mcp__agent_mail__send_work(
       from_id="igor",
       to_category="implement",
       task_type="dashboard_feature",
       context={
           "title": "Build agent-mail dashboard MVP",
           "components": ["QueueCard", "WorkItemsTable", "WorkerRegistry"],
           "backend_routes": ["/api/agent-mail/stats", "/api/agent-mail/workers"],
           "priority": "high"
       }
   )
   ```

2. **Code Review by Agents**:
   ```python
   mcp__agent_mail__send_work(
       from_id="igor",
       to_category="review",
       task_type="code_review",
       context={
           "files": ["apps/dashboard/backend/routes/agent_mail.py"],
           "focus": "security, performance, error handling"
       }
   )
   ```

3. **Learning from Outcomes**:
   - Track success/failure of agent implementations
   - Adjust prompts based on feedback
   - Build confidence in agent capabilities

## Related Tasks

### Dashboard Health Check Fix

Currently, main dashboard shows "unhealthy" due to Docker health check using `wget` (not installed). Service actually works fine (logs show 200 OK).

**Fix**: Change health check from `wget` to `curl` in docker-compose.yml:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  # Instead of: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8000/api/health"]
```

### Dashboard Design Unification

Separate project to audit and unify all dashboard designs:
- `apps/dashboard/` (port 9002)
- `apps/infrastructure-monitor-dashboard/` (port 9001)
- `apps/worker-dashboard/` (unknown port)
- Chronos UI (port 3000)

**Deliverables**:
- Design system documentation
- Shared component library
- Migration plan for each dashboard

## Success Criteria

✅ Agent-mail visible in main dashboard sidebar
✅ Dashboard shows real-time queue status for all categories
✅ Users can see active work items and workers
✅ Health status clearly indicated (green/yellow/red)
✅ Response time < 500ms for initial load
✅ Real-time updates within 1 second
✅ Integrates with existing dashboard without breaking other features

## Future Enhancements

**Mobile View**:
- Responsive design for monitoring on mobile
- Swipe gestures for queue navigation

**Notifications**:
- Browser notifications for critical alerts
- Email/Slack integration for queue backups

**Advanced Analytics**:
- Machine learning for capacity prediction
- Anomaly detection for unusual patterns
- Optimization recommendations

**Multi-Tenancy**:
- If multiple users/projects use agent-mail
- Per-user/project queue isolation
- Access control and permissions

## References

- Main dashboard: `apps/dashboard/`
- Agent-mail HTTP service: `apps/agent-mail-mcp-server/`
- Agent-mail skill: `skills/agent-mail/`
- Dog-fooding guide: Query RAG for "agent-mail dog-fooding"
- Design system planning: Query RAG for "dashboard design unification"

## Current Status

**Status**: 🚧 Planned
**Priority**: Medium (after memoria skill validation, dog-fooding setup)
**Blocked By**: None (can start anytime)
**Estimated Effort**: 3-5 days (MVP) + 1-2 days (real-time) + 3-5 days (advanced)

**Next Steps**:
1. User confirms requirements and MVP scope
2. Create Jira ticket or GitHub issue
3. Delegate to agent-mail system (dog-fooding!)
4. Implement MVP
5. Deploy and gather feedback
6. Iterate on Phase 2/3 features
