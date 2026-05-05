import React, { useCallback, useEffect, useState } from "react";
import PresetModal from "./PresetModal.jsx";

function ruleLabel(rule) {
  if (rule == null) return "none";
  if (typeof rule === "string") return rule;
  if (rule && typeof rule.fingerprint === "string") return rule.fingerprint;
  if (rule && typeof rule.id === "string") return rule.id;
  try {
    return JSON.stringify(rule);
  } catch {
    return "none";
  }
}

/**
 * Umhüllt Rule-Editor-UI und öffnet PresetModal für /api/rules/presets + POST /api/rules/presets/apply (merge wie PresetModal).
 */
export default function RuleEditorWrapper({
  initialRule = null,
  onApplyPreset,
  onMergeRules,
  apiBase = "",
  adminToken,
  children,
}) {
  const [selectedRule, setSelectedRule] = useState(initialRule);
  const [showPresetModal, setShowPresetModal] = useState(false);

  useEffect(() => {
    setSelectedRule(initialRule);
  }, [initialRule]);

  const handlePresetSuccess = useCallback(() => {
    onApplyPreset?.();
    onMergeRules?.();
  }, [onApplyPreset, onMergeRules]);

  return (
    <div data-testid="rule-editor-wrapper">
      <div data-testid="rule-editor-selected">{ruleLabel(selectedRule)}</div>
      {children}
      <button type="button" onClick={() => setShowPresetModal(true)}>
        Use Preset
      </button>
      <PresetModal
        isOpen={showPresetModal}
        onClose={() => setShowPresetModal(false)}
        onApplySuccess={handlePresetSuccess}
        apiBase={apiBase}
        adminToken={adminToken}
      />
    </div>
  );
}
