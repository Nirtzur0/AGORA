import React from 'react';
import { SectionCard } from '../../components/Layout';
import { TASK_STATUSES } from './constants';
import { EmptyState, TaskCard } from './shared';

export default function TasksTab({ tasks, currentAgentId, runAction, updateTask }) {
  return (
    <SectionCard eyebrow="Task execution" title="Assigned tasks">
      {tasks.length ? (
        <div className="stack">
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              currentAgentId={currentAgentId}
              statuses={TASK_STATUSES}
              onUpdate={(payload) => runAction(() => updateTask(task.id, payload), 'Task updated')}
            />
          ))}
        </div>
      ) : (
        <EmptyState title="No tasks assigned" body="Tasks created by ingestion workflows or maintainers will appear here." />
      )}
    </SectionCard>
  );
}
