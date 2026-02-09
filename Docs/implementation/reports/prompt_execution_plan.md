{
  "cycle_stage": "cool_down",
  "decision_mode": "hybrid",
  "deferred_prompts": [],
  "execution_packets": [
    {
      "cycle_hint": "cool_down",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-docs-system.md",
        "guardrails-repo-change.md"
      ],
      "goal": "Pre-release/failure context detected; re-run alignment gate before release sign-off.",
      "packet": 1,
      "phase_hint": "phase_5",
      "prompt_id": "prompt-03-alignment-review-gate"
    }
  ],
  "exploration_prompt_ids": [
    "prompt-14-improvement-direction-bet-loop",
    "prompt-09-tests-refactor-suite",
    "prompt-04-architecture-coherence-loop",
    "prompt-06-ui-e2e-verification-loop",
    "prompt-10-tests-stabilization-loop"
  ],
  "exploration_suggestions": [
    {
      "cycle_hint": "bet",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-app-implementation-system.md",
        "charter-docs-system.md",
        "charter-test-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-14-improvement-direction-bet-loop.md",
      "name": "Discover Improvement Directions -> Integration Bet Plan",
      "phase_hint": "phase_2",
      "phase_hints": [
        "phase_2"
      ],
      "priority": 58,
      "prompt_id": "prompt-14-improvement-direction-bet-loop",
      "reasons": [
        "Revisit improvement directions to keep bets fresh."
      ],
      "tags": [
        "improvement",
        "roadmap",
        "planning",
        "integration",
        "testing",
        "docs_system"
      ],
      "when_to_use": [
        "repository works but next high-impact improvements are unclear",
        "roadmap needs evidence-backed feature and quality direction bets",
        "teams need a concrete handoff from gap analysis to implementation and testing"
      ]
    },
    {
      "cycle_hint": "build",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-docs-system.md",
        "charter-test-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-09-tests-refactor-suite.md",
      "name": "Refactor Test Suite (Clear, Modular, Comprehensive)",
      "phase_hint": "phase_3",
      "phase_hints": [
        "phase_3"
      ],
      "priority": 57,
      "prompt_id": "prompt-09-tests-refactor-suite",
      "reasons": [
        "Test surface exists; refactor/coverage improvements may unlock safer iteration."
      ],
      "tags": [
        "tests",
        "refactor",
        "docs_system"
      ],
      "when_to_use": [
        "test suite structure is hard to maintain despite mostly passing behavior"
      ]
    },
    {
      "cycle_hint": "shape",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-docs-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-04-architecture-coherence-loop.md",
      "name": "Architecture System Diagram Coherence Loop (Design Gate + Continuous Validation)",
      "phase_hint": "phase_0.5",
      "phase_hints": [
        "phase_0.5"
      ],
      "priority": 54,
      "prompt_id": "prompt-04-architecture-coherence-loop",
      "reasons": [
        "Architecture coherence checks reduce integration surprises."
      ],
      "tags": [
        "architecture",
        "systems_design",
        "diagram",
        "coherence",
        "docs_system"
      ],
      "when_to_use": [
        "architecture is unclear, contested, or changing materially",
        "docs architecture and code reality are diverging",
        "implementation readiness needs a GO/NO_GO decision"
      ]
    },
    {
      "cycle_hint": "build",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-artifacts-system.md",
        "charter-docs-system.md",
        "charter-test-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-06-ui-e2e-verification-loop.md",
      "name": "Verify & Stabilize Web UI (Exploration + E2E Debug Loop)",
      "phase_hint": "phase_3",
      "phase_hints": [
        "phase_3"
      ],
      "priority": 53,
      "prompt_id": "prompt-06-ui-e2e-verification-loop",
      "reasons": [
        "UI surface detected; verification loop can expose hidden workflow regressions."
      ],
      "tags": [
        "ui",
        "web",
        "ux",
        "testing",
        "e2e",
        "debugging"
      ],
      "when_to_use": [
        "test failures or flakiness reduce CI trust",
        "critical web UI flows require end-to-end verification"
      ]
    },
    {
      "cycle_hint": "cool_down",
      "dependencies": [
        "charter-prompt-system.md",
        "charter-docs-system.md",
        "charter-test-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-10-tests-stabilization-loop.md",
      "name": "Stabilize Test Suite (Debug Loop)",
      "phase_hint": "phase_4",
      "phase_hints": [
        "phase_4"
      ],
      "priority": 55,
      "prompt_id": "prompt-10-tests-stabilization-loop",
      "reasons": [
        "CI + tests present; stabilization pass can preserve high-signal checks."
      ],
      "tags": [
        "tests",
        "stabilization",
        "debugging",
        "ci"
      ],
      "when_to_use": [
        "test failures or flakiness reduce CI trust"
      ]
    }
  ],
  "generated_at": "2026-02-08T22:20:14+00:00",
  "immediate_plan": [
    {
      "dependencies": [
        "charter-prompt-system.md",
        "charter-docs-system.md",
        "guardrails-repo-change.md"
      ],
      "file": "prompt-03-alignment-review-gate.md",
      "name": "Alignment Review Gate (Objective Drift Check)",
      "phase_hints": [
        "phase_5"
      ],
      "priority": 70,
      "prompt_id": "prompt-03-alignment-review-gate",
      "reasons": [
        "Pre-release/failure context detected; re-run alignment gate before release sign-off."
      ],
      "tags": [
        "alignment",
        "strategy",
        "review_gate",
        "docs_system"
      ],
      "when_to_use": [
        "end of Phase 0 bootstrap",
        "end of each major feature in Phase 3",
        "before release readiness sign-off"
      ]
    }
  ],
  "judged_candidates": [
    {
      "effort_score": 1.0,
      "evidence_score": 1.8,
      "file": "prompt-03-alignment-review-gate.md",
      "fit_score": 3.25,
      "name": "Alignment Review Gate (Objective Drift Check)",
      "phase_hints": [
        "phase_5"
      ],
      "priority": 70,
      "prompt_id": "prompt-03-alignment-review-gate",
      "rationale": "Pre-release/failure context detected; re-run alignment gate before release sign-off. Direct phase match. Low execution cost for the current scope.",
      "risk_coverage_score": 1.75,
      "risk_level_score": 3.0,
      "score": 115.0
    }
  ],
  "phase": "phase_5",
  "recommended_prompt_ids": [
    "prompt-03-alignment-review-gate"
  ],
  "repo_state": {
    "artifact_count": 0,
    "changed_ci_files": 0,
    "changed_files": 55,
    "changed_source_files": 0,
    "changed_test_files": 0,
    "changed_ui_files": 0,
    "docs_root": "docs",
    "has_alignment_review": true,
    "has_arch_container_level": true,
    "has_arch_context_level": true,
    "has_arch_deployment_view": true,
    "has_arch_profile": true,
    "has_arch_quality_and_risks": true,
    "has_arch_runtime_view": true,
    "has_architecture_coherence": true,
    "has_architecture_doc": true,
    "has_artifact_feature_alignment": false,
    "has_artifact_store": false,
    "has_ci": true,
    "has_ci_failure_signal": false,
    "has_core_objective": true,
    "has_docs_baseline": true,
    "has_improvement_bets": true,
    "has_makefile": true,
    "has_milestones": true,
    "has_observability_doc": true,
    "has_package_json": false,
    "has_plan_checklist": true,
    "has_readme": true,
    "has_release_docs": true,
    "has_research_signal": false,
    "has_test_failure_signal": false,
    "has_ui_signal": true,
    "missing_required_artifacts": [],
    "source_files": 135,
    "target_root": "/Users/nirtzur/Documents/projects/AGORA",
    "test_files": 45,
    "total_files": 301
  },
  "selected_prompt_id": "prompt-03-alignment-review-gate",
  "selection_confidence": 0.61,
  "selection_rationale": "Pre-release/failure context detected; re-run alignment gate before release sign-off. Direct phase match. Low execution cost for the current scope.",
  "target_root": "/Users/nirtzur/Documents/projects/AGORA"
}
