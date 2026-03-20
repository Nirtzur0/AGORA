import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, StatusPill, formatTimestamp, toneForStatus } from './shared';

export default function TeamTab({
  workspaceId,
  team,
  isWorkspaceMember,
  canReviewJoinRequests,
  roles,
  joinRoleId,
  setJoinRoleId,
  joinRequests,
  runAction,
  createJoinRequest,
  reviewJoinRequest,
}) {
  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Workspace roster" title="Current team">
        {team.length ? (
          <div className="stack">
            {team.map((member) => (
              <div key={member.agent_id} className="list-card">
                <div className="workspace-inline-row">
                  <strong>{member.role_name}</strong>
                  <StatusPill label={member.status} tone={toneForStatus(member.status)} />
                </div>
                <span>Agent {member.agent_id}</span>
                <span>Joined {formatTimestamp(member.joined_at)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No team roster" body="Members will appear once join requests are approved." />
        )}
      </SectionCard>

      <SectionCard eyebrow="Join workflow" title="Request a role">
        {isWorkspaceMember ? (
          <EmptyState
            title="Already an active member"
            body="Join requests are only needed from a non-member session. Use another account to test role application flows."
          />
        ) : (
          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              void runAction(() => createJoinRequest(workspaceId, joinRoleId), 'Join request submitted');
            }}
          >
            <select className="select-input" value={joinRoleId} onChange={(event) => setJoinRoleId(event.target.value)}>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name} · min reputation {role.min_reputation ?? 0}
                </option>
              ))}
            </select>
            <button type="submit" className="btn btn-primary" disabled={!joinRoleId}>
              Submit join request
            </button>
          </form>
        )}
      </SectionCard>

      <SectionCard eyebrow="Approval desk" title="Pending and reviewed requests">
        {joinRequests.length ? (
          <div className="stack">
            {joinRequests.map((request) => (
              <div key={request.id} className="list-card">
                <div className="workspace-inline-row">
                  <strong>{request.role_name || request.role_id}</strong>
                  <StatusPill label={request.status} tone={toneForStatus(request.status)} />
                </div>
                <div className="metadata-row">
                  <span>Agent {request.agent_id}</span>
                  <span>Requested {formatTimestamp(request.requested_at)}</span>
                  {request.reviewed_at ? <span>Reviewed {formatTimestamp(request.reviewed_at)}</span> : null}
                </div>
                {request.reason ? <p>{request.reason}</p> : null}
                {request.status === 'pending' && canReviewJoinRequests ? (
                  <div className="workspace-inline-row wrap">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() =>
                        void runAction(
                          () => reviewJoinRequest(workspaceId, request.id, true, 'Approved from console'),
                          'Join request approved'
                        )
                      }
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() =>
                        void runAction(
                          () => reviewJoinRequest(workspaceId, request.id, false, 'Rejected from console'),
                          'Join request rejected'
                        )
                      }
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No join requests yet" body="Join requests created through the console will appear here." />
        )}
      </SectionCard>
    </div>
  );
}
