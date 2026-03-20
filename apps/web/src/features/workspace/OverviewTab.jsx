import React, { useMemo } from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, InsightList, MetricTile, StatusPill, formatTimestamp, humanize, toneForStatus } from './shared';

export default function OverviewTab({
  workspaceId,
  workspace,
  team,
  artifacts,
  tasks,
  critiques,
  ruleChecks,
  phaseStatus,
  gateStatus,
  timelineItems,
  workspaceDescription,
  setWorkspaceDescription,
  runAction,
  updateWorkspace,
}) {
  const blockers = useMemo(() => {
    const blockingCritiques = critiques.filter((critique) => critique.status === 'open' && critique.severity === 'blocking');
    const failingChecks = ruleChecks.filter((check) => check.status === 'fail');
    const blockedTasks = tasks.filter((task) => task.status === 'blocked');
    return [
      ...blockingCritiques.map((critique) => ({
        id: critique.id,
        title: `Blocking critique on ${humanize(critique.target_type)}`,
        body: critique.message,
        meta: formatTimestamp(critique.created_at),
      })),
      ...failingChecks.map((check, index) => ({
        id: `${check.rule_name}-${index}`,
        title: `${check.rule_name} failed`,
        body: humanize(check.target_type),
        meta: formatTimestamp(check.created_at),
      })),
      ...blockedTasks.map((task) => ({
        id: task.id,
        title: `Blocked task · ${humanize(task.type)}`,
        body: task.payload?.objective || 'Task requires intervention.',
        meta: formatTimestamp(task.created_at),
      })),
    ].slice(0, 5);
  }, [critiques, ruleChecks, tasks]);

  const nextActions = useMemo(() => {
    const actions = [];
    if (gateStatus?.required_actions?.length) {
      gateStatus.required_actions.forEach((action, index) => {
        actions.push({
          id: `gate-action-${index}`,
          title: action,
          body: 'Required by current gate evaluation.',
        });
      });
    }
    if (!artifacts.length) {
      actions.push({
        id: 'seed-artifact',
        title: 'Create the first artifact record',
        body: 'Artifacts unlock evidence resolution, search, and ingestion workflows.',
      });
    }
    if (!tasks.length) {
      actions.push({
        id: 'seed-task',
        title: 'Seed a task or request workflow',
        body: 'The task lane is still empty. Ingestion and review tasks will appear here.',
      });
    }
    if (!critiques.length) {
      actions.push({
        id: 'seed-critique',
        title: 'Start review pressure',
        body: 'Create a critique against a claim or artifact version once the first evidence is present.',
      });
    }
    return actions.slice(0, 5);
  }, [artifacts.length, critiques.length, gateStatus?.required_actions, tasks.length]);

  const recentArtifacts = artifacts
    .slice(0, 4)
    .map((artifact) => ({
      id: artifact.id,
      title: artifact.metadata?.title || artifact.short_id,
      body: `${humanize(artifact.type)} artifact`,
      meta: artifact.short_id,
    }));

  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Mission control" title="Workspace operating picture">
        <div className="workspace-stat-grid">
          <MetricTile label="Artifacts" value={artifacts.length} />
          <MetricTile label="Active team" value={team.length} />
          <MetricTile label="Open tasks" value={tasks.filter((task) => task.status !== 'completed').length} />
          <MetricTile label="Open blockers" value={blockers.length} tone={blockers.length > 0 ? 'danger' : 'good'} />
        </div>
      </SectionCard>

      <SectionCard eyebrow="Authority boundaries" title="Phase and gate readiness" tone={gateStatus?.can_advance ? 'success' : 'warning'}>
        <div className="stack">
          <div className="workspace-inline-row wrap">
            <StatusPill label={`Current phase · ${humanize(workspace?.phase)}`} tone="info" />
            {gateStatus?.gate_required ? (
              <StatusPill
                label={`Gate ${gateStatus.gate_status || 'unknown'}`}
                tone={gateStatus.can_advance ? 'good' : 'warning'}
              />
            ) : (
              <StatusPill label="No gate required" tone="good" />
            )}
          </div>
          {phaseStatus ? (
            <div className="hint-block">
              <strong>Allowed next phases</strong>
              <span>{phaseStatus.allowed_next_phases?.map(humanize).join(', ') || 'None'}</span>
            </div>
          ) : null}
          {gateStatus?.reasons?.length ? (
            <ul className="bullet-list">
              {gateStatus.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {gateStatus?.required_actions?.length ? (
            <div className="stack">
              <strong>Required actions</strong>
              <ul className="bullet-list">
                {gateStatus.required_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard eyebrow="Immediate attention" title="Next actions">
        <InsightList
          items={nextActions}
          emptyTitle="No immediate actions"
          emptyBody="The workspace is seeded and current gate requirements are satisfied."
        />
      </SectionCard>

      <SectionCard eyebrow="Risk register" title="Current blockers">
        <InsightList
          items={blockers}
          emptyTitle="No active blockers"
          emptyBody="Blocking critiques, failed checks, and blocked tasks will show here."
        />
      </SectionCard>

      <SectionCard eyebrow="Workspace settings" title="Update description">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(() => updateWorkspace(workspaceId, workspaceDescription), 'Workspace description updated');
          }}
        >
          <textarea
            className="text-area"
            value={workspaceDescription}
            onChange={(event) => setWorkspaceDescription(event.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Save description
          </button>
        </form>
      </SectionCard>

      <SectionCard eyebrow="Evidence flow" title="Recent artifacts">
        <InsightList
          items={recentArtifacts}
          emptyTitle="No artifacts yet"
          emptyBody="Create an artifact record, then upload a version to start building evidence."
        />
      </SectionCard>

      <SectionCard eyebrow="Recent activity" title="Latest events and logs">
        {timelineItems.length ? (
          <div className="stack">
            {timelineItems.slice(0, 6).map((item) => (
              <div key={`${item.kind}-${item.id}`} className="timeline-card">
                <div className="workspace-inline-row">
                  <StatusPill
                    label={humanize(item.kind === 'event' ? item.event_type : item.action || item.level || 'log')}
                    tone={toneForStatus(item.level || item.event_type)}
                  />
                  <span>{formatTimestamp(item.created_at)}</span>
                </div>
                <div>{item.kind === 'event' ? item.event_type : item.message || item.action}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No activity yet" body="Events and logs will appear here as work advances." />
        )}
      </SectionCard>
    </div>
  );
}
